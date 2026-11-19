"""
gen_data.py -- builds sql/data.sql and mongo/gps_points.jsonl for RideShare.
Deterministic (seed 42): synthetic data, no real people.
Run:  python3 python/gen_data.py
"""
import json, math, random, datetime as dt, os
random.seed(42)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ZONES = [  # id, name, lat, lng, base demand weight
 (1,"MG Road",12.9757,77.6068,1.3),(2,"Koramangala",12.9352,77.6245,1.4),
 (3,"Indiranagar",12.9784,77.6408,1.2),(4,"Whitefield",12.9698,77.7500,1.0),
 (5,"HSR Layout",12.9116,77.6474,1.0),(6,"Electronic City",12.8452,77.6602,0.8),
 (7,"Jayanagar",12.9308,77.5838,0.8),(8,"Hebbal",13.0358,77.5970,0.7)]
OFFICE = {1,4,6}          # office-heavy zones: busy at evening pickup
RESID  = {5,7,8}          # residential: busy at morning pickup
RATES = [("MINI",30,9.0,1.20,70),("SEDAN",40,12.0,1.50,90),("SUV",55,16.0,2.00,130)]
MODELS = {"MINI":["Maruti WagonR","Tata Tiago","Hyundai Santro"],
          "SEDAN":["Maruti Dzire","Honda Amaze","Hyundai Aura"],
          "SUV":["Toyota Innova","Maruti Ertiga"]}
FIRST = "Aarav Vivaan Aditya Arjun Rohan Karthik Suresh Ramesh Manoj Vikram Sandeep Naveen Prakash Harish Mahesh Anil Deepak Imran Faisal Joseph Ananya Diya Priya Kavya Sneha Meera Divya Lakshmi Pooja Nisha Isha Aditi Shruti Swathi Ritu Neha Tanvi Fatima Sara".split()
LAST  = "Sharma Reddy Nair Iyer Rao Gowda Patel Kumar Singh Menon Pillai Naidu Hegde Shetty Joshi Verma Khan Das Bhat Kulkarni D'Souza George".split()
START, DAYS = dt.datetime(2026,9,1), 60
N_RIDER, N_DRIVER, N_TRIPS = 400, 45, 6500

def hav(la1,lo1,la2,lo2):
    p=math.pi/180; a=math.sin((la2-la1)*p/2)**2+math.cos(la1*p)*math.cos(la2*p)*math.sin((lo2-lo1)*p/2)**2
    return 12742*math.asin(math.sqrt(a))
def q(s): return "'"+str(s).replace("'","''")+"'"
def ts(d): return q(d.strftime("%Y-%m-%d %H:%M:%S")) if d else "NULL"
def v(x): return "NULL" if x is None else str(x)

phones=set()
def phone():
    while True:
        p=str(random.choice("6789"))+"".join(random.choice("0123456789") for _ in range(9))
        if p not in phones: phones.add(p); return p
def name(): return f"{random.choice(FIRST)} {random.choice(LAST)}"

riders=[(i,name(),phone(),None,random.choice(ZONES)[0],
         (START-dt.timedelta(days=random.randint(10,700))).date()) for i in range(1,N_RIDER+1)]
riders=[(i,n,p,f"{n.split()[0].lower()}{i}@mail.com",z,j) for (i,n,p,_,z,j) in riders]

drivers=[];vehicles=[];dq={};dcancel={};dweight={}
for i in range(1,N_DRIVER+1):
    drivers.append((i,name(),phone(),f"KA{random.randint(10,60)}{2015+random.randint(0,8)}{random.randint(1000000,9999999)}",
                    (START-dt.timedelta(days=random.randint(30,1500))).date()))
    vt=random.choices(["MINI","SEDAN","SUV"],[5,4,1])[0]
    vehicles.append((i,i,f"KA{random.choice(['01','02','03','04','05'])}{random.choice('ABCDEFGH')}{random.choice('ABCDEFGH')}{random.randint(1000,9999)}",
                     random.choice(MODELS[vt]),vt,7 if vt=="SUV" else 4 if vt=="SEDAN" else 4))
    dq[i]=min(4.95,max(3.2,random.gauss(4.45,0.35)))
    dcancel[i]=min(0.35,max(0.01,random.gauss(0.07,0.06)))   # chance of cancelling after accepting
    dweight[i]=random.uniform(0.5,1.6)
