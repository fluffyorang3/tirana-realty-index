# Tirana Real Estate Price Dashboard 🏙️

This project automatically scrapes real estate listings from MerrJep.al, cleans the data, calculates price indices per neighborhood, and generates a dynamic HTML dashboard and interactive heatmap visualizing the evolution of price per square meter in Tirana.

## 🔧 Features

- **Automated web scraper** with JS rendering (via Selenium)
- **Data cleaning & validation** (outlier filtering, type conversion)
- **Daily price index computation** (sale & rent, per neighborhood)
- **Time-series graph generation** for each neighborhood + overall average
- **Interactive heatmap** of normalized €/m² values over time
- **Responsive HTML dashboard** with all data and charts embedded

## 📁 Project Structure

```
.
├── generate_dashboard.py         # Generates graphs, dashboard, and heatmap
├── scraper.py                    # Scrapes listings and appends daily indices
├── requirements.txt              # Python dependencies
├── historical_indices.csv        # Historical €/m² data
├── listings_data.csv             # Raw scraped listing data
├── neighborhoods.csv             # List of Tirana neighborhoods
├── tirana_neighborhood_coords.csv # Lat/Lng coordinates for each neighborhood
├── docs/
│   ├── index.html                # The main dashboard page
│   ├── heatmap.html             # The interactive heatmap
│   └── static/graphs/*.png      # All time-series charts
```

## 🚀 Usage

### 1. Install Requirements

```bash
pip install -r requirements.txt
```

### 2. Scrape Listings

```bash
python scraper.py
```

This will:
- Launch a headless Chromium browser
- Scrape listing details for each neighborhood
- Filter outliers and noise
- Update `listings_data.csv` and `historical_indices.csv`

### 3. Generate Dashboard

```bash
python generate_dashboard.py
```

This will:
- Create `/docs/index.html` with per-neighborhood cards
- Generate `/docs/heatmap.html` with a time slider
- Produce all neighborhood graphs in `/docs/static/graphs/`

> You can now host the contents of `docs/` as a static site (e.g., via GitHub Pages or a CDN).

## 🧪 Example Output

- ✅ Dashboard: `docs/index.html`
- 🌡️ Heatmap: `docs/heatmap.html`
- 📈 Example graph: `docs/static/graphs/Blloku.png`

## 🛠️ Technologies Used

- Python 3
- Selenium + BeautifulSoup
- Pandas, Matplotlib
- Folium + Leaflet.TimeDimension
- HTML/CSS (auto-generated)

## ⚠️ Notes

- Ensure `chromium-browser` is installed and available at `/usr/bin/chromium-browser`
- Adjust `MIN_PPSM` and `MAX_PPSM` in `scraper.py` to filter €/m² values appropriately
- The project assumes you're working with apartments in Tirana; the logic may need adjustments for other contexts.
## 🌐 Live Dashboard

Access the hosted dashboard here:  
🔗 **[tirana-realty-index on GitHub Pages](https://fluffyorang3.github.io/tirana-realty-index/)**
