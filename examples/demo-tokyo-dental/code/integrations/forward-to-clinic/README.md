# forward-to-clinic

Forwards form submissions (booking requests, FAQ overflow, follow-up replies) from the customer-facing site to the clinic's primary email address.

## Setup

1. Copy `config.example.json` to `config.json`.
2. Fill in:
   - `default_sender` — the email address the customer expects to receive replies from.
     Usually `noreply@<clinic-domain>.jp` or `reception@<clinic-domain>.jp`.
   - `transport` — `memory` for testing, `smtp` for production.
   - For SMTP: `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`, `smtp_use_ssl`.
3. Test with `smbagent send <customer_id> --integration forward-to-clinic --to <clinic-email> --subject test --body hi`.
4. Wire the site's form action (`/api/book` in booking.html) to a handler that
   instantiates `MailForwarder(workspace, "forward-to-clinic")` and calls `forward(...)`.

## Notes

- The clinic's email is operator-configured, not customer-facing — never expose it on the landing page in plaintext.
- Quiet hours: the follow-up skill respects 21:00–08:00. The booking form is 24/7 (just queues for the clinic to see in the morning).
