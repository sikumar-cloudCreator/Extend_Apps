# Gold shape — compensation / seller-style dashboard (final)

Ground truth: finalized Seller Dashboard page `1af96141-f716-4633-9606-6ffbbde05de1`
(2026-09-16). Customer branding scrubbed from this doc; **control architecture is the
curriculum**. Any FRD that is a seller / IC / manager compensation dashboard must clone
these patterns unless the FRD explicitly diverges.

Companion: `evals/golden/comp_dashboard/shape_manifest.json` + `gate/check_gold_shape.py`.

---

## Required spine (events)

Linear bootstrap — **one VC per link**, each BINDs the previous CREATE:

```
$onPageLoad
  → defaultperiod            (v_period)
  → year_name_vc             (v_year_name)
  → defaultparticipant       (v_participant)
  → current_period_id        (v_current_period_id)
  → month_start_date         (v_month_start_date)
  → default_quarter          (v_quarter)
  → master_participant_id    (v_master_participant_id)  ← also binds rep_select
  → master_position_id       (v_master_position_id)
  → data_ready               (v_quarter_code / terminal ready)
```

**PageLoader:** `showLoader` on `$onPageLoad`; `hideLoader` on **`data_ready`** when the
spine is this long (identity + period fully resolved). Mid-chain hide is only for shorter
pages. Do not fan-out two VCs off the same upstream event.

**Seeds on `$onPageLoad`** (one-row views or static VC): at least `v_lock_status`,
`v_credit_search`, `v_measure` (and manager filter seed if a manager dropdown exists).

---

## Required sections (control kinds)

| Order | Pattern | Control |
|---|---|---|
| 1 | App header (title + refreshed) | `Custom` layoutSize 100, binds refresh-date VC |
| 2 | Filter bar | `dropdown`s + optional empty `label` spacers + `button`; **row sums to 100** (e.g. 6×16.66) |
| 3 | Export | `exportPagePDF` binds download button CREATE |
| 4 | Profile strip | one `Custom` layoutSize 100 with internal CSS grid (not 6 sibling controls) |
| 5 | Performance header | `Custom` section header (static copy) |
| 6 | **Measure matrix** | one `Custom` bound to multi-measure stats view (credits / quota in force / attainment / annual / commission / released / pending × measures) — **not** N separate measure tiles |
| 7 | Payout-by-quarter header + table | header `Custom`; `table` with `title: ""`, `maxHeight` set |
| 8 | Supplemental header + 4 cards | SPIFF / Bonus / PPP / Draw at **layoutSize 25** each |
| 9 | Historical header + measure pills + trend | pills = `Custom` + pick VCs; trend = **percent-only** (HTML bars or composedChart of % only — never $ + % on one axis) |
| 10 | Credit details | search `input` + `tabContainer`; each tab child binds **`$onTabOpen` + `data_ready`** (+ search) |
| 11 | Team section (managers) | `shouldRenderHidden: true`; BIND `team_show`→show, `team_hide`→hide; complementary gate VCs |

---

## Hard rules (from observations + this gold)

1. Table `title` empty when a section header Custom already names it (R9).
2. Every table has `maxHeight` (R10); prefer ≤25–50 `itemsPerPage` for layout; gold used 200 with maxHeight — always set maxHeight.
3. Role gating is wiring, not copy (R11).
4. Measure selector must refresh trend + header subtitle (R13).
5. No placeholder copy (R15).
6. App schema **`$framework`** (team standard); fully qualify `$framework.object` / `xactly.object`.
7. Comp tiles: **no `ShowQuotaAttainment`** — views use quota_assignment + credit spine (Q18 / period R1–R5 / D1–D4).
8. Customs with data bind **Datasource directly** (C2).
9. Deliver via `app_assembler.write_bundle` + `pack_bundle` only.

---

## What the next app must learn after each generate

When a new app is generated and reviewed:

1. Diff control **kinds / patterns** against this shape (or a new gold if the product class differs).
2. Every live defect → one `knowledge_base` SEED or iteration lesson + gate rule if determinable.
3. Drop a scrubbed fixture under `evals/golden/<app_class>/` when that class is stable.
4. Re-run `python evals/run_evals.py`.
