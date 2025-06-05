# Common Issues & Troubleshooting Guide

This guide covers the most frequently encountered issues in the LinkedIn Job Application Automation System and provides step-by-step solutions.

## 🚨 Critical Issues (System Breaking)

### **Issue 1: LinkedIn Scraping Failures**

#### **Symptoms**
- "Redirected to login page" errors
- "Blocked by captcha/challenge" messages
- Empty scraping results
- 403/401 HTTP errors

#### **Root Causes**
1. **Expired LinkedIn Cookie**: Session expired or invalid
2. **Rate Limiting**: Too aggressive scraping detected
3. **IP Blocking**: LinkedIn blocked your IP address
4. **Page Structure Changes**: LinkedIn updated their HTML structure

#### **Solutions**

**🔧 Fix 1: Update LinkedIn Cookie**
```bash
# Step 1: Clear browser cache completely
# Chrome: Settings > Privacy > Clear browsing data > All time

# Step 2: Fresh LinkedIn login
# 1. Go to linkedin.com in incognito/private mode
# 2. Login with your credentials
# 3. Navigate to job search page

# Step 3: Extract new cookie
# 1. Open Developer Tools (F12)
# 2. Go to Application tab > Cookies > linkedin.com
# 3. Copy entire cookie string
# 4. Update .env file:
LINKEDIN_COOKIE="li_at=AQEBARxxxxxxx; JSESSIONID=ajax:1234567890; lang=v=2&lang=en-us; ..."
```

**🔧 Fix 2: Adjust Rate Limiting**
```python
# Edit linkedin_scraper.py - increase delays
await asyncio.sleep(random.uniform(3, 6))  # Increased from 1.5-3

# Reduce concurrent operations
MAX_CONCURRENT_PAGES = 1  # Process one page at a time

# Add longer delays between jobs
await asyncio.sleep(random.uniform(5, 10))  # Between individual jobs
```

**🔧 Fix 3: Change IP Address**
```bash
# Option 1: Use VPN
# Connect to different VPN server location

# Option 2: Use different network
# Switch to mobile hotspot or different WiFi

# Option 3: Proxy rotation (advanced)
# Configure proxy settings in Playwright
```

**🔧 Fix 4: Verify Search URLs**
```bash
# Test your search URLs manually in browser
# Check if they return results when accessed normally

# Common URL fixes:
# Old: https://www.linkedin.com/jobs/search/?keywords=PM
# New: https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&refresh=true

# Ensure URLs are properly encoded
import urllib.parse
encoded_url = urllib.parse.quote("Product Manager", safe='')
```

### **Issue 2: Azure OpenAI API Errors**

#### **Symptoms**
- "Assistant not found" errors
- "Rate limit exceeded" messages
- "Invalid API key" errors
- AI analysis returning empty results

#### **Root Causes**
1. **Invalid API Configuration**: Wrong endpoint or API key
2. **Assistant Not Created**: Missing assistant setup
3. **Rate Limits**: Exceeded Azure OpenAI quotas
4. **Model Deployment Issues**: Model not deployed or wrong name

#### **Solutions**

**🔧 Fix 1: Verify API Configuration**
```bash
# Test Azure OpenAI connection
cat > test_azure_connection.py << 'EOF'
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

try:
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION")
    )
    
    # Test basic API call
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        messages=[{"role": "user", "content": "Test connection"}],
        max_tokens=10
    )
    
    print("✅ Azure OpenAI connection successful")
    print(f"Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nCheck these settings:")
    print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    print(f"Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}")
    print(f"API Version: {os.getenv('AZURE_OPENAI_API_VERSION')}")
EOF

python test_azure_connection.py
```

**🔧 Fix 2: Create/Verify Assistant**
```bash
# Check if assistant exists
cat > check_assistant.py << 'EOF'
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)

assistant_id = os.getenv("AZURE_ASSISTANT_ID")
if assistant_id:
    try:
        assistant = client.beta.assistants.retrieve(assistant_id)
        print(f"✅ Assistant found: {assistant.name}")
        print(f"Model: {assistant.model}")
        print(f"Tools: {[tool.type for tool in assistant.tools]}")
    except Exception as e:
        print(f"❌ Assistant error: {e}")
        print("Run setup_assistant.py to create new assistant")
else:
    print("❌ No AZURE_ASSISTANT_ID configured")
    print("Run setup_assistant.py to create assistant")
EOF

python check_assistant.py
```

