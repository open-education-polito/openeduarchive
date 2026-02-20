#!/usr/bin/env python3
"""Standalone test script for Graph API email sending.

Replicates the exact logic of oauth2.py without any Invenio/Flask dependency.
Supports both 'delegated' and 'client_credentials' flows.

Usage:
    # Delegated flow (personal outlook.com, needs token cache from token_setup.py)
    python3 test_send.py delegated recipient@example.com

    # Client credentials flow (Polito / organizational tenant)
    python3 test_send.py client_credentials recipient@example.com

    # Dry run — test token acquisition only, no email sent
    python3 test_send.py client_credentials --dry-run

Required environment variables (or .env file):
    MAIL_OAUTH2_TENANT_ID        - "consumers" for personal, tenant GUID for org
    MAIL_OAUTH2_CLIENT_ID        - App registration client ID
    MAIL_OAUTH2_CLIENT_SECRET    - App registration client secret
    MAIL_OAUTH2_SENDER_EMAIL     - Sender mailbox address

Delegated flow only:
    MAIL_OAUTH2_TOKEN_CACHE_FILE - Path to token cache from token_setup.py
"""

import os
import sys
import time
from urllib.parse import quote

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import msal
import requests

GRAPH_API = "https://graph.microsoft.com/v1.0"
TIMEOUT = 30

_SENSITIVE_KEYS = {"MAIL_OAUTH2_CLIENT_SECRET"}


def env(key, default=""):
    val = os.environ.get(key, default)
    return val


def env_required(key):
    val = env(key)
    if not val:
        print(f"  MISSING: {key}")
        return ""
    if key in _SENSITIVE_KEYS:
        print(f"  {key} = ****")
    else:
        print(f"  {key} = {val[:8]}{'...' if len(val) > 8 else ''}")
    return val


def acquire_token_delegated(tenant_id, client_id, client_secret, cache_file):
    """Acquire token via delegated flow (refresh token from cache)."""
    print("\n--- Token Acquisition (delegated) ---")

    cache = msal.SerializableTokenCache()
    try:
        with open(cache_file, "r") as f:
            cache.deserialize(f.read())
        print(f"  Loaded token cache from {cache_file}")
    except FileNotFoundError:
        print(f"  ERROR: Cache file not found: {cache_file}")
        print(f"  Run token_setup.py first.")
        sys.exit(1)

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    print(f"  Authority: {authority}")

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
        token_cache=cache,
    )

    accounts = app.get_accounts()
    if not accounts:
        print("  ERROR: No cached accounts found. Run token_setup.py first.")
        sys.exit(1)

    print(f"  Cached account: {accounts[0].get('username', '?')}")
    print("  Calling acquire_token_silent...")

    result = app.acquire_token_silent(
        scopes=["https://graph.microsoft.com/Mail.Send"],
        account=accounts[0],
    )

    if not result or "access_token" not in result:
        print(f"  ERROR: Token acquisition failed:")
        if result:
            print(f"    error: {result.get('error', '?')}")
            print(f"    description: {result.get('error_description', '?')}")
        else:
            print(f"    result is None")
        sys.exit(1)

    print(f"  OK — Got access token ({len(result['access_token'])} chars)")
    print(f"  Expires in: {result.get('expires_in', '?')}s")
    return result["access_token"]


def acquire_token_client_credentials(tenant_id, client_id, client_secret):
    """Acquire token via client_credentials flow (app-only)."""
    print("\n--- Token Acquisition (client_credentials) ---")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    print(f"  Authority: {authority}")

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )

    print("  Calling acquire_token_for_client...")
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"],
    )

    if not result or "access_token" not in result:
        print(f"  ERROR: Token acquisition failed:")
        if result:
            print(f"    error: {result.get('error', '?')}")
            print(f"    description: {result.get('error_description', '?')}")
        else:
            print(f"    result is None")
        sys.exit(1)

    print(f"  OK — Got access token ({len(result['access_token'])} chars)")
    print(f"  Expires in: {result.get('expires_in', '?')}s")
    return result["access_token"]


