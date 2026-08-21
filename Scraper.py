import re, time, sys
from pathlib import Path
from urllib.parse import quote, unquote
import requests
from bs4 import BeautifulSoup

Base_url = "https://www.fia.com"
Landing = f"{Base_url}/documents"
UA = {"User-Agent": "F1-RAG-Bot/0.1 (personal research project; contact: lvproject12@gmail.com)"}
D = 1.5

def get(url):
    time.sleep(D)
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text

def season_urls(min_year=2023):
    """year to season page  url, captures seasons >= 2023"""
    html = get(Landing)
    out = {}
    for full in set(re.findall(r"/documents/championships/fia-formula-one-world-championship-14/season/season-(\d{4})-\d+", html)): 
        year = int(re.search(r"season-(\d{4}))", full).group(1))
        if year >= min_year:
            out[year] = Base_url + full
    return dict(sorted(out.items()))
