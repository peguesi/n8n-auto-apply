"""
LinkedIn Job Scraper - Enhanced with Pagination and Comprehensive Features
- URL-Based Strategy with currentJobId parameter
- Complete pagination support (all pages, all jobs)
- Enhanced job extraction with multiple strategies
- Azure OpenAI description cleaning with smart fallbacks
- Rate limiting and retry logic
- Comprehensive logging and error handling
- Production-ready enhancements
"""

import asyncio
import json
import os
import re
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright
import httpx
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

load_dotenv()

# Configuration
COOKIE = os.getenv("LINKEDIN_COOKIE")
USER_AGENT = os.getenv("USER_AGENT")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:5678/webhook/new-job")
JOBS_SEEN_PATH = Path("data/jobs_seen.json")
SNAPSHOT_DIR = Path("data/job_snapshots")

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('linkedin_scraper.log'),
        logging.StreamHandler()
    ]
)

def load_seen_jobs():
    """Load previously seen job IDs"""
    if JOBS_SEEN_PATH.exists():
        return set(json.loads(JOBS_SEEN_PATH.read_text()))
    return set()

def save_seen_jobs(seen):
    """Save seen job IDs to file"""
    JOBS_SEEN_PATH.write_text(json.dumps(list(seen), indent=2))

async def post_job_to_webhook(payload):
    """Post job data to webhook endpoint"""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(WEBHOOK_URL, json=payload)
            r.raise_for_status()
        except Exception as e:
            logging.warning(f"Failed to POST job {payload['id']} to webhook: {e}")

