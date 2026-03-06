import asyncio
import os
import sqlite3
import requests
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# --- CONFIG ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# The "Hamburg Top 10" Site Map
SITES = [
    {"name": "Otto Group", "url": "https://www.otto.de/jobs/de/jobsuche/hamburg/", "selector": "a[href*='/jobs/de/jobs/']", "cookie": "button:has-text('OK')"},
    {"name": "About You", "url": "https://corporate.aboutyou.de/en/jobs?location=hamburg", "selector": "a[href*='/jobs/']", "cookie": "button:has-text('Accept')"},
    {"name": "Kuehne+Nagel", "url": "https://jobs.kuehne-nagel.com/global/en/search-results?q=IT&location=Hamburg", "selector": "a[data-ph-at-id='job-link']", "cookie": "button:has-text('Accept')"},
    {"name": "XING (New Work)", "url": "https://www.new-work.se/en/career/jobs", "selector": "a.job-card__link", "cookie": "button:has-text('Accept')"},
    {"name": "AppLike", "url": "https://applike-group.com/jobs/", "selector": "a.job-listing", "cookie": "none"},
    {"name": "Lufthansa IS", "url": "https://www.lufthansa-industry-solutions.com/de-de/karriere/jobboerse?location=Hamburg", "selector": "a.job-list-item__link", "cookie": "button:has-text('Zulassen')"},
    {"name": "Jimdo", "url": "https://www.jimdo.com/jobs/", "selector": "a[href*='gh_jid']", "cookie": "button:has-text('OK')"},
    {"name": "Fielmann", "url": "https://www.fielmann-group.com/en/careers/jobs/?location=Hamburg", "selector": "a.job-offer", "cookie": "button:has-text('Accept')"},
    {"name": "Nordex", "url": "https://www.nordex-online.com/en/career/jobs/?location=Hamburg", "selector": "a.job-link", "cookie": "button:has-text('Accept')"},
    {"name": "Goodgame", "url": "https://www.goodgamestudios.com/careers/jobs/", "selector": "a.job-item", "cookie": "none"}
]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

async def scrape_site(page, site, cursor, db):
    print(f"🌐 Scanning {site['name']}...")
    try:
        await page.goto(site['url'], wait_until="networkidle", timeout=60000)
        
        # 1. Clear Cookies
        if site['cookie'] != "none":
            try:
                await page.click(site['cookie'], timeout=5000)
                await asyncio.sleep(1)
            except: pass

        # 2. Scroll to trigger Lazy Loading
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(2)

        # 3. Extract Jobs
        elements = await page.query_selector_all(site['selector'])
        print(f"📊 {site['name']}: Found {len(elements)} possible links.")

        for el in elements:
            title = (await el.inner_text()).split('\n')[0].strip()
            href = await el.get_attribute('href')
            if not href or len(title) < 10: continue

            # Keyword Filter (IT / Student Focus)
            t_low = title.lower()
            if any(kw in t_low for kw in ['it ', 'dev', 'engineer', 'praktikant', 'intern', 'student', 'data', 'cloud', 'software']):
                # Basic URL cleaning
                full_link = href if href.startswith('http') else f"https://{site['name'].lower().replace(' ', '')}.com{href}" # Fallback
                
                # Manual fix for common relative links
                if "otto" in site['name'].lower() and href.startswith('/'): full_link = f"https://www.otto.de{href}"
                if "lufthansa" in site['name'].lower() and href.startswith('/'): full_link = f"https://www.lufthansa-industry-solutions.com{href}"

                try:
                    cursor.execute('INSERT INTO jobs (title, link) VALUES (?, ?)', (title, full_link))
                    db.commit()
                    send_telegram(f"🔥 *New Job: {site['name']}*\n\n*Title:* {title}\n\n[Apply Now]({full_link})")
                    print(f"✨ NEW: {title}")
                except sqlite3.IntegrityError:
                    continue
    except Exception as e:
        print(f"❌ Error on {site['name']}: {str(e)[:100]}")

async def main():
    db = sqlite3.connect('hamburg_jobs.db')
    cursor = db.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, title TEXT, link TEXT UNIQUE)')

    # Use the new Stealth wrapper
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=False)
        
        # Create a context and page normally
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()


        for site in SITES:
            await scrape_site(page, site, cursor, db)
            await asyncio.sleep(3)

        await browser.close()
    db.close()

if __name__ == "__main__":
    asyncio.run(main())