#!/usr/bin/env python3
"""
Throttled MerrJep scraper for sale listings by neighborhood,
using Selenium for search pages, token-bucket rate limiting,
retry/backoff on errors, rotating User-Agents, batches of two,
logging daily sale-price-per-m2 indices, then exit.
"""
import os
import csv
import time
import random
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, quote, urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter, Retry
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm

# Constants
BASE_URL = 'https://www.merrjep.al'
CSV_INPUT = 'neighborhoods.csv'
CSV_LISTINGS_OUTPUT = 'listings_data.csv'
LOG_INDICES_FILE = 'neighborhood_indices_log.csv'
URL_TEMPLATE = BASE_URL + '/njoftime/imobiliare-vendbanime/apartamente/tirane/q-{}'

# Selenium headless options
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.binary_location = "/usr/bin/chromium-browser"

# Requests session with retries
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
session.mount('https://', HTTPAdapter(max_retries=retries))

# User-Agent rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
]

def new_headers():
    return {'User-Agent': random.choice(USER_AGENTS)}

# Rate limiter (token bucket)
class RateLimiter:
    def __init__(self, rate, per):
        self.lock = threading.Lock()
        self.allowance = rate
        self.rate = rate
        self.per = per
        self.last = time.monotonic()
    def wait(self):
        with self.lock:
            current = time.monotonic()
            elapsed = current - self.last
            self.allowance += elapsed * (self.rate / self.per)
            self.last = current
            if self.allowance > self.rate:
                self.allowance = self.rate
            if self.allowance < 1.0:
                to_sleep = (1.0 - self.allowance) * (self.per / self.rate)
                time.sleep(to_sleep)
                self.allowance = 0.0
            else:
                self.allowance -= 1.0

limiter = RateLimiter(rate=8, per=1)

# Cleaning thresholds
MIN_AREA = 20     # m²
MAX_AREA = 500    # m²
MIN_PPSM = 200    # €/m²
MAX_PPSM = 5000   # €/m²


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
            category = 'rent'; break
        if 'shit' in txt:
            category = 'sale'; break
    rooms = None; area = None
    for tag in soup.select('a.tag-item, .tag-item'):
        lbl = tag.select_one('span'); val = tag.select_one('bdi')
        if not lbl or not val: continue
        label = lbl.get_text(strip=True).rstrip(':'); v = val.get_text(strip=True)
        if 'Numri i dhomave' in label:
            try: rooms = int(v.split('+')[0])
            except: pass
        elif 'Sipërfaqe' in label:
            try: area = float(v.split()[0].replace(',', '.'))
            except: pass
    return price, rooms, area, category


def fetch_detail(args):
    href, neighborhood = args
    raw_url = urljoin(BASE_URL, href)
    parsed = urlparse(raw_url)
    fixed_path = quote(parsed.path, safe='/')
    detail_url = urlunparse((parsed.scheme, parsed.netloc, fixed_path, parsed.params, parsed.query, parsed.fragment))
    limiter.wait()
    try:
        r = session.get(detail_url, headers=new_headers(), timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        price, rooms, area, category = parse_listing_detail(soup)
        if price is not None and area and category == 'sale':
            return {'neighborhood': neighborhood, 'price': price, 'rooms': rooms, 'area': area, 'price_per_m2': price/area}
    except Exception as e:
        tqdm.write(f"Detail error {detail_url}: {e}")
    return None


def scrape_neighborhood(nb, total_bar):
    slug = sanitize(nb)
    url = URL_TEMPLATE.format(slug)
    tqdm.write(f"\n[{nb}] loading → {url}")
    driver.get(url)
    driver.set_page_load_timeout(30)
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    anchors = soup.select('a.Link_vis') or [a for c in soup.select('li.announcement-item') for a in [c.find('a', href=True)] if a]
    tqdm.write(f"[{nb}] anchors → {len(anchors)}")
    tasks = [(a['href'], nb) for a in anchors]
    records = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(fetch_detail, t) for t in tasks]
        for fut in tqdm(as_completed(futures), total=len(futures), desc=f'Parsing {nb}', leave=False):
            rec = fut.result()
            if rec:
                records.append(rec)
                total_bar.update(1)
            time.sleep(random.uniform(0.2, 0.5))
    return records


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main():
    with open(CSV_INPUT) as f:
        nbs = [r[0] for r in csv.reader(f) if r]
    all_listings = []
    for batch in chunks(nbs, 2):
        global driver
        driver = webdriver.Chrome(options=chrome_options)
        total = tqdm(desc='Batch Total', unit='listing')
        for nb in tqdm(batch, desc='Neighborhoods Batch'):
            recs = scrape_neighborhood(nb, total)
            all_listings += recs
            tqdm.write(f"✅ Finished {nb}, got {len(recs)} listings")
        total.close()
        driver.quit()
    df = pd.DataFrame(all_listings).drop_duplicates()
    df.to_csv(CSV_LISTINGS_OUTPUT, index=False)
    print(f"Saved {len(df)} listings to {CSV_LISTINGS_OUTPUT}")
    inds = []
    for nb, grp in df.groupby('neighborhood'):
        inds.append({'date': datetime.now().strftime('%Y-%m-%d'), 'neighborhood': nb, 'avg_sale_price_per_m2': grp['price_per_m2'].mean()})
    inds_df = pd.DataFrame(inds)
    if not os.path.exists(LOG_INDICES_FILE):
        inds_df.to_csv(LOG_INDICES_FILE, index=False)
    else:
        inds_df.to_csv(LOG_INDICES_FILE, mode='a', header=False, index=False)
    print(f"Logged indices to {LOG_INDICES_FILE}")

if __name__ == '__main__':
    main()
