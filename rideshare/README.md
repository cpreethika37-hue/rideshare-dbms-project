# RideShare TRANSPORT — Cab Trip and Driver Performance Analytics
DBMS for Analytics project (PostgreSQL 16 + MongoDB). All data is synthetic (seed 42): 6,500 trip requests over 60 days, 5,276 completed.

## Run order
1. `createdb rideshare`
2. `psql -d rideshare -f sql/schema.sql` — tables, constraints, triggers, views
3. `psql -d rideshare -f sql/data.sql` — loads data; `trg_compute_fare` fills `fare` automatically
4. `psql -d rideshare -f sql/dml.sql` — trip lifecycle demo (rolls back); `psql -d rideshare -f sql/queries.sql` — 14 analytical queries
5. `pip install psycopg2-binary pandas matplotlib pymongo` then open `notebook.ipynb` (set `PGHOST/PGPORT/PGUSER/PGPASSWORD` if needed) — charts go to `docs/`
6. MongoDB: `MONGO_URI=mongodb://localhost:27017 python3 mongo/mongo_demo.py` — loads `mongo/gps_points.jsonl`, creates indexes (incl. 2dsphere), CRUD, aggregation

`python/gen_data.py` regenerates `data.sql` and `gps_points.jsonl`; `python/build_deck.py` rebuilds the slides.

## Testing status
- PostgreSQL scripts, notebook and charts: run end-to-end on PostgreSQL 16.
- MongoDB: no MongoDB server was available where this was built. `mongo_demo.py` ran against the in-memory `mongomock` fallback (CRUD and the zone/time-band aggregations). The GPS-distance expression was evaluated by `mongo/mini_eval.py`, and the 2dsphere index and `$geoWithin` query were NOT run. Run once against a real MongoDB before the demo.
