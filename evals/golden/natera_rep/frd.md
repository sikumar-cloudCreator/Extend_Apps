# INTRODUCTION
FRD for a Rep Payout dashboard in Xactly Extend (Natera-style comp plan).

# OVERVIEW
A rep-facing page showing total payout KPIs and an attainment breakdown, filtered by period.

# APPLICATION LAYOUT
One page, "Rep Payout Summary", in the nav. Global filter: Period.

# PAGES

## REP PAYOUT SUMMARY
### User Stories
- As a rep, I want to see my total payout and my attainment breakdown for a period so I can track earnings.

### Assumptions
- The rep sees their own child position/participant; period drives the monthly period ids.

### Filters at the top of the page
- Period (list view, no params).

### Fields and their source
| Field | Datasource view | Column | Params |
|---|---|---|---|
| Period (options) | Period filter | ntr_db_period_dropdown | name, period_id | — |
| Total Payment | KPI tile | ntr_db_total_payout | total_payment | :v_child_master_participant_id, :v_month_period_ids |
| % Approved | KPI tile | ntr_db_total_payout | percent_approve | :v_child_master_participant_id, :v_month_period_ids |
| Attainment bucket | Detail table | ntr_oh_attainment | Bucket | :v_period_id, :v_child_master_position_id, :p_region, :v_month_period_ids |

### Dynamic vs Fixed Data
- The attainment breakdown is **dynamic** → a `table` bound to `ntr_oh_attainment`, not a Custom card.

# DOCUMENT ACCEPTANCE
| Name | Role | Date |
|---|---|---|
|  | Sponsor |  |
