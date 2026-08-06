# Extend LLM

An LLM agent (Claude **Opus 4.8**) that turns a Xactly Incent **Extend** FRD into a complete,
deploy-ready Extend **dashboard application** — navigation, pages, datasource (xSQL) views, and workflows —
where **every generated artifact is gated by a deterministic validator/lint** before it ships. Users drive it
from **Slack**; the project is developed in **Cursor**.

**Design principle:** the LLM does the reasoning and generation; deterministic code guarantees validity
(generate → validate → self-correct). See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design mapped to
an 8-stage agent blueprint, and [`REQUIREMENTS_ANALYSIS.md`](REQUIREMENTS_ANALYSIS.md) for the requirement→design trace.

## Repo layout
```
extend-llm/
├── ARCHITECTURE.md            # full architecture (8 stages)
├── REQUIREMENTS_ANALYSIS.md   # the 8 requirements vs. design + decisions
├── prompts/                   # Opus system prompts (orchestrator + sub-agents)
│   ├── 00_orchestrator.md     # master pipeline + guardrails
│   ├── 10_query_writer.md     # xSQL authoring
│   ├── 20_frd_author.md       # plain-English → FRD (EFM template)
│   ├── 30_page_designer.md    # page-spec → control list (events, Custom rule)
│   └── 40_architect.md        # FRD → app build-spec
├── app/                       # the pipeline + Slack surface
│   ├── schema_tools.py        # grounding: xc_ dictionary + tenant view catalog
│   ├── query_engine.py        # request → xSQL (grounded, lint-gated, self-correct)
│   ├── frd_flows.py           # upload/generate FRD (→ Word doc) + finalize gate
│   ├── page_designer.py       # page JSON (build + validate gate + self-correct)
│   ├── app_assembler.py       # architect → per-page build → deployable bundle
│   ├── feedback_store.py      # learning loop (accepted examples → few-shot)
│   ├── slack_app.py           # Slack bot (query + FRD→dashboard build)
│   └── slack_manifest.yaml
├── gate/                      # VENDORED deterministic gate (self-contained)
│   ├── extend_build.py        # build_page + validate_page (structure/wiring/binding/param)
│   ├── xsql_author.py         # write_xsql + lint_xsql
│   ├── lint_extend_xsql.py    # canonical xSQL rules
│   └── datasources.json       # 82-view tenant catalog (reuse-first)
├── knowledge/frd_template.md  # EFM FRD template
├── evals/                     # golden FRDs + regression/coverage suite
└── requirements.txt
```

## Pipeline (generate → validate → self-correct → assemble)
1. **Query engine** — request → grounded xSQL → `lint_xsql` gate.
2. **FRD flows** — upload an FRD, or generate one (→ downloadable Word doc); **no build until finalized**.
3. **Page designer** — page-spec → control list → `build_page` → `validate_page` gate (events + `:param` wiring).
4. **App assembler** — architect plan → per-page views + pages → deployable Extend export bundle.
5. **Slack** — one app: query assistant **+** FRD→dashboard build trigger.
6. **Feedback + evals** — accepted examples reused as few-shot; golden-FRD regression suite.

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...          # only the Opus steps need this

# deterministic, no key:
python evals/run_evals.py                                  # 10/10 checks
python app/schema_tools.py xc_credit                       # schema grounding

# live (needs key):
python app/query_engine.py "credits by measure for a participant and period" \
  --tables xc_credit xc_credit_type xc_participant xc_period --params v_master_participant_id v_period
python evals/run_evals.py --llm

# Slack bot (needs Slack tokens too):
export SLACK_BOT_TOKEN=xoxb-...  SLACK_APP_TOKEN=xapp-...
python app/slack_app.py
```

## Configuration (tenant-agnostic)
The builder is a general-purpose tool — nothing is hardcoded to one tenant. Point it at any tenant via env:

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Opus 4.8 calls (authoring steps) |
| `EXTEND_DEFAULT_SCHEMA` | `demo` | datasource schema when a view's own schema isn't known (e.g. `paypal`, `$framework`) |
| `EXTEND_CATALOG_PATH` | `gate/datasources.json` | the tenant's reusable-view catalog (name/params/columns/xsql) |
| `XC_TABLES_DIR` | `~/Documents/xc_tables` | the Xactly `xc_*` data dictionary (one CSV per table) |

## External data (not vendored)
- **Xactly `xc_*` data dictionary** — one CSV per table (columns/types/PK/FK); used by
  `schema_tools.schema_lookup` for grounding. Set `XC_TABLES_DIR` to your tenant's dictionary.
- **View catalog** (`gate/datasources.json`) ships one tenant's 82 views as a starting reuse set; replace via
  `EXTEND_CATALOG_PATH` for a different tenant.

## Notes
- Secrets live only in `.env` (gitignored). Never commit an API key.
- The `gate/` code is vendored so the repo is self-contained; it originated from the `extend-mcp` MCP server.
