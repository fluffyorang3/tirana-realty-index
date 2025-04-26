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

# Ensure graph directory exists
os.makedirs(GRAPH_DIR, exist_ok=True)

# Load history\hist = pd.read_csv(HIST_FILE, parse_dates=['date'])

# Graph settings
FIGSIZE = (5, 3)

# Per-neighborhood graphs

for nb in hist['neighborhood'].unique():
    df_nb = hist[hist['neighborhood'] == nb].set_index('date')
    plt.figure(figsize=FIGSIZE)
    dates = df_nb.index
    df_nb['avg_sale_price_per_m2'].plot(title=f'{nb} €/m² over time')
    plt.ylabel('€/m²')
    # x-axis limited to data range
    if dates.min() == dates.max():
        start = dates.min() - pd.Timedelta(hours=12)
        end = dates.max() + pd.Timedelta(hours=12)
        plt.xlim(start, end)
    else:
        plt.xlim(dates.min(), dates.max())
    plt.tight_layout()
    plt.savefig(f'{GRAPH_DIR}/{nb}.png', dpi=100)
    plt.close()

# Overall average graph
overall = hist.groupby('date')['avg_sale_price_per_m2'].mean().reset_index().set_index('date')
plt.figure(figsize=FIGSIZE)
dates = overall.index
overall['avg_sale_price_per_m2'].plot(title='Average €/m² across all neighborhoods')
plt.ylabel('€/m²')
if dates.min() == dates.max():
    start = dates.min() - pd.Timedelta(hours=12)
    end = dates.max() + pd.Timedelta(hours=12)
    plt.xlim(start, end)
else:
    plt.xlim(dates.min(), dates.max())
plt.tight_layout()
plt.savefig(f'{GRAPH_DIR}/average.png', dpi=100)
plt.close()

# Generate HTML
today = date.today()
today_str = today.isoformat()
today_df = hist[hist['date'] == pd.Timestamp(today)]

html_lines = [
    '<!doctype html>',
    '<html lang="en">',
    '<head>',
    '  <meta charset="utf-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1">',
    '  <title>Daily Price/m² Dashboard</title>',
    '  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">',
    '  <style>',
    '    body { font-family: \'Inter\', sans-serif; margin: 0; padding: 1rem; background: #f9f9f9; color: #333; }',
    '    h1 { text-align: center; margin-bottom: 1rem; }',
    '    .container { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }',
    '    section { background: #fff; padding: 1rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }',
    '    section img { width: 100%; height: auto; border-radius: 4px; }',
    '    section h2 { margin-top: 0; }',
    '  </style>',
    '</head>',
    '<body>',
    f'  <h1>Prices on {today_str}</h1>',
    '  <div class="container">'
]

for _, row in today_df.iterrows():
    nb = row['neighborhood']
    price = row['avg_sale_price_per_m2']
    html_lines.append(
        '    <section>' +
        f'<h2>{nb}</h2>' +
        f'<p><strong>{price:.2f} €/m²</strong></p>' +
        f'<img src="{GRAPH_DIR}/{nb}.png" alt="{nb} chart">' +
        '</section>'
    )

avg_today = overall.loc[today, 'avg_sale_price_per_m2'] if today in overall.index else None
if avg_today is not None:
    html_lines.append(
        '    <section>' +
        '<h2>Overall average</h2>' +
        f'<p><strong>{avg_today:.2f} €/m²</strong></p>' +
        f'<img src="{GRAPH_DIR}/average.png" alt="Overall chart">' +
        '</section>'
    )

html_lines.extend([
    '  </div>',
    '</body>',
    '</html>'
])

with open(OUTPUT_HTML, 'w') as f:
    f.write('\n'.join(html_lines))

print(f"Dashboard updated: {OUTPUT_HTML}")
