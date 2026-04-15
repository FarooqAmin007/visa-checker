import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

MAIN_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"
BASE_URL = "https://travel.state.gov"
NTFY = "https://ntfy.sh/visa-bulletin-rauf"

# 🎯 YOUR PRIORITY DATE
YOUR_PD = datetime.strptime("04FEB2011", "%d%b%Y")

def parse_date(d):
    try:
        d = d.strip().upper().replace(" ", "")
        if len(d) == 7:
            d = d[:5] + "20" + d[5:]
        return datetime.strptime(d, "%d%b%Y")
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
    return ""

def months_remaining(current, target):
    if not current or not target:
        return None
    return (target.year - current.year) * 12 + (target.month - current.month)

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

# ================= MAIN =================

title, link = get_latest_link()

if not title:
    exit()

if os.path.exists("last.txt"):
    with open("last.txt", "r") as f:
        old = f.read().split("|")
else:
    old = ["", "", ""]

old_title, old_A, old_B = old

new_A, new_B = get_f4_data(link)

old_A_date = parse_date(old_A)
old_B_date = parse_date(old_B)

new_A_date = parse_date(new_A)
new_B_date = parse_date(new_B)

progress_A = calc_progress(old_A_date, new_A_date)
progress_B = calc_progress(old_B_date, new_B_date)

remaining_A = months_remaining(new_A_date, YOUR_PD)
remaining_B = months_remaining(new_B_date, YOUR_PD)

alerts = ""

# 🎯 ALERT LOGIC

if remaining_A is not None:
    if remaining_A <= 0:
        alerts += "\n🎉 YOU ARE CURRENT (Final Action)"
    elif remaining_A <= 12:
        alerts += f"\n🎯 Very close (~{remaining_A} months left)"

if remaining_B is not None:
    if remaining_B <= 0:
        alerts += "\n🟡 Filing Date reached → Prepare documents NOW"
    elif remaining_B <= 12:
        alerts += f"\n📂 Prepare documents soon (~{remaining_B} months)"

new_data = f"{title}|{new_A}|{new_B}"

# only notify on change
if new_data != "|".join(old):

    message = f"""📢 {title}

F4 Category:
A (Final): {new_A}{progress_A}
B (Filing): {new_B}{progress_B}

📊 Your PD: 04FEB2011
⏳ Remaining (A): {remaining_A} months
⏳ Remaining (B): {remaining_B} months
{alerts}
"""

    requests.post(NTFY, data=message.encode("utf-8"))

    with open("last.txt", "w") as f:
        f.write(new_data)

    print("Notification sent")
else:
    print("No change")
