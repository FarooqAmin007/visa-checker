import requests
from bs4 import BeautifulSoup
import os
import sys
from datetime import datetime
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ================= CONFIG =================

# travel.state.gov now sits behind a bot-check that blocks scripted
# requests (and even headless browsers). The State Department also
# mirrors the exact same content tree, unprotected, at adoptions.state.gov
# (note the extra "s") - verified to have identical Visa Bulletin pages.
# We try that mirror first, then fall back to the real domain in case
# the mirror ever goes away or the block on the main site is lifted.
CANDIDATE_BASES = [
    "https://adoptions.state.gov",
    "https://travel.state.gov",
]

MAIN_PATH = "/content/travel/en/legal/visa-law0/visa-bulletin.html"

NTFY = "https://ntfy.sh/visa-bulletin-rauf"

YOUR_PD = datetime.strptime("04FEB2011", "%d%b%Y")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {"User-Agent": USER_AGENT}

# ================= EMAIL =================

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

TO_EMAIL = "raufamin7871@gmail.com"

# ================= FUNCTIONS =================

def create_pdf():
    pdf_file = "F4_Checklist.pdf"
    doc = SimpleDocTemplate(pdf_file)
    styles = getSampleStyleSheet()
    story = []
    title = Paragraph("<b>F4 Visa Document Checklist</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    checklist = """
    <br/>
    • Passport copies<br/>
    • Birth certificates<br/>
    • Marriage certificate<br/>
    • Police certificates<br/>
    • Passport size photographs<br/>
    • Affidavit of Support (I-864)<br/>
    • Tax returns of petitioner<br/>
    • DS-260 confirmation page<br/>
    • NVC fee payment receipts<br/>
    • Interview appointment letter<br/>
    • Vaccination records<br/>
    • Civil documents translations (if needed)<br/>
    """
    story.append(Paragraph(checklist, styles['BodyText']))
    doc.build(story)
    return pdf_file


def send_email(subject, body, attachment_path):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = TO_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={attachment_path}",
            )
            msg.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print("Email failed:")
        print(str(e))


def notify_ntfy(text):
    try:
        requests.post(NTFY, data=text.encode("utf-8"), timeout=15)
    except Exception as e:
        print("ntfy failed:", e)


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


def looks_like_challenge(html: str) -> bool:
    """Detect a 'Performing security verification' style bot-check page."""
    if not html:
        return True
    lowered = html.lower()
    markers = [
        "performing security verification",
        "verifies you are not a bot",
        "security service to protect against malicious bots",
    ]
    return any(m in lowered for m in markers)


def get_latest_link(base_url):
    """Return (title, full_url) of the newest 'Visa Bulletin For ...' page."""
    url = base_url + MAIN_PATH
    resp = requests.get(url, headers=HEADERS, timeout=30)

    if resp.status_code != 200 or looks_like_challenge(resp.text):
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        if "Visa Bulletin For" in text:
            href = a.get("href")
            if not href:
                continue
            full_url = href if href.startswith("http") else base_url + href
            return text, full_url

    return None, None


def get_f4_data(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)

    if resp.status_code != 200 or looks_like_challenge(resp.text):
        return "Not found", "Not found"

    soup = BeautifulSoup(resp.text, "html.parser")
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


def fetch_bulletin():
    """Try each candidate domain in order until one actually works."""
    for base_url in CANDIDATE_BASES:
        print(f"Trying {base_url} ...")
        title, link = get_latest_link(base_url)

        if not title:
            print(f"  -> blocked or unavailable on {base_url}")
            continue

        new_A, new_B = get_f4_data(link)

        if new_A == "Not found" and new_B == "Not found":
            print(f"  -> got a page on {base_url} but could not find F4 rows")
            continue

        print(f"  -> success via {base_url}: {title}")
        return title, new_A, new_B

    return None, None, None


# ================= MAIN =================

title, new_A, new_B = fetch_bulletin()

if not title:
    notify_ntfy(
        "⚠️ Visa bulletin checker: could not reach any working source "
        "(travel.state.gov or its mirror) or could not find the F4 rows. "
        "Site structure or protection may have changed further."
    )
    sys.exit(0)

if os.path.exists("last.txt"):
    with open("last.txt", "r") as f:
        old = f.read().strip().split("|")
else:
    old = ["", "", ""]

while len(old) < 3:
    old.append("")

old_title, old_A, old_B = old[0], old[1], old[2]

old_A_date = parse_date(old_A)
old_B_date = parse_date(old_B)

new_A_date = parse_date(new_A)
new_B_date = parse_date(new_B)

progress_A = calc_progress(old_A_date, new_A_date)
progress_B = calc_progress(old_B_date, new_B_date)

remaining_A = months_remaining(new_A_date, YOUR_PD)
remaining_B = months_remaining(new_B_date, YOUR_PD)

alerts = ""

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

    notify_ntfy(message)

    pdf_file = create_pdf()

    send_email(
        subject=title,
        body=message,
        attachment_path=pdf_file
    )

    with open("last.txt", "w") as f:
        f.write(new_data)

    print("Notifications sent")

else:
    print("No change")
