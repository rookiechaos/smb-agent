# Language policy

Ship-tree human-facing text and prompts must be **English** and/or **Japanese** only.

| Allowed | Not allowed in the buyer ship tree |
|---|---|
| English docs, comments, prompts, CLI help | Chinese (Simplified or Traditional) prose |
| Japanese customer / portal / sales / trust copy | Korean, Spanish, French, German, etc. UI/docs |
| Code identifiers in English | Mixed seller notes in other languages |

Checks:

- Prompt files: English defaults + `*_ja.md` Japanese variants
- Portal HTML: `lang="ja"` with Japanese UI copy
- Buyer DD: bilingual EN/JA guides under `docs/buyer/`

If you add a new locale, discuss product scope first — the commercial posture is
Japan SMB + English engineering documentation.
