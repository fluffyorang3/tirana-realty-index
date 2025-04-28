#!/usr/bin/env python3
"""
generate_dashboard.py

– Reads historical_indices.csv
– Reads tirana_neighborhood_coords.csv
– Ensures `date` is datetime
– Drops duplicate (date, neighborhood)
– Emits per-neighborhood & overall graphs, bounding x-axis to [first logged date, today]
– Builds docs/index.html with one card per neighborhood + overall card + embedded heatmap
– Generates docs/heatmap.html with interactive time-slider heatmap of avg_sale_price_per_m2
"""

import os
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FixedLocator

# New imports for map
import folium
from folium.plugins import HeatMapWithTime

# ─── CONFIG ────────────────────────────────────────────────────────────────
HIST_FILE    = 'historical_indices.csv'
COORDS_FILE  = 'tirana_neighborhood_coords.csv'
HTML_DIR     = 'docs'
OUTPUT_HTML  = os.path.join(HTML_DIR, 'index.html')
HEATMAP_HTML = os.path.join(HTML_DIR, 'heatmap.html')
GRAPH_OUT    = os.path.join(HTML_DIR, 'static', 'graphs')
GRAPH_URL    = './static/graphs'
GRAPH_SIZE   = (5, 3)     # inches
GRAPH_DPI    = 100
# ────────────────────────────────────────────────────────────────────────────

# 1) Load CSVs and force date → datetime
hist = pd.read_csv(HIST_FILE)
hist['date'] = pd.to_datetime(hist['date'], format='%Y-%m-%d', errors='coerce')
hist = hist.dropna(subset=['date'])

# 1b) Load neighborhood coordinates
coords = pd.read_csv(COORDS_FILE)

# 2) Dedupe so each (date, neighborhood) appears once
hist = (
    hist.sort_values('date')
        .drop_duplicates(subset=['date', 'neighborhood'], keep='last')
)

# 3) Prepare constants for dates
TODAY        = pd.Timestamp(date.today())
DISPLAY_DATE = TODAY.strftime('%Y-%m-%d')
today_dt     = TODAY.to_pydatetime()

# 4) Prepare graph output folder
os.makedirs(GRAPH_OUT, exist_ok=True)
# remove stale PNGs
for fn in os.listdir(GRAPH_OUT):
    if fn.lower().endswith('.png'):
        os.remove(os.path.join(GRAPH_OUT, fn))

