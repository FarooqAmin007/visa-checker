import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

MAIN_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"
BASE_URL = "https://travel.state.gov"
NTFY = "https://ntfy.sh/visa-bulletin-rauf"

def parse_date(d):
    try:
        return datetime.strptime(d.strip(), "%d%b%Y")
    except:
        return None

def calc_progress(old, new):
    if old is None or new is None:
        return ""
    
    months = (new.year - old.year) * 12 + (new.month - old.month)

    if months > 0:
        return f" (+{months} months)"
    elif months == 0:
        return " (no change)"
    else:
        return ""

def get_latest_link():
    res = requests.get(MAIN_URL)
    soup = BeautifulSoup(res.text, "html.parser")

    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        if "Visa Bulletin For" in text:
            return text, BASE_URL + a.get("href")
    return None, None

def get_f4_data(url):
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")

    tables = soup.find_all("table")

    final_action = "Not found"
    filing_date = "Not found"

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]

            if len(cols) > 1 and "F4" in cols[0]:
                if final_action == "Not found":
                    final_action = cols[1]
                else:
                    filing_date = cols[1]

    return final_action, filing_date

# main
title, link = get_latest_link()

if not title:
    print("Error")
    exit()

# read old
if os.path.exists("last.txt"):
    with open("last.txt", "r") as f:
        old = f.read().split("|")
else:
    old = ["", "", ""]

old_title, old_A, old_B = old

new_A, new_B = get_f4_data(link)

progress_A = calc_progress(parse_date(old_A), parse_date(new_A))
progress_B = calc_progress(parse_date(old_B), parse_date(new_B))

new_data = f"{title}|{new_A}|{new_B}"

if True:

    message = f"""📢 {title}

F4 Category:
A (Final): {new_A}{progress_A}
B (Filing): {new_B}{progress_B}
"""

    requests.post(NTFY, data=message.encode("utf-8"))

    with open("last.txt", "w") as f:
        f.write(new_data)

    print("Notification sent")
else:
    print("No change")
