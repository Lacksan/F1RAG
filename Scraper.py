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

def download(url, out_dir):
    """input is pdf url and destination folder, builds file name skips download if file already downloaded, otherwise downloads and saves in destination directory"""
    filename = unquote(url.split("/")[-1])
    destination = Path(out_dir) / filename
    if destination.exists():
        return destination, "cached"
    time.sleep(1.5)
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    destination.write_bytes(r.content) #
    return destination, f"{len(r.content)//1024} KB" 

def run(years = None, min_year=2023, out_dir="fia_cps_pdfs"):
    Path(out_dir).mkdir(exist_ok=True) #creates output folder if it doesnt exist already, does nothing if it does
    seasons = season_urls(min_year=min_year) # gets the dictionary of {year: season_url}, for seasons greater and equal than minimum year

    if years:
        season = {y: u for y, u in seasons.items() if y in years}
    count = 0 # how many pdfs downloaded
    for year, surl in seasons.items(): #loops through every season and its url
        print(f"\n=== {year} ===")
        for ev in events_for(surl):
            try:
                url = pdf_url(surl, ev)  #tries to find url
            except requests.RequestException as e:
                print(f"  {ev} ERROR {e}"); continue # prints error
            if not url:
                print(f"  {ev} (no CPS doc)"); continue
            dest, note = download(url, out_dir) # download the pdf
            print(f"  {ev} {dest.name}  [{note}]"); count += 1 # print result and increments pdf count

    
    print(f"\nDone. {count} PDFs in {out_dir}/") # final summary

    if __name__ == "__main__":
         # only runs if launched directly
         yrs = [int(a) for a in sys.argv[1:]] or None
         run(years=yrs)