vtype={v_[0]:v_[4] for v_ in vehicles}

HOUR_W=[1,.6,.4,.3,.4,.8,1.6,3,4.6,4.4,3,2.6,2.8,2.6,2.4,2.6,3.4,5,5.2,4.4,3.4,2.6,1.9,1.4]
def pick_hour(): return random.choices(range(24),HOUR_W)[0]

# --- build trips chronologically ------------------------------------
reqs=[]
for _ in range(N_TRIPS):
    d=random.randrange(DAYS); h=pick_hour()
    if START.weekday()>=0 and (START+dt.timedelta(days=d)).weekday()>=5 and random.random()<0.25:
        h=random.choice([11,12,13,19,20,21])          # weekend leisure shift
    reqs.append(START+dt.timedelta(days=d,hours=h,minutes=random.randint(0,59),seconds=random.randint(0,59)))
reqs.sort()
busy={i:START for i in range(1,N_DRIVER+1)}
trips=[];gps=[]
for tid,rq in enumerate(reqs,1):
    h=rq.hour
    wz=[]
    for z in ZONES:
        w=z[4]
        if z[0] in RESID and 7<=h<=10: w*=2.2
        if z[0] in OFFICE and 17<=h<=20: w*=2.0
        if z[0] in OFFICE and 8<=h<=10: w*=1.2
        wz.append(w)
    pz=random.choices(ZONES,wz)[0]
    dz=random.choice([z for z in ZONES if z[0]!=pz[0]]) if random.random()<0.88 else pz
    rider=random.choice(riders)[0]
    row=dict(id=tid,rider=rider,driver=None,veh=None,pz=pz[0],dz=dz[0],rq=rq,ac=None,st=None,en=None,
             status="CANCELLED",dist=None,by="RIDER",rating=None)
    peak=(8<=h<=9) or (17<=h<=19)
    free=[i for i in busy if busy[i]<=rq and random.random()<0.9]
    if not free or random.random()<(0.09 if peak else 0.05):   # nobody accepted / rider gave up
        row["by"]="RIDER"; trips.append(row); continue
    drv=random.choices(free,[dweight[i] for i in free])[0]
    ac=rq+dt.timedelta(seconds=random.randint(15,150))
    row.update(driver=drv,veh=drv,ac=ac)
    if random.random()<dcancel[drv]*(1.5 if peak else 1):     # driver cancels after accepting
        row["by"]="DRIVER"; busy[drv]=ac+dt.timedelta(minutes=5); trips.append(row); continue
    if random.random()<0.04:                                   # rider cancels after accept
        row["by"]="RIDER"; busy[drv]=ac+dt.timedelta(minutes=4); trips.append(row); continue
    st=ac+dt.timedelta(minutes=random.randint(3,11),seconds=random.randint(0,59))
    # GPS path: from pickup centre to drop centre with jitter + wobble
    la1=pz[2]+random.uniform(-.008,.008); lo1=pz[3]+random.uniform(-.008,.008)
    la2=dz[2]+random.uniform(-.008,.008); lo2=dz[3]+random.uniform(-.008,.008)
    straight=max(1.2,hav(la1,lo1,la2,lo2))
    road=straight*random.uniform(1.18,1.38)
    speed=random.uniform(17,24) if (peak or 17<=h<=20) else random.uniform(26,38)
    mins=max(6,road/speed*60+random.uniform(-2,4))
    en=st+dt.timedelta(seconds=int(mins*60))
    n=max(4,int(mins))                                         # ~1 point per minute
    pts=[];plen=0;prev=None
    for k in range(n+1):
        f=k/n
        wob=math.sin(f*math.pi*random.choice([3,4,5]))*0.0022*random.uniform(.6,1.4)*(1 if straight>2 else .3)
        la=la1+(la2-la1)*f+wob; lo=lo1+(lo2-lo1)*f-wob*0.7
        if prev: plen+=hav(prev[0],prev[1],la,lo)
        prev=(la,lo)
        pts.append({"ts":(st+dt.timedelta(seconds=int(mins*60*f))).strftime("%Y-%m-%dT%H:%M:%S"),
                    "loc":{"type":"Point","coordinates":[round(lo,6),round(la,6)]},
                    "speed_kmph":round(max(0,random.gauss(speed,6)),1)})
    # make stored (odometer) distance close to GPS path but not identical
    dist=round(max(1.0,plen*random.uniform(1.08,1.30)),2)
    r=round(min(5,max(1,random.gauss(dq[drv],0.7))))
    row.update(st=st,en=en,status="COMPLETED",dist=dist,by=None,
               rating=r if random.random()<0.85 else None)
    busy[drv]=en+dt.timedelta(minutes=2)
    gps.append({"trip_id":tid,"driver_id":drv,"rider_id":rider,"pickup_zone":pz[1],"drop_zone":dz[1],
                "started_at":st.strftime("%Y-%m-%dT%H:%M:%S"),"ended_at":en.strftime("%Y-%m-%dT%H:%M:%S"),
                "points":pts})
    trips.append(row)

