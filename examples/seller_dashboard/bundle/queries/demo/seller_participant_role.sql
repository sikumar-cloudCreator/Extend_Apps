CREATE VIEW demo.seller_participant_role AS
SELECT
  CASE WHEN child_cnt = 0        THEN 'IC'
       WHEN grandchild_cnt > 0   THEN 'Leader'
       ELSE 'Manager' END AS role
FROM (
  SELECT
    COUNT(DISTINCT ch.position_id) AS child_cnt,
    COUNT(DISTINCT gc.position_id) AS grandchild_cnt
  FROM xactly.xc_period prd
  JOIN xactly.xc_participant p
    ON p.participant_id = :v_master_participant_id
   AND p.is_master = 1
   AND p.effective_start_date < prd.end_date
   AND p.effective_end_date   > prd.start_date
  JOIN xactly.xc_pos_part_assignment ppa
    ON ppa.participant_id = p.participant_id
  JOIN xactly.xc_position pos
    ON pos.position_id = ppa.position_id
   AND pos.is_master = 1
   AND pos.effective_start_date < prd.end_date
   AND pos.effective_end_date   > prd.start_date
   AND pos.incent_st_date < prd.end_date
   AND pos.incent_end_date   > prd.start_date
  LEFT JOIN xactly.xc_position ch
    ON ch.parent_position_id = pos.position_id
   AND ch.is_master = 1
   AND ch.effective_start_date < prd.end_date
   AND ch.effective_end_date   > prd.start_date
  LEFT JOIN xactly.xc_position gc
    ON gc.parent_position_id = ch.position_id
   AND gc.is_master = 1
   AND gc.effective_start_date < prd.end_date
   AND gc.effective_end_date   > prd.start_date
  WHERE prd.name = :v_period
) hier
