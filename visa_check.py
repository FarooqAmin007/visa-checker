import requests
from bs4 import BeautifulSoup
import os

MAIN_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"
BASE_URL = "https://travel.state.gov"
NTFY = "https://ntfy.sh/visa-bulletin-rauf"

def get_latest_link():
    res = requests.get(MAIN_URL)
    soup = BeautifulSoup(res.text, "html.parser")

    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        if "Visa Bulletin For" in text:
            link = BASE_URL + a.get("href")
            return text, link
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

print("Latest:", title)

# read old
if os.path.exists("last.txt"):
    with open("last.txt", "r") as f:
        old = f.read().strip()
else:
    old = ""

final_action, filing_date = get_f4_data(link)

new_data = f"{title}|{final_action}|{filing_date}"

if new_data != old:
    message = f"""📢 {title}

F4 Category:
A (Final): {final_action}
B (Filing): {filing_date}
"""

    requests.post(NTFY, data=message.encode("utf-8"))

    with open("last.txt", "w") as f:
        f.write(new_data)

    print("Notification sent")
else:
    print("No change")
