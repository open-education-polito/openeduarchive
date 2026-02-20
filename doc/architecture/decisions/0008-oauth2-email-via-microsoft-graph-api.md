# ADR-0001: OAuth2 Email Sending via Microsoft Graph API

- **Status**: Accepted
- **Date**: 2026-02-20

## Context

OpenEducationArchive (built on InvenioRDM) needs to send transactional emails
(account confirmations, password resets, invitation links) through the
Politecnico di Torino's Microsoft 365 infrastructure.

Traditional SMTP with username/password (Basic Auth) is being deprecated by
Microsoft. 

We do not control the Microsoft 365 tenant, the Exchange admin panel, or the
server-side logs. We are a client application that must authenticate and send
mail with minimal support from the tenant administrator.

## Decision

Replace Flask-Mail's SMTP transport with a monkey-patch that routes emails
through the **Microsoft Graph API** (`POST /v1.0/users/{sender}/sendMail`),
authenticated via OAuth2.

### Key choices

1. **Graph API instead of SMTP**: this is a constraint from the provider. 

2. **Two OAuth2 flows**:
   - `client_credentials` (production): fully autonomous, no user
     interaction. Requires `Mail.Send` application permission granted by the
     tenant admin.
   - `delegated` (just for testing purposes): requires a one-time
     interactive browser login to obtain a refresh token. Uses `Mail.Send`
     delegated permission. Needed because personal Microsoft accounts
     (`outlook.com`) do not support the client_credentials flow.

3. **Monkey-patching Flask-Mail** instead of replacing it: InvenioRDM and its
   extensions (invenio-accounts, invenio-users-resources) call Flask-Mail's
   `Connection.send()` in many places. Patching at the transport layer means
   zero changes to upstream code, and the patch falls back to original SMTP
   behavior when `MAIL_OAUTH2_ENABLED=False`.

4. **MSAL library** for token management: Microsoft's official Python library
   handles token caching, refresh, and retry internally. Avoids reimplementing
   OAuth2 token lifecycle.

5. **Secrets via environment variables only**: `MAIL_OAUTH2_CLIENT_SECRET` is
   never in config files. Injected via `APP_` prefixed env vars (Invenio's
   standard mechanism) or `.env` for local development.

6. **Token cache file with 0600 permissions**: The delegated flow persists a
   refresh token to disk. Written atomically (write to `.tmp`, then
   `os.replace`) with restrictive permissions. The application warns at startup
   if permissions are too open.

## Consequences

### Positive

- Structured error responses with `request-id` enable debugging even without
  access to the Microsoft 365 admin panel.
- No changes required to InvenioRDM or any upstream extension.
- `MAIL_SUPPRESS_SEND` is respected, allowing safe local development.
- Retry logic handles transient failures (429, 5xx) and expired tokens (401
  with automatic re-acquisition).

### Negative

- **Attachments not supported**: Graph API supports attachments, but our
  implementation currently raises `NotImplementedError`. InvenioRDM's
  transactional emails do not use attachments, so this is acceptable for now.
- **Monkey-patching is fragile**: A future Flask-Mail version could change
  `Connection.send()` signature. Mitigated by pinning Flask-Mail version in
  InvenioRDM's dependency tree.
- **Delegated flow requires manual setup**: A one-time browser login and local
  HTTP callback server. Only needed for testing, not production.

### Risks

- **Microsoft throttling**: Graph API has per-mailbox rate limits. Bulk email
  (e.g., mass notifications) could trigger 429 responses. The retry logic
  respects `Retry-After` headers, but sustained high volume would require a
  dedicated bulk-send solution.
- **Client secret rotation**: When the Entra ID app registration secret
  expires, email sending fails until the env var is updated with a new secret.
  The error message is clear, but there is no automated alerting.

## Files

- `site/openeduarchive/mail/oauth2.py` — Core implementation (token management, Graph API send, Flask-Mail patches)
- `site/openeduarchive/mail/token_setup.py` — One-time interactive setup for delegated flow
- `site/openeduarchive/mail/test_send.py` — Standalone test script (no Invenio dependency)
- `site/openeduarchive/ext.py` — Extension entry point, calls `mail.init_app()`
- `invenio.cfg` — Configuration (non-secret values only)
