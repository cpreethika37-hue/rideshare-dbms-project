import copy
from pptx import Presentation
from pptx.util import Pt, Emu
from PIL import Image
SRC="/mnt/user-data/attachments/8f197f34-8b93-5e1d-bba8-4a90fa43b0dd/8b9f6ae0-002_DBMS_Project_Presentation_Template.pptx"
p=Presentation(SRC); S=p.slides
def shp(slide,name_start=None,contains=None):
    for s in slide.shapes:
        if s.has_text_frame and ((name_start and s.name==name_start) or (contains and contains in s.text_frame.text)): return s
    raise KeyError(name_start or contains)
def set_paras(shape, paras, size=None):
    """paras: list of paragraphs; each paragraph = list of strings alternating formatting of template runs (run0 bold label, run1 value)."""
    tf=shape.text_frame; pars=tf.paragraphs
    protos=[copy.deepcopy(pp._p) for pp in pars]
    withruns=[q for q in protos if q.findall('{http://schemas.openxmlformats.org/drawingml/2006/main}r')]
    for pp in pars[1:]: pp._p.getparent().remove(pp._p)
    base=pars[0]._p; parent=base.getparent()
    for i,texts in enumerate(paras):
        proto=copy.deepcopy(protos[min(i,len(protos)-1)])
        if proto not in withruns: proto=copy.deepcopy(withruns[-1] if len(withruns)>0 else proto)
        if i==0: parent.replace(base,proto); last=proto
        else: last.addnext(proto); last=proto
        from pptx.text.text import _Paragraph
        par=_Paragraph(proto,tf)
        runs=par.runs
        for j,t in enumerate(texts):
            if j<len(runs): runs[j].text=t
            else:
                np_=copy.deepcopy(runs[-1]._r); runs[-1]._r.addnext(np_); runs=par.runs; runs[-1].text=t
        for r in runs[len(texts):]: r._r.getparent().remove(r._r)
        if size:
            for r in par.runs: r.font.size=Pt(size)
def code(shape, text, size=9):
    lines=text.split("\n")
    set_paras(shape,[[l if l else " "] for l in lines],size)