# --- write data.sql --------------------------------------------------
def ins(table,cols,rows,chunk=500):
    out=[]
    for i in range(0,len(rows),chunk):
        out.append(f"INSERT INTO {table} ({cols}) VALUES\n"+",\n".join("("+", ".join(r)+")" for r in rows[i:i+chunk])+";")
    return "\n".join(out)
L=["-- data.sql : synthetic RideShare data (generated by python/gen_data.py, seed 42)","BEGIN;"]
L.append(ins("zone","zone_id,zone_name,city,centre_lat,centre_lng",[[str(z[0]),q(z[1]),q("Bengaluru"),str(z[2]),str(z[3])] for z in ZONES]))
L.append(ins("fare_rate","vehicle_type,base_fare,per_km,per_min,min_fare",[[q(a),str(b),str(c),str(d),str(e)] for a,b,c,d,e in RATES]))
L.append(ins("rider","rider_id,full_name,phone,email,home_zone,joined_on",[[str(a),q(b),q(c),q(d),str(e),q(f)] for a,b,c,d,e,f in riders]))
L.append(ins("driver","driver_id,full_name,phone,licence_no,joined_on",[[str(a),q(b),q(c),q(d),q(e)] for a,b,c,d,e in drivers]))
L.append(ins("vehicle","vehicle_id,driver_id,reg_no,model,vehicle_type,seats",[[str(a),str(b),q(c),q(d),q(e),str(f)] for a,b,c,d,e,f in vehicles]))
L.append("-- trips: COMPLETED rows fire trg_compute_fare, which fills the fare table")
L.append(ins("trip","trip_id,rider_id,driver_id,vehicle_id,pickup_zone,drop_zone,requested_at,accepted_at,started_at,ended_at,status,distance_km,cancelled_by,rider_rating",
  [[str(t["id"]),str(t["rider"]),v(t["driver"]),v(t["veh"]),str(t["pz"]),str(t["dz"]),ts(t["rq"]),ts(t["ac"]),ts(t["st"]),ts(t["en"]),
    q(t["status"]),v(t["dist"]),q(t["by"]) if t["by"] else "NULL",v(t["rating"])] for t in trips]))
L.append("""-- payments for every fare (method by trip_id so the mix is ~50% UPI, 20% card, 20% cash, 10% wallet)
INSERT INTO payment (payment_id, trip_id, method, amount, status, paid_at)
SELECT ROW_NUMBER() OVER (ORDER BY f.trip_id),
       f.trip_id,
       CASE WHEN f.trip_id % 10 < 5 THEN 'UPI' WHEN f.trip_id % 10 < 7 THEN 'CARD'
            WHEN f.trip_id % 10 < 9 THEN 'CASH' ELSE 'WALLET' END,
       f.total_amount,
       CASE WHEN f.trip_id % 53 = 0 THEN 'PENDING' ELSE 'PAID' END,
       CASE WHEN f.trip_id % 53 = 0 THEN NULL ELSE t.ended_at + INTERVAL '1 minute' END
FROM fare f JOIN trip t USING (trip_id);
COMMIT;""")
open(os.path.join(ROOT,"sql","data.sql"),"w").write("\n".join(L)+"\n")
with open(os.path.join(ROOT,"mongo","gps_points.jsonl"),"w") as f:
    for g in gps: f.write(json.dumps(g)+"\n")
print("trips",len(trips),"completed",len(gps),"gps points",sum(len(g["points"]) for g in gps))