def normalize_search_url(url):
    """
    Normalize a LinkedIn search URL by removing unnecessary parameters
    and ensuring it's ready for pagination
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    # Keep only essential parameters
    essential_params = {
        'f_WT': params.get('f_WT', ['2']),  # Remote work filter
        'geoId': params.get('geoId', []),   # Location
        'keywords': params.get('keywords', []),  # Search terms
        'refresh': ['true'],  # Always refresh
        'distance': params.get('distance', ['25']),  # Search radius
        'f_TPR': params.get('f_TPR', []),   # Time posted filter
        'f_C': params.get('f_C', []),       # Company filter
        'f_E': params.get('f_E', []),       # Experience level
        'sortBy': params.get('sortBy', [])  # Sort order
    }
    
    # Remove empty parameters
    clean_params = {k: v for k, v in essential_params.items() if v and v[0]}
    
    # Build clean URL
    clean_query = urlencode(clean_params, doseq=True)
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', clean_query, ''))
    
    return clean_url

def add_pagination_to_url(base_url, page_start):
    """Add pagination parameter to URL"""
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query)
    
    if page_start > 0:
        params['start'] = [str(page_start)]
    elif 'start' in params:
        del params['start']
    
    # Remove currentJobId to avoid conflicts
    if 'currentJobId' in params:
        del params['currentJobId']
    
    new_query = urlencode(params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', new_query, ''))


# New version: extract_job_ids_from_search_page
async def extract_job_ids_from_search_page(page, page_num=0):
    """
    Extract job IDs from a LinkedIn search results page using robust strategies.
    """
    job_ids = set()
    print(f"[ENHANCED] Extracting job IDs from search page {page_num + 1}...")
    try:
        await page.wait_for_selector('.jobs-search-results-list', timeout=10000)
    except Exception:
        logging.warning(f"[ENHANCED] Could not find results container on page {page_num + 1}")

    # 1. Extract from job cards with data-job-id
    try:
        cards = await page.locator("[data-job-id]").all()
        print(f"[ENHANCED] Found {len(cards)} cards with data-job-id")
        for card in cards:
            job_id = await card.get_attribute("data-job-id")
            if job_id and job_id.isdigit():
                job_ids.add(job_id)
    except Exception as e:
        logging.warning(f"[ENHANCED] data-job-id extraction failed: {e}")

    # 2. Extract from job links (fallback)
    try:
        links = await page.locator("a[href*='/jobs/view/']").all()
        print(f"[ENHANCED] Found {len(links)} job view links")
        for link in links:
            href = await link.get_attribute("href")
            if href:
                match = re.search(r'/jobs/view/(\d+)', href)
                if match:
                    job_ids.add(match.group(1))
    except Exception as e:
        logging.warning(f"[ENHANCED] /jobs/view/ link extraction failed: {e}")

    # 3. Extract from data-entity-urn
    try:
        urns = await page.locator("[data-entity-urn*='job']").all()
        print(f"[ENHANCED] Found {len(urns)} elements with data-entity-urn")
        for el in urns:
            urn = await el.get_attribute("data-entity-urn")
            if urn:
                m = re.search(r':job:(\d+)', urn)
                if m:
                    job_ids.add(m.group(1))
    except Exception as e:
        logging.warning(f"[ENHANCED] data-entity-urn extraction failed: {e}")

    # 4. Extract from page content (backup)
    try:
        content = await page.content()
        patterns = [
            r'"jobPostingId":"(\d+)"',
            r'"entityUrn":"urn:li:job:(\d+)"',
            r'data-job-id="(\d+)"',
            r'/jobs/view/(\d+)',
        ]
        for pat in patterns:
            for match in re.findall(pat, content):
                if match.isdigit():
                    job_ids.add(match)
    except Exception as e:
        logging.warning(f"[ENHANCED] page content extraction failed: {e}")

    unique_job_ids = list(job_ids)
    print(f"[ENHANCED] Page {page_num + 1}: Found {len(unique_job_ids)} unique job IDs")
    return unique_job_ids
# Enhanced pagination check (insert below imports and utility definitions)
async def check_pagination_available_enhanced(page):
    """
    Enhanced check for whether more pages are available in LinkedIn search results.
    Returns True if 'Next' button is enabled or more jobs are present.
    """
    try:
        # Check for enabled 'Next' button
        next_button = page.locator("button[aria-label='Next']").first
        if await next_button.count() > 0:
            is_disabled = await next_button.get_attribute("disabled")
            if not is_disabled:
                return True
        # Alternative: check for less than 25 jobs (end of results)
        job_count = len(await extract_job_ids_from_search_page(page))
        if job_count < 25:
            return False
        return True
    except Exception as e:
        logging.warning(f"[ENHANCED] Pagination check failed: {e}")
        return False

async def check_pagination_available(page):
    """Check if more pages are available"""
    try:
        # Look for pagination indicators
        pagination_selectors = [
            "button[aria-label='Next']",
            ".artdeco-pagination__button--next",
            "[data-test-pagination-page-btn]",
            ".jobs-search-results-list__pagination"
        ]
        
        for selector in pagination_selectors:
            elements = await page.locator(selector).all()
            if elements:
                for element in elements:
                    is_disabled = await element.get_attribute("disabled")
                    if not is_disabled:
                        return True
        
        # Alternative: Check if current page has fewer than 25 jobs
        job_count = len(await extract_job_ids_from_search_page(page))
        if job_count < 25:
            return False
            
        return True
        
    except Exception as e:
        logging.warning(f"Pagination check failed: {e}")
        return False


# New version: scrape_all_pages
async def scrape_all_pages(page, base_search_url, max_pages=20):
    """
    Scrape all pages using robust pagination and job ID extraction.
    Uses the enhanced extract_job_ids_from_search_page and checks for next page.
    """
    all_job_ids = set()
    page_num = 0
    clean_base_url = normalize_search_url(base_search_url)
    print(f"[ALL PAGES] Normalized base URL: {clean_base_url}")
    while page_num < max_pages:
        page_start = page_num * 25
        current_url = add_pagination_to_url(clean_base_url, page_start)
        print(f"\n[ALL PAGES {page_num + 1}] Loading: {current_url}")
        try:
            await page.goto(current_url, timeout=60000)
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                logging.warning(f"[ALL PAGES] Page load timeout: {e}")
            page_title = await page.title()
            current_page_url = page.url
            if "sign" in page_title.lower() or "login" in page_title.lower():
                logging.error("[ALL PAGES] Redirected to login page")
                break
            if "challenge" in current_page_url.lower() or "captcha" in page_title.lower():
                logging.error("[ALL PAGES] Blocked by captcha/challenge")
                break
            # Scroll to bottom to load all jobs
            for _ in range(2):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1200)
            # Extract job IDs using new function
            page_job_ids = await extract_job_ids_from_search_page(page, page_num)
            if not page_job_ids:
                print(f"[ALL PAGES] No jobs found on page {page_num + 1}, stopping pagination")
                break
            before = len(all_job_ids)
            all_job_ids.update(page_job_ids)
            after = len(all_job_ids)
            print(f"[ALL PAGES] Page {page_num + 1}: {len(page_job_ids)} jobs, {after-before} new")
            # If less than 25 jobs, likely last page
            if len(page_job_ids) < 25:
                print(f"[ALL PAGES] Page {page_num + 1} has <25 jobs, ending")
                break
            page_num += 1
            await asyncio.sleep(random.uniform(1.5, 3))
        except Exception as e:
            logging.error(f"[ALL PAGES] Failed to process page {page_num + 1}: {e}")
            break
    print(f"\n[ALL PAGES SUMMARY] Collected {len(all_job_ids)} unique job IDs across {page_num + 1} pages")
    return list(all_job_ids)

async def scrape_job_with_retry(page, job_id, base_search_url, max_retries=3):
    """Retry job scraping with exponential backoff"""
    for attempt in range(max_retries):
        try:
            result = await scrape_job_by_id(page, job_id, base_search_url)
            if result:
                return result
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1}/{max_retries} failed for job {job_id}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return None


async def safe_get_text(locator, field_name="field"):
    """Safely get text content with better error handling"""
    try:
        if await locator.count() > 0:
            text = await locator.text_content()
            if text and text.strip():
                return text.strip()
    except Exception as e:
        logging.warning(f"Failed to extract {field_name}: {e}")
    return None


# Enhanced job description extraction function
async def extract_job_description(page, job_id):
    """
    Extract the job description using multiple robust strategies.
    Returns the best available description (or None).
    """
    # Try a prioritized list of selectors for job description
    description_selectors = [
        ".jobs-description-content__text",
        ".jobs-description__content",
        ".job-details-jobs-unified-top-card__job-description",
        "[data-test-id='job-description']",
        ".description__text",
        ".jobs-description",
        ".jobs-box__html-content",
        ".jobs-box__content",
        "section.show-more-less-html__markup",
    ]
    description = None
    for selector in description_selectors:
        try:
            desc_element = page.locator(selector).first
            if await desc_element.count() > 0:
                desc_text = await desc_element.text_content()
                if desc_text and len(desc_text.strip()) > 50:
                    description = desc_text.strip()
                    print(f"[extract_job_description] Found description with selector {selector}: {len(description)} chars")
                    break
        except Exception as e:
            logging.debug(f"[extract_job_description] Selector {selector} failed: {e}")

    # Fallback: try to extract from page HTML using regex
    if not description:
        try:
            html = await page.content()
            patterns = [
                r'"description":"(.*?)",',  # JSON embedded description
                r'<section[^>]+class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(.*?)</section>',
            ]
            for pat in patterns:
                matches = re.findall(pat, html, re.DOTALL)
                for match in matches:
                    text = re.sub(r"<[^>]+>", "", match)  # Remove HTML tags
                    text = text.strip()
                    if text and len(text) > 50:
                        description = text
                        print(f"[extract_job_description] Found description via regex ({len(description)} chars)")
                        break
                if description:
                    break
        except Exception as e:
            logging.debug(f"[extract_job_description] Regex fallback failed: {e}")

    # Last resort: try all <section> elements for long text
    if not description:
        try:
            sections = await page.locator("section").all()
            for section in sections:
                txt = await section.text_content()
                if txt and len(txt.strip()) > 100:
                    description = txt.strip()
                    print(f"[extract_job_description] Fallback section: {len(description)} chars")
                    break
        except Exception as e:
            logging.debug(f"[extract_job_description] <section> fallback failed: {e}")

    if not description:
        print(f"[extract_job_description] No substantial description found for job {job_id}")
    return description


# Lenient version: validate_job_data
def validate_job_data(payload):
    """
    Lenient validation for scraped job data.
    Only ensures required fields are present and not empty.
    """
    required_fields = ['title', 'company']
    for field in required_fields:
        if not payload.get(field) or payload[field].strip().lower().startswith("unknown"):
            return False
    # Allow short descriptions, just ensure it's present
    if 'description' not in payload or not payload['description']:
        return False
    return True

def parse_posted_time(time_str):
    """Parse LinkedIn's relative time format"""
    if not time_str:
        return None
    
    time_str = time_str.lower()
    now = datetime.now()
    
    if 'hour' in time_str:
        hours = int(re.search(r'(\d+)', time_str).group(1))
        return now - timedelta(hours=hours)
    elif 'day' in time_str:
        days = int(re.search(r'(\d+)', time_str).group(1))
        return now - timedelta(days=days)
    elif 'week' in time_str:
        weeks = int(re.search(r'(\d+)', time_str).group(1))
        return now - timedelta(weeks=weeks)
    
    return None

