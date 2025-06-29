#!/usr/bin/env python3
"""
generate_dashboard.py

– Reads historical_indices.csv
– Reads tirana_neighborhood_coords.csv
– Ensures `date` is datetime (mixed formats)
– Drops duplicate (date, neighborhood)
– Emits per-neighborhood & overall graphs (with 14-day MA)
– Builds docs/index.html with one card per neighborhood + overall card + embedded heatmap
– Generates docs/heatmap.html with interactive time-slider heatmap
"""

import os
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FixedLocator
import folium
from folium.plugins import HeatMapWithTime

# ── Configuration ───────────────────────────────────────────────────────────────
INPUT_CSV    = 'historical_indices.csv'
COORD_CSV    = 'tirana_neighborhood_coords.csv'
HTML_DIR     = 'docs'
OUTPUT_HTML  = os.path.join(HTML_DIR, 'index.html')
HEATMAP_HTML = os.path.join(HTML_DIR, 'heatmap.html')
GRAPH_DIR    = os.path.join(HTML_DIR, 'graphs')
GRAPH_URL    = 'graphs'
GRAPH_SIZE   = (6, 4)
GRAPH_DPI    = 100

# Ensure all output directories exist
os.makedirs(HTML_DIR, exist_ok=True)
os.makedirs(GRAPH_DIR, exist_ok=True)

# ── Load & preprocess data ──────────────────────────────────────────────────────
hist = pd.read_csv(INPUT_CSV)
coords = pd.read_csv(COORD_CSV)

# Parse mixed-format dates safely
hist['date'] = pd.to_datetime(
    hist['date'],
    format='mixed',
    cache=False,
    errors='coerce'
)
hist = hist.dropna(subset=['date'])

# Remove duplicates
hist = hist.drop_duplicates(['date', 'neighborhood'])

# Identify the latest date
latest = hist['date'].max()
today_dt = latest.to_pydatetime()
display_date = latest.date().strftime('%Y-%m-%d')

# Subset for today's cards
today_df = hist[hist['date'] == latest][['neighborhood', 'avg_sale_price_per_m2']]

