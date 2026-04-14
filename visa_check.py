import requests
from bs4 import BeautifulSoup
import os

URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"
NTFY = "https://ntfy.sh/visa-bulletin-rauf"

def get_latest():
    res = requests.get(URL)
    soup = BeautifulSoup(res.text, "html.parser")

    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        if "Visa Bulletin For" in text:
            return text
    return None

latest = get_latest()

if not latest:
    print("Error fetching data")
    exit()

print("Latest:", latest)

# read old value
if os.path.exists("last.txt"):
    with open("last.txt", "r") as f:
        old = f.read().strip()
else:
    old = ""

# compare
if latest != old:
    print("New update detected")

    requests.post(NTFY, data=f"📢 {latest}".encode("utf-8"))

    with open("last.txt", "w") as f:
        f.write(latest)
else:
    print("No change")