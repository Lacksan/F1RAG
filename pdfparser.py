import re, json, sys
from pathlib import Path
import pdfplumber

HEADER_ANCHORS = ("Updated", "Primary", "Geometric", "Brief")

def clean(s):
    """removes the large gaps of whitespaces into single spaces and cuts the ends of each sentence"""
    return re.sub(r"\s+", " ", (s or "")).strip()


def cluster(vals, tol=3.0):
    """ groups pixels together to prevent duplication with a buffer of 3 pixels"""

    out = []
    for v in sorted(vals):
        if not out or v - out[-1] > tol:
            out.append(v)
    return out

def span(intervals):
    """calculates how much horizontal space is covered by line segments factoring in overlaps"""

    total = 0.0
    cur = None  
    for a, b in sorted(intervals): #a and b are tuples that contain start and end points of lines
        if b <= a:
            continue
        if cur and a <= cur[1]: # checks whether current interval overlaps the previous one
            cur = (cur[0], max(cur[1], b)) # merges the current interval with new one
        else:
            if cur:
                total += cur[1] - cur[0] # calculates length of total current interval and adds to total 
            cur = (a,b)
    return total + (cur[1] - cur[0] if cur else 0.0) # returns total covered length, including final interval

def grid_columns(page, tol=3.0):
    """finds the vertical line of each of the table"""

    xs = cluster([r["x0"] for r in page.rects if r["width"] < 2 and r["height"] > 8], tol) # page rects gets the rectangles drawn in the PDF
    return xs if len(xs) >= 6 else None


def col_rules(page, x0, x1, tol=3.0, cover=0.8):
    """identifies the horizontal lines that seperate rows in a table column, x0 is left boundary of target column, and x1 being the right boundary"""
    ys = cluster([r["top"] for r in page.rects if r["height"] < 2 and r["width"] > 8], tol) #looks for rectangles, with height less than 2 & width greater than 8 and stores the top y coord
    out = [] #stores coordinates that fall out of target column
    width = x1 - x0 # right boundary - left boundary
    for y in ys: #loops through every y co ordinate in ys
        intervals = [] # stores horizontal lines that overlap the target column
        for r in page.rects:
            if r["height"] < 2 and abs(r["top"] - y) <= tol: #
                a = max(x0, r["x0"])
                b = min(x1, r["x1"] + r["width"])
                if b > a:
                    intervals.append((a, b))
        if span(intervals) >= cover * width:
            out.append(y)
    return out

def team_name(text_lines):
    """recieves the text extracted from above the table and works out which team the table belongs to"""
    banner = header = None # banner stores the index of the line containing the words Car presentation, #header stores the index of a line that appears to contain the table column headings
    for i, l in enumerate(text_lines): 
        low = l.strip().lower()
        if banner is None and low.startswith("car presentation"):
            banner = i
        if header is None and low.startswith("updated") and ("reason" in low or "primary" in low):
            header = i
    start = (banner + 1) if banner is not None else 0
    if header is not None:
        cand = " ".join(text_lines[start:header]).strip()
        if not cand:
            return None
    elif banner is not None:
        cand = text_lines[start] if start < len(text_lines) else ""
    elif text_lines:
        cand = " ".join(text_lines).strip()
    else:
        return None
    return (clean(cand).strip("*").strip().rstrip(".")) or None

