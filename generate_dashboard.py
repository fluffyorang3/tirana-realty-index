#!/usr/bin/env python3
"""
generate_dashboard.py

Reads historical_indices.csv, generates per-neighborhood and overall average graphs
(with x-axis from earliest date to today), and writes a modern HTML
dashboard with embedded charts.
"""

import os
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt

# ─── CONFIG ────────────────────────────────────────────────────────────────
HIST_FILE    = 'historical_indices.csv'
OUTPUT_HTML  = 'dashboard.html'
GRAPH_DIR    = 'static/graphs'
GRAPH_SIZE   = (5, 3)    # inches
GRAPH_DPI    = 100       # dpi
# ────────────────────────────────────────────────────────────────────────────

# ─── load history and parse dates ─────────────────────────────────────────
hist = pd.read_csv(HIST_FILE)
hist['date'] = pd.to_datetime(hist['date'], format='%Y-%m-%d', errors='coerce')
hist = hist.dropna(subset=['date'])

# fixed “today” timestamp for axis limits + display
TODAY = pd.Timestamp(date.today())
DISPLAY_DATE = TODAY.date().isoformat()

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
    # x-axis: from first logged date to today
    plt.xlim(series.index.min(), TODAY)

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
    # x-axis: from first overall date to today
    plt.xlim(overall.index.min(), TODAY)
    plt.savefig(os.path.join(GRAPH_DIR, 'average.png'))
    plt.close()

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
    f'  <h1>Prices on {DISPLAY_DATE}</h1>',
    '  <div class="grid">'
]

# one card per neighborhood for the latest date we actually have (which is TODAY if you scraped today)
latest_date = TODAY if TODAY in hist['date'].values else hist['date'].max()
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

# overall average card
if latest_date in overall.index:
    latest_avg = overall.loc[latest_date]
    html_lines += [
        '    <div class="card">',
        '      <h2>Overall Average</h2>',
        f'      <p><strong>{latest_avg:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_DIR}/average.png" alt="Overall price chart">',
        '    </div>'
    ]

html_lines += [
    '  </div>',
    '</body>',
    '</html>'
]

with open(OUTPUT_HTML, 'w') as f:
    f.write('\n'.join(html_lines))

print(f"Dashboard updated: {OUTPUT_HTML}")