def is_job_fresh(posted_time_str, max_age_hours=24):
    """Check if job was posted within the specified timeframe"""
    posted_date = parse_posted_time(posted_time_str)
    if not posted_date:
        return True  # If we can't parse, include it
    
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    return posted_date >= cutoff

async def scrape_job_by_id(page, job_id, base_search_url):
    """Navigate to specific job using currentJobId parameter and scrape details"""
    
    # Construct URL with currentJobId parameter
    clean_base_url = normalize_search_url(base_search_url)
    if '?' in clean_base_url:
        job_url = f"{clean_base_url}&currentJobId={job_id}"
    else:
        job_url = f"{clean_base_url}?currentJobId={job_id}"
    
    try:
        print(f"[DEBUG] Navigating to job URL: {job_url}")
        await page.goto(job_url, timeout=45000)
        
        # Use more lenient loading strategy
        try:
            await page.wait_for_load_state('domcontentloaded', timeout=15000)
            await page.wait_for_timeout(2000)  # Let content settle
        except Exception as e:
            logging.warning(f"Load state timeout for job {job_id}: {e}")
        
        # Check if page loaded correctly
        current_url = page.url
        page_title = await page.title()
        print(f"[DEBUG] Job page title: {page_title}")
        
        if "sign" in page_title.lower() or "login" in current_url.lower():
            logging.error(f"Redirected to login for job {job_id}")
            return None
        
        # Initialize variables
        title = None
        company = None
        location = None
        description = None
        time_posted = None
        
        # Title selectors (try multiple)
        title_selectors = [
            "h1.top-card-layout__title",
            "h1.t-24",
            "h2.topcard__title", 
            ".job-details-jobs-unified-top-card__job-title",
            "[data-test-id='job-title']"
        ]
        
        for selector in title_selectors:
            try:
                title_element = page.locator(selector).first
                if await title_element.count() > 0:
                    title = await title_element.text_content()
                    if title and title.strip():
                        print(f"[DEBUG] Found title with selector {selector}: {title.strip()}")
                        break
            except:
                continue
        
        # Company selectors
        company_selectors = [
            "a.topcard__org-name-link",
            ".job-details-jobs-unified-top-card__company-name",
            ".topcard__flavor--black-link",
            "[data-test-id='job-company']"
        ]
        
        for selector in company_selectors:
            try:
                company_element = page.locator(selector).first
                if await company_element.count() > 0:
                    company = await company_element.text_content()
                    if company and company.strip():
                        print(f"[DEBUG] Found company with selector {selector}: {company.strip()}")
                        break
            except:
                continue
        
        # Location selectors
        location_selectors = [
            ".topcard__flavor--bullet",
            ".job-details-jobs-unified-top-card__primary-description",
            ".job-details-jobs-unified-top-card__bullets li:first-child",
            "span.topcard__flavor",
            "[data-test-id='job-location']"
        ]
        
        for selector in location_selectors:
            try:
                location_element = page.locator(selector).first
                if await location_element.count() > 0:
                    location = await location_element.text_content()
                    if location and location.strip():
                        print(f"[DEBUG] Found location with selector {selector}: {location.strip()}")
                        break
            except:
                continue
        
        # Extract description using enhanced method
        description = await extract_job_description(page, job_id)
        
        # Time posted selectors
        time_selectors = [
            ".posted-time-ago__text",
            ".job-details-jobs-unified-top-card__primary-description time",
            ".jobs-unified-top-card__subtitle-secondary-grouping time",
            "time[datetime]",
            "[data-test-id='job-posted-date']",
            ".topcard__flavor--metadata"
        ]
        
        for selector in time_selectors:
            try:
                time_element = page.locator(selector).first
                if await time_element.count() > 0:
                    time_posted = await time_element.text_content()
                    if time_posted and time_posted.strip():
                        print(f"[DEBUG] Found time posted with selector {selector}: {time_posted.strip()}")
                        break
            except:
                continue
        
        # Save debug screenshot and HTML
        screenshot_path = Path(f"data/linkedin/{datetime.utcnow().date()}/screenshots")
        screenshot_path.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=screenshot_path / f"job_{job_id}.png", full_page=True)

        debug_html = await page.content()
        html_path = Path(f"data/linkedin/{datetime.utcnow().date()}/html")
        html_path.mkdir(parents=True, exist_ok=True)
        (html_path / f"job_{job_id}.html").write_text(debug_html)
        
        # Clean job description by removing irrelevant sections
        def clean_description_basic(raw_text):
            """Basic cleaning without AI"""
            sections_to_remove = ["about us", "about the company", "what we offer", "benefits", "how to apply", "join us", "company overview"]
            lines = raw_text.splitlines()
            cleaned_lines = []
            skip = False
            for line in lines:
                if any(heading in line.lower() for heading in sections_to_remove):
                    skip = True
                if not skip and line.strip():
                    cleaned_lines.append(line)
            return "\n".join(cleaned_lines).strip()

        if description:
            description = clean_description_basic(description)

        # Build initial payload
        payload = {
            "id": f"linkedin_{job_id}",
            "title": title.strip() if title else "Unknown Title",
            "company": company.strip() if company else "Unknown Company", 
            "location": location.strip() if location else "Unknown Location",
            "url": job_url,
            "description": description.strip() if description else "No description found",
            "description_char_count": len(description.strip()) if description else 0,
            "posted_time": time_posted.strip() if time_posted else "Unknown",
            "source": "linkedin",
            "scraped_at": datetime.utcnow().isoformat(),
            "pagination_source": "enhanced_scraper"
        }
        
        # Enhanced Azure OpenAI description cleaning
        if description and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY:
            try:
                from openai import AzureOpenAI

                # Save the original description before modification
                original_description = payload['description']
                original_length = len(original_description)

                # Skip cleaning if description is already too short
                if original_length < 200:
                    print(f"[SKIP] Description too short to clean ({original_length} chars), using original")
                    payload['description'] = original_description
                    payload['description_char_count'] = original_length
                    return payload
                else:
                    # Initialize the Azure OpenAI client
                    client = AzureOpenAI(
                        azure_endpoint=AZURE_OPENAI_ENDPOINT,
                        api_key=AZURE_OPENAI_KEY,
                        api_version=AZURE_OPENAI_API_VERSION
                    )

                    # Improved cleaning prompt - more conservative
                    clean_prompt = f"""You are helping to clean a job description by removing ONLY non-essential sections while preserving all job-relevant content.

REMOVE ONLY these types of sections if they are clearly separate from job requirements:
• Company benefits sections (health insurance, 401k, vacation, perks)
• Company culture/values sections (unless directly related to job requirements)
• Generic calls to action ("Apply now!", "Join our team!")
• Company history/overview (unless relevant to the role)

ALWAYS PRESERVE:
• Job responsibilities and duties
• Required qualifications and skills
• Preferred qualifications
• Technical requirements
• Experience requirements
• Education requirements
• Tools and technologies mentioned
• Salary/compensation information
• Location and work arrangement details
• Reporting structure
• Project descriptions

IMPORTANT RULES:
1. If unsure whether to remove something, KEEP IT
2. Do not paraphrase or rewrite any content - only remove complete sections
3. Maintain original formatting and structure
4. If the description is mostly job requirements, return it nearly unchanged
5. Return the cleaned description directly without explanations

JOB DESCRIPTION:
{payload['description']}"""

                    try:
                        response = client.chat.completions.create(
                            model=AZURE_OPENAI_DEPLOYMENT_NAME,
                            messages=[
                                {
                                    "role": "user",
                                    "content": clean_prompt
                                }
                            ],
                            max_tokens=1500,  # Increased token limit
                            temperature=0.1,  # Lower temperature for more consistent results
                        )

                        cleaned_description = response.choices[0].message.content.strip()
                        cleaned_length = len(cleaned_description)

                        # More intelligent fallback logic
                        should_use_cleaned = True
                        fallback_reason = None

                        # Check 1: Empty or very short result
                        if not cleaned_description or cleaned_length < 100:
                            should_use_cleaned = False
                            fallback_reason = f"Cleaned result too short ({cleaned_length} chars)"

                        # Check 2: AI returned error messages or couldn't process
                        elif any(phrase in cleaned_description.lower() for phrase in [
                            "i cannot", "i can't", "sorry", "unable to", "please provide",
                            "as an ai", "i don't have", "error", "cannot process"
                        ]):
                            should_use_cleaned = False
                            fallback_reason = "AI returned error message"

                        # Check 3: Cleaned version is too much shorter (more than 70% reduction)
                        elif cleaned_length < original_length * 0.3:
                            should_use_cleaned = False
                            fallback_reason = f"Over-trimmed: {original_length} -> {cleaned_length} chars ({(1-cleaned_length/original_length)*100:.1f}% reduction)"

                        # Check 4: Description seems to be mostly job requirements (less than 20% reduction is suspicious)
                        elif cleaned_length > original_length * 0.95:
                            # This is actually good - means the description was already clean
                            print(f"[GOOD] Description was already clean ({original_length} -> {cleaned_length} chars)")

                        if should_use_cleaned:
                            payload['description'] = cleaned_description
                            payload['description_char_count'] = cleaned_length
                            print(f"[CLEANED] Description: {original_length} -> {cleaned_length} chars ({((original_length-cleaned_length)/original_length)*100:.1f}% reduction)")
                        else:
                            print(f"[FALLBACK] {fallback_reason} - using original description")
                            payload['description'] = original_description

                        # Enhanced logging for debugging
                        cleaned_log_path = Path(f"data/linkedin/{datetime.utcnow().date()}/cleaned_log")
                        cleaned_log_path.mkdir(parents=True, exist_ok=True)
                        with open(cleaned_log_path / f"job_{job_id}.json", "w") as debug_f:
                            json.dump({
                                "job_id": job_id,
                                "title": payload.get("title"),
                                "company": payload.get("company"),
                                "original_length": original_length,
                                "cleaned_length": cleaned_length,
                                "used_cleaned": should_use_cleaned,
                                "fallback_reason": fallback_reason,
                                "reduction_percentage": ((original_length-cleaned_length)/original_length)*100 if original_length > 0 else 0,
                                "original_description": original_description,
                                "cleaned_description": (
                                    cleaned_description if should_use_cleaned
                                    else "Original used due to: " + (fallback_reason or "unspecified reason")
                                )
                            }, debug_f, indent=2)

                    except Exception as api_error:
                        logging.error(f"Azure OpenAI API call failed: {api_error}")
                        payload['description'] = original_description

            except Exception as e:
                logging.warning(f"Failed to post-process description with Azure OpenAI: {e}")
                # Keep original description if anything fails
        
        return payload
        
    except Exception as e:
        logging.error(f"Error scraping job {job_id}: {e}")
        return None

