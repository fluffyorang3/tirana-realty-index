#!/usr/bin/env python3
import os, json
import pandas as pd

LOG = 'neighborhood_indices_log.csv'
OUT_DIR = 'data'
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(LOG, parse_dates=['date']).dropna(subset=['avg_sale_price_per_m2'])
# Per-neighborhood series
neigh_ts = {
    nb: [
      {'date': d.strftime('%Y-%m-%d'), 'value': v}
      for d, v in zip(grp.sort_values('date').date, grp.sort_values('date').avg_sale_price_per_m2)
    ]
    for nb, grp in df.groupby('neighborhood')
}
# Overall average per date
overall = (df.groupby('date')['avg_sale_price_per_m2']
             .mean().reset_index().sort_values('date'))
overall_ts = [
  {'date': d.strftime('%Y-%m-%d'), 'value': v}
  for d, v in zip(overall.date, overall.avg_sale_price_per_m2)
]

with open(f'{OUT_DIR}/series_by_neighborhood.json','w') as f:
    json.dump(neigh_ts, f, indent=2)
with open(f'{OUT_DIR}/series_overall.json','w') as f:
    json.dump(overall_ts, f, indent=2)

print("JSON data written to", OUT_DIR)
