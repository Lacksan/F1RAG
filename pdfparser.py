import re, json, sys
from pathlib import Path
import pdfplumber

HEADER_ANCHORS = ("Updated", "Primary", "Geometric", "Brief")

def _clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def _column_edges(page):
    ax = {}
    for w in page.extract_words():
        if w["text"] in HEADER_ANCHORS and w["text"] not in ax:
            ax[w["text"]] = w["x0"]
    if len(ax) < 4:
        return None
    u = ax["Updated"]
    
    return [u - 45, u - 8, ax["Primary"] - 8, ax["Geometric"] - 8, ax["Brief"] - 8]
