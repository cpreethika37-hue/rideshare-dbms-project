"""
mongo_demo.py -- RideShare GPS data in MongoDB: load, index, CRUD, aggregation.

  Real server :  MONGO_URI=mongodb://localhost:27017 python3 mongo/mongo_demo.py
  No server   :  python3 mongo/mongo_demo.py        (falls back to `mongomock`, an in-memory
                 stand-in that supports CRUD + aggregation but NOT geospatial indexes/queries)
Collection  : rideshare.trip_gps  -- one document per completed trip, GPS fixes in an array.
"""
import os, json, datetime as dt, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
URI = os.getenv("MONGO_URI")
if URI:
    from pymongo import MongoClient, GEOSPHERE
    client, MOCK = MongoClient(URI), False
else:
    import mongomock
    from pymongo import GEOSPHERE
    client, MOCK = mongomock.MongoClient(), True
db = client["rideshare"]; col = db["trip_gps"]
D = lambda s: dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
out = []
def show(title, rows):
    out.append(f"\n== {title}"); [out.append("   " + str(r)) for r in rows]; print(out[-len(rows)-1]); [print(out[i]) for i in range(-len(rows),0)]

# ---------------------------------------------------------------- load
col.drop()
batch, n = [], 0
for line in open(os.path.join(HERE, "gps_points.jsonl")):
    d = json.loads(line)
    d["started_at"], d["ended_at"] = D(d["started_at"]), D(d["ended_at"])
    for p in d["points"]: p["ts"] = D(p["ts"])
    batch.append(d); n += 1
    if len(batch) == 1000: col.insert_many(batch); batch = []
if batch: col.insert_many(batch)
print(f"loaded {col.count_documents({})} trip documents")

# ---------------------------------------------------------------- indexes
col.create_index("trip_id", unique=True)
col.create_index([("pickup_zone", 1), ("started_at", 1)])
try:
    col.create_index([("points.loc", GEOSPHERE)])         # geospatial: GeoJSON Points inside the array
    geo = True
except Exception as e:
    geo = False; print("2dsphere index skipped:", type(e).__name__)
print("indexes:", sorted(col.index_information().keys()), "| 2dsphere:", geo)

# ---------------------------------------------------------------- CRUD
sample = col.find_one({"trip_id": 1} if col.find_one({"trip_id": 1}) else {}, {"_id": 0, "points": {"$slice": 2}})
show("find_one (first 2 GPS points)", [json.dumps(sample, default=str)[:400] + " ..."])

new = {"trip_id": 900001, "driver_id": 3, "rider_id": 7, "pickup_zone": "Koramangala", "drop_zone": "MG Road",
       "started_at": D("2026-11-02T18:12:00"), "ended_at": D("2026-11-02T18:41:00"),
       "points": [{"ts": D("2026-11-02T18:12:00"), "loc": {"type": "Point", "coordinates": [77.6245, 12.9352]}, "speed_kmph": 0.0},
                  {"ts": D("2026-11-02T18:13:00"), "loc": {"type": "Point", "coordinates": [77.6231, 12.9400]}, "speed_kmph": 21.5}]}
col.insert_one(new)                                                                    # C
r1 = col.update_one({"trip_id": 900001}, {"$push": {"points": {"ts": D("2026-11-02T18:14:00"),   # U
        "loc": {"type": "Point", "coordinates": [77.6210, 12.9455]}, "speed_kmph": 19.0}}, "$set": {"status": "COMPLETED"}})
doc = col.find_one({"trip_id": 900001}, {"_id": 0, "trip_id": 1, "status": 1})            # R
npts = col.aggregate([{"$match": {"trip_id": 900001}}, {"$project": {"n": {"$size": "$points"}}}]).next()["n"]
show("CRUD on trip 900001", [f"inserted -> {doc}", f"update matched={r1.modified_count}, GPS points now {npts}"])
if not MOCK:
    near = col.count_documents({"points.loc": {"$geoWithin": {"$centerSphere": [[77.6068, 12.9757], 0.5/6378.1]}}})
    show("geo: trips with a GPS fix within 500 m of MG Road centre", [near])
d1 = col.delete_one({"trip_id": 900001})                                                  # D
show("delete_one", [f"deleted={d1.deleted_count}; remaining={col.count_documents({})}"])

# ---------------------------------------------------------------- aggregation 1: zone x time band
band = {"$switch": {"branches": [
    {"case": {"$and": [{"$gte": ["$h", 6]},  {"$lte": ["$h", 9]}]},  "then": "1 Morning (6-9)"},
    {"case": {"$and": [{"$gte": ["$h", 10]}, {"$lte": ["$h", 16]}]}, "then": "2 Midday (10-16)"},
    {"case": {"$and": [{"$gte": ["$h", 17]}, {"$lte": ["$h", 20]}]}, "then": "3 Evening (17-20)"}],
    "default": "4 Night (21-5)"}}
PIPE_BAND = [
    {"$project": {"pickup_zone": 1, "h": {"$hour": "$started_at"}}},
    {"$addFields": {"time_band": band}},
    {"$group": {"_id": {"zone": "$pickup_zone", "band": "$time_band"}, "trips": {"$sum": 1}}},
    {"$sort": {"_id.zone": 1, "_id.band": 1}}]
