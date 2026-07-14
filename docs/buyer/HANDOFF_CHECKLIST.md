# IP transfer & acceptance checklist

Use this checklist when selling or transferring `smbagent` to another Japanese
company that will commercialize the product.

## 1. Legal / ownership (outside the repo, but required)

- Separate **IP assignment / SPA** signed with Schedule of Assets
  ([`SPA_SCHEDULE_OF_ASSETS_EN.md`](SPA_SCHEDULE_OF_ASSETS_EN.md) /
  [`SPA_SCHEDULE_OF_ASSETS_JA.md`](SPA_SCHEDULE_OF_ASSETS_JA.md))
- [ ] Decide whether Apache-2.0 distribution continues or buyer re-licenses derivatives under their policy (Apache obligations still apply to the received Work unless rewritten with assignment counsel)
- [ ] Update buyer-facing copyright in `NOTICE` / `LICENSE` appendix after assignment closes
- [ ] Remove or replace seller personal contacts in public docs
- [ ] Confirm partner/customer workflow packs and partner-demo assets are **excluded** from the SPA asset schedule (seller retains under `do-not-upload/`)

## 2. Branding scrub (buyer post-close)

- [ ] Replace seller voice (“our team”, pricing card) with buyer commercial terms
- [ ] Rebrand portal demo labels if still generic placeholders are preferred
- [ ] Decide fate of root `PRICING.md` (**must rewrite** — seller rate card is excluded; placeholder only)
- [ ] Rewrite sales one-pager / flyer with buyer company name
- [ ] Keep competitor market notes in `internal_doc/` only; do not lead customer README with third-party product links

## 3. Clean export / provenance

- [ ] Run [`../../scripts/package_transfer_release.sh`](../../scripts/package_transfer_release.sh) `/tmp`
- [ ] Confirm archive has **no** `do-not-upload/` directory
- [ ] Verify `shasum -a 256 -c …sha256` succeeds
- [ ] Confirm `PROVENANCE.txt` lists `git_head` (may be `none`) and `content_tree_sha256`
- [ ] Verify `workspaces/` and `analytics/` contain only placeholders
- [ ] Hand buyer Schedule of Assets: [`SPA_SCHEDULE_OF_ASSETS_JA.md`](SPA_SCHEDULE_OF_ASSETS_JA.md) / [`SPA_SCHEDULE_OF_ASSETS_EN.md`](SPA_SCHEDULE_OF_ASSETS_EN.md)
- [ ] Hand buyer [`TRANSFER_ONEPAGER_JA.md`](TRANSFER_ONEPAGER_JA.md) / [`TRANSFER_ONEPAGER_EN.md`](TRANSFER_ONEPAGER_EN.md) with the archive
- [ ] Optional hygiene: create a curated git commit + annotated tag *after* scrub (counsel may still rely on sha256 if history was empty at pack time)

## 4. Engineering acceptance (buyer machine)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,voice]"
cp .env.example .env   # fill credentials locally
smbagent doctor
smbagent launch-readiness
smbagent security-readiness
smbagent smoke-harness --out installation_acceptance.plan.json
pytest -q
```

- [ ] Doctor / readiness green
- [ ] Isolation mode decided (`apple-container` recommended on Apple Silicon)
- [ ] Claude Code + Codex CLI versions recorded
- [ ] Optional: real smoke on approved machine only (`--real`)

## 5. First commercial SKU (recommended)

Do **not** relaunch as “general AI agent platform”.

Pick one:

- [ ] Industry pilot using `smbagent/templates/` (e.g. dental booking + FAQ on Mac mini)
- [ ] New governed workflow pack designed by the buyer (do **not** expect seller-withheld partner packs in the transfer)
- [ ] Managed appliance + owner monitor only (narrowest)

## 6. Knowledge transfer sessions (suggested agenda)

1. Product posture & what not to claim ([READY_VS_EXPERIMENTAL.md](READY_VS_EXPERIMENTAL.md))
2. Architecture walkthrough ([ARCHITECTURE.md](ARCHITECTURE.md))
3. Live demo: `new` → `qualify` → `run` → `monitor`
4. HITL approval path + Japan trust notes
5. Incident / backup / maintenance runbook (`RUNBOOK.md`)
6. Known gaps & 90-day buyer roadmap

## 7. Credentials & secrets

- [ ] No seller API keys in the transfer tree
- [ ] Buyer creates own Anthropic / OpenAI / tool credentials
- [ ] Rotate any shared demo tokens
- [ ] Confirm `.env` is gitignored and absent from archive

## Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Seller technical lead | | | |
| Buyer technical lead | | | |
| Buyer commercial owner | | | |
