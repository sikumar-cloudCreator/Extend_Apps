# INTRODUCTION
FRD for a Quota Attainment dashboard in Xactly Extend for sales managers.

# OVERVIEW
A single graphical page: attainment KPIs and a by-measure detail table, filtered by period and position.

# APPLICATION LAYOUT
One page, "Quota Attainment", in the nav. Global filters: Period, Position.

# PAGES

## QUOTA ATTAINMENT
### User Stories
- As a sales manager, I want to see quota attainment % by measure for a position and period so I can coach reps.

### Assumptions
- Position and period are selected via filters; year is derived from the period.

### Filters at the top of the page
- Period, Position.

### Fields and their source
| Field | Datasource view | Column | Params |
|---|---|---|---|
| Measure | Detail table | q_sd_quota_attainment_by_measure | quota_name | :v_master_position_id, :v_period, :v_year_number |
| Attainment % | Detail table | q_sd_quota_attainment_by_measure | attainment_pct | :v_master_position_id, :v_period, :v_year_number |
| Total Credit | Detail table | q_sd_quota_attainment_by_measure | total_credit | :v_master_position_id, :v_period, :v_year_number |
| Quota | Detail table | q_sd_quota_attainment_by_measure | quota_amount | :v_master_position_id, :v_period, :v_year_number |

### Dynamic vs Fixed Data
- The by-measure detail is **dynamic** (row count varies) → a `table` bound to the view, not a Custom card.

# DOCUMENT ACCEPTANCE
| Name | Role | Date |
|---|---|---|
|  | Sponsor |  |
