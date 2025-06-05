import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Launch Chromium in headful mode (so you see the window)
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Navigate to LinkedIn (or any URL you want)
        await page.goto("https://www.linkedin.com", wait_until="networkidle")
        
        # Keep the browser open indefinitely (or until you manually close it)
        print("🚀 Browser is open. Log in manually, then press CTRL+C in this terminal to exit.")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())