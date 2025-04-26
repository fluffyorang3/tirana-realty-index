# generate_dashboard.py
#!/usr/bin/env python3
import os
import pandas as pd
from matplotlib import pyplot as plt
from datetime import date

# Paths
HIST_FILE = 'historical_indices.csv'
GRAPH_DIR = 'static/graphs'
OUTPUT_HTML = 'dashboard.html'

os.makedirs(GRAPH_DIR, exist_ok=True)

# Load history
hist = pd.read_csv(HIST_FILE, parse_dates=['date'])

# Per-neighborhood graphs
for nb in hist['neighborhood'].unique():
    df_nb = hist[hist['neighborhood'] == nb].set_index('date')
    plt.figure()
    df_nb['avg_sale_price_per_m2'].plot(title=f'{nb} €/m² over time')
    plt.ylabel('€/m²')
    plt.tight_layout()
    plt.savefig(f'{GRAPH_DIR}/{nb}.png')
    plt.close()

# Overall average graph
overall = hist.groupby('date')['avg_sale_price_per_m2'].mean().reset_index().set_index('date')
plt.figure()
overall['avg_sale_price_per_m2'].plot(title='Average €/m² across all neighborhoods')
plt.ylabel('€/m²')
plt.tight_layout()
plt.savefig(f'{GRAPH_DIR}/average.png')
plt.close()

# Generate HTML
today = date.today()
today_str = today.isoformat()
today_df = hist[hist['date'] == pd.Timestamp(today)]

html_lines = [
    '<!doctype html>',
    '<html><head><meta charset="utf-8"><title>Daily Price/m²</title></head><body>',
    f'<h1>Prices on {today_str}</h1>'
]

for _, row in today_df.iterrows():
    nb = row['neighborhood']
    price = row['avg_sale_price_per_m2']
    html_lines.append(
        f'<section><h2>{nb}</h2>'
        f'<p><strong>{price:.2f} €/m²</strong></p>'
        f'<img src="{GRAPH_DIR}/{nb}.png" alt="{nb} chart"></section>'
    )

avg_today = overall.loc[today, 'avg_sale_price_per_m2'] if today in overall.index else None
if avg_today is not None:
    html_lines.append(
        '<section><h2>Overall average</h2>'
        f'<p><strong>{avg_today:.2f} €/m²</strong></p>'
        f'<img src="{GRAPH_DIR}/average.png" alt="Overall chart"></section>'
    )

html_lines.append('</body></html>')

with open(OUTPUT_HTML, 'w') as f:
    f.write('\n'.join(html_lines))


print(f"Dashboard updated: {OUTPUT_HTML}")