**🔧 Fix 3: Check Rate Limits**
```bash
# Monitor Azure OpenAI usage
# Go to Azure Portal > OpenAI Resource > Metrics
# Check Token Usage and Request Rate

# Temporary rate limit solutions:
# 1. Reduce concurrent AI requests
# 2. Add delays between API calls
# 3. Use cheaper models (gpt-3.5-turbo instead of gpt-4)

# Update .env for rate limiting:
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-35-turbo  # Cheaper model
```

### **Issue 3: PDF Generation Problems**

#### **Symptoms**
- "WeasyPrint not found" errors
- Malformed or corrupted PDFs
- Missing fonts in generated documents
- Layout issues in PDFs

#### **Solutions**

**🔧 Fix 1: Install WeasyPrint Dependencies**
```bash
# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3-dev python3-pip python3-cffi python3-brotli libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0
sudo apt-get install fonts-liberation fonts-dejavu fonts-lato

# macOS
brew install pango gdk-pixbuf libffi
brew install --cask font-lato font-oswald

# Windows
# Download and install fonts manually from Google Fonts
# Install Microsoft Visual C++ Build Tools
```

**🔧 Fix 2: Fix Font Issues**
```bash
# Verify fonts are available
python -c "
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

font_config = FontConfiguration()
css = CSS(string='@import url(\"https://fonts.googleapis.com/css2?family=Lato:wght@400;700&family=Oswald:wght@400;500;600&display=swap\");')

# Test basic PDF generation
html = HTML(string='<html><body><h1 style=\"font-family: Oswald;\">Test</h1></body></html>')
html.write_pdf('test.pdf', font_config=font_config)
print('✅ PDF generation working')
"
```

**🔧 Fix 3: Template Validation**
```python
# Validate HTML templates
def validate_template(template_path):
    """Check template for common issues"""
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    issues = []
    
    # Check for unclosed tags
    open_divs = content.count('<div')
    close_divs = content.count('</div>')
    if open_divs != close_divs:
        issues.append(f"Mismatched div tags: {open_divs} open, {close_divs} close")
    
    # Check for missing fonts
    if 'font-family' in content:
        if 'Oswald' in content and '@import' not in content:
            issues.append("Oswald font used but not imported")
        if 'Lato' in content and '@import' not in content:
            issues.append("Lato font used but not imported")
    
    return issues

# Check templates
for template in ['resume-template-annotated.html', 'cover-letter-template-annotated.html']:
    issues = validate_template(template)
    if issues:
        print(f"❌ {template} issues:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print(f"✅ {template} validates correctly")
```

### **Issue 4: Application Submission Failures**

#### **Symptoms**
- Forms not submitting
- "No submit button found" errors
- Applications marked as failed in Google Sheets
- Screenshot shows incomplete forms

#### **Solutions**

**🔧 Fix 1: Debug Form Detection**
```bash
# Enable debug mode for form analysis
python auto_apply.py --debug-url "https://jobs.ashbyhq.com/example-job"

# This will print all form fields and their properties
# Look for missing fields or changed selectors
```

**🔧 Fix 2: Update ATS Selectors**
```python
# Check if ATS has updated their form structure
# Update selectors in auto_apply.py

# Common Ashby updates:
name_field_selectors = [
    'input[name="_systemfield_name"]',     # Original
    'input[name="name"]',                  # Fallback
    'input[placeholder*="name" i]',        # New pattern
    'input[aria-label*="name" i]'          # Accessibility pattern
]

email_field_selectors = [
    'input[name="_systemfield_email"]',
    'input[name="email"]', 
    'input[type="email"]',
    'input[aria-label*="email" i]'
]
```

**🔧 Fix 3: Handle Dynamic Forms**
```python
# Add wait for dynamic content
async def wait_for_form_ready(page):
    """Wait for form to be fully loaded"""
    
    # Wait for form elements to appear
    await page.wait_for_selector('input[type="email"]', timeout=10000)
    
    # Wait for any loading spinners to disappear
    try:
        await page.wait_for_selector('.loading', state='detached', timeout=5000)
    except:
        pass
    
    # Additional wait for dynamic content
    await page.wait_for_timeout(2000)
```

### **Issue 5: Google Sheets Synchronization Issues**

#### **Symptoms**
- "Permission denied" errors
- Data not appearing in sheets
- Duplicate entries in tracking sheet
- Authentication failures

#### **Solutions**

