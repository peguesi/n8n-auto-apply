#!/usr/bin/env python3
"""
Mini LinkedIn Pagination Tester - WITH COOKIE AUTHENTICATION
Focuses purely on testing pagination and job counting with proper login
"""

import asyncio
import os
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

# Get cookie from environment (same as main scraper)
COOKIE = os.getenv("LINKEDIN_COOKIE")
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

async def setup_authenticated_page(context):
    """Set up page with LinkedIn cookie authentication"""
    page = await context.new_page()
    
    if COOKIE:
        print("🔐 Setting up LinkedIn authentication...")
        
        # First navigate to LinkedIn to establish session
        print("🌐 Navigating to LinkedIn homepage first...")
        try:
            await page.goto("https://www.linkedin.com", timeout=30000)
            await page.wait_for_load_state('domcontentloaded', timeout=10000)
            print("✅ LinkedIn homepage loaded")
        except Exception as e:
            print(f"⚠️ Homepage navigation failed: {e}")
        
        # Set the cookie
        await context.add_cookies([{
            'name': 'li_at',
            'value': COOKIE,
            'domain': '.linkedin.com',
            'path': '/'
        }])
        
        # Set user agent
        await page.set_extra_http_headers({
            'User-Agent': USER_AGENT
        })
        
        # Test the authentication by going to a simple LinkedIn page
        print("🔍 Testing authentication...")
        try:
            await page.goto("https://www.linkedin.com/feed", timeout=30000)
            await page.wait_for_load_state('domcontentloaded', timeout=10000)
            
            title = await page.title()
            if "feed" in title.lower() or "linkedin" in title.lower():
                print("✅ Authentication successful!")
            else:
                print(f"⚠️ Authentication may have failed. Title: {title}")
        except Exception as e:
            print(f"⚠️ Auth test failed: {e}")
        
        print("✅ Authentication configured")
    else:
        print("⚠️ No LINKEDIN_COOKIE found in environment!")
    
    return page

async def extract_job_count_methods(page, page_num):
    """Extract job count using multiple methods for debugging"""
    print(f"🔍 Extracting jobs from page {page_num + 1}...")
    
    # Wait for page to settle
    await page.wait_for_timeout(2000)
    
    # Method 1: data-job-id attributes
    method1_count = 0
    try:
        elements = await page.locator("[data-job-id]").all()
        method1_count = len(elements)
        print(f"🎯 Method 1 (data-job-id): {method1_count} elements")
    except Exception as e:
        print(f"❌ Method 1 failed: {e}")
    
    # Method 2: Job view links
    method2_count = 0
    method2_urls = []
    try:
        links = await page.locator("a[href*='/jobs/view/']").all()
        method2_count = len(links)
        print(f"🔗 Method 2 (job links): {method2_count} links")
        
        # Extract a few sample URLs for debugging
        for i, link in enumerate(links[:3]):
            href = await link.get_attribute("href")
            if href:
                method2_urls.append(href)
        
        if method2_urls:
            print(f"📄 Sample URLs: {method2_urls}")
    except Exception as e:
        print(f"❌ Method 2 failed: {e}")
    
    # Method 3: Job cards
    method3_count = 0
    try:
        cards = await page.locator(".jobs-search-card, .job-search-card, .jobs-search-results__list-item").all()
        method3_count = len(cards)
        print(f"🃏 Method 3 (job cards): {method3_count} cards")
    except Exception as e:
        print(f"❌ Method 3 failed: {e}")
    
    # Method 4: Extract job IDs like the main scraper
    method4_ids = set()
    try:
        # Check for data-job-id
        elements = await page.locator("[data-job-id]").all()
        for element in elements:
            job_id = await element.get_attribute("data-job-id")
            if job_id and job_id.isdigit():
                method4_ids.add(job_id)
        
        # Check for job view links
        links = await page.locator("a[href*='/jobs/view/']").all()
        for link in links:
            href = await link.get_attribute("href")
            if href:
                match = re.search(r'/jobs/view/(\d+)', href)
                if match:
                    method4_ids.add(match.group(1))
        
        print(f"🆔 Method 4 (unique IDs): {len(method4_ids)} unique job IDs")
        if len(method4_ids) > 0:
            print(f"📋 Sample IDs: {list(method4_ids)[:5]}")
            
    except Exception as e:
        print(f"❌ Method 4 failed: {e}")
    
    # Return the best count
    max_count = max(method1_count, method2_count, method3_count, len(method4_ids))
    return max_count, list(method4_ids)

async def scroll_and_load_jobs(page):
    """Scroll down to load all jobs on the page"""
    print("📜 Scrolling to load all content...")
    
    # Initial wait
    await page.wait_for_timeout(2000)
    
    # Scroll down in chunks
    for i in range(5):
        await page.evaluate("window.scrollBy(0, 800)")
        await page.wait_for_timeout(1000)
    
    # Scroll to bottom
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(3000)
    
    # Small scroll back up to trigger any lazy loading
    await page.evaluate("window.scrollBy(0, -400)")
    await page.wait_for_timeout(1000)

async def check_login_status(page):
    """Check if we're properly logged in"""
    title = await page.title()
    url = page.url
    
    print(f"📄 Page title: {title}")
    print(f"🌐 Current URL: {url}")
    
    if "sign" in title.lower() or "login" in title.lower():
        print("❌ NOT LOGGED IN - Redirected to login page")
        return False
    
    if "linkedin.com/jobs" in url:
        print("✅ LOGGED IN - On jobs page")
        return True
    
    print("❓ LOGIN STATUS UNCLEAR")
    return True  # Assume OK

