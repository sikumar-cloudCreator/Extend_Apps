CREATE VIEW demo.seller_portfolio_details AS
SELECT
  Nvl(c.CUSTOMER_NAME, '—') AS account_name,
  c.CUSTOMER_ID AS customer_id,
  c.TRANS_ID AS bt_id,
  Nvl(FormatNumber(SUM(c.AMOUNT), '#,##0.00'), '0.00') AS measure_value
FROM xactly.xc_credit c
JOIN xactly.xc_position pos
  ON c.POSITION_ID = pos.POSITION_ID
JOIN xactly.xc_period p
  ON c.PERIOD_ID = p.PERIOD_ID
WHERE pos.MASTER_POSITION_ID = :v_master_position_id
  AND pos.EFFECTIVE_START_DATE < p.END_DATE
  AND pos.EFFECTIVE_END_DATE > p.START_DATE
  AND pos.INCENT_ST_DATE < p.END_DATE
  AND pos.INCENT_END_DATE > p.START_DATE
  AND c.CREDIT_TYPE_ID = :v_measure
  AND c.PERIOD_ID = :v_period
GROUP BY c.CUSTOMER_NAME, c.CUSTOMER_ID, c.TRANS_ID