**🔧 Fix 1: Fix Permissions**
```bash
# 1. Get service account email from credentials.json
cat credentials.json | grep "client_email"

# 2. Share Google Sheet with service account
# - Go to Google Sheets
# - Click "Share" button  
# - Add service account email
# - Set permission to "Editor"
# - Uncheck "Notify people"

# 3. Verify sheet ID is correct
# Sheet URL: https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
# GOOGLE_SHEET_ID should be the SHEET_ID_HERE part
```

**🔧 Fix 2: Test Google Sheets Connection**
```python
# test_google_sheets.py
import gspread
from google.oauth2.service_account import Credentials
import os

try:
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    creds = Credentials.from_service_account_file(
        os.getenv("GOOGLE_CREDENTIALS_PATH"), scopes=scope)
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID"))
    
    # Test read access
    worksheet = sheet.sheet1
    all_records = worksheet.get_all_records()
    print(f"✅ Read access working - {len(all_records)} rows found")
    
    # Test write access
    test_cell = worksheet.cell(1, 1)
    original_value = test_cell.value
    worksheet.update_cell(1, 1, "TEST")
    worksheet.update_cell(1, 1, original_value)
    print("✅ Write access working")
    
except Exception as e:
    print(f"❌ Google Sheets error: {e}")
    print("\nTroubleshooting steps:")
    print("1. Check credentials.json file exists")
    print("2. Verify GOOGLE_SHEET_ID in .env")
    print("3. Ensure service account has Editor access to sheet")
```

## ⚠️ High Priority Issues

### **Issue 6: Browser Automation Failures**

#### **Symptoms**
- "Browser not found" errors
- Playwright timeouts
- Inconsistent automation behavior

#### **Solutions**

**🔧 Fix 1: Reinstall Playwright Browsers**
```bash
# Completely reinstall browsers
playwright uninstall
playwright install webkit chromium firefox

# Install system dependencies (Linux)
sudo playwright install-deps

# Verify installation
playwright --version
python -c "import playwright; print('Playwright imported successfully')"
```

**🔧 Fix 2: Handle Browser Launch Issues**
```python
# Add fallback browser strategy
async def create_browser_context_with_fallback(playwright):
    """Try multiple browser engines"""
    
    browsers_to_try = [
        ('webkit', playwright.webkit),
        ('chromium', playwright.chromium),
        ('firefox', playwright.firefox)
    ]
    
    for browser_name, browser_type in browsers_to_try:
        try:
            context = await browser_type.launch_persistent_context(
                user_data_dir=f".pw-session-{browser_name}",
                headless=False,
                viewport={"width": 1280, "height": 800}
            )
            print(f"✅ Successfully launched {browser_name}")
            return context
        except Exception as e:
            print(f"❌ {browser_name} failed: {e}")
            continue
    
    raise Exception("All browsers failed to launch")
```

### **Issue 7: Data Corruption or Loss**

#### **Symptoms**
- JSONL files corrupted
- Missing job data
- Incomplete scraping results

#### **Solutions**

**🔧 Fix 1: Implement Data Validation**
```python
def validate_jsonl_file(file_path):
    """Validate JSONL file integrity"""
    
    valid_lines = 0
    invalid_lines = 0
    
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                data = json.loads(line)
                
                # Check required fields
                required_fields = ['id', 'title', 'company', 'description']
                if all(field in data for field in required_fields):
                    valid_lines += 1
                else:
                    print(f"Line {line_num}: Missing required fields")
                    invalid_lines += 1
                    
            except json.JSONDecodeError as e:
                print(f"Line {line_num}: JSON decode error - {e}")
                invalid_lines += 1
    
    print(f"Validation complete: {valid_lines} valid, {invalid_lines} invalid")
    return invalid_lines == 0
```

**🔧 Fix 2: Automatic Backup System**
```python
def create_backup(file_path):
    """Create timestamped backup of data file"""
    
    if not Path(file_path).exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(file_path).with_suffix(f".backup_{timestamp}.jsonl")
    
    shutil.copy2(file_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path
```

## 🔍 Medium Priority Issues

### **Issue 8: Performance Degradation**

#### **Symptoms**
- Slow scraping speed
- High memory usage
- System becoming unresponsive

#### **Solutions**

**🔧 Fix 1: Memory Management**
```python
# Add memory cleanup
import gc
import psutil

def monitor_memory():
    """Monitor system memory usage"""
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory usage: {memory_mb:.1f} MB")
    
    if memory_mb > 1000:  # Over 1GB
        print("⚠️ High memory usage detected")
        gc.collect()  # Force garbage collection

# Add to scraping loop
if job_count % 50 == 0:  # Every 50 jobs
    monitor_memory()
```

