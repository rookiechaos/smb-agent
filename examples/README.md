# Examples

Sample workspaces that show what a smbagent deliverable looks like before you
commit to running the pipeline for your own customer.

## `demo-tokyo-dental/`

A fully-populated Growth-tier engagement for a fictional dental clinic in Tokyo.

What's in it:

- `qualification.json` — Qualify agent's go/no-go + tier recommendation
- `requirements.json` — collected via the Negotiation conversation (Japanese)
- `transcript.txt` — the full back-and-forth that produced requirements.json
- `plan.md` + `tasks.json` — Plan agent's structured deliverable spec
- `code/landing-page/` — branded HTML site (2 pages: index + booking)
- `code/agent-skills/` — 4 markdown skills with valid frontmatter
- `code/integrations/` — 2 stubs: forward-to-clinic (SMTP) + book-viewing (Google Calendar)
- `runs/round-1/verdict.json` + `feedback.md` — validator's PASSED verdict
- `.workspace_meta.json` — schema version stamp

## What to do with it

```bash
# Browse the structure
ls -R examples/demo-tokyo-dental/

# Render the operator portal to see what the dashboard looks like
smbagent portal demo-tokyo-dental    # writes portal.html

# Open the landing page in a browser
open examples/demo-tokyo-dental/code/landing-page/index.html
```

If you've cloned the repo and want to "try the system" without burning API credits,
this is the easiest way to see the full output shape end-to-end.

## Building your own demo

The fictional dental clinic above came from running the pipeline once and then
committing the output. To build a different demo, run the full pipeline:

```bash
smbagent qualify my-demo --brief "..."
smbagent negotiate my-demo
smbagent run my-demo
cp -r workspaces/my-demo examples/my-demo
```

## `partner-demo/`

Partner-branded demo assets are **seller-only** and live under
`do-not-upload/examples/partner-demo/` (excluded from buyer export).