async def run_linkedin_scraper_batch(urls):
    """Run the scraper for multiple URLs (for API compatibility)"""
    if not urls:
        return []
    
    # Set override URLs for the main scraper function
    scrape_jobs.override_urls = urls
    
    # Run the main scraping function
    await scrape_jobs()
    
    # Return empty list for now (main function handles file output)
    return []

async def scrape_jobs():
    """Main scraping function using enhanced URL-based strategy with pagination"""
    seen_jobs = load_seen_jobs()
    today = datetime.utcnow().date()
    timestamp = datetime.utcnow().strftime("%H%M%S")
    OUTPUT_PATH = Path(f"data/linkedin/{today}/results_{timestamp}.jsonl")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()
    OUTPUT_PATH.touch()

    # Create symlink to latest results file
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    latest_symlink.parent.mkdir(parents=True, exist_ok=True)
    if latest_symlink.exists() or latest_symlink.is_symlink():
        latest_symlink.unlink()
    latest_symlink.symlink_to(OUTPUT_PATH.resolve())

    # Allow dynamic override of search URLs from FastAPI
    if hasattr(scrape_jobs, "override_urls"):
        print(f"[INFO] Received override URLs: {scrape_jobs.override_urls}")
        base_search_urls = scrape_jobs.override_urls
    else:
        base_search_urls = os.getenv("SEARCH_URLS", "").split(",")
    base_search_urls = [url.strip() for url in base_search_urls if url.strip()]

    if not base_search_urls:
        print("[ERROR] No search URLs provided via override or env. Exiting scrape_jobs().")
        return
    else:
        print(f"[INFO] Using {len(base_search_urls)} search URL(s)")

    async with async_playwright() as p:
        context = await p.webkit.launch_persistent_context(
            user_data_dir=str(Path.home() / ".pw-session"),
            headless=False,
            viewport={"width": 1280, "height": 800}
        )

        page = await context.new_page()

        total_jobs_scraped = 0
        total_jobs_found = 0

        for url_index, base_search_url in enumerate(base_search_urls):
            print(f"\n[+] Processing search URL {url_index + 1}/{len(base_search_urls)}: {base_search_url}")

            try:
                # Scrape all pages to get job IDs with enhanced pagination
                all_job_ids = await scrape_all_pages(page, base_search_url, max_pages=20)
                
                if not all_job_ids:
                    print("[WARN] No job IDs found across all pages")
                    continue

                total_jobs_found += len(all_job_ids)
                print(f"[INFO] Starting to scrape {len(all_job_ids)} individual jobs...")
                
                # Scrape each job with retry logic
                scraped_count = 0
                for i, job_id in enumerate(all_job_ids, 1):
                    if f"linkedin_{job_id}" in seen_jobs:
                        print(f"[SKIP] Job {i}/{len(all_job_ids)}: Already seen {job_id}")
                        continue

                    print(f"[SCRAPE] Job {i}/{len(all_job_ids)}: Processing {job_id}")
                    
                    # Use retry logic for robustness
                    payload = await scrape_job_with_retry(page, job_id, base_search_url, max_retries=3)

                    if payload:
                        # Validate job data quality
                        if not validate_job_data(payload):
                            print(f"[INVALID] Job {job_id} failed validation: {json.dumps(payload, indent=2)}")
                            continue
                        
                        # Check job freshness if needed
                        if not is_job_fresh(payload.get('posted_time', ''), max_age_hours=720):  # 30 days
                            print(f"[OLD] Job {job_id} is too old, skipping")
                            continue

                        # Before writing to file, validate JSON
                        try:
                            json.dumps(payload)
                        except Exception as e:
                            print(f"[ERROR] Invalid payload for job {job_id}: {e}")
                            continue

                        # Save and process the job
                        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
                        with open(SNAPSHOT_DIR / f"linkedin_{job_id}.json", "w") as f:
                            json.dump(payload, f, indent=2)

                        await post_job_to_webhook(payload)

                        with open(OUTPUT_PATH, "a") as out_f:
                            out_f.write(json.dumps(payload, ensure_ascii=False) + "\n")

                        seen_jobs.add(f"linkedin_{job_id}")
                        scraped_count += 1
                        total_jobs_scraped += 1
                        print(f"[✓] Scraped: {payload['title']} @ {payload['company']}")
                    else:
                        print(f"[!] Failed to scrape job {job_id}")
                    
                    # Rate limiting between jobs
                    await asyncio.sleep(random.uniform(1, 2))

                print(f"[INFO] URL {url_index + 1} complete: Scraped {scraped_count} new jobs from {len(all_job_ids)} found")

            except Exception as e:
                logging.error(f"Failed to process search URL {base_search_url}: {e}")
                # Save debug info
                try:
                    error_path = Path(f"data/linkedin/{datetime.utcnow().date()}/debug")
                    error_path.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=error_path / f"error_url_{url_index}.png", full_page=True)
                    debug_html = await page.content()
                    (error_path / f"error_url_{url_index}.html").write_text(debug_html)
                except:
                    pass
                continue

        await context.close()
        save_seen_jobs(seen_jobs)

    print(f"\n[INFO] ===== SCRAPING COMPLETE =====")
    print(f"[INFO] Total jobs found: {total_jobs_found}")
    print(f"[INFO] Total jobs scraped: {total_jobs_scraped}")
    print(f"[INFO] Success rate: {(total_jobs_scraped/max(total_jobs_found,1)*100):.1f}%")
    print(f"[INFO] Results saved to: {OUTPUT_PATH}")
    print(f"[INFO] Latest symlink: {latest_symlink}")

