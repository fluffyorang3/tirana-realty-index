#!/usr/bin/env python3
"""
generate_dashboard.py

– Reads historical_indices.csv
– Drops duplicate (date, neighborhood) rows so each appears once
– Emits per-neighborhood and overall graphs (x-axis from first date → today)
– Builds docs/index.html with one card per neighborhood + one overall card.
"""

import os
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FixedLocator

# ─── CONFIG ────────────────────────────────────────────────────────────────
HIST_FILE   = 'historical_indices.csv'
HTML_DIR    = 'docs'
OUTPUT_HTML = os.path.join(HTML_DIR, 'index.html')
GRAPH_OUT   = os.path.join(HTML_DIR, 'static', 'graphs')
GRAPH_URL   = './static/graphs'      # what <img src=""> will use, relative to index.html
GRAPH_SIZE  = (5, 3)                 # inches
GRAPH_DPI   = 100
# ────────────────────────────────────────────────────────────────────────────

# 1) Load & dedupe
hist = pd.read_csv(HIST_FILE, parse_dates=['date'])
hist = hist.sort_values('date') \
           .drop_duplicates(subset=['date','neighborhood'], keep='last')

# 2) Prepare dates
TODAY        = pd.Timestamp(date.today())
DISPLAY_DATE = TODAY.date().isoformat()

# 3) Ensure output folder & clear old PNGs
os.makedirs(GRAPH_OUT, exist_ok=True)
for fn in os.listdir(GRAPH_OUT):
    if fn.lower().endswith('.png'):
        os.remove(os.path.join(GRAPH_OUT, fn))

# 4) Per-neighborhood graphs
for neighborhood, grp in hist.groupby('neighborhood'):
    grp = grp.set_index('date').sort_index()
    series = grp['avg_sale_price_per_m2'].dropna()
    if series.empty:
        continue

    min_date = series.index.min()
    fig, ax = plt.subplots(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    ax.plot(series.index, series.values, marker='o', linestyle='-')
    ax.set_title(f'{neighborhood} €/m² over time')
    ax.set_ylabel('€/m²')

    # lock x-axis from first data → today
    ax.set_xlim(min_date, TODAY)
    if len(series) > 1:
        locator = mdates.AutoDateLocator()
    else:
        locator = FixedLocator([mdates.date2num(min_date), mdates.date2num(TODAY)])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    fig.tight_layout()
    safe = neighborhood.replace(' ', '_')
    fig.savefig(os.path.join(GRAPH_OUT, f'{safe}.png'))
    plt.close(fig)

# 5) Overall average graph
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
    fig.savefig(os.path.join(GRAPH_OUT, 'average.png'))
    plt.close(fig)

# 6) Build HTML
latest = TODAY if TODAY in hist['date'].values else hist['date'].max()
today_df = (
    hist[hist['date'] == latest]
    .drop_duplicates(subset=['neighborhood'])
)

html = [
    '<!doctype html>',
    '<html lang="en">',
    '<head>',
    '  <meta charset="utf-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1">',
    '  <title>Daily Price/m² Dashboard</title>',
    '  <link href="https://fonts.googleapis.com/css2?family=Inter&display=swap" rel="stylesheet">',
    '  <style>',
    '    body { font-family: "Inter", sans-serif; margin:0; padding:1rem; background:#f5f5f5; }',
    '    h1   { text-align:center; margin-bottom:1rem; }',
    '    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:1rem; }',
    '    .card { background:#fff; padding:1rem; border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.1); }',
    '    .card img { width:100%; height:auto; }',
    '    .card h2{ margin-top:0; }',
    '  </style>',
    '</head>',
    '<body>',
    f'  <h1>Prices on {DISPLAY_DATE}</h1>',
    '  <div class="grid">'
]

# neighborhood cards
for _, row in today_df.iterrows():
    nb      = row['neighborhood']
    price   = row['avg_sale_price_per_m2']
    safe    = nb.replace(' ', '_')
    html += [
        '    <div class="card">',
        f'      <h2>{nb}</h2>',
        f'      <p><strong>{price:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_URL}/{safe}.png" alt="{nb} price chart">',
        '    </div>'
    ]

# overall card
if latest in overall.index:
    avg = overall.loc[latest]
    html += [
        '    <div class="card">',
        '      <h2>Overall Average</h2>',
        f'      <p><strong>{avg:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_URL}/average.png" alt="Overall price chart">',
        '    </div>'
    ]

# close tags
html += [
    '  </div>',
    '</body>',
    '</html>'
]

os.makedirs(HTML_DIR, exist_ok=True)
with open(OUTPUT_HTML, 'w') as f:
    f.write('\n'.join(html))

print(f"Dashboard updated: {OUTPUT_HTML}")
