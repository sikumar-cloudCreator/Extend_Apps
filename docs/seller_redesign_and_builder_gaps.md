# Seller Dashboard redesign + Extend Builder gaps

Driven by the customer feedback (Jess's email) on the built Seller Dashboard page
(`31f22653…`, ~30 controls: VC init chain → PageLoader → header Customs → rep/manager/quarter
dropdowns → 3 measure Custom cards + 3 payout Custom cards → historical composedChart → attainment
table → ledger search input + table → export button). Two parts: the **redesign** (what to build) and the
**builder changes** (what the LLM/gate must gain to build it). Blocked items need DropZone files we don't have.

---

## Part A — Redesign (per the 5 comments)

**1. Core 1 test data.** Current data = Ewa (Emerging OB, not Core 1, not QTD). Swap the rep/title source to
the Core 1 list (`Dashboard Mockup_RepList_Core1`, 2026-07-15). *Data/config change* — the
`seller_representative_list` / participant views must filter to Core 1 titles. **Needs the Core 1 rep-list file.**

**2. Seller Representative filter → role-aware dashboard.** Filter should include anyone on a comp plan
(IC / Manager / Leader). Behavior branches on the selected user's role:
- **IC** → the base dashboard (current layout).
- **Manager / Leader** → base **plus** a team section: Leaderboard, each IC's contribution to team
  performance, manager insights.
Design: derive a `v_role` variable from a role-lookup view keyed by the selected participant; render the
team section only when role ∈ {Manager, Leader}. In Extend this is **conditional visibility** (a control's
`shouldRenderHidden` toggled by a variable) or a **tabContainer / slideout** holding the team canvas.

**3. Branded Checkout TPV shows no data.** Ewa has values but the BXO cards are blank → **data-mapping bug**
in `seller_measure_branded_checkout` / `seller_payout_branded_checkout`: the view must filter/join on
**credit type = `BXO TPV`**. *xSQL fix* — correct the credit-type predicate. **Needs the Order File Mapping**
to confirm the exact credit_type / component code.

**4. Historical Performance.** (a) Add a **measure selector** (Revenue / Profitability / Branded Checkout TPV)
that drives the `seller_attainment_trend_monthly` chart via a `v_measure` param. (b) Fix the **attainment
scale/legend** on the left — it's inconsistent with the plotted data (review y-axis domain + the
`accelerator_goal_pct` series).

**5. New detail tables — Portfolio Details & Incremental Details.** Each:
- Default metric = one measure (Revenue), **switchable** Revenue / Profitability / BXO TPV (shared `v_measure`).
- **Search**: Portfolio → Account Name, Customer ID, BT ID; Incremental → Opportunity ID, Opportunity Name,
  Customer ID, BT ID (an `input` with `useEnterBroadcast` → search channel → table `whereClauseVariable`).
- **Quarter default, expand to Monthly** — a `v_granularity` toggle (Quarter/Monthly) parameterizing the views.
**Needs the mockups + Order File Mapping** (tabs: *Seller DB Mockup for Sireesh*, *Order File Mapping*,
*Dashboard Screenshots*) for exact columns/searches/measure mapping.

---

## Part B — Builder (LLM) changes this feedback requires

Verified against the real page + `gate/extend_build.py`:

| # | Gap | Evidence | Change |
|---|---|---|---|
| B1 | **`build_page` can't emit `input`, `button`, `exportPagePDF`** | ledger search (`input`, useEnterBroadcast), Download button, Export-PDF | add these `kind`s to `build_page` |
| B2 | **`validate_page` rejects `exportPagePDF`** | control_208 type | add `exportPagePDF` (and `input`) to `valid_types` |
| B3 | **No conditional visibility** | comment 2 (IC vs Manager sections) | support `shouldRenderHidden` driven by a variable, or a `tabContainer`/`slideout` kind for the team canvas |
| B4 | **"repeated cards → one table" rule is too strict** | 3 rich per-measure Custom cards + 3 payout cards (styled, fixed-field) are the *correct* design here, not a table | refine the page-designer rule: rich **fixed-field** measure cards may be N `Custom` cards; only *dynamic/variable-column* data must be a table |
| B5 | **Owning dropdown handler `assignCurrentVariable` not taught** | control_14 uses `["assignCurrentVariable","refresh"]` | page-designer prompt: a dropdown that *sets* its own variable uses `[assignCurrentVariable, refresh]` when binding its default channel |
| B6 | **Measure / granularity selector + search patterns not in prompt** | comments 4–5 | add prompt patterns: a selector dropdown sets `v_measure`/`v_granularity`; data views take it as `:param`; a search `input` broadcasts to a table's `whereClauseVariable` |
| B7 | **Custom-card `layoutSize` fractions** (33.33/16.66) already supported | measure cards use 33.33 | none — confirm designer emits thirds for 3-across card rows |

None of these are seller-specific — they're general Extend capabilities the builder currently lacks.
B1/B2 are hard blockers (the builder literally cannot produce this page today); B3 is the big new feature.

---

## Blocked on inputs (can't fabricate)
- **Core 1 rep list** (`Dashboard Mockup_RepList_Core1`, screenshot 07-15) — for comment 1.
- **Order File Mapping** tab — the component→credit-type→view mapping, incl. **`BXO TPV`** for comment 3 and
  the measure columns for comments 4–5.
- **Mockups** (`Seller DB Mockup for Sireesh`, `Dashboard Screenshots`) — the redesign layout for the team
  section + the two new tables.
These live in DropZone `Xactly_SideCar_ShareFolder / SideCar_Track1_SL_Tracker_sharedwithXactly0728`.

## Recommended sequence
1. **Builder changes B1–B6** (product work — unblocks generating pages like this at all). Testable now.
2. Get the DropZone files → encode the mappings/rep-list into datasource views (query engine).
3. Generate the redesigned page (IC base + role-gated team section + measure selector + 2 detail tables),
   gated as usual, using the **user-provided** `pageDefinitionId`.