# Additional utility functions for production use

async def scrape_with_rate_limiting():
    """Add random delays between requests"""
    delay = random.uniform(2, 5)
    await asyncio.sleep(delay)

async def extract_all_jobs_with_pagination(page, base_search_url, max_pages=10):
    """
    Alternative pagination method - handles LinkedIn pagination by clicking Next button
    """
    all_job_ids = []
    page_num = 0
    
    # Start with the base URL
    await page.goto(base_search_url, timeout=60000)
    await page.wait_for_load_state('domcontentloaded')
    
    while page_num < max_pages:
        print(f"[ALT-PAGINATION] Processing page {page_num + 1}")
        
        # Extract jobs from current page
        job_ids = await extract_job_ids_from_search_page(page, page_num)
        if not job_ids:
            print(f"[ALT-PAGINATION] No jobs found on page {page_num + 1}")
            break
            
        all_job_ids.extend(job_ids)
        print(f"[ALT-PAGINATION] Page {page_num + 1}: Found {len(job_ids)} jobs")
        
        # Try to find and click the "Next" button
        try:
            next_button = page.locator("button[aria-label='Next']").first
            if await next_button.count() > 0:
                is_disabled = await next_button.get_attribute("disabled")
                if not is_disabled:
                    await next_button.click()
                    await page.wait_for_load_state('domcontentloaded')
                    await page.wait_for_timeout(3000)
                    page_num += 1
                else:
                    print(f"[ALT-PAGINATION] Next button is disabled, reached end")
                    break
            else:
                print(f"[ALT-PAGINATION] No next button found, reached end")
                break
        except Exception as e:
            print(f"[ALT-PAGINATION] Error clicking next: {e}")
            break
    
    return list(set(all_job_ids))  # Remove duplicates

