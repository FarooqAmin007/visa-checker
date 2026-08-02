import requests
from bs4 import BeautifulSoup
import os
import sys
import time
from datetime import datetime
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from playwright.sync_api import sync_playwright

# ================= CONFIG =================

MAIN_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"
BASE_URL = "https://travel.state.gov"

NTFY = "https://ntfy.sh/visa-bulletin-rauf"

YOUR_PD = datetime.strptime("04FEB2011", "%d%b%Y")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

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
    """Detect the 'Performing security verification' bot-check interstitial."""
    if not html:
        return True
    lowered = html.lower()
    markers = [
        "performing security verification",
        "verifies you are not a bot",
        "security service to protect against malicious bots",
    ]
    return any(m in lowered for m in markers)


def fetch_rendered_html(url: str, page, max_attempts: int = 3) -> str:
    """
    Load a URL in the shared Playwright page and wait out the bot-check
    challenge if one appears. Returns the final rendered HTML.
    """
    last_html = ""

    for attempt in range(1, max_attempts + 1):

        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Give the challenge JS a chance to run and redirect/replace content.
        for _ in range(6):
            html = page.content()
            if not looks_like_challenge(html):
                return html
            page.wait_for_timeout(5000)

        last_html = page.content()
        print(f"Attempt {attempt}: still on security-verification page, retrying...")
        page.wait_for_timeout(3000)

    return last_html


def get_latest_link(page):

    html = fetch_rendered_html(MAIN_URL, page)

    if looks_like_challenge(html):
        print("Blocked by bot-check on main bulletin index page.")
        return None, None

    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a"):

        text = a.get_text(strip=True)

        if "Visa Bulletin For" in text:

            href = a.get("href")
            if href and href.startswith("http"):
                full_url = href
            else:
                full_url = BASE_URL + href

            return text, full_url

    return None, None


def get_f4_data(url, page):

    html = fetch_rendered_html(url, page)

    if looks_like_challenge(html):
        print("Blocked by bot-check on bulletin detail page.")
        return "Not found", "Not found"

    soup = BeautifulSoup(html, "html.parser")

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

with sync_playwright() as p:

    browser = p.chromium.launch(headless=True)

    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1366, "height": 900},
        locale="en-US",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    page = context.new_page()

    title, link = get_latest_link(page)

    if not title:
        browser.close()
        # Site is still blocking us even after rendering - alert once via ntfy
        # so it's obvious this needs a manual look, then exit without touching
        # last.txt (so we retry cleanly next run).
        notify_ntfy(
            "⚠️ Visa bulletin checker: could not get past travel.state.gov "
            "bot-check after retries. Site structure or protection may have "
            "changed further."
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

    new_A, new_B = get_f4_data(link, page)

    browser.close()

old_A_date = parse_date(old_A)
old_B_date = parse_date(old_B)

new_A_date = parse_date(new_A)
new_B_date = parse_date(new_B)

progress_A = calc_progress(old_A_date, new_A_date)
progress_B = calc_progress(old_B_date, new_B_date)

remaining_A = months_remaining(new_A_date, YOUR_PD)
remaining_B = months_remaining(new_B_date, YOUR_PD)

alerts = ""

# ================= ALERTS =================

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

# ================= NOTIFY =================

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

    # ntfy notification
    notify_ntfy(message)

    # create checklist pdf
    pdf_file = create_pdf()

    # send email
    send_email(
        subject=title,
        body=message,
        attachment_path=pdf_file
    )

    # save latest data
    with open("last.txt", "w") as f:

        f.write(new_data)

    print("Notifications sent")

else:

    print("No change")
