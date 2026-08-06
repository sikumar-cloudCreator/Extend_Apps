# Extend LLM — Architecture

An LLM agent (Claude **Opus 4.8**) that turns a Xactly Extend **FRD / requirements doc** into a
**complete, deploy-ready Extend application** — navigation, multiple pages, datasource (xSQL) views,
and workflows — where **every generated artifact is gated by the deterministic validator/lint** before
it is returned. Users drive it from **Slack**; the project is built and deployed via **Cursor**.

Design principle: **the LLM does the reasoning and generation; deterministic code guarantees validity.**
"Replace the tools with an LLM" here means the *authoring* (architect, xSQL, page design) moves from
brittle hardcoded builders to Opus — but the `extend-mcp` validator + xSQL lint stay as the **gate** so
output can't silently be schema-invalid. This is the LLM-with-tools pattern (not fine-tuning weights).

---

## Stage 1 — Purpose & Scope
- **Use case:** FRD → full Extend app bundle (nav + N pages + `.sql` datasource views + workflow config).
- **User needs:** a comp implementation consultant pastes/links an FRD in Slack and gets back a reviewed,
  validation-passing app bundle, cutting manual build time.
- **Success criteria:**
  1. 100% of returned artifacts PASS the deterministic gate (page structure/wiring + xSQL lint).
  2. Page/component/view coverage matches the FRD (no dropped requirements).
  3. Existing tenant views are **reused**, not duplicated.
- **Constraints:** only real Extend control types; never invent a `pageDefinitionId` (comes from the created-page shell);
  ground all schema on the real `xc_*` dictionary + tenant view catalog; Opus 4.8; Slack = async (build runs as a job).
- **Out of scope (v1):** live deploy to a tenant, live xSQL execution against the DB (the gate is static-only).

## Stage 2 — System Prompt Design
One **master orchestrator** prompt + focused **sub-agent** prompts (see `prompts/`). Each defines
role/persona, step instructions, and hard guardrails. Guardrails encode the rules the deterministic
gate enforces, so the LLM aims for valid output on the first pass and self-corrects on gate failures.

## Stage 3 — Model
- **Claude Opus 4.8** (`claude-opus-4-8`) for architect, xSQL authoring, and page design (strict JSON + FRD reasoning).
- Optional later: Sonnet 5 for cheap deterministic sub-steps once the gate proves the loop is reliable.

## Stage 4 — Tools & Integrations
The deterministic layer, exposed as tools the LLM calls:
- `validate_extend_page(page, shell)` — structure + wiring + catalog-aware binding/param gate.
- `lint_xsql(sql, strict, declared_params)` — canonical xSQL rule gate.
- `list_datasources()` / `resolve_datasource(cols)` — the **82-view tenant catalog** (reuse-first).
- `schema_lookup(table)` — reads `~/Downloads/xc_tables/xc_<table>.csv` for exact columns/types/PK/FK
  (ignore `_hist`). *(New thin tool — the authoritative data dictionary.)*
- `build_extend_page(controls, shell)` — optional deterministic assembler the LLM can hand a control list to,
  instead of emitting raw JSON (keeps the envelope perfect).
Source: reuse `~/Downloads/extend-mcp/` (already an MCP server + importable modules).

## Stage 5 — Memory Systems
- **Retrieval / grounding context:** the `xc_*` data dictionary, `datasources.json` view catalog,
  known-good page examples (e.g. `SellerDashboard_INTX`), the control-type catalog. Lives in `knowledge/`.
- **Working memory:** the in-progress app-build state (app spec → per-page artifacts → validation results).
- **Episodic:** the Slack thread (FRD, clarifications, iterations).

## Stage 6 — Orchestration
Multi-agent **generate → validate → self-correct → assemble** pipeline (mirrors the existing
`extend-orchestrator` sub-agents, but LLM-driven):
1. **Architect** — FRD → app build-spec (pages, components, variables, datasources, nav, workflows).
2. **xSQL Writer** — per page, author/reuse datasource views → `lint_xsql` gate → self-correct.
3. **Page Designer** — per page, control list → `build_extend_page` / raw JSON → `validate_extend_page` gate → self-correct.
4. **Reviewer** — semantic/altitude check that the app fulfills FRD intent beyond what the gate catches.
5. **Assembler** — bundle nav + pages + views + workflows into the deployable app structure.
Loop stops when every artifact PASSes the gate (bounded retries, then flag `needs_human`).

## Stage 7 — User Interface
**Slack bot** (`/extend-build` slash command or @mention). Flow: user posts/links FRD → bot ack →
async build job runs the pipeline → bot returns the app bundle (files/thread) + a validation report.
Built and deployed from **Cursor** (Bolt for Python or Slack Events API).

## Stage 8 — Testing & Evals
- **Golden FRDs** with expected page counts / key bindings → assert coverage (`evals/`).
- **Gate pass-rate** across a batch of FRDs (target 100% of *returned* artifacts).
- **Regression:** re-generate known-good pages, diff control shapes against the real page JSON.
- **Latency & cost** per build (Slack async budget).

---

## Repo layout
```
extend-llm/
  ARCHITECTURE.md        # this file
  prompts/               # master orchestrator + sub-agent system prompts
  app/                   # Slack bot + orchestration loop + tool bindings
  knowledge/             # grounding assets (schema dict refs, view catalog, example pages)
  evals/                 # golden FRDs + assertions
```

## Reused assets on disk
- `~/Downloads/extend-mcp/` — deterministic gate (validator + xSQL lint) + 82-view catalog. **Tool layer.**
- `~/Downloads/xc_tables/xc_*.csv` — authoritative Xactly data dictionary (104 tables; ignore `_hist`).
- `~/Downloads/SellerDashboard_INTX.zip` — known-good deployed page (shape ground truth for regression).
- `extend-orchestrator` skill + sub-agents — the pipeline topology this LLM version mirrors.
