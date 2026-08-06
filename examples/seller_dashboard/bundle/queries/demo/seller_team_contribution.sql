CREATE VIEW demo.seller_team_contribution AS
SELECT
  CASE
    WHEN Nvl(SUM(c.AMOUNT), 0) > 0 THEN
      Concat(
        FormatNumber(
          SUM(CASE WHEN c.EFF_PARTICIPANT_ID = :v_master_participant_id THEN Nvl(c.AMOUNT, 0) ELSE 0 END)
          / SUM(c.AMOUNT) * 100,
          '#,##0.00'),
        '%')
    ELSE '—'
  END AS contribution_pct
FROM xactly.xc_credit c
WHERE c.PERIOD_ID = :v_period
  AND c.EFF_POSITION_ID IN (
    SELECT pr.FROM_POS_ID
    FROM xactly.xc_pos_relations pr
    WHERE pr.TO_POS_ID = :v_master_position_id
    UNION
    SELECT :v_master_position_id FROM xactly.xc_period WHERE PERIOD_ID = :v_period AND rownum = 1
  )