rows = list(col.aggregate(PIPE_BAND))
show("trips per pickup zone and time band (first 8 rows)", [(r["_id"]["zone"], r["_id"]["band"], r["trips"]) for r in rows[:8]])

# ---------------------------------------------------------------- aggregation 2: busiest zone per band
PIPE_BUSY = PIPE_BAND[:3] + [
    {"$sort": {"trips": -1}},
    {"$group": {"_id": "$_id.band", "busiest_zone": {"$first": "$_id.zone"}, "trips": {"$first": "$trips"}}},
    {"$sort": {"_id": 1}}]
show("busiest pickup zone per time band", [(r["_id"], r["busiest_zone"], r["trips"]) for r in col.aggregate(PIPE_BUSY)])

# ---------------------------------------------------------------- aggregation 3: trip distance from GPS (haversine)
def hav(a, b):   # a, b = GeoJSON [lng, lat] expressions
    rad = lambda x: {"$degreesToRadians": x}
    dlat = {"$subtract": [rad({"$arrayElemAt": [b, 1]}), rad({"$arrayElemAt": [a, 1]})]}
    dlng = {"$subtract": [rad({"$arrayElemAt": [b, 0]}), rad({"$arrayElemAt": [a, 0]})]}
    h = {"$add": [{"$pow": [{"$sin": {"$divide": [dlat, 2]}}, 2]},
                  {"$multiply": [{"$cos": rad({"$arrayElemAt": [a, 1]})}, {"$cos": rad({"$arrayElemAt": [b, 1]})},
                                 {"$pow": [{"$sin": {"$divide": [dlng, 2]}}, 2]}]}]}
    return {"$multiply": [12742, {"$asin": {"$sqrt": h}}]}
at = lambda i: {"$arrayElemAt": ["$points.loc.coordinates", i]}
PIPE_DIST = [{"$addFields": {"gps_km": {"$sum": {"$map": {          # sum of consecutive-fix segment lengths
        "input": {"$range": [1, {"$size": "$points"}]}, "as": "i",
        "in": hav(at({"$subtract": ["$$i", 1]}), at("$$i"))}}}}},
    {"$project": {"_id": 0, "trip_id": 1, "pickup_zone": 1, "drop_zone": 1, "gps_km": 1, "fixes": {"$size": "$points"}}}]
if MOCK:      # mongomock cannot run $range -> evaluate the identical expression locally
    from mini_eval import ev
    expr = PIPE_DIST[0]["$addFields"]["gps_km"]
    dist = [{"trip_id": d["trip_id"], "pickup_zone": d["pickup_zone"], "drop_zone": d["drop_zone"], "gps_km": ev(expr, d),
             "fixes": len(d["points"])} for d in col.find({}, {"_id": 0})]
else:
    dist = list(col.aggregate(PIPE_DIST))
for d in dist: d["gps_km"] = round(d["gps_km"], 2)
show("GPS-estimated distance per trip (first 5)", [(d["trip_id"], d["pickup_zone"] + " -> " + d["drop_zone"], d["gps_km"]) for d in dist[:5]])
avg = sum(d["gps_km"] for d in dist) / len(dist)
show("average GPS-estimated trip distance", [f"{avg:.2f} km over {len(dist)} trips"])

# compare with SQL odometer distance if PostgreSQL is reachable
try:
    import psycopg2
    c = psycopg2.connect(host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "5432"),
                         user=os.getenv("PGUSER", "postgres"), password=os.getenv("PGPASSWORD", ""), dbname=os.getenv("PGDATABASE", "rideshare"))
    cur = c.cursor(); cur.execute("SELECT trip_id, distance_km FROM trip WHERE distance_km IS NOT NULL")
    sql = {t: float(k) for t, k in cur.fetchall()}
    pairs = [(d["gps_km"], sql[d["trip_id"]]) for d in dist if d["trip_id"] in sql]
    ratio = sum(s / g for g, s in pairs) / len(pairs)
    show("SQL billed km vs MongoDB GPS km", [f"{len(pairs)} trips: mean billed/GPS ratio = {ratio:.3f}; mean GPS {sum(g for g,_ in pairs)/len(pairs):.2f} km, mean billed {sum(s for _,s in pairs)/len(pairs):.2f} km"])
except Exception as e:
    print("(PostgreSQL comparison skipped:", type(e).__name__, ")")

# ---------------------------------------------------------------- aggregation 4: slowest corridors (avg speed)
PIPE_SPEED = [{"$unwind": "$points"}, {"$group": {"_id": {"zone": "$pickup_zone", "band": {"$cond": [{"$and": [{"$gte": [{"$hour": "$started_at"}, 17]}, {"$lte": [{"$hour": "$started_at"}, 20]}]}, "evening", "other"]}},
        "avg_speed": {"$avg": "$points.speed_kmph"}}}, {"$sort": {"avg_speed": 1}}, {"$limit": 4}]
show("slowest pickup-zone / period combinations (avg km/h)", [(r["_id"]["zone"], r["_id"]["band"], round(r["avg_speed"], 1)) for r in col.aggregate(PIPE_SPEED)])
open(os.path.join(HERE, "..", "docs", "mongo_output.txt"), "w").write("\n".join(out) + f"\n\n(engine: {'mongomock (in-memory)' if MOCK else 'MongoDB server'})\n")