# ── 1) Per-neighborhood time series graphs ──────────────────────────────────────
for neighborhood, grp in hist.groupby('neighborhood'):
    grp = grp.set_index('date').sort_index()
    series = grp['avg_sale_price_per_m2'].dropna()
    if series.empty:
        continue

    # Plot raw daily series + 14-day MA
    ma = series.rolling(window=14, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    ax.plot(series.index, series.values, marker='o', linestyle='-', label='Daily price')
    ax.plot(ma.index, ma.values, linestyle='--', linewidth=1.5, label='14-day MA')

    ax.set_title(f'{neighborhood} €/m² over time')
    ax.set_ylabel('€/m²')
    ax.set_xlim(series.index.min(), today_dt)
    locator = (mdates.AutoDateLocator() if len(series) > 1
               else FixedLocator([mdates.date2num(series.index.min()), mdates.date2num(today_dt)]))
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()
    ax.legend()
    fig.tight_layout()

    safe = neighborhood.replace(' ', '_')
    fig.savefig(os.path.join(GRAPH_DIR, f'{safe}.png'))
    plt.close(fig)

# ── 2) Overall average time series graph ─────────────────────────────────────────
overall = (hist.groupby('date')['avg_sale_price_per_m2']
              .mean().dropna().sort_index())

if not overall.empty:
    overall_ma = overall.rolling(window=14, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)
    ax.plot(overall.index, overall.values, marker='o', linestyle='-', label='Daily average')
    ax.plot(overall_ma.index, overall_ma.values, linestyle='--', linewidth=1.5, label='14-day MA')

    ax.set_title('Average €/m² across all neighborhoods')
    ax.set_ylabel('€/m²')
    ax.set_xlim(overall.index.min(), today_dt)
    locator = (mdates.AutoDateLocator() if len(overall) > 1
               else FixedLocator([mdates.date2num(overall.index.min()), mdates.date2num(today_dt)]))
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()
    ax.legend()
    fig.tight_layout()

    fig.savefig(os.path.join(GRAPH_DIR, 'average.png'))
    plt.close(fig)

# ── 3) Heatmap with time slider ──────────────────────────────────────────────────
df_map = hist.merge(coords, on='neighborhood', how='left')
dates = sorted(df_map['date'].dt.strftime('%Y-%m-%d').unique())
MIN_VAL, MAX_VAL = df_map['avg_sale_price_per_m2'].min(), df_map['avg_sale_price_per_m2'].max()

heat_data = []
for d in dates:
    frame = []
    day = df_map[df_map['date'].dt.strftime('%Y-%m-%d') == d]
    for _, r in day.iterrows():
        w = max(0, min(1, (r['avg_sale_price_per_m2'] - MIN_VAL) / (MAX_VAL - MIN_VAL)))
        frame.append([r['latitude'], r['longitude'], w])
    heat_data.append(frame)

m = folium.Map(
    location=[coords['latitude'].mean(), coords['longitude'].mean()],
    zoom_start=12,
    tiles='CartoDB positron'
)
HeatMapWithTime(heat_data, index=dates, auto_play=False, max_opacity=0.8).add_to(m)
m.save(HEATMAP_HTML)

# ── 4) Build docs/index.html ────────────────────────────────────────────────────
html = [
    '<!doctype html>',
    '<html lang="en">',
    '<head>',
    '  <meta charset="utf-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1">',
    f'  <title>Tirana Neighborhood Prices — {display_date}</title>',
    '  <link href="https://fonts.googleapis.com/css2?family=Inter&display=swap" rel="stylesheet">',
    '  <style>',
    '    body { font-family: Inter, sans-serif; margin: 0; padding: 1rem; background: #f5f5f5; }',
    '    h1 { text-align: center; margin-bottom: 1rem; }',
    '    .map-container { width: 100%; height: 500px; margin-bottom: 1.5rem; }',
    '    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }',
    '    .card { background: #fff; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }',
    '    .card img { width: 100%; height: auto; }',
    '    .card h2 { margin-top: 0; }',
    '  </style>',
    '</head>',
    '<body>',
    f'  <h1>Prices as of {display_date}</h1>',
    '  <div class="map-container">',
    '    <iframe src="heatmap.html" style="width:100%;height:100%;border:none"></iframe>',
    '  </div>',
    '  <div class="grid">'
]

# Neighborhood cards
for _, row in today_df.iterrows():
    nb, price = row['neighborhood'], row['avg_sale_price_per_m2']
    # 14-day MA for today
    past = hist[(hist['neighborhood'] == nb) & (hist['date'] >= latest - pd.Timedelta(days=13))]
    ma_today = past['avg_sale_price_per_m2'].mean()

    safe = nb.replace(' ', '_')
    html += [
        '    <div class="card">',
        f'      <h2>{nb}</h2>',
        f'      <p><strong>{price:.2f} €/m²</strong></p>',
        f'      <p>14-day MA: <strong>{ma_today:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_URL}/{safe}.png" alt="{nb} chart">',
        '    </div>'
    ]

# Overall card
if not overall.empty and latest in overall.index:
    avg_price = overall.loc[latest]
    ma_overall_today = overall_ma.loc[latest]
    html += [
        '    <div class="card">',
        '      <h2>Overall Average</h2>',
        f'      <p><strong>{avg_price:.2f} €/m²</strong></p>',
        f'      <p>14-day MA: <strong>{ma_overall_today:.2f} €/m²</strong></p>',
        f'      <img src="{GRAPH_URL}/average.png" alt="overall chart">',
        '    </div>'
    ]

html += [
    '  </div>',
    '</body>',
    '</html>'
]

with open(OUTPUT_HTML, 'w') as f:
    f.write("\n".join(html))

print(f"Dashboard updated: {OUTPUT_HTML}")