async def test_single_page(page, url, page_num):
    """Test a single page and return job count"""
    print(f"\n🌐 Page {page_num + 1}: {url}")
    
    try:
        # Navigate to page with more forgiving settings
        print("📍 Navigating to jobs page...")
        await page.goto(url, timeout=45000, wait_until='domcontentloaded')
        
        # Wait a bit more for content to load
        await page.wait_for_timeout(3000)
        
        # Check login status
        if not await check_login_status(page):
            print("🔄 Trying to navigate to jobs page differently...")
            # Try going to jobs homepage first
            await page.goto("https://www.linkedin.com/jobs/", timeout=30000)
            await page.wait_for_timeout(2000)
            # Then try our specific search
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(3000)
            
            if not await check_login_status(page):
                return 0, []
        
        # Scroll to load content
        await scroll_and_load_jobs(page)
        
        # Extract job counts
        job_count, job_ids = await extract_job_count_methods(page, page_num)
        
        # Save screenshot for debugging
        screenshot_dir = Path("debug_screenshots")
        screenshot_dir.mkdir(exist_ok=True)
        await page.screenshot(path=screenshot_dir / f"page_{page_num + 1}.png", full_page=True)
        
        # Save page HTML for debugging
        html_content = await page.content()
        with open(screenshot_dir / f"page_{page_num + 1}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"📊 Page {page_num + 1}: {job_count} jobs, {len(job_ids)} unique IDs")
        
        return job_count, job_ids
        
    except Exception as e:
        print(f"❌ Error on page {page_num + 1}: {e}")
        
        # Try to save debug info even on error
        try:
            screenshot_dir = Path("debug_screenshots")
            screenshot_dir.mkdir(exist_ok=True)
            await page.screenshot(path=screenshot_dir / f"error_page_{page_num + 1}.png", full_page=True)
            html_content = await page.content()
            with open(screenshot_dir / f"error_page_{page_num + 1}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
        except:
            pass
        
        return 0, []

async def test_linkedin_pagination():
    """Test LinkedIn pagination with proper authentication"""
    
    # Test URL (update this with your actual search URL)
    base_url = "https://www.linkedin.com/jobs/search/?f_WT=1%2C2&geoId=101282230&keywords=Product+Manager&f_TPR=r86400&refresh=true"
    
    print("🚀 Starting LinkedIn Pagination Test with Authentication")
    print("=" * 70)
    print(f"🧪 Testing pagination for: {base_url}")
    print(f"🔐 Using cookie: {'✅ YES' if COOKIE else '❌ NO'}")
    print()
    
    async with async_playwright() as p:
        # Use webkit browser like main scraper
        context = await p.webkit.launch_persistent_context(
            user_data_dir=str(Path.home() / ".pw-session-mini"),
            headless=False,  # Keep visible for debugging
            viewport={"width": 1280, "height": 800}
        )
        
        page = await setup_authenticated_page(context)
        
        all_job_ids = set()
        total_jobs = 0
        
        # Test first 5 pages manually
        for page_num in range(5):
            # Construct URL with start parameter
            if page_num == 0:
                test_url = base_url
            else:
                separator = '&' if '?' in base_url else '?'
                test_url = f"{base_url}{separator}start={page_num * 25}"
            
            job_count, job_ids = await test_single_page(page, test_url, page_num)
            
            if job_count == 0:
                print(f"🛑 No jobs found on page {page_num + 1}")
                if page_num == 0:
                    print("❌ No jobs on first page - something is wrong!")
                    break
                else:
                    print(f"✅ Reached end of results after {page_num} pages")
                    break
            
            # Track unique jobs
            before_count = len(all_job_ids)
            all_job_ids.update(job_ids)
            after_count = len(all_job_ids)
            new_jobs = after_count - before_count
            
            total_jobs += job_count
            print(f"🎉 Page {page_num + 1}: Found {job_count} total, {new_jobs} new unique jobs")
            print(f"📊 Total so far: {len(all_job_ids)} unique jobs")
            
            # Small delay between pages
            await asyncio.sleep(2)
        
        await context.close()
        
        # Final results
        print(f"\n🎯 PAGINATION TEST RESULTS:")
        print("=" * 50)
        print(f"📈 Total unique jobs found: {len(all_job_ids)}")
        print(f"📄 Pages tested: {min(5, page_num + 1)}")
        print(f"🔄 Authentication: {'✅ SUCCESS' if COOKIE else '❌ MISSING COOKIE'}")
        
        # Save results for analysis
        results = {
            "total_unique_jobs": len(all_job_ids),
            "job_ids": list(all_job_ids)[:10],  # First 10 for debugging
            "pages_tested": min(5, page_num + 1),
            "authenticated": bool(COOKIE),
            "test_url": base_url
        }
        
        with open("pagination_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"💾 Test results saved to pagination_test_results.json")
        
        if len(all_job_ids) >= 25:
            print("🎉 SUCCESS! Found 25+ jobs - pagination is working!")
        elif len(all_job_ids) > 0:
            print("⚠️ PARTIAL SUCCESS! Found some jobs but may need investigation")
        else:
            print("😞 FAILED! No jobs found - check authentication and URL")
        
        return len(all_job_ids)

if __name__ == "__main__":
    asyncio.run(test_linkedin_pagination())