from playwright.sync_api import sync_playwright
from datetime import datetime
from zoneinfo import ZoneInfo
import smtplib
from email.mime.text import MIMEText
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time
from dotenv import load_dotenv

# Ensure logs directory exists
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "crossword_bot.log")

# Configure logger with dual handlers: stdout (console/CI) + RotatingFileHandler (persistent EC2 disk)
logger = logging.getLogger("DailyCrosswordBot")
logger.setLevel(logging.INFO)

# Prevent duplicate handlers if module is re-imported
if not logger.handlers:
    log_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler (stdout)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)

    # Persistent Rotating File Handler (max 2 MB per log file, keep up to 5 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)


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
    pacific_today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    return "tca" + pacific_today.strftime("%y%m%d")


def scrape_single_attempt(url, args):
    with sync_playwright() as p:
        ua_header = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        )
        browser = None
        page = None
        try:
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

            logger.info(f"Navigating to {url}...")
            page.route("**/*", block_ads)
            page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Dismiss terms-of-service / metering modal if it appears
            try:
                page.click('[data-tos-handler="accept-tos"]', timeout=8000)
                page.wait_for_timeout(500)
                logger.info("TOS modal accepted")
            except Exception:
                logger.info("No TOS modal appeared (or timed out) — continuing")

            # Dynamic polling for amuselabs frame (up to 20 seconds)
            logger.info("Waiting for amuselabs iframe...")
            frame = None
            start_time = time.time()
            while time.time() - start_time < 20:
                for f in page.frames:
                    if "amuselabs" in f.url:
                        frame = f
                        logger.info("Found amuselabs iframe")
                        break
                if frame:
                    break
                page.wait_for_timeout(1000)

            if frame is None:
                raise TimeoutError("Could not find amuselabs puzzle iframe within 20s")

            # Wait for play invite button in iframe
            frame.wait_for_selector(
                ".nav-social-play-invite-icon", state="visible", timeout=20000
            )
            frame.click(".nav-social-play-invite-icon")
            logger.info("Play Together button clicked")

            # Wait for copy share link button
            frame.wait_for_selector(
                "#footer-btn.copy-social-link-button", state="visible", timeout=15000
            )
            frame.click("#footer-btn.copy-social-link-button")
            logger.info("Share button clicked")

            share_link = frame.locator(".social-play-textarea").inner_text(timeout=10000).strip()
            if not share_link or not share_link.startswith("http"):
                raise ValueError(f"Invalid share link retrieved: '{share_link}'")

            return share_link

        except Exception as e:
            logger.error(f"Scrape step failed: {e}")
            if page:
                try:
                    screenshot_path = os.path.join(LOG_DIR, "error_screenshot.png")
                    page.screenshot(path=screenshot_path)
                    logger.info(f"Saved diagnostic screenshot: {screenshot_path}")
                except Exception as ss_err:
                    logger.warning(f"Failed to capture error screenshot: {ss_err}")

                try:
                    html_path = os.path.join(LOG_DIR, "error_page.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(page.content())
                    logger.info(f"Saved diagnostic HTML page: {html_path}")
                except Exception as html_err:
                    logger.warning(f"Failed to save error HTML content: {html_err}")
            raise

        finally:
            if browser:
                try:
                    browser.close()
                    logger.info("Browser closed cleanly")
                except Exception as close_err:
                    logger.warning(f"Error closing browser: {close_err}")


def get_share_link(args, max_retries=3, retry_delay=5):
    url = f"https://www.latimes.com/games/daily-crossword?id={get_puzzle_id()}"
    for attempt in range(1, max_retries + 1):
        logger.info(f"Scraping attempt {attempt}/{max_retries}...")
        try:
            return scrape_single_attempt(url, args)
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("All scraping retries exhausted.")
                raise


def send_email(link):
    load_dotenv()
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    recipients_str = os.environ.get("RECIPIENTS")

    if not gmail_user or not gmail_pass or not recipients_str:
        raise ValueError("Missing required environment variables: GMAIL_USER, GMAIL_APP_PASSWORD, or RECIPIENTS")

    recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    if not recipients:
        raise ValueError("No valid recipient emails found in RECIPIENTS environment variable")

    msg = MIMEText(f"Today's crossword: {link}")
    msg["Subject"] = "Crossword time!"
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(gmail_user, gmail_pass)
            s.send_message(msg)
        logger.info(f"Successfully sent crossword email to {len(recipients)} recipient(s)")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise


if __name__ == "__main__":
    try:
        link = get_share_link(sys.argv)
        logger.info(f"Scraped share link: {link}")
        send_email(link)
    except Exception as e:
        logger.critical(f"DailyCrosswordBot failed: {e}")
        sys.exit(1)