def picture(slide, placeholder, path, pad=0):
    L,T,W,H=placeholder.left,placeholder.top,placeholder.width,placeholder.height
    w,h=Image.open(path).size; sc=min(W/w,H/h); nw,nh=int(w*sc),int(h*sc)
    placeholder._element.getparent().remove(placeholder._element)
    slide.shapes.add_picture(path,L+(W-nw)//2,T+(H-nh)//2,nw,nh)
def ph(slide,contains):
    for s in slide.shapes:
        if s.name=="Screenshot placeholder" and contains in s.text_frame.text: return s
    raise KeyError(contains)
def cell(c,text,size=8):
    tf=c.text_frame; par=tf.paragraphs[0]
    if par.runs:
        par.runs[0].text=text
        for r in par.runs[1:]: r._r.getparent().remove(r._r)
        r=par.runs[0]
    else:
        r=par.add_run(); r.text=text
    r.font.size=Pt(size); r.font.italic=False
    from pptx.dml.color import RGBColor
    r.font.color.rgb=RGBColor(0x1B,0x2A,0x3A)
    c.margin_top=c.margin_bottom=Emu(18000)
    c.margin_left=c.margin_right=Emu(54000)
def fill_table(tbl,rows,size=8,rowh=None):
    while len(tbl.rows)-1<len(rows):
        tbl._tbl.append(copy.deepcopy(tbl._tbl.tr_lst[-1]))
    for i,row in enumerate(rows,1):
        for j,t in enumerate(row): cell(tbl.cell(i,j),t,size)
    if rowh:
        for r in tbl.rows: r.height=Emu(rowh)
    return tbl
def table_of(slide):
    return [s for s in slide.shapes if s.has_table][0].table

# ---- slide 1
s=S[0]
shp(s,"Project title").text_frame.paragraphs[0].runs[0].text="RideShare TRANSPORT: Cab Trip and Driver Performance Analytics"
shp(s,"Project title").text_frame.paragraphs[0].runs[0].font.size=Pt(18)
set_paras(shp(s,"Text 6"),[["Problem statement: ride-hailing demand, driver earnings and cancellations   ·   Domain: Transport / Ride-hailing"]])
t=table_of(s)
for j,v in enumerate(["1","C Preethika Sree","[add reg. no.]","All parts"]): cell(t.cell(1,j),v,10)
set_paras(shp(s,"Text 8"),[["Database: ","PostgreSQL 16  +  MongoDB   (synthetic data: 6,500 trips, 60 days)"]]) if len(shp(s,"Text 8").text_frame.paragraphs[0].runs)>1 else set_paras(shp(s,"Text 8"),[["Database: PostgreSQL 16  +  MongoDB  (synthetic data: 6,500 trips, 60 days)"]])
set_paras(shp(s,"Text 9"),[["Guide / Examiner: ","[add]","     Date: ","19 Nov 2026"]]) if len(shp(s,"Text 9").text_frame.paragraphs[0].runs)>=4 else None
set_paras(shp(s,"Text 10"),[["GitHub: ","[add repository link]"]]) if len(shp(s,"Text 10").text_frame.paragraphs[0].runs)>=2 else None

# ---- slide 2
s=S[1]
picture(s,ph(s,"ER diagram"),"docs/er_diagram.png")
fill_table(table_of(s),[
 ["zone","zone_id","—"],["fare_rate","vehicle_type","—"],["rider","rider_id","home_zone"],["driver","driver_id","—"],
 ["vehicle","vehicle_id","driver_id, vehicle_type"],["trip","trip_id","rider_id, driver_id, vehicle_id, pickup_zone, drop_zone"],
 ["fare","trip_id","trip_id"],["payment","payment_id","trip_id"]],size=8,rowh=240000)
set_paras(shp(s,contains="Key functional"),[
 ["Key FD: ","trip_id → rider, driver, zones, times, status, km"],
 ["Highest normal form: ","3NF"],
 ["Redundancy removed: ","rates out of vehicle (fare_rate); zone names/coords (zone); fare split from trip"]],size=9)

# ---- slide 3
s=S[2]
code(shp(s,"Code sample"),"""CREATE TABLE trip (
  trip_id      INT PRIMARY KEY,
  rider_id     INT NOT NULL REFERENCES rider,
  driver_id    INT REFERENCES driver,
  pickup_zone  SMALLINT NOT NULL
               REFERENCES zone(zone_id),
  requested_at TIMESTAMP NOT NULL,
  status VARCHAR(10) NOT NULL CHECK (status IN
    ('REQUESTED','ACCEPTED','ONGOING',
     'COMPLETED','CANCELLED')),
  distance_km  NUMERIC(6,2) CHECK (distance_km>0),
  cancelled_by VARCHAR(6),  -- + time-order and
  rider_rating SMALLINT     -- rating CHECKs
);  -- abridged; full DDL in schema.sql""",8.5)
set_paras(shp(s,contains="Trigger:"),[
 ["Trigger: ","trg_compute_fare (AFTER INSERT/UPDATE) prices a trip when COMPLETED: base+km+min, surge, min fare; trg_trip_guard (BEFORE UPDATE) rejects illegal status moves"],
 ["View: ","v_driver_performance (trips, cancels, earnings, rating per driver); v_zone_hour_demand"],
 ["Rows loaded: ","17,553 across 8 tables (6,500 trips, 5,276 fares and payments)"]],size=9)
fill_table(table_of(s),[
 ["Peak demand hours?","GROUP BY, EXTRACT, COUNT","17-19h ≈ 540 requests/hour; 8-9h ≈ 440-490"],
 ["Busiest zone per hour?","View, RANK() OVER PARTITION","MG Road 17-19h; HSR Layout 7 & 9h"],
 ["Driver earnings & ratings?","JOIN, SUM, view, window RANK","Top: Kavya Gowda ₹77.9k, 193 trips"],
 ["Who cancels, where?","FILTER, HAVING, CORR","18.8% cancelled; Whitefield 21.1%; 22 drivers ≥10%"]],size=8,rowh=420000)
picture(s,ph(s,"Result of your most interesting"),"docs/img_q9.png")

# ---- slide 4
s=S[3]
code(shp(s,"Code sample"),"""import psycopg2, pandas as pd

conn = psycopg2.connect(
    host="localhost", dbname="rideshare",
    user="postgres", password="...")

def run(sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return pd.DataFrame(cur.fetchall(),
            columns=[c[0] for c in cur.description])

hourly = run('''SELECT EXTRACT(HOUR FROM
  requested_at)::int AS hour, COUNT(*)
  FROM trip GROUP BY 1 ORDER BY 1''')""",8)
picture(s,ph(s,"Chart 1"),"docs/chart_hourly.png")
picture(s,ph(s,"Chart 2"),"docs/chart_zone_band.png")
set_paras(shp(s,contains="Insight 1"),[
 ["Insight 1:  ","Requests peak 8-9am and 5-8pm; hours 17-19 alone carry 25% of all requests."],
 ["Insight 2:  ","MG Road leads the evening; Whitefield and Electronic City are evening-heavy (offices), HSR and Jayanagar morning-heavy."],
 ["Insight 3:  ","Earnings follow trip count (corr 0.83), not rating (-0.03)."]],size=10)

# ---- slide 5
s=S[4]
code(shp(s,"Code sample"),"""{
 "_id": ObjectId("..."),
 "trip_id": 1, "driver_id": 32,
 "pickup_zone": "Electronic City",
 "drop_zone": "HSR Layout",
 "started_at": ISODate("2026-09-01T00:24:16Z"),
 "points": [
  { "ts": ISODate("...T00:24:16Z"),
    "loc": { "type": "Point",
      "coordinates": [77.6546, 12.8505] },
    "speed_kmph": 35.8 },
  ... ~20 fixes per trip
 ]
}""",8)
codes=[s2 for s2 in s.shapes if s2.name=="Code sample"]
code(codes[1],"""db.trip_gps.aggregate([
 { $project: { pickup_zone: 1,
     h: { $hour: "$started_at" } } },
 { $addFields: { time_band:
     { $switch: {...} } } },
 { $group: {
     _id: { zone: "$pickup_zone",
            band: "$time_band" },
     trips: { $sum: 1 } } },
 { $sort: { trips: -1 } }
])""",8)
set_paras(shp(s,contains="Indexes created"),[["Indexes: trip_id (unique), (pickup_zone, started_at), 2dsphere on points.loc"]],size=8)
set_paras(shp(s,contains="CRUD shown"),[["CRUD shown: insert_one · find · update ($push) · delete_one"]],size=9)
picture(s,ph(s,"Pipeline output"),"docs/img_mongo.png")
fill_table(table_of(s),[
 ["Schema","Fixed, enforced by constraints","Flexible documents"],
 ["Relations","JOINs across 8 tables","GPS fixes embedded in trip"],
 ["Best for","Fares, payments, reports","Variable-length GPS paths"],
 ["Our choice","Trips, money, drivers","GPS tracks, geo queries"]],size=8)
# table has Schema row preset; rows 2-4 are Relations/Best for/Our choice
set_paras(shp(s,contains="Why this part"),[["Why a document model fits: a trip's GPS fixes are always read together, vary in length and need no joins; a 2dsphere index supports geo queries."]],size=9)

# ---- slide 6
s=S[5]
set_paras(shp(s,contains="Finding 1"),[
 ["Finding 1: ","Evening peak 17-19h = 25% of requests; the 1.5x surge band earns 49.8% of revenue."],
 ["Finding 2: ","18.8% of requests cancel (594 by drivers); Whitefield worst at 21.1%."],
 ["Finding 3: ","Rating barely predicts cancelling (corr -0.13): track both."]],size=10)
set_paras(shp(s,contains="Challenge:"),[
 ["Challenge: ","No real trip data; keeping SQL and GPS consistent."],
 ["How we solved it: ","Seeded generator builds both from one trip list."],
 ["Learning: ","Triggers keep fares consistent; embed GPS in documents."]],size=10)
set_paras(shp(s,contains="Files submitted"),[["Files submitted: ","schema.sql · data.sql · dml.sql · queries.sql · notebook.ipynb · MongoDB scripts · README"]],size=10)
for sh in S[5].shapes:
    if sh.has_text_frame and "Show the schema" in sh.text_frame.text:
        for par in sh.text_frame.paragraphs:
            for r in par.runs: r.text=r.text.replace("MySQL / PostgreSQL","PostgreSQL")
p.save("RideShare_DBMS_Project_Presentation.pptx")
