#!/usr/bin/env python3
"""
generate_dashboard.py

– Reads historical_indices.csv
– Reads tirana_neighborhood_coords.csv
– Ensures `date` is datetime
– Drops duplicate (date, neighborhood)
– Emits per-neighborhood & overall graphs (now with 14-day MA)
– Builds docs/index.html with one card per neighborhood + overall card + embedded heatmap
– Generates docs/heatmap.html with interactive time-slider heatmap of avg_sale_price_per_m2 normalized to 0–1
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
INPUT_CSV       = 'historical_indices.csv'
COORD_CSV       = 'tirana_neighborhood_coords.csv'
OUTPUT_HTML     = 'docs/index.html'
HEATMAP_HTML    = 'docs/heatmap.html'
GRAPH_OUT       = 'docs/graphs'
GRAPH_URL       = 'graphs'
GRAPH_SIZE      = (6, 4)
GRAPH_DPI       = 100

os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
os.makedirs(GRAPH_OUT, exist_ok=True)

# ── Load & preprocess data ──────────────────────────────────────────────────────
hist = pd.read_csv(INPUT_CSV)
coords = pd.read_csv(COORD_CSV)

# ensure date dtype and drop duplicates
hist['date'] = pd.to_datetime(hist['date'])
hist = hist.drop_duplicates(['date', 'neighborhood'])

# find latest date
latest   = hist['date'].max()
today_dt = latest.to_pydatetime()
today    = latest.date()

# subset for “today” cards
today_df = (
    hist[hist['date'] == latest]
       .loc[:, ['neighborhood', 'avg_sale_price_per_m2']]
)

# ── 5) Per-neighborhood time series graphs ──────────────────────────────────────
for neighborhood, grp in hist.groupby('neighborhood'):
    grp = grp.set_index('date').sort_index()
    if not pd.api.types.is_datetime64_any_dtype(grp.index):
        grp.index = pd.to_datetime(grp.index)

    series = grp['avg_sale_price_per_m2'].dropna()
    if series.empty:
        continue

    min_dt = series.index.min().to_pydatetime()
    fig, ax = plt.subplots(figsize=GRAPH_SIZE, dpi=GRAPH_DPI)

    # raw daily series
    ax.plot(
        series.index.to_pydatetime(),
        series.values,
        marker='o',
        linestyle='-',
        label='Daily price'               # ← MA: label added
    )

    # ← MA: compute & plot 14-day moving average
    ma = series.rolling(window=14, min_periods=1).mean()
    ax.plot(
        ma.index.to_pydatetime(),
        ma.values,
        linestyle='--',
        linewidth=1.5,
        label='14-day MA'                # ← MA: label added
    )

    ax.set_title(f'{neighborhood} €/m² over time')
    ax.set_ylabel('€/m²')
    ax.set_xlim(min_dt, today_dt)
    locator = (
        mdates.AutoDateLocator()
        if len(series) > 1
        else FixedLocator([mdates.date2num(min_dt), mdates.date2num(today_dt)])
    )
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()
    fig.tight_layout()
    ax.legend()                            # ← MA: legend

    safe = neighborhood.replace(' ', '_')
    fig.savefig(os.path.join(GRAPH_OUT, f'{safe}.png'))
    plt.close(fig)

# ── 6) Overall average time series graph ────────────────────────────────────────
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

    # raw daily average
    ax.plot(
        overall.index.to_pydatetime(),
        overall.values,
        marker='o',
        linestyle='-',
        label='Daily average'            # ← MA: label added
    )

    # ← MA: compute & plot overall 14-day MA
    overall_ma = overall.rolling(window=14, min_periods=1).mean()
    ax.plot(
        overall_ma.index.to_pydatetime(),
        overall_ma.values,
        linestyle='--',
        linewidth=1.5,
        label='14-day MA'               # ← MA: label added
    )

    ax.set_title('Average €/m² across all neighborhoods')
    ax.set_ylabel('€/m²')
    ax.set_xlim(min_dt, today_dt)
    locator = (
        mdates.AutoDateLocator()
        if len(overall) > 1
        else FixedLocator([mdates.date2num(min_dt), mdates.date2num(today_dt)])
    )
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()
    fig.tight_layout()
    ax.legend()                            # ← MA: legend

    fig.savefig(os.path.join(GRAPH_OUT, 'average.png'))
    plt.close(fig)

# ── 7) Heatmap with time slider ──────────────────────────────────────────────────
df_map = hist.merge(coords, on='neighborhood', how='left')
dates  = sorted(df_map['date'].dt.strftime('%Y-%m-%d').unique())
MIN_VAL = df_map['avg_sale_price_per_m2'].min()
MAX_VAL = df_map['avg_sale_price_per_m2'].max()

heat_data = []
for d in dates:
    frame = []
    day = df_map[df_map['date'].dt.strftime('%Y-%m-%d') == d]
    for _, r in day.iterrows():
        lat, lon, val = (
            r['latitude'],
            r['longitude'],
            r['avg_sale_price_per_m2']
        )
        w = max(0, min(1, (val - MIN_VAL) / (MAX_VAL - MIN_VAL)))
        frame.append([lat, lon, w])
    heat_data.append(frame)

m = folium.Map(
    location=[coords['latitude'].mean(), coords['longitude'].mean()],
    zoom_start=12,
    tiles='CartoDB positron'
)
HeatMapWithTime(
    heat_data,
    index=dates,
    auto_play=False,
    max_opacity=0.8
).add_to(m)
m.save(HEATMAP_HTML)

# ── 8) Build docs/index.html ────────────────────────────────────────────────────
html = [
    '<!doctype html>',
    '<html>',
    '<head>',
    '  <meta charset="utf-8">',
    '  <title>Tirana Neighborhood Prices</title>',
    '  <link rel="stylesheet" href="styles.css">',
    '</head>',
    '<body>',
    f'  <h1>Prices as of {today}</h1>',
    '  <div class="map-container">',
    '    <iframe src="heatmap.html" style="width:100%;height:100%;border:none"></iframe>',
    '  </div>',
    '  <div class="grid">'
]

# per-neighborhood cards
for _, r in today_df.iterrows():
    nb, p = r['neighborhood'], r['avg_sale_price_per_m2']
    # ← MA: compute today’s 14-day MA
    past = hist[
        (hist['neighborhood'] == nb) &
        (hist['date'] >= latest - pd.Timedelta(days=13))
    ]
    ma_today = past['avg_sale_price_per_m2'].mean()

    safe = nb.replace(' ', '_')
    html += [
        '<div class="card">',
        f'  <h2>{nb}</h2>',
        f'  <p><strong>{p:.2f} €/m²</strong></p>',
        f'  <p>14-day MA: <strong>{ma_today:.2f} €/m²</strong></p>',  # ← MA line
        f'  <img src="{GRAPH_URL}/{safe}.png" alt="{nb} chart">',
        '</div>'
    ]

# overall card
if not overall.empty and latest in overall.index:
    avg = overall.loc[latest]
    # ← MA: get overall MA for today
    overall_ma_today = (
        overall_ma.loc[latest]
        if 'overall_ma' in locals()
        else overall.rolling(window=14, min_periods=1).mean().loc[latest]
    )
    html += [
        '<div class="card">',
        '  <h2>Overall Average</h2>',
        f'  <p><strong>{avg:.2f} €/m²</strong></p>',
        f'  <p>14-day MA: <strong>{overall_ma_today:.2f} €/m²</strong></p>',  # ← MA line
        f'  <img src="{GRAPH_URL}/average.png" alt="overall chart">',
        '</div>'
    ]

html += ['</div>', '</body>', '</html>']

with open(OUTPUT_HTML, 'w') as f:
    f.write("\n".join(html))

print(f"Dashboard updated: {OUTPUT_HTML}")
