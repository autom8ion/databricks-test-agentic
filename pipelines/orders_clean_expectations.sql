-- Layer 3: data quality enforced inside the pipeline itself, on every load
-- (not just in CI). This is a Lakeflow Declarative Pipelines (formerly Delta
-- Live Tables) example for this project's orders domain — deploy it as part
-- of a pipeline, it isn't run by pytest.
--
-- ON VIOLATION controls what happens to a bad row:
--   (default)   keep the row, just record the violation metric
--   DROP ROW    silently exclude the row from the output
--   FAIL UPDATE fail the whole pipeline run
CREATE OR REFRESH STREAMING TABLE orders_clean (
  CONSTRAINT known_customer   EXPECT (customer_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT positive_amount  EXPECT (amount > 0),
  CONSTRAINT has_order_ts     EXPECT (order_ts IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT known_status     EXPECT (status IN ('placed', 'shipped', 'delivered', 'cancelled', 'returned'))
) AS
SELECT * FROM STREAM(raw.orders);
