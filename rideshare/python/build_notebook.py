import nbformat as nbf
nb = nbf.v4.new_notebook(); C=[]
md=lambda s: C.append(nbf.v4.new_markdown_cell(s)); code=lambda s: C.append(nbf.v4.new_code_cell(s))
md("# RideShare — demand, earnings and cancellations\nPython DB-API (`psycopg2`) + pandas + matplotlib on the PostgreSQL `rideshare` database.\nSet `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` if your server is not on `localhost:5432`.")
code('''import os, psycopg2, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
os.makedirs("docs", exist_ok=True)
conn = psycopg2.connect(host=os.getenv("PGHOST","localhost"), port=os.getenv("PGPORT","5432"),
                        user=os.getenv("PGUSER","postgres"), password=os.getenv("PGPASSWORD",""),
                        dbname=os.getenv("PGDATABASE","rideshare"))
def run(sql, params=None):
    """DB-API cursor -> DataFrame (parameterised, so no string-built SQL)."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
run("SELECT COUNT(*) AS trips, COUNT(*) FILTER (WHERE status='COMPLETED') AS completed FROM trip")''')
md("## 1. Demand by hour of day")
code('''hourly = run("""SELECT EXTRACT(HOUR FROM requested_at)::int AS hour, COUNT(*) AS requests
                 FROM trip GROUP BY 1 ORDER BY 1""")
peak = hourly.requests >= hourly.requests.quantile(0.75)
fig, ax = plt.subplots(figsize=(6.4,4.2), dpi=160)
ax.bar(hourly.hour, hourly.requests, color=["#0F6E6E" if p else "#B9D3D3" for p in peak])
ax.set_xticks(range(0,24,3)); ax.set_xlabel("Hour of day"); ax.set_ylabel("Trip requests")
ax.set_title("Requests peak at 8-9 am and 5-7 pm", loc="left", fontsize=11, fontweight="bold")
for s in ("top","right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("docs/chart_hourly.png"); hourly.sort_values("requests", ascending=False).head(5)''')
md("## 2. Demand by pickup zone and time band")
code('''zb = run("""SELECT z.zone_name,
   CASE WHEN h BETWEEN 6 AND 9 THEN 'Morning (6-9)' WHEN h BETWEEN 10 AND 16 THEN 'Midday (10-16)'
        WHEN h BETWEEN 17 AND 20 THEN 'Evening (17-20)' ELSE 'Night (21-5)' END AS band, COUNT(*) AS n
 FROM (SELECT pickup_zone, EXTRACT(HOUR FROM requested_at)::int AS h FROM trip) t
 JOIN zone z ON z.zone_id=t.pickup_zone GROUP BY 1,2""")
pv = zb.pivot(index="zone_name", columns="band", values="n")[["Morning (6-9)","Midday (10-16)","Evening (17-20)","Night (21-5)"]]
pv = pv.loc[pv.sum(axis=1).sort_values().index]
cols = ["#7FB5B5","#B9D3D3","#0F6E6E","#E3A857"]
fig, ax = plt.subplots(figsize=(6.4,4.2), dpi=160)
left = None
import numpy as np
left = np.zeros(len(pv))
for c,col in zip(pv.columns, cols):
    ax.barh(pv.index, pv[c], left=left, color=col, label=c); left += pv[c].values
ax.set_xlabel("Trip requests"); ax.legend(frameon=False, fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.45,-0.16), columnspacing=1)
ax.set_title("MG Road and Koramangala lead; Whitefield peaks in the evening", loc="left", fontsize=10.5, fontweight="bold")
for s in ("top","right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("docs/chart_zone_band.png"); pv''')
md("## 3. Driver earnings and ratings")
code('''dp = run("SELECT * FROM v_driver_performance ORDER BY gross_earnings DESC")
top = dp.head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(6.4,4.2), dpi=160)
ax.barh(top.full_name, top.gross_earnings.astype(float)/1000, color="#0F6E6E")
for y,(e,r) in enumerate(zip(top.gross_earnings.astype(float)/1000, top.avg_rating)): ax.text(e+0.6, y, f"★{r}", va="center", fontsize=8)
ax.set_xlabel("Gross earnings (₹ thousand)"); ax.set_title("Top 10 drivers by earnings", loc="left", fontsize=11, fontweight="bold")
for s in ("top","right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("docs/chart_drivers.png")
dp[["completed_trips","gross_earnings","avg_rating"]].astype(float).corr().round(2)''')
md("## 4. Cancellations: zone and driver view")
code('''cz = run("""SELECT z.zone_name, ROUND(100.0*COUNT(*) FILTER (WHERE status='CANCELLED')/COUNT(*),1) AS cancel_pct
            FROM trip t JOIN zone z ON z.zone_id=t.pickup_zone GROUP BY 1 ORDER BY 2 DESC""")
dc = run("""SELECT driver_id, COUNT(*) AS accepted,
            100.0*COUNT(*) FILTER (WHERE cancelled_by='DRIVER')/COUNT(*) AS cancel_pct, AVG(rider_rating) AS rating
            FROM trip WHERE driver_id IS NOT NULL GROUP BY 1""").astype(float)
fig, ax = plt.subplots(1,2,figsize=(10,4), dpi=160)
ax[0].barh(cz.zone_name[::-1], cz.cancel_pct.astype(float)[::-1], color="#E3A857"); ax[0].set_xlabel("% of requests cancelled")
ax[0].set_title("Cancellation rate by pickup zone", loc="left", fontsize=10.5, fontweight="bold")
ax[1].scatter(dc.rating, dc.cancel_pct, s=dc.accepted/3, color="#0F6E6E", alpha=.7)
ax[1].set_xlabel("Average rider rating"); ax[1].set_ylabel("% cancelled by driver after accepting")
ax[1].set_title("Drivers: rating vs cancellation", loc="left", fontsize=10.5, fontweight="bold")
for a in ax:
    for s in ("top","right"): a.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("docs/chart_cancel.png")
print("overall cancellation %:", run("SELECT ROUND(100.0*COUNT(*) FILTER (WHERE status='CANCELLED')/COUNT(*),1) AS p FROM trip").p[0])
cz''')
code("conn.close()")
nb.cells=C; nb.metadata["kernelspec"]={"name":"python3","display_name":"Python 3","language":"python"}
nbf.write(nb,"../notebook.ipynb")
