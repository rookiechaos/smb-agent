# book-viewing

Creates Google Calendar events for new appointments scheduled by the
`book-appointment` skill.

## Setup

1. In Google Cloud Console, enable the Calendar API and create OAuth credentials.
2. Mint a refresh token via the offline OAuth flow (one-time setup).
3. Copy `config.example.json` to `config.json` and fill in:
   - `client_id` / `client_secret` from the OAuth credentials
   - `refresh_token` from step 2
   - `calendar_id` — typically a shared calendar like `appointments@clinic-domain.jp`
   - `timezone` — `Asia/Tokyo`
4. The `book-appointment` skill calls `BookingForwarder(workspace, "book-viewing").book(...)`.

## Notes

- Calendar IDs may contain `@` — the transport URL-encodes them automatically.
- The OAuth refresh token is sensitive. Restrict `config.json` permissions: `chmod 600`.
- `safety.scan_for_secrets` will flag any real-looking value here. Always use `<PLACEHOLDER>` until the operator wires the live config.
