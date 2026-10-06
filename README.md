# Olist delivery performance

**Where are late deliveries concentrated, and how do delivery outcomes relate to customer reviews?**

An analysis of the Brazilian Olist e-commerce dataset using PostgreSQL, Python and Streamlit. The model keeps one row per order, so orders with several items, payments or reviews do not inflate counts or monetary totals.

![Delivery overview](results/overview.png)

| Full-dataset measure | Result |
|---|---:|
| Source orders | 99,441 |
| Eligible deliveries | 96,470 |
| Late deliveries | 6,534 |
| Late-delivery rate | 6.8% |

A delivery is late only when its **calendar date** falls after the estimated date. Cancelled orders and orders without usable delivery dates are excluded from the rate's denominator.

## What the results show

- March 2018 has a **19.0% late rate** across 7,003 eligible deliveries. Monthly rates describe purchase cohorts, not the month of delivery.
- **São Paulo (SP)** has the largest late-order count: 1,820, with a 4.5% late rate. **Rio de Janeiro (RJ)** has 1,495 late orders and a 12.1% rate. Compare affected volume and rate together when choosing where to investigate.
- The next useful analysis is a comparison of these states within the same purchase months and categories. These descriptive results do not establish causes or estimate preventable delays.

[View the state chart and supporting tables](results/README.md). The images are static charts built from the supplied real-data aggregates, not dashboard screenshots. The dashboard also supports category filters and review comparisons.

## How the analysis works

1. `src/ingest.py` validates CSV headers and loads selected fields with PostgreSQL COPY.
2. `sql/02_order_mart.sql` aggregates items and payments before joining them, and selects one review per order.
3. `sql/03_quality.sql` checks order grain, source-total reconciliation and source anomalies. Blocking failures roll back the import.
4. `src/dashboard.py` presents interactive filters and charts; `src/metrics.py` calculates summaries for the selected orders.
5. `src/results.py` optionally publishes a small, full-dataset snapshot in `results/`.

## Run locally on Windows

Use Python 3.11 or 3.12 and a running Docker Desktop installation. Run commands from the project root.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If you already have a working `.env` and `.venv`, keep them. For an existing environment, run only the dependency-install command above; Matplotlib is used for the result images.

Download and extract the [Olist dataset from Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) into `data/raw`. Keep the original filenames. The loader uses seven files:

- `olist_customers_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`

The download also contains geolocation and category translations. They may remain in `data/raw`, but this model does not load them. Category labels remain in Portuguese.

```powershell
docker compose up -d --wait
.\.venv\Scripts\python.exe -m src.pipeline --data-dir data/raw --label olist
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For an intentional refresh of an already loaded database, add `--replace` to the pipeline command. This replaces the project's database rows transactionally; the raw CSV files remain unchanged. An existing loaded database does not need reimporting just to use this revised dashboard.

The dashboard opens at [localhost:8501](http://localhost:8501). Keep Docker and its PowerShell process running. Use the dashboard's **Refresh data** button after a database refresh.

On macOS/Linux, create and activate a virtual environment with `python3 -m venv .venv` and `source .venv/bin/activate`; then use `python` for the commands above and `cp .env.example .env` to create settings.

## Refresh the published results

The repository already includes the saved Olist snapshot. To replace it with results from your currently loaded database:

```powershell
.\.venv\Scripts\python.exe -m src.results --replace
```

This reads one consistent, read-only database snapshot and refreshes six assets: two PNG charts, three CSV tables and `provenance.json`. It preserves the manually written `results/README.md`. Review that page and the headline findings above if the source data changes. Without `--replace`, existing generated assets are protected from accidental overwrite.

The provenance file records the input file hashes, SQL hashes, dataset scope and summary counts. The bundled provenance explicitly identifies the supplied saved run; it does not claim a new PostgreSQL execution.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The PostgreSQL integration test skips unless `TEST_DATABASE_URL` is set. To run it, use an empty dedicated database, with credentials matching your local settings:

```powershell
docker compose exec db createdb -U olist olist_test
$env:TEST_DATABASE_URL='postgresql://olist:olist_local_learning@localhost:5433/olist_test'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:TEST_DATABASE_URL
```

Skip `createdb` if the empty database already exists. Never point `TEST_DATABASE_URL` at your working Olist database. The integration test refuses existing project schemas and rolls back its fixtures. Test records exist only in a temporary directory; they are independent of the removed demo script.

See [the verification record](docs/VERIFICATION.md) for checks actually executed and remaining runtime checks.

## Project guide

| Path | Responsibility |
|---|---|
| `app.py` | Dashboard entry point |
| `src/` | Loading, database access, dashboard calculations and result publishing |
| `sql/` | Schema, order model, quality checks and analytical queries |
| `tests/` | Calculation, publishing and database regression checks |
| `results/` | Published images, aggregate tables and provenance |
| `docs/METRICS.md` | Metric definitions, populations and caveats |
| `docs/WALKTHROUGH.md` | Implementation explanation |
| `data/raw/` | Local input CSVs, excluded from Git |

Keep `.env`, `.venv`, raw data, caches and ZIP archives out of Git. `.env.example` contains only example local settings. `compose.yaml` binds PostgreSQL to localhost. To stop the database, use `docker compose down`; its named volume preserves the data. `docker compose down -v` deletes that volume.

## Limitations

- **Historical data:** The results describe the supplied Olist dataset and should not be interpreted as current delivery performance.

- **Delivered orders only:** The late-delivery rate includes delivered orders with usable purchase, delivery and estimated dates. It does not measure overdue orders that remained undelivered, so it is not a complete measure of fulfilment performance.

- **Recorded dates and data quality:** Lateness is measured against the recorded estimated calendar date. Missing or inconsistent dates limit interpretation. Quality checks identify anomalies but cannot establish whether the source records are accurate.