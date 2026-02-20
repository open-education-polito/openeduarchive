"""OAuth2 email sending via Microsoft Graph API.

Replaces Flask-Mail's SMTP transport with Microsoft Graph API for sending
system emails (registration confirmations, password resets, invitations).

Supports two OAuth2 flows:

- "client_credentials": App-only authentication. No user interaction.
  For organizational M365 tenants (production with Polito).
  Uses Mail.Send application permission.
  Endpoint: POST /users/{sender}/sendMail

- "delegated": Uses a refresh token obtained via one-time interactive login.
  For testing with personal accounts (outlook.com).
  Uses Mail.Send delegated permission.
  Endpoint: POST /me/sendMail

Configuration (via environment variables with APP_ prefix):

    MAIL_OAUTH2_ENABLED          - Enable OAuth2 email (default: False)
    MAIL_OAUTH2_FLOW             - "client_credentials" or "delegated"
    MAIL_OAUTH2_TENANT_ID        - Entra ID tenant GUID, or "consumers"
    MAIL_OAUTH2_CLIENT_ID        - App registration client ID
    MAIL_OAUTH2_CLIENT_SECRET    - App registration client secret (NEVER in code)
    MAIL_OAUTH2_SENDER_EMAIL     - Sender mailbox address
    MAIL_OAUTH2_TOKEN_CACHE_FILE - Delegated flow only: path to token cache

Security:
- Client secret must be injected via environment variable, never committed.
- Token cache file (delegated flow) must have 0600 permissions.
- All communication with Microsoft uses HTTPS/TLS.
- Tokens are cached in-memory (client_credentials) or in a protected
  file (delegated). Never logged, never exposed.
"""

import logging
import os
import stat
import threading
import time
from urllib.parse import quote

import flask_mail
import msal
import requests

logger = logging.getLogger(__name__)

_GRAPH_API_SEND_URL = "https://graph.microsoft.com/v1.0"
_GRAPH_API_TIMEOUT = 30

# Original Flask-Mail methods, saved before patching.
_original_configure_host = flask_mail.Connection.configure_host
_original_send = flask_mail.Connection.send

# Thread-safe MSAL app cache. One ConfidentialClientApplication per
# (tenant, client, flow) tuple, reused across requests within the same
# process. MSAL handles token caching and refresh internally.
_msal_apps = {}
_msal_apps_lock = threading.Lock()
_cache_persist_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Authority helper
# ---------------------------------------------------------------------------

def _build_authority(tenant_id):
    """Build the MSAL authority URL from a tenant identifier.

    Args:
        tenant_id: Entra ID tenant GUID, "consumers", or "common".
    """
    return f"https://login.microsoftonline.com/{tenant_id}"


# ---------------------------------------------------------------------------
# MSAL token management
# ---------------------------------------------------------------------------

def _get_msal_app(config):
    """Get or create a thread-safe cached MSAL ConfidentialClientApplication."""
    tenant_id = config["MAIL_OAUTH2_TENANT_ID"]
    client_id = config["MAIL_OAUTH2_CLIENT_ID"]
    flow = config["MAIL_OAUTH2_FLOW"]
    cache_key = (tenant_id, client_id, flow)

    with _msal_apps_lock:
        if cache_key in _msal_apps:
            return _msal_apps[cache_key]

        token_cache = msal.SerializableTokenCache()
        if flow == "delegated":
            cache_file = config.get("MAIL_OAUTH2_TOKEN_CACHE_FILE", "")
            if cache_file:
                try:
                    with open(cache_file, "r") as f:
                        token_cache.deserialize(f.read())
                except FileNotFoundError:
                    pass

        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=config["MAIL_OAUTH2_CLIENT_SECRET"],
            authority=_build_authority(tenant_id),
            token_cache=token_cache,
        )
        _msal_apps[cache_key] = app
        return app