def send_email(access_token, flow, sender_email, recipient, token_acquirer=None):
    """Send a test email via Graph API, with retry logic."""
    print("\n--- Sending Email ---")

    if flow == "delegated":
        url = f"{GRAPH_API}/me/sendMail"
    else:
        url = f"{GRAPH_API}/users/{quote(sender_email, safe='@')}/sendMail"

    print(f"  URL: {url}")
    print(f"  From: {sender_email}")
    print(f"  To: {recipient}")

    payload = {
        "message": {
            "subject": f"Test OAuth2 ({flow}) — {time.strftime('%H:%M:%S')}",
            "body": {
                "contentType": "Text",
                "content": (
                    f"Test email sent via Microsoft Graph API.\n"
                    f"Flow: {flow}\n"
                    f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
            },
            "toRecipients": [{"emailAddress": {"address": recipient}}],
            "from": {"emailAddress": {"address": sender_email}},
        },
        "saveToSentItems": False,
    }

    retryable = {401, 429, 500, 502, 503, 504}
    max_retries = 2

    for attempt in range(max_retries + 1):
        print(f"\n  Attempt {attempt + 1}/{max_retries + 1}...")
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            print(f"  ERROR: Request failed: {e}")
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
                continue
            sys.exit(1)

        print(f"  Status: {response.status_code}")
        print(f"  Request-ID: {response.headers.get('request-id', '?')}")

        if response.status_code == 202:
            print(f"\n  SUCCESS — Email sent to {recipient}")
            return

        print(f"  Response: {response.text[:500]}")

        if response.status_code not in retryable:
            break

        if attempt < max_retries:
            if response.status_code == 401 and token_acquirer:
                print(f"  Got 401, re-acquiring token...")
                access_token = token_acquirer()
                wait = 1
            elif response.status_code == 429:
                wait = int(response.headers.get("Retry-After", 2 ** attempt))
            else:
                wait = 2 ** attempt
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)

    print(f"\n  FAILED — Could not send email")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <delegated|client_credentials> <recipient>")
        print(f"       python3 {sys.argv[0]} <delegated|client_credentials> --dry-run")
        print(f"\nExamples:")
        print(f"  python3 {sys.argv[0]} delegated test@example.com")
        print(f"  python3 {sys.argv[0]} client_credentials test@example.com")
        print(f"  python3 {sys.argv[0]} client_credentials --dry-run  # token check only")
        sys.exit(1)

    flow = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    recipient = None if dry_run else (sys.argv[2] if len(sys.argv) > 2 else None)

    if not dry_run and not recipient:
        print(f"ERROR: Recipient required (or use --dry-run)")
        sys.exit(1)

    if flow not in ("delegated", "client_credentials"):
        print(f"ERROR: Invalid flow '{flow}'. Must be 'delegated' or 'client_credentials'.")
        sys.exit(1)

    print(f"=== Graph API Email Test ===")
    print(f"Flow: {flow}")
    print(f"Recipient: {recipient}")
    print(f"\n--- Configuration ---")

    tenant_id = env_required("MAIL_OAUTH2_TENANT_ID")
    client_id = env_required("MAIL_OAUTH2_CLIENT_ID")
    client_secret = env_required("MAIL_OAUTH2_CLIENT_SECRET")
    sender_email = env_required("MAIL_OAUTH2_SENDER_EMAIL")

    missing = not all([tenant_id, client_id, client_secret, sender_email])

    if flow == "delegated":
        cache_file = env_required("MAIL_OAUTH2_TOKEN_CACHE_FILE")
        if not cache_file:
            missing = True
    else:
        cache_file = ""

    if missing:
        print("\nERROR: Missing required environment variables (see above).")
        sys.exit(1)

    # Acquire token
    if flow == "delegated":
        token_acquirer = lambda: acquire_token_delegated(tenant_id, client_id, client_secret, cache_file)
    else:
        token_acquirer = lambda: acquire_token_client_credentials(tenant_id, client_id, client_secret)

    token = token_acquirer()

    if dry_run:
        print(f"\n--- Dry Run ---")
        print(f"  Token acquisition successful.")
        print(f"  Token length: {len(token)} chars")
        print(f"  No email sent (--dry-run).")
        return

    # Send email
    send_email(token, flow, sender_email, recipient, token_acquirer=token_acquirer)


if __name__ == "__main__":
    main()
