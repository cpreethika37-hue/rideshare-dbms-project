import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
def card(lines, path, w, h, size=8.5):
    fig = plt.figure(figsize=(w, h), dpi=220); fig.patch.set_facecolor("#F4F7FB")
    fig.text(0.02, 0.96, "\n".join(lines), family="DejaVu Sans Mono", fontsize=size, va="top", color="#1B2A3A", linespacing=1.35)
    fig.savefig(path, facecolor=fig.get_facecolor()); plt.close(fig)
card(["rideshare=# -- Q9: drivers cancelling >=10% after accepting (>=50 trips)",
      " driver_id | full_name     | accepted | cancels | cancel_% | rating",
      "-----------+---------------+----------+---------+----------+-------",
      "        35 | Imran Joshi   |      119 |      31 |     26.1 |   3.86",
      "         9 | Shruti Singh  |      182 |      47 |     25.8 |   4.75",
      "         8 | Suresh Pillai |       96 |      20 |     20.8 |   4.16",
      "         7 | Vivaan Hegde  |      122 |      24 |     19.7 |   3.67",
      "(22 rows: 22 of 45 drivers)"], "docs/img_q9.png", 6.3, 1.7, 7.6)
card(["// busiest pickup zone per time band",
      "1 Morning (6-9)    HSR Layout    176 trips",
      "2 Midday (10-16)   Koramangala   304 trips",
      "3 Evening (17-20)  MG Road       342 trips",
      "4 Night (21-5)     Koramangala   155 trips",
      "",
      "// GPS km vs billed km (5,276 trips)",
      "mean GPS 11.09 km | billed 13.22 km"], "docs/img_mongo.png", 3.6, 1.6, 7.2)
