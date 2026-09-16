# Training loop — next apps → PRD-ready zip

Use this every time you generate an app after the seller gold baseline (2026-09-16).

## Before generate
1. Classify the app: `comp_dashboard` | `claims` | `other`.
2. If `comp_dashboard`, open `knowledge/gold_comp_dashboard_shape.md` and the canvas playbook §6.
3. Confirm knowledge pack is current: official BPs, runtime D1–D5, period R1–R5, render R1–R16.
4. Ground on real schema + catalog — never invent columns.

## Generate (mandatory path)
1. Architect → build-spec with **customer schema name** + helper views listed.
2. xSQL → helpers first, leaves second; no `ShowQuotaAttainment` for pay/attainment/MBO.
3. Page designer → control list matching gold **kinds** for that app class.
4. `validate_extend_page` + xSQL lint + `check_gold_shape` (comp) + `check_page_render`.
5. **Only** `app_assembler.write_bundle` then `pack_bundle` — never hand-zip.
6. `check_import_ready` + `simulate_events` must PASS.

## After human / tenant review
For each defect (wrong number, missing section, import fail, unbound param):

```bash
cd app && python knowledge_base.py add <scope> "<rule>" "<why>"
```

Scopes: `query` | `page` | `architect` | `all`.

If the defect is structural and recurring, add a gate check (do not rely on memory alone).

## Promote a new gold
When an app class is “perfect till now” like seller:

1. Scrub customer names/HTML brand.
2. Add `evals/golden/<app_class>/{frd.md,expected.json,shape_manifest.json}`.
3. Point `knowledge/gold_<app_class>_shape.md` at it.
4. Keep full branded JSON out of git (`evals/golden.local/`, `out_app/`).

## Definition of PRD-ready
- All gates PASS (structure, xSQL, render, gold shape, import, simulate).
- Bundle produced only by assembler.
- Live tenant smoke on numbers (period R1–R5 / D1–D4) signed off by a human once.