def get_scraping_stats(output_file):
    """Get statistics from a scraping session"""
    if not Path(output_file).exists():
        return {"error": "File not found"}
    
    stats = {
        "total_jobs": 0,
        "companies": set(),
        "locations": set(),
        "job_titles": set(),
        "avg_description_length": 0,
        "jobs_with_cleaned_descriptions": 0,
        "recent_jobs": 0,  # Jobs posted in last 7 days
        "remote_jobs": 0,
        "description_lengths": []
    }
    
    try:
        with open(output_file, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        job_data = json.loads(line)
                        stats["total_jobs"] += 1
                        
                        # Collect unique values
                        if job_data.get("company"):
                            stats["companies"].add(job_data["company"])
                        if job_data.get("location"):
                            stats["locations"].add(job_data["location"])
                        if job_data.get("title"):
                            stats["job_titles"].add(job_data["title"])
                        
                        # Description stats
                        desc_length = job_data.get("description_char_count", 0)
                        if desc_length > 0:
                            stats["description_lengths"].append(desc_length)
                        
                        # Check for cleaned descriptions
                        if "cleaned_description" in str(job_data):
                            stats["jobs_with_cleaned_descriptions"] += 1
                        
                        # Check for recent jobs
                        posted_time = job_data.get("posted_time", "")
                        if any(word in posted_time.lower() for word in ["hour", "day"]):
                            if "week" not in posted_time.lower():
                                stats["recent_jobs"] += 1
                        
                        # Check for remote jobs
                        location = job_data.get("location", "").lower()
                        if any(word in location for word in ["remote", "anywhere"]):
                            stats["remote_jobs"] += 1
                            
                    except json.JSONDecodeError:
                        continue
        
        # Calculate averages
        if stats["description_lengths"]:
            stats["avg_description_length"] = sum(stats["description_lengths"]) / len(stats["description_lengths"])
        
        # Convert sets to counts
        stats["unique_companies"] = len(stats["companies"])
        stats["unique_locations"] = len(stats["locations"])  
        stats["unique_job_titles"] = len(stats["job_titles"])
        
        # Remove the sets (not JSON serializable)
        del stats["companies"]
        del stats["locations"]
        del stats["job_titles"]
        
        return stats
        
    except Exception as e:
        return {"error": str(e)}

def create_scraping_report(output_file, report_file=None):
    """Create a comprehensive scraping report"""
    stats = get_scraping_stats(output_file)
    
    if "error" in stats:
        return stats
    
    if not report_file:
        report_file = Path(output_file).with_suffix('.md')
    
    report_content = f"""# LinkedIn Scraping Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source File: {output_file}

## Summary Statistics

- **Total Jobs Scraped**: {stats['total_jobs']:,}
- **Unique Companies**: {stats['unique_companies']:,}
- **Unique Locations**: {stats['unique_locations']:,}
- **Unique Job Titles**: {stats['unique_job_titles']:,}

## Job Characteristics

- **Recent Jobs** (≤7 days): {stats['recent_jobs']:,} ({stats['recent_jobs']/max(stats['total_jobs'],1)*100:.1f}%)
- **Remote Jobs**: {stats['remote_jobs']:,} ({stats['remote_jobs']/max(stats['total_jobs'],1)*100:.1f}%)
- **Jobs with Cleaned Descriptions**: {stats['jobs_with_cleaned_descriptions']:,}

## Description Analysis

- **Average Description Length**: {stats['avg_description_length']:.0f} characters
- **Min Description Length**: {min(stats['description_lengths']) if stats['description_lengths'] else 0} characters
- **Max Description Length**: {max(stats['description_lengths']) if stats['description_lengths'] else 0} characters

## Quality Metrics

- **Completion Rate**: {(stats['total_jobs']/max(stats['total_jobs'],1)*100):.1f}%
- **Data Quality**: {'High' if stats['avg_description_length'] > 500 else 'Medium' if stats['avg_description_length'] > 200 else 'Low'}

---

*Report generated by Enhanced LinkedIn Scraper*
"""
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"📄 Report saved to: {report_file}")
        return {"success": True, "report_file": str(report_file), "stats": stats}
    except Exception as e:
        return {"error": f"Failed to write report: {e}"}

