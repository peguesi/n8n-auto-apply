# LinkedIn Scraper Documentation

The LinkedIn Scraper is the foundation of the job automation system, responsible for discovering and extracting job postings from LinkedIn search results with advanced pagination support and intelligent content processing.

## 🎯 Overview

The scraper (`linkedin_scraper.py`) implements a sophisticated job discovery system with:

- **Enhanced Pagination**: Automatically traverses multiple pages of search results
- **Multi-Strategy Extraction**: Uses multiple techniques to extract job IDs and data
- **AI-Powered Cleaning**: Azure OpenAI integration for description processing
- **Robust Error Handling**: Comprehensive retry logic and debugging capabilities
- **Rate Limiting**: Intelligent delays to avoid detection
- **Debug Capabilities**: Screenshot capture and HTML analysis

## 🏗️ Architecture

### **Core Components**

```python
# Main scraping workflow
async def scrape_jobs():
    """Main scraping function using enhanced URL-based strategy with pagination"""
    
# Enhanced pagination handler  
async def scrape_all_pages(page, base_search_url, max_pages=20):
    """Scrape all pages using robust pagination and job ID extraction"""
    
# Multi-strategy job extraction
async def extract_job_ids_from_search_page(page, page_num=0):
    """Extract job IDs from a LinkedIn search results page using robust strategies"""
    
# Individual job scraping
async def scrape_job_by_id(page, job_id, base_search_url):
    """Navigate to specific job using currentJobId parameter and scrape details"""
```

### **Data Flow**

```
LinkedIn Search URLs
        ↓
    URL Normalization
        ↓
    Pagination Loop (up to 20 pages)
        ↓
    Job ID Extraction (4 strategies)
        ↓
    Individual Job Scraping
        ↓
    Azure OpenAI Description Cleaning
        ↓
    JSONL Output + Debug Files
```

## ⚙️ Configuration

### **Environment Variables**

```bash
# Required LinkedIn Configuration
LINKEDIN_COOKIE="li_at=AQEBARxxxxxxx; JSESSIONID=ajax:1234567890..."
USER_AGENT="Mozilla/5.0 (compatible browser string)"
SEARCH_URLS="https://www.linkedin.com/jobs/search/?keywords=Senior%20Product%20Manager"

# Azure OpenAI for Description Cleaning
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
AZURE_OPENAI_KEY="your-api-key"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o"

# Optional Webhook Integration
WEBHOOK_URL="http://localhost:5678/webhook/new-job"

# Scraping Controls
SKIP_SCRAPE="false"  # Set to "true" to disable scraping
```

### **Search URL Parameters**

LinkedIn job search URLs support various filters:

```bash
# Basic search
https://www.linkedin.com/jobs/search/?keywords=Product%20Manager

# With location filter
https://www.linkedin.com/jobs/search/?keywords=Senior%20PM&location=New%20York

# With remote work filter
https://www.linkedin.com/jobs/search/?keywords=PM&f_WT=2

# Time-based filtering
https://www.linkedin.com/jobs/search/?keywords=PM&f_TPR=r86400  # Last 24 hours

# Experience level
https://www.linkedin.com/jobs/search/?keywords=PM&f_E=4  # Senior level

# Multiple filters combined
https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&location=San%20Francisco&f_WT=2&f_TPR=r604800&f_E=3,4
```

**Common Filter Parameters:**
- `f_WT=2`: Remote work
- `f_TPR=r86400`: Posted in last 24 hours (r604800 = 7 days)
- `f_E=3,4`: Associate and Senior level
- `f_C=123456`: Specific company ID
- `distance=25`: Search radius in miles
- `sortBy=DD`: Sort by date (most recent first)

## 🔍 Job Extraction Strategies

The scraper uses four different strategies to extract job IDs, ensuring maximum coverage:

### **Strategy 1: Data Attributes**
```python
# Extract from job cards with data-job-id
cards = await page.locator("[data-job-id]").all()
for card in cards:
    job_id = await card.get_attribute("data-job-id")
    if job_id and job_id.isdigit():
        job_ids.add(job_id)
```

### **Strategy 2: URL Patterns**
```python
# Extract from job view links
links = await page.locator("a[href*='/jobs/view/']").all()
for link in links:
    href = await link.get_attribute("href")
    match = re.search(r'/jobs/view/(\d+)', href)
    if match:
        job_ids.add(match.group(1))
```

