# Xactly Extend — official builder best practices

Source: Xactly platform docs (Schemas + Builder Quick Reference), ingested
**2026-09-16**. These are **mandatory** for every app this builder emits from today.
Customer / tenant specifics are omitted; rules are general.

Companion docs (still apply; where they conflict, **this file wins**):
- `dashboard_render_defects.md` — on-screen defects R1–R16
- `period_correctness_rules.md` — quota/commission correctness R1–R5
- `runtime_data_defects.md` — D1–D5
- `extend_xsql_cookbook.md` — canonical xSQL shapes
- `import_blockers.md` — bundle import gates

---

## 1. Schemas (team standard: `$framework`)

A **schema** is a namespace for tables, views, and Extend queries — a folder for the
app's data architecture.

**This builder's standard app schema is `$framework`.** All new app tables and queries
default there unless the FRD or grounding names another schema. Always fully qualify.

| Rule | Detail |
|---|---|
| **S1** | Default app schema = **`$framework`** (`EXTEND_DEFAULT_SCHEMA`). Override only when grounding/FRD requires it. |
| **S2** | Shared cross-app objects may still live in `$framework` (team convention). Dedicated customer schemas are optional, not required for this pipeline. |
| **S3** | Naming for *new* custom schemas (if ever used): lowercase letters, numbers, underscores; must start with a letter; immutable after create. |
| **S4** | Always **fully qualify**: `schema_name.object_name`. Example: `SELECT * FROM $framework.approval_records`. |
| **S5** | **MANDATORY by Oct 2026:** unqualified Incent tables fail. ✅ `xactly.xc_commission` ❌ `xc_commission`. |
| **S6** | Builder components: pick `$framework` (or the app schema) in the Schema drop-down first so the Datasource list is scoped. |

Platform Incent facts stay under `xactly.*`. App-authored views/tables use `$framework.*` by default.

---

## 2. Components

| # | Avoid | Do |
|---|---|---|
| **C1** | Grid/Pivot for primarily-mobile apps | Grid for wide desktop tables (horizontal scroll + pagination); List for mobile autofit (few columns) |
| **C2** | Pushing data into Custom via Variable Configurator events | **Bind Datasource directly** on the Custom — VC push races render |
| **C3** | Hidden controls as layout spacers | **2026 platform change:** hidden controls no longer reserve space. Use empty text / padding / right-align. `hidden` only for real show/hide |
| **C4** | Huge Tab Container stacks | Stay under tab height limits; paginate or split |
| **C5** | Bulk "Approve All" against rendered Grid rows | Grid loads **≤1000** rows initially then lazy-loads. Bulk ops + totals hit the **underlying table/query**, not the grid |
| **C6** | Duplicate Control Keys | Every control key unique on the page |

---

## 3. Queries & xSQL

| # | Rule |
|---|---|
| **Q1** | Names: lowercase + underscores (case-insensitive, but be consistent). |
| **Q2** | Include `$` on system fields: `SELECT $id … FROM $framework.my_custom_table`. |
| **Q3** | Fully qualify every object (`xactly.…` for Incent facts, `$framework.…` for app tables/queries). |
| **Q4** | Join on **IDs** (PK/FK), not names, whenever possible. |
| **Q5** | Point Grids/Lists/Dropdowns at structured queries. If a dropdown needs dynamic vars/functions, **materialize into a table first** — type-to-filter breaks on dynamic query sources. |
| **Q6** | Prefer queries over ETL copies into `$framework` — one source of truth; create tables only when required (Extend Data → Tables). |
| **Q7** | Prefer **ShowFunctions()** / platform functions over hand-rolled join graphs when the function is correct for the use case. |
| **Q8** | **Avoid query-in-query** nesting at scale — #1 production perf hotspot and cascade-break risk. Exception: a **single** parameterless helper leaf (cookbook Rule 12) that collapses a repeated domain rule; do not stack parameterized query→query→query. |
| **Q9** | `DISTINCT` carefully; in `UNION ALL` lists prefer `SELECT DISTINCT …` over `GROUP BY col, 2`. Prefer `<=` / `>=` date bounds over `BETWEEN`. |
| **Q10** | **Never JOIN `xactly.xc_part_user_assignment` to "dedupe" participants** — it can **bypass row-level security** on `xc_participant`. Use `DISTINCT` on `xc_participant`; always test via manager impersonation. |
| **Q11** | Conditional single-row insert: `INSERT … SELECT … FROM Empty() WHERE … NOT IN (…)`. (`Empty()` is for **DML/workflow**, not for strict VC/whereClause — lint still bans it there.) |
| **Q12** | Validate dates in a staging table before `ToDate()` on INSERT — one bad date fails the whole statement. |
| **Q13** | **Static** table/column names in DDL/DML — no `:v_table` / `:v_col` interpolation (breaks app export). |
| **Q14** | Boolean filters: integer `1`/`0` or string `'Y'`/`'N'` / `'1'` — never `'true'`/`'false'` keywords. Aligns with runtime D2 (flag columns are often `string(1)`). |
| **Q15** | Evaluate any query with **>3 joins**; prefer fewer. |
| **Q16** | Prefer `UNION ALL` over `UNION`; avoid unions unless design requires them. |
| **Q17** | Run `AnalyzeQuery` / Analyze — demerits: 0–5 OK, 5–10 warn, 10+ likely problems. |

