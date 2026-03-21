import asyncio
import random
import os
import pytz
import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from datetime import datetime


# läd Variablen aus .env
load_dotenv()

def send_telegram_message(message):
    token = os.getenv("TELEGRAM_API_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Fehler beim Senden der Telegram-Nachricht: {e}")

def send_telegram_photo(caption, photo_path):
    token = os.getenv("TELEGRAM_API_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: 
        return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            payload = {'chat_id': chat_id, 'caption': caption}
            requests.post(url, data=payload, files=files, timeout=30)
    except Exception as e:
        print(f"Fehler beim Senden des Fotos: {e}")

async def human_delay(min_ms=500, max_ms=1500):
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

async def run_bot():
    email = os.getenv("WG_EMAIL")
    password = os.getenv("WG_PASSWORD")
    asset_ids_raw = os.getenv("ASSET_IDS")

    async with Stealth().use_async(async_playwright()) as p:
        # 1. Browser und dynamischer User Agend (UA)
        browser = await p.chromium.launch(headless=True)

        temp_page = await browser.new_page()
        clean_ua = (await temp_page.evaluate("navigator.userAgent")).replace("HeadlessChrome", "Chrome")
        await temp_page.close()

        # Arbeits-Kontext mit dem sauberen UA starten
        context = await browser.new_context(user_agent=clean_ua, viewport={'width': 1920, 'height': 1080})
        #context.set_default_timeout(5000)
        #context.set_default_navigation_timeout(15000)
        page = await context.new_page()

        print(f"Bot startet mit UA: {clean_ua}")

        try:
            await page.goto("https://www.wg-gesucht.de/", wait_until="networkidle")
            await human_delay()

            # 2. Cookie-Banner akzeptieren (falls vorhanden)
            try:
                await page.locator('a[role="button"]:has(#cmpbntyestxt)').click()
            except:
                print("Keinen Cookie-Bannder gefunden.")

            # 3. Login
            account_trigger = page.locator('nav.navbar').get_by_text('Mein Konto')
            # await page.locator('nav.navbar').locator('a[onclick*="sign_in"]').click()
            await account_trigger.click()
            await human_delay()

            # playwright wartet automatisch vor fill, click und check bis das Element handlungsbereit ist
            await page.locator('#login_email_username').fill(email)
            await human_delay()
            await page.locator('#login_password').fill(password)
            await human_delay()
            await page.locator('#login_submit').click()
            await human_delay()

            # 4. Anzeigen aufrufen
            await account_trigger.hover()
            dropdown_content = page.locator(".dropdown-mini-content")
            await dropdown_content.wait_for(state="visible")
            await dropdown_content.get_by_text('Meine Anzeigen').click()
            my_offers_url = "https://www.wg-gesucht.de/meine-anzeigen.html"
            await page.wait_for_url(my_offers_url)

            # 5. Anzeigen bearbeiten / aktualisieren
            my_offers = page.locator('#my_offers')
            asset_ids = asset_ids_raw.split(",")
            for aid in asset_ids:
                try:
                    three_dots = my_offers.locator(f'span[data-asset_id="{aid}"]')
                    await three_dots.click()
                    await human_delay()
                    # dropdown taucht auf, klicke auf Bearbeiten + Fotos
                    dropdown_menu = my_offers.locator(f'#my_asset_{aid}').locator('ul[role="menu"]')
                    await dropdown_menu.wait_for(state="visible")
                    await dropdown_menu.get_by_text('Bearbeiten + Fotos').click()
                    # neue Seite mit Anzeige, scrolle nach unten und klicke auf akualisieren
                    await page.wait_for_url(f"https://www.wg-gesucht.de/angebot-bearbeiten.html?action=update_offer&offer_id={aid}", wait_until='networkidle')
                    update_button = page.locator('#update_offer')
                    await update_button.scroll_into_view_if_needed()
                    await update_button.click()
                    # warte bis "Anzeige aktualisiert" aufgetaucht ist und gehe dann zurück zur Anzeigen-Übersicht
                    await page.locator('#main_content').locator('i.update_offer_message').wait_for(state="visible")
                    await page.screenshot(path="test.png")
                    await page.go_back()
                    await page.wait_for_url(my_offers_url)
                except Exception as e:
                    error_text = f"Anzeige {aid} konnte nicht bearbeitet werden. Details: {str(e)}"
                    print(error_text)
                    await page.screenshot(path="debug.png")
                    send_telegram_photo(error_text, "debug.png")

            await page.screenshot(path="check.png")
            send_telegram_photo("✅ WG-Gesucht: Anzeigen erfolgreich aktualisiert!", "check.png")
            print("Screenshot unter check.png gespeichert.")

        except Exception as e:
            error_msg = f"❌ Fehler: {str(e)}"
            print(error_msg)
            await page.screenshot(path="debug.png")
            send_telegram_photo(
                caption=f"📸:\n{str(e)[:150]}...", # Caption auf 150 Zeichen kürzen
                photo_path="debug.png"
            )
            send_telegram_message(error_msg)

        finally:
            await browser.close()


async def main():
    tz_berlin = pytz.timezone('Europe/Berlin')
    while True:
        now = datetime.now(tz_berlin)
        hour = now.hour

        # Nachtruhe (00:00 bis 07:00 Uhr)
        if 0 <= hour < 7:
            pause_msg = f"[{now.strftime('%H:%M:%S')}] Nachtruhe aktiv. Bot schläft bis 07:00"
            print(pause_msg)
            send_telegram_message(pause_msg)
            # überprüft erneut alle 30 min
            await asyncio.sleep(1800)
            continue

        print(f"[{now.strftime('%H:%M')}]")
        await run_bot()

        # Randomisiertes Intervall: 1 Stunde +/- 15 Minuten (2700 bis 4500 Sek)
        wait_time = random.randint(2700, 4500)

        next_run = wait_time / 60
        after_msg = f"Durchgang beendet. Nächstes Update in ca. {next_run:.1f} Minuten."
        print(after_msg)
        send_telegram_message(after_msg)

        await asyncio.sleep(wait_time)


if __name__ == "__main__":
    asyncio.run(main())

#asyncio.run(run_bot())
