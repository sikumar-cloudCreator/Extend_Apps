# Extend LLM — app/

The **query engine** (queries-first foundation) and, later, the FRD flows, page designer, assembler,
and Slack surface. See `../ARCHITECTURE.md` and `../REQUIREMENTS_ANALYSIS.md`.

## Files
- `schema_tools.py` — grounding. Two real sources, **no API key needed**:
  1. `schema_lookup(table)` / `render_schema(table)` → columns/types/PK/FK from `~/Documents/xc_tables/xc_<table>.csv`
     (override with `XC_TABLES_DIR`; `_hist` tables ignored).
  2. `list_views()` / `resolve_view(cols)` / `render_reuse_candidates(cols)` → the 82 tenant views in
     `~/Downloads/extend-mcp/datasources.json` (reuse-first).
- `query_engine.py` — request → grounding → **Opus 4.8** authors xSQL (or picks REUSE) → `lint_xsql` gate →
  self-correct loop → PASS-ing view. Lint gate imported from the extend-mcp project (single source of truth).

## Run (in Cursor)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt
export ANTHROPIC_API_KEY=sk-...            # only the authoring step needs this

# deterministic parts — work with NO key:
python app/schema_tools.py xc_credit                       # dump a table
python app/schema_tools.py --resolve measure_name credits  # best reusable view
python app/query_engine.py "credits by measure" --tables xc_credit xc_credit_type --dry   # grounding+prompt only

# full authoring (needs key):
python app/query_engine.py "credits by measure for a participant and period" \
  --tables xc_credit xc_credit_type xc_participant xc_period \
  --columns measure_name credits --params v_master_participant_id v_period --name v_credits_by_measure
```

## FRD flows (`frd_flows.py` + `../prompts/20_frd_author.md`) — point 1 & 2
Two-path entry: **Upload FRD** (`read_frd` → text) or **Generate FRD** (`generate_frd` Opus → EFM-template
markdown → `markdown_to_docx` Word doc). `FRDSession` holds state; **`guard_build()` blocks all code/JSON
generation until `finalize()`** (point 2). `revise(comment)` logs user comments for the learning loop (point 5).
```bash
python app/frd_flows.py --to-docx sample_frd.md out.docx   # markdown FRD -> Word doc (no key)
python app/frd_flows.py --read some_frd.docx               # extract FRD text (no key)
```

## Page/dashboard designer (`page_designer.py` + `../prompts/30_page_designer.md`) — points 3,4,6
Page-spec + datasource names + shell → grounding (view columns/params) → Opus emits a **control list** →
`build_extend_page` (exact envelope, from extend-mcp) → `validate_extend_page` (structure + wiring +
catalog-aware binding/param gate) → self-correct loop → PASS page JSON. Enforces: `tile` for KPIs, `chart`
for trends, **`table` for dynamic/variable columns (never `Custom`)**, channel CREATE/BIND wiring, and
view `:param` ↔ page-variable agreement. The **`pageDefinitionId` is REQUIRED from the user** (create the page
in Extend, paste its id) — the designer never generates one (`design_page` raises `MissingPageId`; CLI refuses
without `--id`).
```bash
python app/page_designer.py --assemble controls.json --title "My Page" --id <extend-pageDefinitionId>   # --id required
```

## App assembler (`app_assembler.py` + `../prompts/40_architect.md`) — step 4
FRD → `architect` (build-spec) → per page: author/reuse xSQL (`query_engine`) + design page (`page_designer`),
both gated → `write_bundle` emits the **real Extend export layout**: `ADLC.json`, `app/Application.json` (nav),
`app/<id>.json` (pages), `queries/<schema>/<view>.json`, `tables/schemas/xactly/<xc_table>.json` (from the
xc_ dictionary). Enforces the FRD finalize gate (`session.guard_build()`) and the user-provided-id rule
(`required_page_ids` lists pages still needing an id). `coverage_report` = pages built vs FRD + gate verdicts.
```bash
python app/app_assembler.py --bundle bundle_in.json --out ./out_app   # deterministic bundle write, no key
```

## Slack surface (`slack_app.py` + `slack_manifest.yaml`) — step 5 (one app, both modes)
`/extend` (or @mention) opens a menu: **Write a Query** / **Upload FRD** / **Generate FRD**. Per-thread state.
- *Query*: `credits by measure  tables: xc_credit, xc_period  params: v_period` → `query_engine` → posts the
  lint-passing xSQL (or REUSE).
- *Generate FRD*: plain-English requirements → `generate_frd` → uploads the Word doc → **Revise** / **Finalize & Build**.
- *Upload FRD*: attach `.docx`/`.md` → **Finalize & Build**.
- Build: `finalize()` (gate) → `architect` → asks for `name = pageDefinitionId` per page → `assemble_app` →
  posts coverage report + uploads the deployable app bundle (zip).

**Setup (Socket Mode) in Cursor:**
1. api.slack.com/apps → *From an app manifest* → paste `slack_manifest.yaml`.
2. Enable Socket Mode; make an App-Level token (`connections:write`) → `SLACK_APP_TOKEN=xapp-...`.
3. Install to workspace → Bot token → `SLACK_BOT_TOKEN=xoxb-...`. Also `ANTHROPIC_API_KEY=sk-...`.
4. `pip install -r ../requirements.txt` then `python app/slack_app.py`.

## Status
- ✅ Query engine grounding (both sources) + lint gate: tested, deterministic, no key.
- ✅ FRD flows: read + markdown→docx export + finalize gate: tested, deterministic, no key.
- ✅ Page designer assemble + gate: tested (valid→PASS, broken→FAIL with wiring/param errors), no key.
- ✅ App assembler bundling: tested — output tree matches the real Extend export shape; coverage/required-ids work.
- ✅ Slack app: compiles; query-hint parser tested. Needs Slack + Anthropic tokens to run live.
- ✅ Feedback loop (`feedback_store.py`): store + `few_shot` recall auto-injected into query/page prompts;
  Slack 👍 Accept / ✍️ Correct buttons record; `promote_candidates()` surfaces recurring fixes. Tested.
- ✅ Evals (`../evals/run_evals.py`): 10/10 deterministic checks pass (gate regressions, bundle shape,
  grounding, feedback roundtrip); LLM checks (architect coverage, query PASS) run with a key + golden FRD.
- ⏳ Opus calls (`architect`, query authoring, `generate_frd`, `design_page`): coded; need `ANTHROPIC_API_KEY` + deps.

**All 6 build steps are code-complete; every deterministic path is tested green.** Remaining to run live:
`pip install -r ../requirements.txt`, set `ANTHROPIC_API_KEY` (+ Slack tokens), then exercise the Opus paths in Cursor.