### **Strategy 3: URN Patterns**
```python
# Extract from data-entity-urn attributes
urns = await page.locator("[data-entity-urn*='job']").all()
for el in urns:
    urn = await el.get_attribute("data-entity-urn")
    match = re.search(r':job:(\d+)', urn)
    if match:
        job_ids.add(match.group(1))
```

### **Strategy 4: Content Analysis**
```python
# Extract from page HTML content
content = await page.content()
patterns = [
    r'"jobPostingId":"(\d+)"',
    r'"entityUrn":"urn:li:job:(\d+)"',
    r'data-job-id="(\d+)"',
    r'/jobs/view/(\d+)'
]
```

## 📊 Individual Job Scraping

### **Job Data Structure**

Each scraped job contains:

```python
{
    "id": "linkedin_123456789",
    "title": "Senior Product Manager",
    "company": "Amazing Tech Company",
    "location": "New York, NY (Remote)",
    "url": "https://www.linkedin.com/jobs/view/123456789?currentJobId=123456789",
    "description": "We're looking for a Senior Product Manager...",
    "description_char_count": 1250,
    "posted_time": "2 hours ago",
    "source": "linkedin",
    "scraped_at": "2024-01-15T14:30:00.000Z",
    "pagination_source": "enhanced_scraper"
}
```

### **Field Extraction Selectors**

The scraper uses multiple CSS selectors for each field to handle LinkedIn's varying HTML structures:

```python
# Job Title
title_selectors = [
    "h1.top-card-layout__title",
    "h1.t-24",
    "h2.topcard__title",
    ".job-details-jobs-unified-top-card__job-title",
    "[data-test-id='job-title']"
]

# Company Name
company_selectors = [
    "a.topcard__org-name-link",
    ".job-details-jobs-unified-top-card__company-name",
    ".topcard__flavor--black-link",
    "[data-test-id='job-company']"
]

# Location
location_selectors = [
    ".topcard__flavor--bullet",
    ".job-details-jobs-unified-top-card__primary-description",
    ".job-details-jobs-unified-top-card__bullets li:first-child",
    "[data-test-id='job-location']"
]

# Job Description
description_selectors = [
    ".jobs-description-content__text",
    ".jobs-description__content",
    ".job-details-jobs-unified-top-card__job-description",
    "section.show-more-less-html__markup"
]
```

## 🤖 AI-Powered Description Cleaning

The scraper integrates with Azure OpenAI to clean and optimize job descriptions:

### **Cleaning Process**

```python
async def extract_job_description(page, job_id):
    """Extract the job description using multiple robust strategies"""
    
    # 1. Try prioritized CSS selectors
    # 2. Fallback to regex extraction from HTML
    # 3. Last resort: analyze all <section> elements
    
    # Send to Azure OpenAI for cleaning
    if description and AZURE_OPENAI_ENDPOINT:
        cleaned_description = await clean_with_azure_openai(description)
```

### **AI Cleaning Prompt**

```python
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

JOB DESCRIPTION:
{description}"""
```

### **Fallback Logic**

The cleaning system includes intelligent fallbacks:

```python
# Check if AI cleaning was successful
should_use_cleaned = True
fallback_reason = None

# Check 1: Empty or very short result
if not cleaned_description or len(cleaned_description) < 100:
    should_use_cleaned = False
    fallback_reason = "Cleaned result too short"

# Check 2: AI returned error messages
elif any(phrase in cleaned_description.lower() for phrase in [
    "i cannot", "sorry", "unable to", "error"
]):
    should_use_cleaned = False
    fallback_reason = "AI returned error message"

# Check 3: Over-trimmed (more than 70% reduction)
elif len(cleaned_description) < len(original_description) * 0.3:
    should_use_cleaned = False
    fallback_reason = "Over-trimmed content"
```

## 🔄 Pagination Logic

### **Enhanced Pagination Strategy**

```python
async def scrape_all_pages(page, base_search_url, max_pages=20):
    """Scrape all pages using robust pagination"""
    
    all_job_ids = set()
    page_num = 0
    
    while page_num < max_pages:
        # Build paginated URL
        page_start = page_num * 25  # LinkedIn shows 25 jobs per page
        current_url = add_pagination_to_url(base_search_url, page_start)
        
        # Navigate and extract jobs
        await page.goto(current_url)
        page_job_ids = await extract_job_ids_from_search_page(page, page_num)
        
        # Stop if no jobs found or less than full page
        if not page_job_ids or len(page_job_ids) < 25:
            break
            
        all_job_ids.update(page_job_ids)
        page_num += 1
```

