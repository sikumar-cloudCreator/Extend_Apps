# Dashboard render defects — the failure classes a structural gate can't see

A generated page can pass every structural check — valid control types, no dangling channels, every
`:param` satisfied — and still be **wrong on screen**. This is the catalogue of how, drawn from reviewing
shipped dashboards against their live tenants.

Rules **R1–R15** below are what the builder enforces. Each names its enforcement point. None of them are
specific to one customer or one page; they are the recurring ways a dashboard ships broken.

---

## Data / xSQL defects

| # | Symptom on screen | Root cause | Rule |
|---|---|---|---|
| **R1** | A KPI tile renders the literal string **`undefined`** (value, label, or both) | The tile's view returned **zero rows**, or a column the card didn't bind. A `Custom`/tile card renders `undefined` for a missing field — not blank, not `0`. | **A card/tile view must ALWAYS return exactly one row.** Aggregate the whole view (`SUM`/`MAX`/`COUNT`) with no `GROUP BY`, so an empty match still yields one row of zeros, and wrap every output in `Nvl(...)`. |
| **R2** | A percent or money field renders as a bare **`%`** or **`$`** with no number | `Concat(ToString(Round(x, 1)), '%')` where `x` was NULL — the suffix survives, the value doesn't | **`Nvl` goes INSIDE, before formatting.** `Concat(FormatNumber(Nvl(x, 0), '#,##0.0'), '%')`, never `Nvl(Concat(...), ...)`. |
| **R3** | One measure card sits at `0` / blank while its sibling cards populate, and its quota rows look fine | The credit side filtered on a **hardcoded display name** that doesn't equal the tenant's `quota_name` / credit-type value | **Never hardcode a component / quota / credit-type name in a predicate.** Resolve it from the same source that feeds the label, or take it as `:v_measure`. One parameterized view beats N literal-filtered ones. |
| **R4** | A breakdown table shows `0` in every component column while the total column shows real money | Pivot columns used `LIKE '<Component>%'` patterns matching nothing, while the total had no name filter | **A breakdown column and its total must come from the same rowset.** Build parts as `SUM(CASE WHEN <resolved key> ... END)` over the total's rowset, never as independently filtered sub-selects. If the parts sum to 0 but the total doesn't, the part predicate is wrong. |
| **R5** | A card's headline % doesn't reconcile with the credits and quota listed on that same card | The headline came from a table function at one period grain; the listed figures came from another rowset at a different grain | **One card, one rowset, one period grain.** If the card shows QTD credits and QTD quota, the headline % must be that pair. Name the grain in the field (`qtd_`, `annual_`). |
| **R6** | A "deal" ledger contains engine rows — trigger/adjustment entries, paired zero-value corrections | Engine-generated credit rows leaked into a transaction ledger | **A detail ledger must exclude engine-generated rows.** A ledger shows deals, not the engine's bookkeeping. |
| **R7** | Every row in a detail table appears two or more times, and two columns carry identical values | Join fan-out against a mapping table with several ids per entity; two columns bound to one source field | **De-duplicate at the grain the columns imply** (`GROUP BY` the displayed keys), and never bind two columns to the same source column — ship one. |
| **R8** | Money renders inconsistently across the page — some tiles with a currency symbol, some without | Each view formatted independently | **One money format app-wide**: `Concat('$', FormatNumber(Nvl(x, 0), '#,##0'))`. One percent format: `Concat(FormatNumber(Nvl(x, 0), '#,##0.0'), '%')`. Format in the SELECT, never in a predicate. |

## Page / layout defects

| # | Symptom on screen | Root cause | Rule |
|---|---|---|---|
| **R9** | Every section heading appears twice, the second prefixed (`X` then `Table - X`) | A `label`/`Custom` section header **plus** the data control's own rendered title | **Title once.** Either a section `label` with the table's title empty, or the table's own title — never both. |
| **R10** | Sections render **on top of** each other; a search box or heading overlaps the rows of the table above it; pagination controls collide with data | Sections stacked after a table whose height is **data-driven** (large page size, no `maxHeight`) | **Bound every table's height**: cap `itemsPerPage` (~25) and set `maxHeight`, give each table its own full-width row, and never place a control at a fixed offset below a variable-height one. |
| **R11** | A role-gated section renders for the wrong role, often with copy that *says* it's restricted | The section was gated in the **copy** only; `shouldRenderHidden` was never driven by the role variable | **Conditional visibility is wiring, not text.** Derive `:v_role` from a role view → the section's controls default `hidden: true` → the role channel toggles visibility. |
| **R12** | A card inside a conditional section reads `undefined` | R1, in a section whose view legitimately has no rows for this user | **A card that can legitimately have no data needs an explicit empty state** — the one-row aggregate plus a literal fallback, not a raw bind. |
| **R13** | A selector is set to one value while the chart, table, or subtitle below still reflects another | The selector set its variable, but the dependent view / caption never consumed it | **A variable that is set must be read** — by the view's `:param`, by every dependent control's channel, and by the header/subtitle copy. A produced-but-unconsumed selector is a defect. |
| **R14** | A trend chart has bars on only a couple of periods, a y-axis scaled to one series, other series flat on zero, and the legend drawn over the data | A percent series and an amount series share one y-axis; the view returned only periods that had data; the legend sits inside the plot | **Never plot a percent series and an amount series on one axis** (chart the percent, or use the second axis). A trend view returns **one row per period, zero-filled**. Legend outside the plot. |
| **R15** | Placeholder copy visible to the customer; a progress bar or gauge that never fills | Literal placeholder text shipped in `controlData`; the meter's fill was static HTML | **No placeholder copy** (`TODO`, `Coming soon`, `Verification in progress`, `undefined`) and **no unbound meters** — if the fill can't be bound, don't draw the bar. |

---

## Where each rule is enforced

| Rule | Enforced by |
|---|---|
| R1, R2, R8 | `gate/lint_extend_xsql.py` (single-row / Nvl checks) + cookbook Pattern A + `prompts/10_query_writer.md` |
| R3, R4 | `prompts/10_query_writer.md` ("names are data, not literals") + cookbook Rule 5 |
| R5 | cookbook Pattern A (one rowset, one grain) |
| R6, R7 | cookbook Pattern H (detail/ledger hygiene) |
| R9, R10, R13, R15 | `gate/check_page_render.py` + `prompts/30_page_designer.md` |
| R11, R12 | `prompts/30_page_designer.md` + `gate/check_page_render.py` (P5 advisory) |
| R14 | `prompts/30_page_designer.md` (chart axis rules) + cookbook Pattern G |

## Binding rules (2026-08-15 directive)

1. **`participant_id`, never `eff_participant_id`** — fact tables are scoped on `participant_id`.
2. **No `ToNumber(...)`**, and no `ToString(col)` in a predicate. Bind directly
   (`WHERE c.participant_id = :v_master_participant_id`) and declare the variable's `dataType` in the query
   object's `variables[]`. Casting in the predicate was papering over zero-row resolvers; the real fix is R1.
3. **No `rownum` / `RowNumber()`.** Guarantee a single row by **aggregating** (`Nvl(MAX(id), 0)`), which also
   returns one row when nothing matches instead of zero rows — the same fix as R1.
