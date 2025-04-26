#!/usr/bin/env python3
"""
generate_dashboard.py

Reads historical_indices.csv, generates per-neighborhood and overall average graphs
(with x-axis limited to each series’ own date range), and writes a modern HTML
dashboard with embedded charts.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date

# ─── CONFIG ────────────────────────────────────────────────────────────────
HIST_FILE    = 'historical_indices.csv'
OUTPUT_HTML  = 'dashboard.html'
GRAPH_DIR    = 'static/graphs'
GRAPH_SIZE   = (5, 3)    # inches
GRAPH_DPI    = 100       # dots per inch
# ────────────────────────────────────────────────────────────────────────────

# ─── load history and parse dates ─────────────────────────────────────────
hist = pd.read_csv(HIST_FILE)
# force-parse the date column (format YYYY-MM-DD)
hist['date'] = pd.to_datetime(hist['date'], format='%Y-%m-%d', errors='coerce')
# drop any bad parses
hist = hist.dropna(subset=['date'])

# ─── ensure graph output directory exists ──────────────────────────────────
os.makedirs(GRAPH_DIR, exist_ok=True)

# ─── per-neighborhood graphs ───────────────────────────────────────────────
for nb in hist['neighborhood'].unique():
    df_nb = (
        hist[hist['neighborhood'] == nb]
        .set_index('date')
        .sort_index()
    )
    series = df_nb['avg_sale_price_per_m2'].dropna()
    if series.empty:
        continue

    plt.figure(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    series.plot(marker='o', linestyle='-')
    plt.title(f'{nb} €/m² over time')
    plt.ylabel('€/m²')
    plt.tight_layout()
    plt.xlim(series.index.min(), series.index.max())

    safe_nb = nb.replace(' ', '_')
    plt.savefig(os.path.join(GRAPH_DIR, f'{safe_nb}.png'))
    plt.close()

# ─── overall average graph ────────────────────────────────────────────────
overall = (
    hist.groupby('date')['avg_sale_price_per_m2']
    .mean()
    .dropna()
    .sort_index()
)

if not overall.empty:
    plt.figure(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    overall.plot(marker='o', linestyle='-')
    plt.title('Average €/m² across all neighborhoods')
    plt.ylabel('€/m²')
    plt.tight_layout()
    plt.xlim(overall.index.min(), overall.index.max())
    plt.savefig(os.path.join(GRAPH_DIR, 'average.png'))
    plt.close()

# ─── pick the most recent date we actually have ───────────────────────────
latest_date = hist['date'].max()
display_date = latest_date.date().isoformat()

# ─── build HTML ───────────────────────────────────────────────────────────
html_lines = [
    '<!doctype html>',
    '<html lang="en">',
    '<head>',
    '  <meta charset="utf-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1">',
    '  <title>Daily Price/m² Dashboard</title>',
    '  <link href="https://fonts.googleapis.com/css2?family=Inter&display=swap" rel="stylesheet">',
    '  <style>',
    '    body { font-family: "Inter", sans-serif; margin: 0; padding:1rem; background: #f5f5f5; }',
    '    h1   { text-align: center; margin-bottom:1rem; }',
    '    .grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(300px,1fr)); gap:1rem; }',
    '    .card { background: #fff; padding:1rem; border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.1); }',
    '    .card img { width:100%; height:auto; }',
    '    .card h2{ margin-top:0; }',
    '  </style>',
    '</head>',
    '<body>',
    f'  <h1>Prices on {display_date}</h1>',
    '  <div class="grid">'
]

# one card per neighborhood
for _, row in hist[hist['date'] == latest_date].iterrows():
    nb      = row['neighborhood']
    price   = row['avg_sale_price_per_m2']
    safe_nb = nb.replace(' ', '_')
    html_lines += [
        '    <div class="card">',
        f'      <h2>{nb}</h2>',
        f'      <p><strong>{price:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_DIR}/{safe_nb}.png" alt="{nb} price chart">',
        '    </div>'
    ]

# overall average card (if available for that date)
if (not overall.empty) and (latest_date in overall.index):
    latest_avg = overall.loc[latest_date]
    html_lines += [
        '    <div class="card">',
        '      <h2>Overall Average</h2>',
        f'      <p><strong>{latest_avg:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_DIR}/average.png" alt="Overall price chart">',
        '    </div>'
    ]

# close grid & body
html_lines += [
    '  </div>',
    '</body>',
    '</html>'
]

# ─── write out the dashboard ────────────────────────────────────────────────
with open(OUTPUT_HTML, 'w') as f:
    f.write('\n'.join(html_lines))

print(f"Dashboard updated: {OUTPUT_HTML}")