### **URL Normalization**

```python
def normalize_search_url(url):
    """Normalize a LinkedIn search URL by removing unnecessary parameters"""
    
    # Keep only essential parameters
    essential_params = {
        'f_WT': params.get('f_WT', ['2']),      # Remote work filter
        'geoId': params.get('geoId', []),       # Location
        'keywords': params.get('keywords', []),  # Search terms
        'refresh': ['true'],                     # Always refresh
        'distance': params.get('distance', ['25']),
        'f_TPR': params.get('f_TPR', []),       # Time posted filter
        'f_E': params.get('f_E', [])            # Experience level
    }
    
    # Build clean URL without currentJobId conflicts
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', clean_query, ''))
```

## 🛡️ Anti-Detection Measures

### **Rate Limiting**

```python
# Random delays between requests
await asyncio.sleep(random.uniform(1.5, 3))

# Exponential backoff on failures
for attempt in range(max_retries):
    try:
        # Scraping logic
        break
    except Exception as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # 2, 4, 8 seconds
```

### **Browser Simulation**

```python
# Use persistent browser context to maintain session
context = await p.webkit.launch_persistent_context(
    user_data_dir=str(Path.home() / ".pw-session"),
    headless=False,  # Sometimes helps avoid detection
    viewport={"width": 1280, "height": 800}
)

# Realistic user agent strings
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
```

### **Error Detection**

```python
# Check for LinkedIn blocking
page_title = await page.title()
current_url = page.url

if "sign" in page_title.lower() or "login" in page_title.lower():
    logging.error("Redirected to login page")
    
if "challenge" in current_url.lower() or "captcha" in page_title.lower():
    logging.error("Blocked by captcha/challenge")
```

## 📁 Output Management

### **File Structure**

```bash
data/
├── linkedin/
│   ├── 2024-01-15/           # Date-based organization
│   │   ├── results_143022.jsonl  # Timestamped results
│   │   ├── screenshots/      # Debug screenshots
│   │   ├── html/            # Raw HTML snapshots
│   │   └── cleaned_log/     # AI cleaning logs
│   └── results/
│       └── latest.jsonl     # Symlink to latest results
```

### **JSONL Output Format**

Each line in the output file is a complete JSON object:

```json
{"id": "linkedin_123456", "title": "Senior PM", "company": "TechCorp", ...}
{"id": "linkedin_789012", "title": "Product Manager", "company": "StartupCo", ...}
```

### **Debug Outputs**

```python
# Screenshot for visual debugging
screenshot_path = Path(f"data/linkedin/{date}/screenshots")
await page.screenshot(path=screenshot_path / f"job_{job_id}.png", full_page=True)

# Raw HTML for analysis
html_path = Path(f"data/linkedin/{date}/html")
(html_path / f"job_{job_id}.html").write_text(debug_html)

# AI cleaning log
cleaned_log_path = Path(f"data/linkedin/{date}/cleaned_log")
with open(cleaned_log_path / f"job_{job_id}.json", "w") as f:
    json.dump({
        "original_length": len(original_description),
        "cleaned_length": len(cleaned_description),
        "reduction_percentage": reduction_percent,
        "used_cleaned": should_use_cleaned
    }, f, indent=2)
```

## 🚀 Usage Examples

### **Basic Scraping**

```bash
# Single URL scraping
python linkedin_scraper.py "https://www.linkedin.com/jobs/search/?keywords=Product%20Manager"

# Multiple URLs from environment
export SEARCH_URLS="url1,url2,url3"
python linkedin_scraper.py
```

### **API Integration**

```python
# Via FastAPI endpoint
import requests

response = requests.post(
    "http://localhost:8000/scrape/linkedin",
    json={
        "urls": [
            "https://www.linkedin.com/jobs/search/?keywords=Senior%20PM&location=NYC",
            "https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&f_WT=2"
        ]
    }
)
```

### **Command Line Options**

```bash
# Generate statistics report
python linkedin_scraper.py --stats data/linkedin/results/latest.jsonl

# Create markdown report
python linkedin_scraper.py --report data/linkedin/results/latest.jsonl

# Override with specific URLs
python linkedin_scraper.py "url1" "url2" "url3"
```

