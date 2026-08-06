CREATE VIEW demo.seller_team_leaderboard AS
SELECT
  d.rep_name AS rep_name,
  '—' AS attainment_pct,  -- TODO: needs tenant quota-assignment mapping (xc_quota_assignment.ASSIGNMENT_ID)
  Nvl(FormatNumber(d.total_credits, '#,##0.00'), '0.00') AS credits,
  RANK() OVER (ORDER BY d.total_credits DESC) AS rank
FROM (
  SELECT
    part.NAME AS rep_name,
    SUM(Nvl(c.AMOUNT, 0)) AS total_credits
  FROM xactly.xc_period p
  JOIN xactly.xc_position mgr
    ON mgr.MASTER_POSITION_ID = :v_master_position_id
   AND mgr.EFFECTIVE_START_DATE < p.END_DATE AND mgr.EFFECTIVE_END_DATE > p.START_DATE
   AND mgr.INCENT_ST_DATE < p.END_DATE AND mgr.INCENT_END_DATE > p.START_DATE
  JOIN xactly.xc_pos_relations rel
    ON rel.TO_POS_ID = mgr.POSITION_ID
  JOIN xactly.xc_position rep
    ON rep.POSITION_ID = rel.FROM_POS_ID
   AND rep.EFFECTIVE_START_DATE < p.END_DATE AND rep.EFFECTIVE_END_DATE > p.START_DATE
   AND rep.INCENT_ST_DATE < p.END_DATE AND rep.INCENT_END_DATE > p.START_DATE
  JOIN xactly.xc_participant part
    ON part.PARTICIPANT_ID = rep.PARTICIPANT_ID
   AND part.EFFECTIVE_START_DATE < p.END_DATE AND part.EFFECTIVE_END_DATE > p.START_DATE
   AND part.IS_MASTER = 1
  LEFT JOIN xactly.xc_credit c
    ON c.POSITION_ID = rep.POSITION_ID AND c.PERIOD_ID = p.PERIOD_ID
  WHERE p.PERIOD_ID = :v_period
  GROUP BY part.NAME
) d
