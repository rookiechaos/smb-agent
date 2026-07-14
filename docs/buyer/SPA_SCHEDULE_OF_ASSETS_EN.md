# SPA Schedule of Assets (English)

**Contract exhibit (one page).** Attach to the IP assignment / share purchase agreement for transferring `smbagent` to a Japanese commercializing entity.

| Field | Value |
|---|---|
| Product name | `smbagent` |
| Transfer form | Code + documentation framework (technology transfer) |
| Delivery medium | Checksummed archive from `scripts/package_transfer_release.sh` |
| Governing license meta | Apache-2.0 text ships with the Work; **commercial ownership assignment is by this SPA** |
| Authorship baseline | `NOTICE` / `LICENSE` — “Copyright 2026 the smbagent authors” |

---

## A. Included assets (Buyer receives)

| # | Asset | Path / description |
|---|---|---|
| A1 | Core framework Python package | `smbagent/` |
| A2 | Local SLM scaffold (default-off) | `slm/` |
| A3 | Role-separated portal surfaces | `portal/` |
| A4 | Japan trust templates | `japan_trust/` |
| A5 | Apple container contracts | `containers/` |
| A6 | Automated tests | `tests/` |
| A7 | Demo workspace example | `examples/demo-tokyo-dental/` |
| A8 | Buyer diligence & framework guides | `docs/buyer/` (incl. this Schedule) |
| A9 | Commercial / deploy / security / runbook docs | Root `*.md` listed in delivery tree + `internal_doc/` (except seller-withheld stubs) |
| A10 | Build / packaging / CI metadata | `pyproject.toml`, `.github/`, `scripts/`, `.env.example`, `.gitignore` |
| A11 | Legal meta files | `LICENSE`, `NOTICE` |
| A12 | Delivery provenance | `PROVENANCE.txt`, `TRANSFER_MANIFEST.txt`, `*.tar.gz` + `*.sha256` created at packing |

**Meaning of “full framework”:** buyer can install, run `smbagent doctor`, create a customer workspace, execute the five-stage pipeline, and operate monitor/governance without the excluded packs below.

---

## B. Excluded assets (Seller retains; not in transfer archive)

| # | Asset | Path | Reason |
|---|---|---|---|
| B1 | Pioneer / partner workflow pack | Retained only under seller `do-not-upload/` (not in archive) | Customer/partner-specific; out of SPA scope |
| B2 | Seller commercial rate card | `do-not-upload/PRICING.md` | Buyer sets own pricing |
| B3 | Seller marketing artwork | `do-not-upload/flyer.png` | Seller brand |
| B4 | Third-party brand demo assets | `do-not-upload/examples/partner-demo/` | No re-license by default |
| B5 | Seller competitive / pioneer notes | `do-not-upload/internal_doc/*` | Seller-internal |
| B6 | Local IDE / ops / tuning state | `do-not-upload/local-ide/`, `ops` runtime DBs, tuning logs | Machine-local, not product IP |
| B7 | Secrets / credentials | `.env`, API keys, tokens | Never transferred |

Root `PRICING.md` in the buyer tree is a **placeholder only** and is **not** a licensed commercial tariff.

---

## C. Disclosures (read with Schedule)

1. **Provenance / authorship.** If the working tree has no git commit history at packing time, counsel shall rely on (i) this Schedule, (ii) `NOTICE`/`LICENSE`, and (iii) the archive `sha256` + `PROVENANCE.txt` content-tree hash. A later curated git tag is optional operational hygiene, not a condition of asset identification.
2. **Historical market wording.** Older drafts referenced third-party market product names for deliverable-shape analogy. Active prompts and code comments were scrubbed for transfer. Any residual mention is descriptive residue only and **does not** grant trademark rights, software licenses, or affiliation with any third party.
3. **Pricing.** Seller rate cards are excluded. Buyer must replace root `PRICING.md` before customer offers.
4. **Not included.** Training data of live customers, production workspaces, cloud accounts, or reseller agreements are outside this Schedule unless added by written amendment.
5. **No regulatory warranty.** Japan trust templates support operator diligence; they do not certify industry-specific legal clearance for every customer.

---

## D. Delivery acceptance (technical)

Buyer confirms receipt when all are true:

- [ ] Archive `*.tar.gz` and matching `*.sha256` received  
- [ ] `shasum -a 256 -c …sha256` succeeds  
- [ ] Tree contains A1–A12; no `do-not-upload/` directory  
- [ ] `docs/buyer/SPA_SCHEDULE_OF_ASSETS_EN.md` and `_JA.md` present  
- [ ] Root `PRICING.md` marked as buyer-must-replace placeholder  

Pack command:

```bash
./scripts/package_transfer_release.sh /tmp
```

---

## E. Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Seller | | | |
| Buyer | | | |

Japanese version: [`SPA_SCHEDULE_OF_ASSETS_JA.md`](SPA_SCHEDULE_OF_ASSETS_JA.md)
