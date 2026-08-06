# Seller Dashboard (example build)

A worked example of the builder producing the redesigned PayPal Seller Dashboard from the customer
feedback (role-aware sections, measure selector, Portfolio/Incremental search tables, KPI tiles, measure
ring cards + stacked payout cards). See `../../docs/seller_redesign_and_builder_gaps.md`.

## Files
- `build_seller_dashboard.py` — constructs the control list and builds the page JSON via the gate
  (`build_page` + `validate_page`). Run: `python examples/seller_dashboard/build_seller_dashboard.py`
  (writes to `out_app/seller_redesign/`).
- `bundle/` — the deployable Extend export: `app/<pageId>.json` (design page, gate PASS),
  `app/Application.json` (nav), `ADLC.json` (manifest), `queries/demo/*.sql` (datasource xSQL).

## Status / caveats
- The page JSON is structurally valid (gate PASS) and uses the real page id `31f22653-…`.
- The 8 `queries/demo/*.sql` views are **best-guess xSQL** — lint-PASS and column-verified against the
  `xc_*` dictionary, but their SEMANTICS need the customer's **Order File Mapping** to finalize:
  BXO TPV credit-type filter, quota-attainment linkage (leaderboard `attainment_pct` is stubbed),
  and the portfolio/incremental account/customer/BT/opportunity fields.
- KPI tiles are 4 separate white/blue Custom components; measure ring cards bind `seller_measure_<m>`
  (needs numeric `qtd_attainment_pct` for the ring); payout cards bind `seller_payout_<m>`.
- Baseline views (`seller_measure_*`, `seller_payout_*`, `seller_master_*`, etc.) already exist in the
  tenant and are not included here — only the net-new views are.