# 5) Per-neighborhood time series graphs
for neighborhood, grp in hist.groupby('neighborhood'):
    grp = grp.set_index('date').sort_index()
    if not pd.api.types.is_datetime64_any_dtype(grp.index):
        grp.index = pd.to_datetime(grp.index)

    series = grp['avg_sale_price_per_m2'].dropna()
    if series.empty:
        continue

    min_dt = series.index.min().to_pydatetime()
    fig, ax = plt.subplots(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    ax.plot(series.index.to_pydatetime(), series.values, marker='o', linestyle='-')
    ax.set_title(f'{neighborhood} €/m² over time')
    ax.set_ylabel('€/m²')
    ax.set_xlim(min_dt, today_dt)
    locator = mdates.AutoDateLocator() if len(series) > 1 else FixedLocator([mdates.date2num(min_dt), mdates.date2num(today_dt)])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()
    fig.tight_layout()

    safe = neighborhood.replace(' ', '_')
    fig.savefig(os.path.join(GRAPH_OUT, f'{safe}.png'))
    plt.close(fig)

# 6) Overall average time series graph
overall = (
    hist.groupby('date')['avg_sale_price_per_m2']
        .mean()
        .dropna()
        .sort_index()
)
if not overall.empty:
    if not pd.api.types.is_datetime64_any_dtype(overall.index):
        overall.index = pd.to_datetime(overall.index)

    min_dt = overall.index.min().to_pydatetime()
    fig, ax = plt.subplots(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    ax.plot(overall.index.to_pydatetime(), overall.values, marker='o', linestyle='-')
    ax.set_title('Average €/m² across all neighborhoods')
    ax.set_ylabel('€/m²')
    ax.set_xlim(min_dt, today_dt)
    locator = mdates.AutoDateLocator() if len(overall) > 1 else FixedLocator([mdates.date2num(min_dt), mdates.date2num(today_dt)])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(GRAPH_OUT, 'average.png'))
    plt.close(fig)

# 7) Generate interactive heatmap with historical slider
# Merge historical data with coordinates
df_map = pd.merge(
    hist,
    coords[['neighborhood', 'latitude', 'longitude']],
    on='neighborhood',
    how='inner'
)
df_map = df_map.sort_values('date')

# Build heatmap frames per date
dates = df_map['date'].dt.strftime('%Y-%m-%d').unique().tolist()
heat_data = []
for d in dates:
    d_df = df_map[df_map['date'].dt.strftime('%Y-%m-%d') == d]
    heat_data.append(
        d_df[['latitude', 'longitude', 'avg_sale_price_per_m2']].values.tolist()
    )

# Create folium map centered on Tirana average coordinate
map_center = [coords['latitude'].mean(), coords['longitude'].mean()]
m = folium.Map(location=map_center, zoom_start=12)

# Updated heatmap parameters: larger radius and value-based gradient
min_val, max_val = 800, 3000  # €/m² range for normalization
gradient = {
    0.0: 'blue',        # ~800
    0.3: 'lime',        # ~1500
    0.5: 'yellow',      # ~2000
    0.8: 'orange',      # ~2500
    1.0: 'red'          # ~3000
}

HeatMapWithTime(
    heat_data,
    index=dates,
    gradient=gradient,
    radius=35,
    min_opacity=0.3,
    max_opacity=0.7,
    use_local_extrema=False,
    auto_play=False,
    overlay=True,
    control=True,
    show=True
).add_to(m)

# Save the interactive map
os.makedirs(HTML_DIR, exist_ok=True)
m.save(HEATMAP_HTML)

# 8) Build HTML dashboard with embedded heatmap
latest_date = TODAY if TODAY in hist['date'].values else hist['date'].max()
today_df = (
    hist[hist['date'] == latest_date].drop_duplicates(subset=['neighborhood'])
)

html_parts = [
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
    '    .map-container { width:100%; height:500px; margin-bottom:1.5rem; }',
    '    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:1rem; }',
    '    .card { background:#fff; padding:1rem; border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.1); }',
    '    .card img { width:100%; height:auto; }',
    '    .card h2{ margin-top:0; }',
    '  </style>',
    '</head>',
    '<body>',
    f'  <h1>Prices on {DISPLAY_DATE}</h1>',
    '  <div class="map-container">',
    '    <iframe src="heatmap.html" style="width:100%; height:100%; border:none;"></iframe>',
    '  </div>',
    '  <div class="grid">'
]

# Add cards
for _, row in today_df.iterrows():
    nb    = row['neighborhood']
    price = row['avg_sale_price_per_m2']
    safe  = nb.replace(' ', '_')
    html_parts += [
        '    <div class="card">',
        f'      <h2>{nb}</h2>',
        f'      <p><strong>{price:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_URL}/{safe}.png" alt="{nb} price chart">',
        '    </div>'
    ]

# Overall average
if latest_date in overall.index:
    avg = overall.loc[latest_date]
    html_parts += [
        '    <div class="card">',
        '      <h2>Overall Average</h2>',
        f'      <p><strong>{avg:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_URL}/average.png" alt="Overall price chart">',
        '    </div>'
    ]

html_parts += [
    '  </div>',
    '</body>',
    '</html>'
]

with open(OUTPUT_HTML, 'w') as f:
    f.write('\n'.join(html_parts))

print(f"Dashboard updated: {OUTPUT_HTML}")