if __name__ == "__main__":
    import sys

    skip_scrape = os.getenv("SKIP_SCRAPE", "false").lower() == "true"
    if skip_scrape:
        print("[INFO] Skipping execution — SKIP_SCRAPE=true set.")
        sys.exit(0)

    # Handle command line arguments
    urls = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    
    # Special commands
    if len(sys.argv) > 1:
        if sys.argv[1] == "--stats":
            if len(sys.argv) > 2:
                stats = get_scraping_stats(sys.argv[2])
                print(json.dumps(stats, indent=2))
            else:
                print("Usage: python linkedin_scraper.py --stats <output_file.jsonl>")
            sys.exit(0)
        
        elif sys.argv[1] == "--report":
            if len(sys.argv) > 2:
                result = create_scraping_report(sys.argv[2])
                print(json.dumps(result, indent=2))
            else:
                print("Usage: python linkedin_scraper.py --report <output_file.jsonl>")
            sys.exit(0)

        elif sys.argv[1] == "--job-id" and len(sys.argv) > 3:
            job_id = sys.argv[2]
            search_url = sys.argv[3]
            print(f"[INFO] Scraping single job {job_id} using base URL: {search_url}")
            async def scrape_single():
                async with async_playwright() as p:
                    context = await p.webkit.launch_persistent_context(
                        user_data_dir=str(Path.home() / ".pw-session"),
                        headless=False,
                        viewport={"width": 1280, "height": 800}
                    )
                    page = await context.new_page()
                    payload = await scrape_job_by_id(page, job_id, search_url)
                    if payload:
                        print(json.dumps(payload, indent=2))
                    await context.close()
            asyncio.run(scrape_single())
            sys.exit(0)
    
    # Normal scraping execution
    if urls:
        print(f"[INFO] Running with CLI URLs: {urls}")
        scrape_jobs.override_urls = urls
    else:
        print("[INFO] No CLI URLs passed. Will use SEARCH_URLS env if set.")

    try:
        asyncio.run(scrape_jobs())
    except KeyboardInterrupt:
        print("\n[INFO] Scraping interrupted by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)