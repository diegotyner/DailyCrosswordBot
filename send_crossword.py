from playwright.sync_api import sync_playwright
from datetime import date
import smtplib
from email.mime.text import MIMEText
import os
import sys
from dotenv import load_dotenv


AD_DOMAINS = [
    "doubleclick.net",
    "googlesyndication.com",
    "googletagservices.com",
    "google-analytics.com",
    "amazon-adsystem.com",
    "rubiconproject.com",
    "pubmatic.com",
    "permutive.com",
    "confiant-integrations.net",
    "chartbeat.com",
    "chartbeat.net",
]


def block_ads(route):
    if any(domain in route.request.url for domain in AD_DOMAINS):
        route.abort()
    else:
        route.continue_()


def get_puzzle_id():
    return "tca" + date.today().strftime("%y%m%d")


def get_share_link(args):
    url = f"https://www.latimes.com/games/daily-crossword?id={get_puzzle_id()}"
    with sync_playwright() as p:
        ua_header = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        page = None
        if "headless=False" not in args:
            browser = p.chromium.launch(headless=True, args=["--headless=new"])
            context = browser.new_context(
                user_agent=ua_header,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/Los_Angeles",
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            page = context.new_page()
        else:
            browser = p.chromium.launch(headless=False, slow_mo=800)
            context = browser.new_context()
            page = context.new_page()

        print("Navigating to page...")
        page.route("**/*", block_ads)
        page.goto(url)

        # Dismiss the terms-of-service / metering modal if it appears
        try:
            page.click('[data-tos-handler="accept-tos"]', timeout=8000)
            page.wait_for_timeout(500)  # let the modal actually close/animate out
            print("TOS modal accepted")
        except Exception:
            print("No TOS modal appeared (or it didn't show up in time) — continuing")

        # click "Play together" to open the share modal
        # with open("initial_page.html", "w") as f:
        #     f.write(page.content())
        print("Initial page written")

        # The ad needs to load before the iframe is loaded afterwards
        print("Starting wait")
        wait_time_seconds = 5
        page.wait_for_timeout(wait_time_seconds * 1000)
        print("Waited " + str(wait_time_seconds) + " seconds")

        frame = None
        for f in page.frames:
            if "amuselabs" in f.url:
                frame = f
                break

        if frame is None:
            raise Exception("Could not find amuselabs puzzle iframe")

        frame.click(".nav-social-play-invite-icon")
        print("Button found and clicked")

        # wait for the copy button to actually be present/visible
        frame.wait_for_timeout(500)
        # with open("clicked_page.html", "w") as f:
        #     f.write(frame.content())
        print("Clicked page written")

        frame.wait_for_selector("#footer-btn.copy-social-link-button", state="visible")
        frame.click("#footer-btn.copy-social-link-button")
        print("Share button found and clicked")

        share_link = frame.locator(".social-play-textarea").inner_text()

        browser.close()
        return share_link


def send_email(link):
    load_dotenv()
    msg = MIMEText(f"Today's crossword: {link}")
    msg["Subject"] = "Crossword time!"
    msg["From"] = os.environ["GMAIL_USER"]
    msg["To"] = ", ".join(os.environ["RECIPIENTS"].split(","))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)


if __name__ == "__main__":
    link = get_share_link(sys.argv)
    print("Scraped: " + str(link))
    send_email(link)
