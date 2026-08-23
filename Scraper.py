import re, time, sys
from pathlib import Path
from urllib.parse import quote, unquote
import requests
from bs4 import BeautifulSoup

Base_url = "https://www.fia.com"
Landing = f"{Base_url}/documents"
UA = {"User-Agent": "F1-RAG-Bot/0.1 (personal research project; contact: lvproject12@gmail.com)"}

def get(url):
    """url string passed in, waits 1.5 seconds, fetches the page and returns HTML code, raises error if request failed"""
    time.sleep(1.5) 
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text

def season_urls(min_year=2023):
    """fetches landing page, uses regex to extract season url where years >= min year, output is dictionary {year : url}"""
    html = get(Landing)
    out = {}
    for full in set(re.findall(r"/documents/championships/fia-formula-one-world-championship-14/season/season-(\d{4})-\d+", html)): 
        year = int(re.search(r"season-(\d{4}))", full).group(1))
        if year >= min_year:
            out[year] = Base_url + full
    return dict(sorted(out.items()))

def events_for(season_url):
    """fetches url page, extracts every event name and decodes the URL encoding"""
    html = get(season_url)
    return sorted({unquote(e) for e in re.findall(r"/event/([^\"'?]+)", html)}) # finds /events/ then captures remaining html until quote

def pdf_url(season_url, event):
    """fetches the venets page, finds all pdf links and returns the ones that contain both words 'car' and 'presentation' """
    html = get(f"{season_url}/event{quote(event)}")
    for href in re.findall(r'href="([^"]+\.pdf)"', html):
        if "car" in href.lower() and "presentation" in href.lower():
            return href if href.startswith("https") else Base_url + href
    return None