def _persist_token_cache(config, msal_app):
    """Atomically persist the MSAL token cache to disk.

    Only relevant for the delegated flow. Writes to a temp file first,
    then atomically replaces the target to avoid corruption. File
    permissions are set to 0600 (owner read/write only).
    """
    cache_file = config.get("MAIL_OAUTH2_TOKEN_CACHE_FILE", "")
    if not cache_file:
        return

    cache = msal_app.token_cache
    if not getattr(cache, "has_state_changed", False):
        return

    with _cache_persist_lock:
        tmp_file = cache_file + ".tmp"
        try:
            fd = os.open(tmp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(cache.serialize())
            os.replace(tmp_file, cache_file)
            cache.has_state_changed = False
            logger.debug("OAuth2 token cache persisted to %s", cache_file)
        except OSError:
            logger.exception("Failed to persist OAuth2 token cache to %s", cache_file)
            try:
                os.unlink(tmp_file)
            except OSError:
                pass


def _acquire_token(config):
    """Acquire a valid OAuth2 access token.

    For client_credentials: fetches a new token using app identity.
    For delegated: silently refreshes using the cached refresh token.

    Returns:
        The access token string.

    Raises:
        RuntimeError: If token acquisition fails.
    """
    msal_app = _get_msal_app(config)
    flow = config["MAIL_OAUTH2_FLOW"]

    if flow == "client_credentials":
        scopes = ["https://graph.microsoft.com/.default"]
        result = msal_app.acquire_token_for_client(scopes=scopes)

    elif flow == "delegated":
        scopes = ["https://graph.microsoft.com/Mail.Send"]
        accounts = msal_app.get_accounts()
        if not accounts:
            raise RuntimeError(
                "No cached OAuth2 account found. Run "
                "'python -m openeduarchive.mail' first."
            )
        result = msal_app.acquire_token_silent(
            scopes=scopes, account=accounts[0],
        )
        if result and "access_token" in result:
            _persist_token_cache(config, msal_app)
    else:
        raise RuntimeError(f"Invalid MAIL_OAUTH2_FLOW: '{flow}'")

    if not result or "access_token" not in result:
        error_detail = "unknown error"
        if result:
            error_detail = result.get(
                "error_description", result.get("error", "unknown error")
            )
        raise RuntimeError(f"OAuth2 token acquisition failed: {error_detail}")

    return result["access_token"]


# ---------------------------------------------------------------------------
# Graph API email sending
# ---------------------------------------------------------------------------

def _flask_message_to_graph_payload(message, sender_email):
    """Convert a flask_mail.Message to a Microsoft Graph API sendMail payload.

    Args:
        message: A flask_mail.Message instance.
        sender_email: The sender email address (from config).

    Returns:
        A dict suitable for JSON serialization as the Graph API request body.
    """
    def _make_recipients(addresses):
        if not addresses:
            return []
        return [{"emailAddress": {"address": addr}} for addr in addresses]

    body = {
        "contentType": "HTML" if message.html else "Text",
        "content": message.html or message.body or "",
    }

    graph_message = {
        "subject": message.subject or "",
        "body": body,
        "toRecipients": _make_recipients(message.recipients),
        "ccRecipients": _make_recipients(message.cc),
        "bccRecipients": _make_recipients(message.bcc),
        "from": {"emailAddress": {"address": sender_email}},
    }

    if message.reply_to:
        reply_to = message.reply_to
        if isinstance(reply_to, str):
            reply_to = [reply_to]
        graph_message["replyTo"] = _make_recipients(reply_to)

    return {"message": graph_message, "saveToSentItems": False}


def _send_via_graph(message, config):
    """Send an email through the Microsoft Graph API.

    Args:
        message: A flask_mail.Message instance.
        config: The Flask app config dict.

    Raises:
        RuntimeError: If the API call fails.
    """
    access_token = _acquire_token(config)
    sender_email = config["MAIL_OAUTH2_SENDER_EMAIL"]
    flow = config["MAIL_OAUTH2_FLOW"]

    # /me/sendMail for delegated, /users/{email}/sendMail for app-only
    if flow == "delegated":
        url = f"{_GRAPH_API_SEND_URL}/me/sendMail"
    else:
        url = f"{_GRAPH_API_SEND_URL}/users/{quote(sender_email, safe='@')}/sendMail"

    payload = _flask_message_to_graph_payload(message, sender_email)

    _RETRYABLE_STATUS_CODES = {401, 429, 500, 502, 503, 504}
    _MAX_RETRIES = 2
    last_response = None

    for attempt in range(_MAX_RETRIES + 1):
        try:
            last_response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=_GRAPH_API_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning(
                "Graph API request failed: %s (attempt %d/%d)",
                exc, attempt + 1, _MAX_RETRIES + 1,
            )
            if attempt < _MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Graph API sendMail request failed: {exc}") from exc

        if last_response.status_code == 202:
            logger.info("Email sent via Graph API (recipients=%d)", len(message.recipients))
            logger.debug(
                "Email sent via Graph API: to=%s subject='%s'",
                message.recipients,
                message.subject,
            )
            return

        if last_response.status_code not in _RETRYABLE_STATUS_CODES:
            break

        if attempt < _MAX_RETRIES:
            # Re-acquire token on 401 (expired mid-flight)
            if last_response.status_code == 401:
                logger.warning(
                    "Graph API returned 401, re-acquiring token (attempt %d/%d)",
                    attempt + 1, _MAX_RETRIES,
                )
                access_token = _acquire_token(config)
                wait = 1
            elif last_response.status_code == 429:
                # Respect Microsoft's Retry-After header on throttling
                wait = int(last_response.headers.get("Retry-After", 2 ** attempt))
            else:
                wait = 2 ** attempt

            logger.warning(
                "Graph API returned %d, retrying in %ds (attempt %d/%d)",
                last_response.status_code, wait, attempt + 1, _MAX_RETRIES,
            )
            time.sleep(wait)

    request_id = last_response.headers.get("request-id", "?")
    logger.error(
        "Graph API sendMail failed: status=%d request-id=%s body=%s",
        last_response.status_code,
        request_id,
        last_response.text[:500],
    )
    raise RuntimeError(
        f"Graph API sendMail failed ({last_response.status_code}): "
        f"request-id={request_id} {last_response.text[:200]}"
    )


# ---------------------------------------------------------------------------
# Flask-Mail monkey-patches
# ---------------------------------------------------------------------------

def _patched_configure_host(self):
    """Patched Flask-Mail Connection.configure_host.

    Returns None when Graph API backend is active (no SMTP needed).
    Falls back to the original method otherwise.
    """
    from flask import current_app

    if current_app.config.get("MAIL_OAUTH2_ENABLED"):
        # Graph API does not use SMTP. Return None so Flask-Mail's
        # __exit__ skips calling host.quit().
        return None

    return _original_configure_host(self)


def _patched_send(self, message, envelope_from=None):
    """Patched Flask-Mail Connection.send.

    When OAuth2 is enabled, validates the message and sends via Graph API.
    Otherwise delegates to the original Flask-Mail send method.
    """
    from flask import current_app

    if not current_app.config.get("MAIL_OAUTH2_ENABLED"):
        return _original_send(self, message, envelope_from)

    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        logger.debug("Email suppressed (MAIL_SUPPRESS_SEND=True): %s", message.subject)
        return

    # Validate message (same checks as Flask-Mail)
    if not message.send_to:
        raise ValueError("No recipients have been added")
    if not message.sender:
        raise ValueError(
            "The message does not specify a sender and a default sender "
            "has not been configured"
        )
    if message.has_bad_headers():
        raise flask_mail.BadHeaderError

    if message.date is None:
        message.date = time.time()

    if message.attachments:
        raise NotImplementedError(
            "Graph API mail backend does not yet support attachments. "
            f"Message subject: '{message.subject}'"
        )

    _send_via_graph(message, current_app.config)
    self.num_emails += 1


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

_VALID_FLOWS = ("client_credentials", "delegated")

_REQUIRED_CONFIG_KEYS = (
    "MAIL_OAUTH2_TENANT_ID",
    "MAIL_OAUTH2_CLIENT_ID",
    "MAIL_OAUTH2_CLIENT_SECRET",
    "MAIL_OAUTH2_SENDER_EMAIL",
)


def _validate_config(config):
    """Validate OAuth2 configuration at startup. Raises RuntimeError on error."""
    for key in _REQUIRED_CONFIG_KEYS:
        if not config.get(key):
            raise RuntimeError(f"MAIL_OAUTH2_ENABLED is True but {key} is empty")

    flow = config.get("MAIL_OAUTH2_FLOW", "")
    if flow not in _VALID_FLOWS:
        raise RuntimeError(
            f"MAIL_OAUTH2_FLOW must be one of {_VALID_FLOWS}, got '{flow}'"
        )

    if flow == "delegated":
        cache_file = config.get("MAIL_OAUTH2_TOKEN_CACHE_FILE", "")
        if not cache_file:
            raise RuntimeError(
                "MAIL_OAUTH2_FLOW='delegated' requires "
                "MAIL_OAUTH2_TOKEN_CACHE_FILE to be set"
            )


def _check_token_cache_permissions(cache_file):
    """Warn if the token cache file has insecure permissions."""
    if not cache_file or not os.path.exists(cache_file):
        return
    try:
        mode = stat.S_IMODE(os.stat(cache_file).st_mode)
        if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
            logger.warning(
                "Token cache file '%s' is accessible by group/others "
                "(mode=%o). Fix with: chmod 600 %s",
                cache_file, mode, cache_file,
            )
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Flask extension initialization
# ---------------------------------------------------------------------------

_CONFIG_DEFAULTS = {
    "MAIL_OAUTH2_ENABLED": False,
    "MAIL_OAUTH2_FLOW": "client_credentials",
    "MAIL_OAUTH2_TENANT_ID": "",
    "MAIL_OAUTH2_CLIENT_ID": "",
    "MAIL_OAUTH2_CLIENT_SECRET": "",
    "MAIL_OAUTH2_SENDER_EMAIL": "",
    "MAIL_OAUTH2_TOKEN_CACHE_FILE": "",
}


def init_app(app):
    """Initialize OAuth2 email sending for a Flask/Invenio application.

    This function:
    1. Sets configuration defaults.
    2. Validates configuration if OAuth2 is enabled.
    3. Monkey-patches Flask-Mail to route emails through Graph API.

    The patches are safe to apply even when OAuth2 is disabled — they
    check MAIL_OAUTH2_ENABLED at runtime and fall back to the original
    Flask-Mail behavior when it is False.
    """
    for key, default in _CONFIG_DEFAULTS.items():
        app.config.setdefault(key, default)

    if app.config.get("MAIL_OAUTH2_ENABLED"):
        _validate_config(app.config)

        if app.config["MAIL_OAUTH2_FLOW"] == "delegated":
            _check_token_cache_permissions(
                app.config.get("MAIL_OAUTH2_TOKEN_CACHE_FILE", "")
            )

        logger.info(
            "OAuth2 email enabled (flow=%s, sender=%s)",
            app.config["MAIL_OAUTH2_FLOW"],
            app.config["MAIL_OAUTH2_SENDER_EMAIL"],
        )

    # Apply patches once — runtime checks handle the fallback.
    if not getattr(init_app, "_patched", False):
        flask_mail.Connection.configure_host = _patched_configure_host
        flask_mail.Connection.send = _patched_send
        init_app._patched = True