### Compensation displays (overrides older cookbook Rule 0)

| # | Rule |
|---|---|
| **Q18** | **Do not use `ShowQuotaAttainment()` for employee-facing attainment, payout, or MBO.** Official BP: known discrepancies vs raw tables. Compute from `xactly.xc_quota_assignment` + credits/commission with `period_correctness_rules.md` (R1–R5). |
| **Q19** | Table functions that remain OK as sole-FROM shapes (cookbook Rule 1) still must not sit inside a JOIN (504). Prefer them for non-compensation lookups via `ShowFunctions()`. |

---

## 4. Variables

| # | Rule |
|---|---|
| **V1** | **Page-scoped component variables only.** No `set varname` in Command Editor / xSQLRunner / workflow buttons (those create **globals** that collide across sessions). Audit with `show variables;`. |
| **V2** | Initialize every query `:param` on `$onPageLoad` via Variable Configurator (null / `''` / sentinel) **before** first refresh — otherwise "Could not find parameter or variable". |
| **V3** | Cast on INSERT when types disagree: `cast(:v_x as string)`. Prefer declaring `dataType` on the query object for SELECTs (existing binding rules). |

---

## 5. XFlow & workflows

| # | Rule |
|---|---|
| **W1** | Pass **named component variables** into XFlow — do not rely on session / `CurrentUser` inside the flow. |
| **W2** | Use **synchronous** Incent commands when downstream depends on completion: `incent synchronous create batches (…)`, `incent synchronous calculate (…)`. |
| **W3** | Workflows ~**20 min** max. Batch **200–500** rows; checkpoint last ID to a log table; resume on timeout. |
| **W4** | Build `$framework.workflow_log_tbl` (or app-schema equivalent) health log: in_progress → batch updates → complete/failed. Surface on an Admin page. |
| **W5** | No native cron in Extend — schedule via Connect/external trigger. |
| **W6** | One Connect flow **cannot** call another; orchestrate in Extend workflow or external process. |
| **W7** | `DeployIncent()` deprecated (early 2026) → `DeployIncentLegacyCICD()` / `DeployIncentLegacy()`. |

---

## 6. Integration & calc engine

| # | Rule |
|---|---|
| **I1** | CAE `PeriodName` must match a real `xactly.xc_period` name — territory/model names silently assign **zero**. Preview is looser than full calc; always verify DB output. |
| **I2** | xFlow schedules in **UTC** only. |
| **I3** | AI features: `ai.CreateModelResponse()` (Model Responses API). Legacy OpenAI Assistants path is deprecated. |

---

## 7. Ops checklist (before support / go-live)

- [ ] `show variables;` → no unexpected globals
- [ ] All page vars seeded on `$onPageLoad`
- [ ] No duplicate control keys
- [ ] CAE PeriodNames valid in `xc_period`
- [ ] xFlow schedules UTC
- [ ] Security tested via **manager impersonation** (not admin-only)
- [ ] Workflow health log reviewed
- [ ] No deprecated `DeployIncent()` / Assistants API
- [ ] App objects in **`$framework`** (team standard) unless FRD says otherwise; all SQL fully qualified
- [ ] Comp tiles do **not** call `ShowQuotaAttainment`

---

## Quick-reference matrix (builder)

| Topic | Avoid | Best practice |
|---|---|---|
| Schema | Unqualified / wrong schema | **`$framework`** for app objects; fully qualify; `xactly.*` for Incent facts |
| Variables | Global `set` | VC on `$onPageLoad`, page-scoped |
| Variable setup | Query before init | Seed defaults first |
| Row security | JOIN `xc_part_user_assignment` to dedupe | `DISTINCT` on `xc_participant` + impersonation test |
| Dedup insert | `INSERT…VALUES…WHERE NOT EXISTS` | `INSERT…SELECT…FROM Empty() WHERE…NOT IN` |
| UNION lists | `GROUP BY name, 2` | `UNION ALL` + `SELECT DISTINCT` |
| Dynamic DDL | `:v_table` / `:v_col` | Static names only |
| Incent cmds | Async when chained | `incent synchronous …` |
| Custom data | VC event push | Datasource bind on Custom |
| Spacers | Hidden controls | Empty text / padding (2026) |
| Booleans | `true`/`false` strings | `1`/`0` or `'Y'`/`'N'`/`'1'` |
| CAE period | Model/territory as PeriodName | Real `xc_period` name |
| Comp math | `ShowQuotaAttainment` for pay/MBO | Underlying tables + period R1–R5 |
| Deprecated | `DeployIncent()`, Assistants API | Legacy deploy helpers / Model Responses |
