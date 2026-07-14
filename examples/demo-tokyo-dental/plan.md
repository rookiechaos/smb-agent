# Plan — デモ東京ホワイトデンタル

**Tier:** growth — caps: 5 skills / 5 pages / 3 integrations.

## Summary

A clean, trust-building landing site for a Tokyo dental clinic plus four AI skills
covering inquiry handling, new-patient booking, FAQ, and post-visit follow-up. Two
integrations: Gmail to forward leads to the clinic, Google Calendar for live
appointment-slot management. White + blue palette, friendly-formal Japanese (敬語).

## Architecture

- Static HTML/CSS landing page (no framework — fast load, easy to host)
- Agent skills as markdown manifests under `agent-skills/` for runtime dispatch
- Integration stubs under `integrations/` — operator wires up credentials post-deploy

## Tasks

| ID | Description | Acceptance |
|---|---|---|
| T1 | `code/landing-page/index.html` — hero + services + hours + contact | Renders with brand colors, CTA "今すぐ予約" links to /booking |
| T2 | `code/landing-page/booking.html` — booking intake form | Form POSTs to `/api/book`; mobile-responsive |
| T3 | `code/agent-skills/understand-white-dental.md` — context skill | Has frontmatter, lists hours/services/practitioners placeholders |
| T4 | `code/agent-skills/book-appointment.md` — booking flow | Collects 5 fields, integrates with Google Calendar |
| T5 | `code/agent-skills/answer-faq.md` — FAQ over hours/insurance/etc. | Defers anything outside understand-white-dental scope |
| T6 | `code/agent-skills/follow-up.md` — post-visit nudges | Respects 21:00-08:00 quiet hours |
| T7 | `code/integrations/forward-to-clinic/` — SMTP forwarder stub | README + config.example.json with placeholders |
| T8 | `code/integrations/book-viewing/` — Google Calendar stub | OAuth refresh-token flow documented |
| T9 | `code/README.md` — orientation for the operator | Explains each subdir |
