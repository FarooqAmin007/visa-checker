import requests
import re
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

import pdfplumber
import io

# ================= CONFIG =================

BASE_URL = "https://travel.state.gov"
PDF_URL_TEMPLATE = BASE_URL + "/content/dam/visas/Bulletins/visabulletin_{month}{year}.pdf"

NTFY = "https://ntfy.sh/visa-bulletin-rauf"

YOUR_PD = datetime.strptime("04FEB2011", "%d%b%Y")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {"User-Agent": USER_AGENT}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

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


def add_months(base_year, base_month_index, offset):
    """base_month_index is 0-based (0=January)."""
    total = base_month_index + offset
    year = base_year + total // 12
    month_index = total % 12
    return year, month_index


def find_latest_bulletin_pdf():
    """
    The Visa Bulletin PDF URL is predictable: visabulletin_<Month><Year>.pdf.
    A new bulletin usually goes up shortly before the month it covers starts,
    so we probe a small window around today and take the furthest-future
    one that actually exists.
    """
    today = datetime.utcnow()
    base_month_index = today.month - 1

    # Check next month first (already published near month end), then
    # current month, then fall back a month or two if needed.
    for offset in [2, 1, 0, -1, -2]:
        year, month_index = add_months(today.year, base_month_index, offset)
        month_name = MONTH_NAMES[month_index]
        url = PDF_URL_TEMPLATE.format(month=month_name, year=year)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except Exception as e:
            print(f"Request failed for {url}: {e}")
            continue

        if resp.status_code == 200 and resp.headers.get("Content-Type", "").lower().startswith("application/pdf"):
            title = f"Visa Bulletin For {month_name} {year}"
            print(f"Found bulletin: {title} -> {url}")
            return title, resp.content

        print(f"Not available yet: {url} (status {resp.status_code})")

    return None, None


F4_ROW_RE = re.compile(
    r"F4\s+"
    r"((?:\d{2}[A-Z]{3}\d{2}|C|U))\s+"
    r"((?:\d{2}[A-Z]{3}\d{2}|C|U))\s+"
    r"((?:\d{2}[A-Z]{3}\d{2}|C|U))\s+"
    r"((?:\d{2}[A-Z]{3}\d{2}|C|U))\s+"
    r"((?:\d{2}[A-Z]{3}\d{2}|C|U))"
)


def get_f4_data(pdf_bytes):
    """
    Extract F4 (Brothers/Sisters of Adult US Citizens) rows.
    The PDF has two F4 rows in this order: Final Action Dates, then
    Dates for Filing. We take the "All Chargeability Areas" column
    (the first value after F4) from each.
    """
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    full_text = "\n".join(text_parts)
    # Collapse whitespace/newlines so the regex can match rows that PDF
    # extraction may have wrapped oddly.
    flat_text = re.sub(r"\s+", " ", full_text)

    matches = F4_ROW_RE.findall(flat_text)

    final_action = matches[0][0] if len(matches) >= 1 else "Not found"
    filing_date = matches[1][0] if len(matches) >= 2 else "Not found"

    return final_action, filing_date


# ================= MAIN =================

title, pdf_bytes = find_latest_bulletin_pdf()

if not title:
    notify_ntfy(
        "⚠️ Visa bulletin checker: could not find a current bulletin PDF "
        "at travel.state.gov. URL pattern or publishing schedule may have "
        "changed."
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

new_A, new_B = get_f4_data(pdf_bytes)

if new_A == "Not found" and new_B == "Not found":
    notify_ntfy(
        f"⚠️ Visa bulletin checker: found {title} but could not parse the "
        "F4 rows. PDF layout may have changed."
    )
    sys.exit(0)

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
