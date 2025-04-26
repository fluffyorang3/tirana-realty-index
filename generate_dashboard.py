#!/usr/bin/env python3
"""
generate_dashboard.py

Reads historical_indices.csv, generates per-neighborhood and overall average graphs
(with x-axis from earliest logged date to today), and writes a modern HTML
dashboard with embedded charts.
"""

import os
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FixedLocator

# ─── CONFIG ────────────────────────────────────────────────────────────────
HIST_FILE    = 'historical_indices.csv'
OUTPUT_HTML  = 'docs/index.html'
GRAPH_DIR    = 'docs/static/graphs'
GRAPH_SIZE   = (5, 3)    # inches
GRAPH_DPI    = 100       # dots per inch
# ────────────────────────────────────────────────────────────────────────────

# ─── load history and parse dates ─────────────────────────────────────────
hist = pd.read_csv(HIST_FILE)
hist['date'] = pd.to_datetime(hist['date'], format='%Y-%m-%d', errors='coerce')
hist = hist.dropna(subset=['date'])

# fixed “today” timestamp for axis limits + display
TODAY        = pd.Timestamp(date.today())
DISPLAY_DATE = TODAY.date().isoformat()

# ─── clear out old graphs ─────────────────────────────────────────────────
if os.path.isdir(GRAPH_DIR):
    for fn in os.listdir(GRAPH_DIR):
        if fn.lower().endswith('.png'):
            os.remove(os.path.join(GRAPH_DIR, fn))
else:
    os.makedirs(GRAPH_DIR)

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

    min_date = series.index.min()

    fig, ax = plt.subplots(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    ax.plot(series.index, series.values, marker='o', linestyle='-')
    ax.set_title(f'{nb} €/m² over time')
    ax.set_ylabel('€/m²')

    # force axis from first logged date to today
    ax.set_xlim(min_date, TODAY)
    # locator: auto when >1 point, fixed at [min_date, TODAY] when only 1
    if len(series) > 1:
        locator = mdates.AutoDateLocator()
    else:
        locator = FixedLocator([mdates.date2num(min_date), mdates.date2num(TODAY)])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    fig.tight_layout()
    safe_nb = nb.replace(' ', '_')
    fig.savefig(os.path.join(GRAPH_DIR, f'{safe_nb}.png'))
    plt.close(fig)

# ─── overall average graph ────────────────────────────────────────────────
overall = (
    hist.groupby('date')['avg_sale_price_per_m2']
    .mean()
    .dropna()
    .sort_index()
)
if not overall.empty:
    min_date = overall.index.min()

    fig, ax = plt.subplots(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    ax.plot(overall.index, overall.values, marker='o', linestyle='-')
    ax.set_title('Average €/m² across all neighborhoods')
    ax.set_ylabel('€/m²')

    ax.set_xlim(min_date, TODAY)
    if len(overall) > 1:
        locator = mdates.AutoDateLocator()
    else:
        locator = FixedLocator([mdates.date2num(min_date), mdates.date2num(TODAY)])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    fig.tight_layout()
    fig.savefig(os.path.join(GRAPH_DIR, 'average.png'))
    plt.close(fig)

# ─── pick the latest date we actually have ────────────────────────────────
latest_date = TODAY if TODAY in hist['date'].values else hist['date'].max()

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