## 🔧 Performance Optimization

### **Scraping Speed**

- **Jobs per minute**: ~50-100 (with rate limiting)
- **Pages per minute**: ~10-15
- **Memory usage**: ~100-200MB per browser context

### **Optimization Tips**

```python
# Adjust rate limiting for faster scraping
await asyncio.sleep(random.uniform(0.5, 1.5))  # Faster, more risky

# Use headless mode for better performance
context = await p.webkit.launch_persistent_context(
    headless=True,  # Faster but may trigger detection
    user_data_dir=user_data_path
)

# Reduce wait times for faster pages
await page.wait_for_timeout(1000)  # Reduced from 2000ms
```

### **Resource Management**

```python
# Cleanup browser contexts
await context.close()

# Limit concurrent operations
semaphore = asyncio.Semaphore(3)  # Max 3 concurrent browsers
```

## ⚠️ Troubleshooting

### **Common Issues**

#### **1. LinkedIn Login Required**
```bash
# Symptoms: "Redirected to login page" errors
# Cause: Cookie expired or invalid
# Solution: Update LINKEDIN_COOKIE in .env

# Get new cookie:
# 1. Clear browser cache
# 2. Login to LinkedIn fresh  
# 3. Export cookie string from browser dev tools
```

#### **2. Captcha/Challenge Page**
```bash
# Symptoms: "Blocked by captcha/challenge" errors
# Cause: Too aggressive scraping detected
# Solution: Increase rate limiting delays

# Temporary fix:
# 1. Stop scraping for 1-2 hours
# 2. Use different IP/VPN
# 3. Increase delays between requests
```

#### **3. No Jobs Found**
```bash
# Symptoms: Empty results or "No jobs found on page"
# Cause: Search URL returns no results or page structure changed
# Solution: Verify search URL manually

# Debug steps:
# 1. Test search URL in browser
# 2. Check LinkedIn page structure changes
# 3. Review debug screenshots
```

#### **4. Azure OpenAI Errors**
```bash
# Symptoms: Description cleaning failures
# Cause: API key issues or rate limits
# Solution: Check Azure OpenAI configuration

# Fallback: Disable AI cleaning
AZURE_OPENAI_ENDPOINT=""  # Disables AI cleaning
```

### **Debug Procedures**

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Capture debug screenshots
await page.screenshot(path=f"debug_{job_id}.png", full_page=True)

# Analyze page content
content = await page.content()
print(f"Page content length: {len(content)}")
print(f"Page title: {await page.title()}")

# Check for specific elements
job_cards = await page.locator("[data-job-id]").count()
print(f"Found {job_cards} job cards")
```

### **Performance Monitoring**

```python
# Track scraping statistics
stats = {
    "jobs_found": len(all_job_ids),
    "jobs_scraped": scraped_count,
    "success_rate": scraped_count / max(len(all_job_ids), 1) * 100,
    "pages_processed": page_num + 1,
    "time_elapsed": time.time() - start_time
}

print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Jobs per minute: {stats['jobs_scraped'] / (stats['time_elapsed'] / 60):.1f}")
```

## 🔮 Advanced Features

### **Custom Extraction Rules**

```python
# Add custom job extraction logic
def extract_custom_fields(page, job_data):
    """Extract additional fields specific to your needs"""
    
    # Extract salary information
    salary_elem = await page.query_selector(".salary-info")
    if salary_elem:
        job_data["salary"] = await salary_elem.text_content()
    
    # Extract company size
    size_elem = await page.query_selector("[data-test='company-size']")
    if size_elem:
        job_data["company_size"] = await size_elem.text_content()
    
    return job_data
```

### **Custom Filters**

```python
# Add job filtering logic
def should_process_job(job_data):
    """Filter jobs based on custom criteria"""
    
    # Skip jobs without remote option
    if "remote" not in job_data.get("location", "").lower():
        return False
    
    # Skip certain companies
    excluded_companies = ["Bad Company", "Avoid Corp"]
    if job_data.get("company") in excluded_companies:
        return False
    
    return True
```

---

The LinkedIn Scraper forms the critical foundation of the job automation system. Its robust extraction strategies, intelligent pagination, and AI-powered content processing ensure comprehensive job discovery while maintaining reliability and avoiding detection.