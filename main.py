import asyncio
import json
import random
import re
import sys
import math
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Persistent browser profile dir — accumulates cookies/history across runs to build reCAPTCHA trust score
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'browser_profile')

# Global to track current mouse coordinates
current_mouse_x = 0
current_mouse_y = 0

async def move_mouse_humanlike(page, target_x, target_y, steps=25):
    global current_mouse_x, current_mouse_y

    if current_mouse_x == 0 and current_mouse_y == 0:
        viewport = page.viewport_size
        width = viewport['width'] if viewport else 1280
        height = viewport['height'] if viewport else 800
        current_mouse_x = random.randint(100, width - 100)
        current_mouse_y = random.randint(100, height - 100)
        await page.mouse.move(current_mouse_x, current_mouse_y)

    ctrl_x1 = current_mouse_x + (target_x - current_mouse_x) * random.uniform(0.1, 0.4) + random.randint(-40, 40)
    ctrl_y1 = current_mouse_y + (target_y - current_mouse_y) * random.uniform(0.1, 0.4) + random.randint(-40, 40)
    ctrl_x2 = current_mouse_x + (target_x - current_mouse_x) * random.uniform(0.6, 0.9) + random.randint(-40, 40)
    ctrl_y2 = current_mouse_y + (target_y - current_mouse_y) * random.uniform(0.6, 0.9) + random.randint(-40, 40)

    points = []
    for i in range(steps + 1):
        t = math.sin((i / steps) * (math.pi / 2))
        x = ((1 - t) ** 3) * current_mouse_x + 3 * ((1 - t) ** 2) * t * ctrl_x1 + 3 * (1 - t) * (t ** 2) * ctrl_x2 + (t ** 3) * target_x
        y = ((1 - t) ** 3) * current_mouse_y + 3 * ((1 - t) ** 2) * t * ctrl_y1 + 3 * (1 - t) * (t ** 2) * ctrl_y2 + (t ** 3) * target_y
        points.append((x, y))

    for pt_x, pt_y in points:
        jitter_x = pt_x + random.uniform(-1.2, 1.2)
        jitter_y = pt_y + random.uniform(-1.2, 1.2)
        await page.mouse.move(jitter_x, jitter_y)
        await asyncio.sleep(random.uniform(0.004, 0.012))

    await page.mouse.move(target_x, target_y)
    current_mouse_x = target_x
    current_mouse_y = target_y
    await asyncio.sleep(random.uniform(0.08, 0.15))

async def click_element_humanlike(page, selector):
    element = page.locator(selector).first
    await element.scroll_into_view_if_needed()
    box = await element.bounding_box()
    if box:
        target_x = box['x'] + box['width'] * random.uniform(0.2, 0.8)
        target_y = box['y'] + box['height'] * random.uniform(0.2, 0.8)
        await move_mouse_humanlike(page, target_x, target_y)
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.06, 0.14))
        await page.mouse.up()

async def random_mouse_move(page):
    try:
        viewport = page.viewport_size
        width = viewport['width'] if viewport else 1280
        height = viewport['height'] if viewport else 800

        num_movements = random.randint(3, 6)
        for _ in range(num_movements):
            target_x = random.randint(100, width - 100)
            target_y = random.randint(100, height - 100)
            steps = random.randint(15, 35)
            await move_mouse_humanlike(page, target_x, target_y, steps=steps)

            if random.random() < 0.35:
                jitter_x = target_x + random.randint(-4, 4)
                jitter_y = target_y + random.randint(-4, 4)
                await page.mouse.move(jitter_x, jitter_y)
                await asyncio.sleep(random.uniform(0.04, 0.12))

            await asyncio.sleep(random.uniform(0.2, 0.6))
    except Exception:
        pass

async def scroll_page_naturally(page):
    """Simulate reading the page before interacting — helps reCAPTCHA score."""
    try:
        scroll_down = random.randint(80, 250)
        await page.evaluate(f'window.scrollBy({{top: {scroll_down}, behavior: "smooth"}})')
        await asyncio.sleep(random.uniform(0.6, 1.4))
        scroll_back = random.randint(20, 60)
        await page.evaluate(f'window.scrollBy({{top: -{scroll_back}, behavior: "smooth"}})')
        await asyncio.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass

def validate_rego(rego: str) -> bool:
    if not rego:
        return False
    if not re.match(r'^[A-Za-z0-9]{1,8}$', rego):
        return False
    return True

