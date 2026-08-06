CREATE VIEW demo.seller_incremental_details AS
SELECT
  c.ORDER_ITEM_ID AS opportunity_id,
  Nvl(c.ORDER_CODE, c.ITEM_CODE) AS opportunity_name,
  c.CUSTOMER_ID AS customer_id,
  c.CREDIT_ID AS bt_id,
  Nvl(FormatNumber(SUM(c.AMOUNT), '#,##0.00'), '0.00') AS measure_value
FROM xactly.xc_credit c
WHERE c.POSITION_ID = :v_master_position_id
  AND c.PERIOD_ID = :v_period
  AND c.CREDIT_TYPE_NAME = :v_measure
  AND c.IS_ACTIVE = '1'
GROUP BY c.ORDER_ITEM_ID, Nvl(c.ORDER_CODE, c.ITEM_CODE), c.CUSTOMER_ID, c.CREDIT_ID
