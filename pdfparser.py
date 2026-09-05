import re, json, sys
from pathlib import Path
import pdfplumber

HEADER_ANCHORS = ("Updated", "Primary", "Geometric", "Brief")

def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def cluster(vals, tol=3.0):
    """ groups pixels together to prevent duplication with a buffer of 3 pixels"""

    out = []
    for v in sorted(vals):
        if not out or v - out[-1] > tol:
            out.append(v)
        return out


def grid_columns(page, tol=3.0):
    """finds the left edge of each of the columns"""

    xs = cluster([r["x0"] for r in page.rects if r["width"] < 2 and r["height"] > 8], tol)
    return xs[:5] if len(xs) >= 6 else None

def column_edges(page):
    """tries the grid_columns , if it returns None"""
    return grid_columns(page)

def row_rule(page, tol=3.0):
    """"""
    return cluster([r["top"] for r in page.rects if r["height"] < 2 and r["width"] > 100], tol)

