import requests
from bs4 import BeautifulSoup

URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"
NTFY = "https://ntfy.sh/visa-bulletin-rauf"

res = requests.get(URL)
soup = BeautifulSoup(res.text, "html.parser")

found = None

for a in soup.find_all("a"):
    text = a.get_text(strip=True)
    if "Visa Bulletin For" in text:
        found = text
        break

print("Latest:", found)

if found:
    requests.post(NTFY, data=f"📢 {found}".encode("utf-8"))
    print("Notification sent")