**🔧 Fix 2: Optimize Database Operations**
```python
# Batch write operations instead of individual writes
def batch_write_jobs(jobs, output_file):
    """Write multiple jobs at once"""
    
    with open(output_file, 'a') as f:
        for job in jobs:
            f.write(json.dumps(job, ensure_ascii=False) + '\n')
    
    # Flush to disk
    f.flush()
    os.fsync(f.fileno())
```

### **Issue 9: Network Connectivity Issues**

#### **Symptoms**
- Intermittent connection failures
- API timeouts
- DNS resolution errors

#### **Solutions**

**🔧 Fix 1: Add Retry Logic**
```python
import asyncio
from functools import wraps

def retry_on_failure(max_attempts=3, delay=1):
    """Decorator to retry failed operations"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise e
                    
                    wait_time = delay * (2 ** attempt)  # Exponential backoff
                    print(f"Attempt {attempt + 1} failed: {e}")
                    print(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
            
        return wrapper
    return decorator

# Apply to network operations
@retry_on_failure(max_attempts=3, delay=2)
async def scrape_job_with_retry(page, job_id):
    return await scrape_job_by_id(page, job_id)
```

## 🛠️ Diagnostic Tools

### **System Health Check**

```bash
# Create comprehensive health check script
cat > health_check.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from pathlib import Path
import requests

def check_python_environment():
    """Check Python and package versions"""
    print("🐍 Python Environment:")
    print(f"   Python: {sys.version.split()[0]}")
    
    packages = ['playwright', 'fastapi', 'openai', 'weasyprint', 'gspread']
    for package in packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} missing")

def check_environment_variables():
    """Check critical environment variables"""
    print("\n🔑 Environment Variables:")
    
    required_vars = [
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_API_KEY', 
        'LINKEDIN_COOKIE',
        'GOOGLE_SHEET_ID'
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print(f"   ✅ {var}: {masked}")
        else:
            print(f"   ❌ {var}: Not set")

def check_files_and_directories():
    """Check required files exist"""
    print("\n📁 Files & Directories:")
    
    required_files = [
        'credentials.json',
        'resume-template-annotated.html',
        'cover-letter-template-annotated.html'
    ]
    
    for file in required_files:
        if Path(file).exists():
            size = Path(file).stat().st_size
            print(f"   ✅ {file} ({size} bytes)")
        else:
            print(f"   ❌ {file} missing")

def check_api_connectivity():
    """Test API endpoints"""
    print("\n🌐 API Connectivity:")
    
    # Test local API server
    try:
        response = requests.get("http://localhost:8000/status", timeout=5)
        if response.status_code == 200:
            print("   ✅ FastAPI server running")
        else:
            print(f"   ⚠️ FastAPI server returned {response.status_code}")
    except requests.exceptions.RequestException:
        print("   ❌ FastAPI server not accessible")
    
    # Test Azure OpenAI
    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-12-01-preview"
        )
        
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        print("   ✅ Azure OpenAI accessible")
    except Exception as e:
        print(f"   ❌ Azure OpenAI failed: {str(e)[:50]}...")

def check_data_integrity():
    """Check recent data files"""
    print("\n📊 Data Integrity:")
    
    latest_file = Path("data/linkedin/results/latest.jsonl")
    if latest_file.exists():
        try:
            valid_jobs = 0
            with open(latest_file, 'r') as f:
                for line in f:
                    if line.strip():
                        json.loads(line)  # Validate JSON
                        valid_jobs += 1
            print(f"   ✅ Latest results: {valid_jobs} valid jobs")
        except Exception as e:
            print(f"   ❌ Latest results corrupted: {e}")
    else:
        print("   ⚠️ No recent results found")

if __name__ == "__main__":
    print("🔍 LinkedIn Automation System Health Check\n")
    
    check_python_environment()
    check_environment_variables()
    check_files_and_directories()
    check_api_connectivity()
    check_data_integrity()
    
    print("\n✅ Health check complete!")
EOF

python health_check.py
```

### **Log Analysis Tool**

