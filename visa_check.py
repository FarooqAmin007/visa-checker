import requests
from bs4 import BeautifulSoup

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
else:
    print("Latest:", latest)

    # Always send notification (temporary test)
    requests.post(NTFY, data=f"📢 {latest}".encode("utf-8"))

    print("Notification sent")