async def fetch_rego_details(plate_number: str):
    global current_mouse_x, current_mouse_y
    current_mouse_x = 0
    current_mouse_y = 0

    if not validate_rego(plate_number):
        print(json.dumps({"error": "Invalid registration number format. Must be up to 8 alphanumeric characters."}))
        return

    os.makedirs(PROFILE_DIR, exist_ok=True)

    async with async_playwright() as p:
        # Use real Chrome (channel='chrome') for an authentic browser fingerprint.
        # Persistent context saves cookies/history between runs, building reCAPTCHA trust over time.
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel='chrome',
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-infobars',
            ],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            viewport={'width': random.randint(1240, 1360), 'height': random.randint(780, 860)},
            locale='en-AU',
            timezone_id='Australia/Sydney',
            extra_http_headers={
                'Accept-Language': 'en-AU,en;q=0.9',
            },
        )

        page = await context.new_page()

        # Patch the few navigator properties that even real Chrome exposes under automation
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-AU', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            window.chrome = { runtime: {} };
        """)

        # Apply playwright-stealth patches on top
        await Stealth().apply_stealth_async(page)

        try:
            target_url = 'https://check-registration.service.nsw.gov.au/frc?isLoginRequired=true'
            plate_upper = plate_number.upper()

            await page.goto(target_url)
            await page.wait_for_load_state('networkidle')

            # Read the page naturally before touching any controls
            await scroll_page_naturally(page)
            await random_mouse_move(page)

            input_selector = '#plateNumberInput'
            try:
                await page.wait_for_selector(input_selector, timeout=10000)
            except Exception:
                print(json.dumps({"error": "Could not find the registration input field. The site may be down or has a different layout."}))
                return

            await click_element_humanlike(page, input_selector)
            await asyncio.sleep(random.uniform(0.2, 0.4))

            await page.keyboard.press('Control+a')
            await asyncio.sleep(random.uniform(0.05, 0.1))

            for char in plate_upper:
                await page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.08, 0.18))

            await asyncio.sleep(random.uniform(0.4, 0.8))

            terms_selector = '#termsAndConditions'
            try:
                await page.wait_for_selector(terms_selector, timeout=5000)
                if not await page.locator(terms_selector).is_checked():
                    await click_element_humanlike(page, terms_selector)
                    await asyncio.sleep(random.uniform(0.5, 1.0))
            except Exception:
                pass

            await random_mouse_move(page)

            try:
                await click_element_humanlike(page, 'button:has-text("Check registration")')
            except Exception as e:
                print(json.dumps({"error": f"Failed to click the submit button. Error: {str(e)}"}))
                return

            # 120s timeout lets the user solve a reCAPTCHA manually if one appears
            try:
                await page.wait_for_selector('text="Make"', timeout=120000)
            except Exception as wait_err:
                if not page.is_closed():
                    try:
                        body_text = await page.inner_text("body")
                        if "unexpected error occurred" in body_text or "complete the reCAPTCHA" in body_text:
                            print(json.dumps({"error": "reCAPTCHA verification was not completed."}))
                        elif "Enter a NSW number plate" in body_text:
                            print(json.dumps({"error": "Plate number not found or invalid format."}))
                        else:
                            print(json.dumps({"error": f"Results not found or CAPTCHA blocked the request: {str(wait_err)}"}))
                    except Exception as inner_err:
                        print(json.dumps({"error": f"Wait for selector failed: {str(wait_err)}. Inner error: {str(inner_err)}"}))
                else:
                    print(json.dumps({"error": f"Page was closed during execution. Wait for selector failed: {str(wait_err)}"}))
                return

            await asyncio.sleep(1)

            details = {}
            keys_to_extract = ["Make", "Model", "Variant", "Colour", "Shape", "Manufacture year"]

            for key in keys_to_extract:
                try:
                    label_locator = page.locator(f'text="{key}"').first
                    value = await label_locator.evaluate('''el => {
                        let next = el.nextElementSibling;
                        if (next) return next.innerText.trim();
                        if (el.parentElement && el.parentElement.nextElementSibling) {
                            return el.parentElement.nextElementSibling.innerText.trim();
                        }
                        return null;
                    }''')
                    details[key] = value if value else "Not found"
                except Exception:
                    details[key] = "Error extracting"

            print(json.dumps(details, indent=4))

        except Exception as e:
            print(json.dumps({"error": str(e)}))
        finally:
            await context.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        rego_to_check = sys.argv[1]
    else:
        rego_to_check = input("Enter Registration Number: ").strip()

    asyncio.run(fetch_rego_details(rego_to_check))
