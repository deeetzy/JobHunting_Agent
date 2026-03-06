import asyncio
import sqlite3
import os
import requests
from google import genai
from playwright.async_api import async_playwright

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# --- 1. CONFIGURATION ---
# IMPORTANT: Delete this key from Google AI Studio after testing and use an Environment Variable!
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

MY_PROFILE = """
I am an IT student at Universitatea Politehnica Timisoara. 
Skills: Python, Java, SQL, Web Automation.
Goal: Find an Internship or Working Student (Werkstudent) role in Hamburg.
"""

# --- 2. DATABASE LOGIC ---
def setup_db():
    conn = sqlite3.connect('hamburg_jobs.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS jobs 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, link TEXT UNIQUE)''')
    conn.commit()
    return conn

# --- 3. AI LOGIC ---
async def ask_gemini(job_title, job_desc):
    prompt = f"Profile: {MY_PROFILE}\n\nJob: {job_title}\nDesc: {job_desc}\n\n" \
             "Task: Is this a match for an IT student? List 3 key skills and a 2-sentence application pitch."
    try:
        # Using Gemini 2.0 Flash for speed and intelligence
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"AI Analysis failed: {e}"

# --- 4. MAIN AGENT ---
async def run_agent():
    db_conn = setup_db()
    cursor = db_conn.cursor()
    
    async with async_playwright() as p:
        # headless=False lets you see the bot work
        browser = await p.chromium.launch(headless=False, slow_mo=800)
        page = await browser.new_page()
        
        url = "https://www.otto.de/jobs/de/jobsuche/hamburg/"
        print(f"🤖 Agent opening: {url}")
        
        await page.goto(url, wait_until="domcontentloaded")

        # --- STEP A: SMASH POP-UPS ---
        # 1. Cookies (The teal 'OK' button)
        try:
            print("Trying to click the 'OK' button...")
            ok_btn = page.get_by_role("button", name="OK", exact=True)
            await ok_btn.wait_for(state="visible", timeout=7000)
            await ok_btn.click()
            print("✅ Cookies cleared.")
        except: 
            print("ℹ️ Cookie button not found.")

        # 2. Language Preference
        try:
            print("Checking for language preference...")
            language_locator = page.locator("text='Stay on German page'").first
            if await language_locator.is_visible(timeout=5000):
                await language_locator.click(force=True)
                print("✅ Language pop-up dismissed.")
        except:
            print("ℹ️ Language pop-up not found.")

        # --- STEP B: WAKE UP THE PAGE (Scroll Logic) ---
        print("Ensuring job section is in view...")
        await page.mouse.wheel(0, 2000)
        await asyncio.sleep(2) 
        await page.evaluate("window.scrollTo(0, 0)")
        
# --- STEP 4: CLEAN GRAB & FILTER ---
        print("🔍 Filtering for real IT jobs...")
        
        # 1. DEFINE FILTERS
        # Only analyze if title contains these
        it_keywords = ['developer', 'it ', 'projekt manager', 'engineer', 'data', 'software', 'praktikant', 'intern', 'student', 'cloud']
        # IGNORE if title contains these (Navigation/Info pages)
        noise_words = ['onboarding', 'berufserfahrene', 'schüler', 'studierende', 'einstiegsbereiche', 'kultur', 'vision', 'vorteile', 'news']

        all_links = await page.query_selector_all('a[href*="/jobs/"]')
        new_jobs_count = 0

        for el in all_links:
            link = await el.get_attribute('href')
            if not link: continue
            
            full_link = f"https://www.otto.de{link}" if link.startswith('/') else link
            raw_text = await el.inner_text()
            if not raw_text: continue
            
            title = raw_text.split('\n')[0].strip()
            title_lower = title.lower()

            # Apply Filter Logic
            is_it_job = any(word in title_lower for word in it_keywords)
            is_noise = any(word in title_lower for word in noise_words)

            # ONLY proceed if it's a tech job and NOT navigation noise
            if is_it_job and not is_noise:
                try:
                    cursor.execute('INSERT INTO jobs (title, link) VALUES (?, ?)', (title, full_link))
                    db_conn.commit()
                    
                    print(f"🎯 REAL JOB FOUND: {title}")
                    new_jobs_count += 1
                    # Telegram Notification
                    msg = f"🚀 *New IT Job in Hamburg!*\n\n*Title:* {title}\n\n({full_link})"
                    send_telegram_msg(msg)

                except sqlite3.IntegrityError:
                    continue # Already in DB, skip

        print(f"\n🏁 Finished! Added {new_jobs_count} new IT/Student jobs to your database.")
        await browser.close()
        db_conn.close()

if __name__ == "__main__":
    asyncio.run(run_agent())