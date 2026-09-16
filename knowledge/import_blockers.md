# Import blockers — the defects no page-level gate catches

Observed on the ClaimRequest bundle, 2026-09-05. All five pages passed
`validate_extend_json.py`, the xSQL linted clean, and the bundle still would not
import. These are checked deterministically by `gate/check_import_ready.py`; run
it on every bundle before delivery.

| # | Defect | Why it passes other gates | Fix |
|---|---|---|---|
| I1 | Zip wraps everything in a top-level folder | Nothing inspects the archive | `pack_bundle()` — `make_archive(root_dir=out_dir)`, never `zip -r x.zip <dir>` |
| I2 | Id is UUID-*shaped* but not hex (`c1a1m000-…-claimrequest01`, `adm00001-…`) | Gates check structure, not id format | Mint with `_uuid_for()`; never hand-write an id |
| I3 | `xsql` embeds `CREATE VIEW x AS` | Valid SQL in isolation | Store a **bare SELECT** — the importer builds DDL from `name`+`schemaName`, so an embedded one doubles it |
| I4 | CSV row short of the schema's column count | Data is never opened | Every row, header included, must have exactly N fields — a short row shifts all later columns left |
| I5 | ADLC names a missing file, or a file is shipped unlisted | Manifest never cross-checked | Both directions must match |

## The real lesson
A gate that passes tells you the page is well-formed, **not** that the bundle is
deliverable. Page gate → export gate → import gate are three different questions.
`check_export_completeness.py` had existed for a while and was wired into
nothing; an unwired gate protects nobody. Worse, when it was finally read its W1
rule turned out to be wrong in two ways — an unrun check also never gets corrected.

## Id formats that are actually correct
- `applicationId`, `pageDefinitionId`, `controlId` → real UUIDs (hex, 8-4-4-4-12).
- table schema `id` → `ent` + 30 hex chars (e.g. `ent60f97e05399f9d8cd3a215ac4adb4`),
  matching real Xactly exports. This one is **not** a UUID and must not be "fixed".

## Importing is not working
`check_import_ready.py` says the bundle will load. `simulate_events.py` says it will
*behave*. They are different questions and both are wired into `write_bundle`.
ClaimRequest passed the import gate and still had 8 controls firing at round 0 with
`v_session_employee_id` unbound — every KPI and grid dead on arrival.

## Datasource resolution (S8/S9, added 2026-09-05)
`simulate_events.py` now also checks both directions of the control<->query link,
bundle-wide:
- **S8 (ERROR)** a control binds a datasource no shipped query provides. The
  control renders empty forever and every other gate passes. Use
  `--external name1,name2` for views that already live in the tenant.
- **S9 (WARN)** a query ships that no control binds — drift. Three of these were
  stranded on Seller Dashboard v3.4 by a layout change and had to be found by hand.

`check_export_completeness.py` has been **deleted** (2026-09-05). All four of its
rules now live in `simulate_events.py`, which actually runs:
- E1 -> **S8** (datasource does not resolve)
- E2 -> **S7**, refined: a param is satisfied if a control owns it OR the query
  seeds it in `variables[]`
- W1 -> **S10**, with two bugs fixed. It recognised only `'All'` as a bypass, so it
  missed the `:v_x = ''` idiom; and it discarded an empty-string seed as "no
  default". Together those made it false-alarm on every search box — it fired 3
  times on Seller Dashboard v3.4, all wrong.
- W2 -> **S11** (ships tables / reads framework data but declares no policySets)
