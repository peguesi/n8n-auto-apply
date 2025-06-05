

import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import os

OUTPUT_DIR = "debug"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def export_html(url: str, output_name: str):
    async with async_playwright() as p:
        browser = await p.webkit.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url)
        await page.wait_for_timeout(5000)  # wait to ensure content loads

        html_content = await page.content()

        timestamp = datetime.utcnow().isoformat()
        file_path = os.path.join(OUTPUT_DIR, f"{output_name}_{timestamp}.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"[+] HTML content saved to {file_path}")
        await browser.close()

if __name__ == "__main__":
    test_url = "https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&location=Germany"
    asyncio.run(export_html(test_url, "linkedin_test"))