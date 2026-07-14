# デモ東京ホワイトデンタル — Deliverable

This directory contains the full deliverable for the demo dental-clinic engagement.

## Structure

- **`landing-page/`** — branded site
  - `index.html` — clinic homepage
  - `booking.html` — appointment-request form
- **`agent-skills/`** — markdown skill manifests; the runtime dispatches to these
  - `understand-white-dental.md` — foundational context skill
  - `book-appointment.md` — new-appointment scheduling
  - `answer-faq.md` — clinic-procedural FAQ
  - `follow-up.md` — post-visit nudges
- **`integrations/`** — adapter stubs
  - `forward-to-clinic/` — SMTP forwarder for booking forms
  - `book-viewing/` — Google Calendar event creation

## Deploying

```bash
smbagent auth-issue demo-tokyo-dental
smbagent deploy demo-tokyo-dental --target vercel
smbagent serve-http --host 0.0.0.0 --port 8000
```

After deploy, embed the chat widget on the landing page:

```html
<script
  src="/smbagent-widget.js"
  data-customer-id="demo-tokyo-dental"
  data-api-base="https://api.your-host.example.com"
  data-token="<TOKEN_FROM_auth-issue>"
  defer></script>
```