```bash
# Create log analysis script
cat > analyze_logs.py << 'EOF'
#!/usr/bin/env python3
import re
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta

def analyze_scraper_logs():
    """Analyze linkedin_scraper.log for patterns"""
    
    log_file = Path("linkedin_scraper.log")
    if not log_file.exists():
        print("No scraper log found")
        return
    
    errors = []
    warnings = []
    successes = []
    
    with open(log_file, 'r') as f:
        for line in f:
            if "ERROR" in line:
                errors.append(line.strip())
            elif "WARNING" in line:
                warnings.append(line.strip())
            elif "✅" in line or "SUCCESS" in line:
                successes.append(line.strip())
    
    print(f"📊 Scraper Log Analysis:")
    print(f"   Errors: {len(errors)}")
    print(f"   Warnings: {len(warnings)}")
    print(f"   Successes: {len(successes)}")
    
    # Show recent errors
    if errors:
        print(f"\n❌ Recent Errors:")
        for error in errors[-5:]:  # Last 5 errors
            print(f"   {error}")

def analyze_application_logs():
    """Analyze auto_apply.log for patterns"""
    
    log_file = Path("auto_apply.log")
    if not log_file.exists():
        print("No application log found")
        return
    
    ats_types = Counter()
    success_count = 0
    failure_count = 0
    
    with open(log_file, 'r') as f:
        for line in f:
            if "ATS:" in line:
                ats_match = re.search(r'ATS: (\w+)', line)
                if ats_match:
                    ats_types[ats_match.group(1)] += 1
            
            if "Application successful" in line:
                success_count += 1
            elif "Application failed" in line:
                failure_count += 1
    
    print(f"\n📊 Application Log Analysis:")
    print(f"   Successful applications: {success_count}")
    print(f"   Failed applications: {failure_count}")
    
    if ats_types:
        print(f"   ATS Types encountered:")
        for ats, count in ats_types.most_common():
            print(f"     {ats}: {count}")

if __name__ == "__main__":
    analyze_scraper_logs()
    analyze_application_logs()
EOF

python analyze_logs.py
```

## 📞 Getting Help

### **When to Seek Support**

1. **Immediate Help Needed**: System completely broken, no jobs being processed
2. **Performance Issues**: System working but very slow or consuming too many resources
3. **Integration Problems**: Third-party services (Azure, Google, Telegram) not working
4. **Data Issues**: Corruption, loss, or inconsistencies in job data

### **Information to Include in Support Requests**

```bash
# Gather system information for support
cat > gather_debug_info.py << 'EOF'
import sys
import os
import platform
from pathlib import Path

print("🔧 Debug Information for Support")
print("=" * 40)

print(f"Operating System: {platform.system()} {platform.release()}")
print(f"Python Version: {sys.version}")
print(f"Working Directory: {os.getcwd()}")

# Environment variables (masked)
critical_vars = ['AZURE_OPENAI_ENDPOINT', 'LINKEDIN_COOKIE', 'GOOGLE_SHEET_ID']
for var in critical_vars:
    value = os.getenv(var)
    if value:
        masked = value[:10] + "..." if len(value) > 10 else "SET"
        print(f"{var}: {masked}")
    else:
        print(f"{var}: NOT SET")

# Recent errors from logs
log_files = ['linkedin_scraper.log', 'auto_apply.log']
for log_file in log_files:
    if Path(log_file).exists():
        print(f"\nRecent errors from {log_file}:")
        with open(log_file, 'r') as f:
            lines = f.readlines()
            error_lines = [line for line in lines[-50:] if 'ERROR' in line]
            for error in error_lines[-3:]:  # Last 3 errors
                print(f"  {error.strip()}")

# System resources
try:
    import psutil
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('.')
    print(f"\nSystem Resources:")
    print(f"  Memory: {memory.used/1024/1024/1024:.1f}GB / {memory.total/1024/1024/1024:.1f}GB")
    print(f"  Disk: {disk.used/1024/1024/1024:.1f}GB / {disk.total/1024/1024/1024:.1f}GB")
except ImportError:
    print("\npsutil not available for resource monitoring")
EOF

python gather_debug_info.py
```

### **Self-Help Resources**

1. **Review Logs**: Always check log files first
2. **Run Health Check**: Use the health check script above
3. **Test Components**: Isolate and test individual components
4. **Check GitHub Issues**: Search for similar problems
5. **Review Documentation**: Ensure correct configuration

---

This troubleshooting guide covers the most common issues encountered in the LinkedIn Job Application Automation System. Most problems can be resolved by following these step-by-step solutions. For issues not covered here, use the diagnostic tools to gather information before seeking support.