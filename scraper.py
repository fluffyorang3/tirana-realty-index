# scraper.py
#!/usr/bin/env python3
"""
Concurrent scraper for MerrJep real estate listings by neighborhood with live progress and JS rendering,
with fallback link detection and data cleaning.

Appends daily neighborhood indices to historical_indices.csv.
"""

import os
import csv
import time
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, quote, urlparse, urlunparse

import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm

# Constants
BASE_URL = 'https://www.merrjep.al'
CSV_INPUT = 'neighborhoods.csv'
CSV_LISTINGS_OUTPUT = 'listings_data.csv'
HIST_FILE = 'historical_indices.csv'
URL_TEMPLATE = BASE_URL + '/njoftime/imobiliare-vendbanime/apartamente/tirane/q-{}'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/115.0.0.0 Safari/537.36'
    )
}

# Cleaning thresholds
MIN_AREA = 20     # m²
MAX_AREA = 500    # m²
MIN_PPSM = 200    # €/m²
MAX_PPSM = 5000   # €/m²

# Globals for session and driver
session = None
driver = None

# Selenium options
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')


def sanitize(name):
    return quote(name.strip().lower().replace(' ', '-'))


def extract_price(el):
    raw = el.get('value') or el.get_text()
    clean = raw.replace('.', '').replace(',', '').strip()
    return int(clean) if clean.isdigit() else None


def parse_listing_detail(soup):
    price = None
    el = soup.select_one('bdi.new-price span.format-money-int')
    if el:
        price = extract_price(el)

    category = 'sale'
    for tag in soup.select('a.tag-item'):
        txt = tag.get_text(strip=True).lower()
        if 'qera' in txt:
            category = 'rent'
            break
        if 'shit' in txt:
            category = 'sale'
            break

    rooms = None
    area = None
    for tag in soup.select('a.tag-item, .tag-item'):
        lbl = tag.select_one('span')
        val = tag.select_one('bdi')
        if not lbl or not val:
            continue
        label = lbl.get_text(strip=True).rstrip(':')
        v = val.get_text(strip=True)
        if 'Numri i dhomave' in label:
            try:
                rooms = int(v.split('+')[0])
            except:
                pass
        elif 'Sipërfaqe' in label:
            try:
                area = float(v.split()[0].replace(',', '.'))
            except:
                pass

    return price, rooms, area, category


def fetch_detail(args):
    href, neighborhood = args
    raw_url = urljoin(BASE_URL, href)
    parsed = urlparse(raw_url)
    fixed_path = quote(parsed.path, safe='/')
    detail_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        fixed_path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))

    try:
        r = session.get(detail_url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        price, rooms, area, category = parse_listing_detail(soup)
        if price is not None and area:
            return {
                'neighborhood': neighborhood,
                'price': price,
                'rooms': rooms,
                'area': area,
                'category': category,
                'price_per_m2': price / area
            }
    except Exception as e:
        tqdm.write(f"Detail error {detail_url}: {e}")
    return None


def scrape_neighborhood(nb, total_bar):
    slug = sanitize(nb)
    url = URL_TEMPLATE.format(slug)
    tqdm.write(f"\n[{nb}] loading → {url}")

    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    anchors = soup.select('a.Link_vis')
    if not anchors:
        conts = soup.select('li.announcement-item')
        anchors = [c.find('a', href=True) for c in conts]
        anchors = [a for a in anchors if a]
        tqdm.write(f"[{nb}] fallback anchors → {len(anchors)}")
    else:
        tqdm.write(f"[{nb}] anchors found → {len(anchors)}")

    tasks = [(a['href'], nb) for a in anchors]
    records = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_detail, t) for t in tasks]
        for fut in tqdm(as_completed(futures), total=len(futures),
                        desc=f'Parsing {nb}', leave=False):
            rec = fut.result()
            if rec:
                records.append(rec)
                total_bar.update(1)
                tqdm.write(f"Scraped → {rec}")

    return records


def main():
    global session, driver

    # Read neighborhoods
    with open(CSV_INPUT) as f:
        neighborhoods = [row[0] for row in csv.reader(f) if row]

    all_records = []
    total = tqdm(desc='Total listings', unit='listing')

    # Process in chunks of 2
    for i in range(0, len(neighborhoods), 2):
        chunk = neighborhoods[i:i + 2]

        session = requests.Session()
        session.headers.update(HEADERS)
        driver = webdriver.Chrome(options=chrome_options)

        for nb in tqdm(chunk, desc=f'Neighborhoods {i+1}-{i+len(chunk)}'):
            try:
                all_records += scrape_neighborhood(nb, total)
            except Exception as e:
                tqdm.write(f"{nb} error: {e}")

        driver.quit()
        driver = None
        session = None

    total.close()

    # Build and clean DataFrame
    df = pd.DataFrame(all_records)
    df = df.drop_duplicates()
    df = df[(df['area'] >= MIN_AREA) & (df['area'] <= MAX_AREA)]
    df = df[(df['price_per_m2'] >= MIN_PPSM) & (df['price_per_m2'] <= MAX_PPSM)]

    df.to_csv(CSV_LISTINGS_OUTPUT, index=False)
    print(f"Saved {len(df)} cleaned listings to {CSV_LISTINGS_OUTPUT}")

    # Compute indices per neighborhood
    indices = []
    for nb, grp in df.groupby('neighborhood'):
        sale = grp[grp['category'] == 'sale']
        rent = grp[grp['category'] == 'rent']
        indices.append({
            'neighborhood': nb,
            'avg_sale_price_per_m2': sale['price_per_m2'].mean() if not sale.empty else None,
            'avg_rent_price': rent['price'].mean() if not rent.empty else None,
            'avg_rent_price_per_m2': rent['price_per_m2'].mean() if not rent.empty else None,
            'avg_rooms': grp['rooms'].mean()
        })

    # Append to historical CSV
    indices_df = pd.DataFrame(indices)
    indices_df['date'] = date.today()

    if os.path.exists(HIST_FILE):
        hist = pd.read_csv(HIST_FILE, parse_dates=['date'])
        hist = pd.concat([hist, indices_df], ignore_index=True)
    else:
        hist = indices_df.copy()

    hist.to_csv(HIST_FILE, index=False)
    print(f"Appended today's indices to {HIST_FILE}")


if __name__ == '__main__':
    main()

