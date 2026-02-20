"""One-time interactive setup for OAuth2 delegated flow.

Obtains a refresh token via Authorization Code flow so the server can
later acquire access tokens without user interaction.

This script is only needed for the "delegated" flow (testing with
personal outlook.com accounts). Production with Polito uses
"client_credentials" and does not need this.

Usage:
    python -m openeduarchive.oauth2_token_setup

Required environment variables:
    MAIL_OAUTH2_TENANT_ID        - "consumers" for personal, or tenant GUID
    MAIL_OAUTH2_CLIENT_ID        - App registration client ID
    MAIL_OAUTH2_CLIENT_SECRET    - App registration client secret
    MAIL_OAUTH2_TOKEN_CACHE_FILE - Where to save the token cache

Prerequisites:
    - pip install msal
    - Add http://localhost:8400 as a Redirect URI in Azure App Registration
      (Authentication > Add a platform > Web)
"""

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

try:
    import msal
except ImportError:
    print("ERROR: msal is not installed. Run: pip install msal")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_REDIRECT_PORT = 8400
_REDIRECT_URI = f"http://localhost:{_REDIRECT_PORT}"
_SCOPES = ["https://graph.microsoft.com/Mail.Send"]
_CALLBACK_TIMEOUT = 300  # 5 minutes

# Shared state between the HTTP handler and the main thread.
_auth_result = {"response": {}}
_auth_received = threading.Event()


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the OAuth2 redirect."""

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        _auth_result["response"] = {k: v[0] if len(v) == 1 else v for k, v in params.items()}

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body>"
            b"<h2>Authentication successful</h2>"
            b"<p>You can close this tab.</p>"
            b"</body></html>"
        )
        _auth_received.set()

    def log_message(self, format, *args):
        """Suppress default HTTP request logging."""


def _save_cache(cache, path):
    """Atomically write the token cache with secure permissions (0600)."""
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(cache.serialize())
    os.replace(tmp, path)
    print(f"Token cache saved to {path}")


def _read_required_env():
    """Read and validate required environment variables."""
    keys = (
        "MAIL_OAUTH2_TENANT_ID",
        "MAIL_OAUTH2_CLIENT_ID",
        "MAIL_OAUTH2_CLIENT_SECRET",
        "MAIL_OAUTH2_TOKEN_CACHE_FILE",
    )
    values = {k: os.environ.get(k, "") for k in keys}
    missing = [k for k, v in values.items() if not v]
    if missing:
        print("ERROR: Missing required environment variables:")
        for k in missing:
            print(f"  - {k}")
        sys.exit(1)
    return values


def main():
    env = _read_required_env()
    tenant_id = env["MAIL_OAUTH2_TENANT_ID"]
    client_id = env["MAIL_OAUTH2_CLIENT_ID"]
    client_secret = env["MAIL_OAUTH2_CLIENT_SECRET"]
    cache_file = env["MAIL_OAUTH2_TOKEN_CACHE_FILE"]

    # Load existing cache if present
    cache = msal.SerializableTokenCache()
    if os.path.exists(cache_file):
        # Warn if permissions are too open
        try:
            import stat
            mode = stat.S_IMODE(os.stat(cache_file).st_mode)
            if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
                print(
                    f"WARNING: Token cache '{cache_file}' is accessible by "
                    f"group/others (mode={oct(mode)}). Fix with: chmod 600 {cache_file}"
                )
        except OSError:
            pass
        with open(cache_file, "r") as f:
            cache.deserialize(f.read())

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
        token_cache=cache,
    )

    # Check if we already have a valid refresh token
    accounts = app.get_accounts()
    if accounts:
        account = accounts[0]
        print(f"Found cached account: {account.get('username', 'unknown')}")
        result = app.acquire_token_silent(scopes=_SCOPES, account=account)
        if result and "access_token" in result:
            print("Refresh token is still valid. No action needed.")
            _save_cache(cache, cache_file)
            return

    # Start local callback server
    server = HTTPServer(("127.0.0.1", _REDIRECT_PORT), _OAuthCallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    # Initiate authorization code flow
    auth_flow = app.initiate_auth_code_flow(
        scopes=_SCOPES,
        redirect_uri=_REDIRECT_URI,
    )
    if "auth_uri" not in auth_flow:
        print(f"ERROR: Failed to initiate auth flow: {auth_flow}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("Open this URL in your browser to authenticate:")
    print()
    print(f"  {auth_flow['auth_uri']}")
    print()
    print("=" * 60)

    import webbrowser
    webbrowser.open(auth_flow["auth_uri"])

    print("\nWaiting for authentication (timeout: 5 minutes)...")
    _auth_received.wait(timeout=_CALLBACK_TIMEOUT)
    server.server_close()

    if not _auth_result["response"]:
        print("ERROR: Authentication timed out.")
        sys.exit(1)

    if "error" in _auth_result["response"]:
        desc = _auth_result["response"].get("error_description", _auth_result["response"]["error"])
        print(f"ERROR: Authentication failed: {desc}")
        sys.exit(1)

    # Exchange authorization code for tokens
    result = app.acquire_token_by_auth_code_flow(
        auth_code_flow=auth_flow,
        auth_response=_auth_result["response"],
    )
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "unknown"))
        print(f"ERROR: Token exchange failed: {error}")
        sys.exit(1)

    username = result.get("id_token_claims", {}).get("preferred_username", "?")
    print(f"\nAuthentication successful for: {username}")
    _save_cache(cache, cache_file)
    print(f"\nDone. The server will use this token to send emails.")
    print(f"IMPORTANT: chmod 600 {cache_file}")


if __name__ == "__main__":
    main()