def parse_team_page(page, edges):
    """ takes a PDF page and its table column boundaries, then extracts the team name and the rows of technical updates"""

    def col_of(x):
        """finds which of the columns the horizontal coordinate x belongs to"""
        return min(max(sum(x >= e for e in edges) - 1, 0), 4)

    rules = [col_rules(page, edges[c], edges[c + 1]) for c in range(5)]
    row_edges = rules[0]
    if len(row_edges) < 2:
        return None, [], False

    words = page.extract_words()
    bands = list(zip(row_edges, row_edges[1:]))

    def cell_words(c, top, bot):
        """finds the words belonging to a particular cell in the table"""
        mid = (top + bot) / 2
        ds = rules[c] or row_edges
        ct = max([d for d in ds if d <= mid + 1], default=top)
        cb = min([d for d in ds if d > mid + 1], default=bot)
        return sorted((w["top"], w["x0"], w["text"]) for w in words
                      if ct < (w["top"] + w["bottom"]) / 2 < cb
                      and col_of((w["x0"] + w["x1"]) / 2) == c)

    def is_header(top, bot):
        """checks if a row is likely to be a table haeder"""
        cols = {col_of((w["x0"] + w["x1"]) / 2) for w in words
                if w["text"] in HEADER_ANCHORS and top < (w["top"] + w["bottom"]) / 2 < bot}
        return len(cols) >= 2

    above = [w for w in words if w["bottom"] <= row_edges[0] - 2]
    text_lines = []
    for w in sorted(above, key=lambda w: (w["top"], w["x0"])):
        if not text_lines or abs(w["top"] - text_lines[-1][0]) > 3:
            text_lines.append([w["top"], w["text"]])
        else:
            text_lines[-1][1] += " " + w["text"]
    text_lines = [x[1] for x in text_lines]

    headed = any(is_header(*b) for b in bands)
    team = team_name(text_lines) if (headed or above) else None
    banner = any(clean(w["text"]).lower() == "car" and w["bottom"] <= row_edges[0] - 2
                 for w in words) or any("presentation" in w["text"].lower() for w in above)

    if not headed and not banner and above:
        bands.insert(0, (min(w["top"] for w in above) - 2, row_edges[0]))

    body = [b for b in bands if not is_header(*b)]
    if headed:
        body = bands[bands.index(next(b for b in bands if is_header(*b))) + 1:]

    rows = []
    for top, bot in body:
        cells = [clean(" ".join(t for *_, t in cell_words(c, top, bot))) for c in range(5)]
        if any(cells[1:]):
            rows.append(cells)

    _reconcile_merged_reason(rows)

    continues = bool(rows) and not rows[0][0] and not rows[0][1]
    return team, rows, continues

def _reconcile_merged_reason(rows):
    """ joins text from rows that share the same description and geometric differences"""
    i = 0
    while i < len(rows):
        j = i + 1
        while (j < len(rows) and rows[j][3] and rows[j][4]
               and rows[j][3] == rows[i][3] and rows[j][4] == rows[i][4]):
            j += 1
        if j - i > 1:
            fragments = [rows[k][2] for k in range(i, j) if rows[k][2]]
            combined = clean(" ".join(fragments))
            for k in range(i, j):
                rows[k][2] = combined
        i = j

def parse_pdf(path):
    """Parse one Car Presentation Submissions PDF into a list of record dicts."""
    stem = Path(path).stem.replace("_", " ")
    m = re.search(r"(\d{4})\s+(.*?)\s*-\s*car presentation", stem, re.I)
    year = int(m.group(1)) if m else None
    race = clean(m.group(2)).title() if m else None
    out, last_team = [], None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            edges = grid_columns(page)
            if not edges:
                continue                      # cover sheet, diagram, "no updates"
            team, rows, continues = parse_team_page(page, edges)
            if team:
                last_team = team
            else:
                team = last_team
            if continues and out:
                # Tail of a row that overflowed the page break: fold it back in.
                tail = rows.pop(0)
                for k, key in zip(range(2, 5),
                                  ("reason", "geometric_difference", "description")):
                    if tail[k]:
                        out[-1][key] = clean(out[-1][key] + " " + tail[k])
            for num, comp, reason, geo, desc in rows:
                out.append({
                    "race": race, "year": year, "team": team, "number": num,
                    "component": comp, "reason": reason,
                    "geometric_difference": geo, "description": desc,
                })
    return out


if __name__ == "__main__":
    pdf_folder = Path("fia_cps_pdfs")
    all_records = []

    for pdf in pdf_folder.glob("*.pdf"):
        all_records.extend(parse_pdf(pdf))

    with open("fia_cps_output.json", "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2) 