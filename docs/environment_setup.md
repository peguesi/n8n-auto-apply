# Environment Setup Guide

This guide will walk you through setting up the LinkedIn Job Application Automation System from scratch. Follow these steps carefully to ensure all components work correctly.

## 📋 Prerequisites Checklist

Before starting, ensure you have:

- [ ] **Python 3.8+** installed
- [ ] **Node.js 16+** (for n8n automation)
- [ ] **Git** for repository management
- [ ] **4GB+ RAM** available
- [ ] **2GB+ storage** for job data
- [ ] **Active LinkedIn account**
- [ ] **Azure subscription** with OpenAI access
- [ ] **Google account** for Sheets API
- [ ] **Telegram account** for notifications

## 🐍 Python Environment Setup

### 1. **Install Python Dependencies**

```bash
# Clone the repository
git clone <your-repository-url>
cd linkedin-job-automation

# Create and activate virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt

# Verify installation
python -c "import playwright, fastapi, openai; print('Dependencies installed successfully')"
```

### 2. **Install Playwright Browsers**

```bash
# Install browser dependencies
playwright install

# Install specific browsers (recommended)
playwright install webkit chromium

# Verify installation
playwright --version
```

### 3. **Verify Python Setup**

```python
# test_environment.py
import sys
print(f"Python version: {sys.version}")

# Test critical imports
try:
    import playwright
    import fastapi
    import openai
    import weasyprint
    import gspread
    print("✅ All critical packages imported successfully")
except ImportError as e:
    print(f"❌ Missing package: {e}")
```

## 🔑 Azure OpenAI Setup

### 1. **Create Azure OpenAI Resource**

1. **Login to Azure Portal**: https://portal.azure.com
2. **Create Resource Group**:
   ```bash
   # Using Azure CLI (optional)
   az group create --name linkedin-automation-rg --location eastus
   ```
3. **Create OpenAI Service**:
   - Search for "OpenAI" in Azure Portal
   - Click "Create"
   - Select your subscription and resource group
   - Choose region (East US recommended)
   - Select pricing tier (Standard recommended)

### 2. **Deploy Required Models**

```bash
# In Azure OpenAI Studio (https://oai.azure.com/)
# Deploy these models:

# 1. GPT-4 (for analysis)
Model: gpt-4
Deployment Name: gpt-4o
Version: Latest available

# 2. GPT-3.5 Turbo (for cost optimization)  
Model: gpt-35-turbo
Deployment Name: gpt-35-turbo
Version: Latest available

# 3. Text Embedding (for vector store)
Model: text-embedding-ada-002
Deployment Name: text-embedding-ada-002
Version: Latest available
```

### 3. **Create AI Assistant**

```bash
# Create assistant_setup.py
cat > assistant_setup.py << 'EOF'
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview"
)

# Create vector store
vector_store = client.beta.vector_stores.create(
    name="linkedin_job_knowledge",
    file_ids=[]  # Add your resume/CV files here
)

# Create assistant
assistant = client.beta.assistants.create(
    name="LinkedIn Job Analyzer",
    instructions="""You are an expert job market analyst and career strategist. 
    You help analyze job postings for fit and generate strategic application materials.
    Always validate company contexts and maintain authenticity in generated content.""",
    model="gpt-4o",
    tools=[{"type": "file_search"}],
    tool_resources={
        "file_search": {
            "vector_store_ids": [vector_store.id]
        }
    }
)

print(f"✅ Assistant created successfully!")
print(f"AZURE_ASSISTANT_ID={assistant.id}")
print(f"AZURE_VECTOR_STORE_ID={vector_store.id}")
print("\nAdd these to your .env file")
EOF

# Run the setup
python assistant_setup.py
```

### 4. **Get API Keys and Endpoints**

```bash
# In Azure Portal -> OpenAI Resource -> Keys and Endpoint
# Copy these values for your .env file:

AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-32-character-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

## 📊 Google Sheets API Setup

### 1. **Enable Google Sheets API**

1. **Go to Google Cloud Console**: https://console.cloud.google.com/
2. **Create New Project** (or select existing):
   ```
   Project Name: linkedin-automation
   Project ID: linkedin-automation-[random]
   ```
3. **Enable APIs**:
   - Search for "Google Sheets API"
   - Click "Enable"
   - Search for "Google Drive API" 
   - Click "Enable"

### 2. **Create Service Account**

```bash
# In Google Cloud Console:
# 1. Go to IAM & Admin > Service Accounts
# 2. Click "Create Service Account"
# 3. Fill details:
Service Account Name: linkedin-automation-service
Service Account ID: linkedin-automation-service
Description: Service account for LinkedIn job automation

# 4. Skip role assignment (click "Continue")
# 5. Click "Done"
```

### 3. **Generate Service Account Key**

```bash
# 1. Click on the created service account
# 2. Go to "Keys" tab
# 3. Click "Add Key" > "Create new key"
# 4. Select "JSON"
# 5. Download the file as "credentials.json"
# 6. Move to your project directory
```

### 4. **Create Google Sheet for Tracking**

```bash
# Create a new Google Sheet manually:
# 1. Go to https://sheets.google.com
# 2. Create new sheet named "Job Applications Tracker"
# 3. Add these column headers in row 1:

Job ID | Title | Company | Location | Posted Date | Scraped Date | Score | Interview Probability | Recommendation | Status | Resume Link | Cover Letter Link | Job URL | Key Requirements | Why Good Fit | Application Deadline | Notes
```

### 5. **Share Sheet with Service Account**

```bash
# 1. Copy the service account email from credentials.json
# 2. In Google Sheets, click "Share"
# 3. Add the service account email
# 4. Set permission to "Editor"
# 5. Copy the sheet ID from URL:
# https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit

GOOGLE_SHEET_ID=your-sheet-id-from-url
```

## 📱 Telegram Bot Setup

### 1. **Create Telegram Bot**

```bash
# 1. Open Telegram and search for @BotFather
# 2. Send /newbot command
# 3. Follow prompts:
Bot Name: LinkedIn Automation Bot
Username: your_linkedin_automation_bot

# 4. Save the bot token
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 2. **Get Chat ID**

```bash
# 1. Send a message to your bot
# 2. Get your chat ID:
curl "https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

# 3. Find your chat ID in the response
TELEGRAM_CHAT_ID=987654321
```

### 3. **Test Telegram Integration**

```bash
# Test notification
curl -X POST "https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id={TELEGRAM_CHAT_ID}" \
  -d "text=LinkedIn automation bot is working!"
```

## 🔗 LinkedIn Configuration

### 1. **Get LinkedIn Session Cookie**

```bash
# Method 1: Browser Developer Tools
# 1. Login to LinkedIn in browser
# 2. Open Developer Tools (F12)
# 3. Go to Application/Storage tab
# 4. Find Cookies for linkedin.com
# 5. Copy the entire cookie string

# Method 2: Using browser extension
# Use a cookie export extension to get all LinkedIn cookies

# The cookie should look like:
LINKEDIN_COOKIE="li_at=AQEBARxxxxxxx; JSESSIONID=ajax:1234567890; lang=v=2&lang=en-us; ..."
```

### 2. **Configure Search URLs**

```bash
# Create your job search URLs
# Example searches:
SEARCH_URLS="https://www.linkedin.com/jobs/search/?keywords=Senior%20Product%20Manager&location=New%20York&f_WT=2,https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&location=San%20Francisco&f_WT=2"

# URL Parameters:
# f_WT=2 : Remote work filter
# f_TPR=r86400 : Posted in last 24 hours
# f_E=4 : Senior level
# geoId=103644278 : United States
```

### 3. **Test LinkedIn Access**

```python
# test_linkedin.py
import asyncio
from playwright.async_api import async_playwright

async def test_linkedin():
    async with async_playwright() as p:
        browser = await p.webkit.launch(headless=False)
        page = await browser.new_page()
        
        # Set cookies
        await page.context.add_cookies([
            {"name": "li_at", "value": "your-li_at-value", "domain": ".linkedin.com"}
        ])
        
        # Test navigation
        await page.goto("https://www.linkedin.com/jobs/search/")
        title = await page.title()
        print(f"Page title: {title}")
        
        if "sign" not in title.lower():
            print("✅ LinkedIn access working")
        else:
            print("❌ LinkedIn login required")
        
        await browser.close()

asyncio.run(test_linkedin())
```

## 🔧 n8n Automation Setup (Optional)

### 1. **Install n8n**

```bash
# Option 1: NPM installation
npm install n8n -g

# Option 2: Docker installation
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n

# Start n8n
n8n start
# Access at http://localhost:5678
```

### 2. **Import Workflow**

```bash
# 1. Open n8n interface (http://localhost:5678)
# 2. Click "Import from File"
# 3. Upload n8n_autoapply.json
# 4. Configure credentials:
#    - Google Sheets API
#    - Telegram Bot
#    - HTTP credentials for API calls
```

### 3. **Configure Webhook URL**

```bash
# Update n8n workflow nodes to point to your API:
# HTTP Request nodes should use:
http://host.docker.internal:8000  # If using Docker
# OR
http://localhost:8000  # If running locally
```

## 📁 Create Environment File

Create your complete `.env` file:

```bash
cat > .env << 'EOF'
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-32-character-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_VECTOR_STORE_ID=vs_your_vector_store_id
AZURE_ASSISTANT_ID=asst_your_assistant_id

# LinkedIn Configuration
LINKEDIN_COOKIE="li_at=AQEBARxxxxxxx; JSESSIONID=ajax:1234567890; lang=v=2&lang=en-us"
USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SEARCH_URLS="https://www.linkedin.com/jobs/search/?keywords=Senior%20Product%20Manager&location=New%20York&f_WT=2"

# Google Sheets Integration
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_SHEET_ID=your-google-sheet-id-from-url
GOOGLE_SHEET_NAME="Job Applications Tracker"

# Telegram Notifications
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321

# Application Settings
MAX_DAILY_APPS=50
BUSINESS_HOURS_ONLY=true
WEBHOOK_URL=http://localhost:5678/webhook/new-job

# Optional Settings
SKIP_SCRAPE=false
CONCURRENT_WINDOWS=3
MIN_SCORE_THRESHOLD=6
EOF
```

## 🧪 System Verification

### 1. **Test All Components**

```bash
# Create verification script
cat > verify_setup.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

print("🔍 LinkedIn Automation System Verification\n")

# Check Python environment
print("1. Python Environment:")
print(f"   Python version: {sys.version.split()[0]}")

# Check critical imports
critical_imports = [
    'playwright', 'fastapi', 'openai', 'weasyprint', 
    'gspread', 'python-telegram-bot'
]

for package in critical_imports:
    try:
        __import__(package)
        print(f"   ✅ {package}")
    except ImportError:
        print(f"   ❌ {package} - Missing!")

# Check environment variables
print("\n2. Environment Variables:")
required_vars = [
    'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY',
    'LINKEDIN_COOKIE', 'GOOGLE_SHEET_ID', 'TELEGRAM_BOT_TOKEN'
]

for var in required_vars:
    value = os.getenv(var)
    if value:
        print(f"   ✅ {var} (set)")
    else:
        print(f"   ❌ {var} (missing)")

# Check file structure
print("\n3. File Structure:")
required_files = [
    'credentials.json', 'resume-template-annotated.html',
    'cover-letter-template-annotated.html', 'linkedin_scraper.py'
]

for file in required_files:
    if Path(file).exists():
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} (missing)")

# Check directories
print("\n4. Directories:")
required_dirs = ['data', 'data/linkedin', 'data/resumes']

for dir in required_dirs:
    Path(dir).mkdir(parents=True, exist_ok=True)
    print(f"   ✅ {dir}")

print("\n✅ Verification complete!")
EOF

python verify_setup.py
```

### 2. **Test Azure OpenAI Connection**

```python
# test_azure_openai.py
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
        messages=[{"role": "user", "content": "Hello, are you working?"}],
        max_tokens=50
    )
    
    print("✅ Azure OpenAI connection successful")
    print(f"Response: {response.choices[0].message.content}")
    
    # Test assistant if available
    assistant_id = os.getenv("AZURE_ASSISTANT_ID")
    if assistant_id:
        assistant = client.beta.assistants.retrieve(assistant_id)
        print(f"✅ Assistant found: {assistant.name}")
    else:
        print("⚠️ No assistant ID configured")
        
except Exception as e:
    print(f"❌ Azure OpenAI connection failed: {e}")
```

### 3. **Test Google Sheets Integration**

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
    worksheet = sheet.sheet1
    
    # Test write access
    test_cell = worksheet.acell('A1')
    print(f"✅ Google Sheets connection successful")
    print(f"Cell A1 value: {test_cell.value}")
    
except Exception as e:
    print(f"❌ Google Sheets connection failed: {e}")
```

### 4. **Test Complete System**

```bash
# Run end-to-end test
python -c "
import subprocess
import sys

tests = [
    ('verify_setup.py', 'System verification'),
    ('test_azure_openai.py', 'Azure OpenAI test'),
    ('test_google_sheets.py', 'Google Sheets test')
]

for test_file, description in tests:
    print(f'\n🧪 Running {description}...')
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f'Warnings: {result.stderr}')
    except Exception as e:
        print(f'❌ Test failed: {e}')
"
```

## 🚀 Final Steps

### 1. **Start the API Server**

```bash
# Start in development mode
python main.py

# Or use uvicorn directly
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Verify server is running
curl http://localhost:8000/status
```

### 2. **Test First Job Scrape**

```bash
# Test scraping with a simple search
curl -X POST "http://localhost:8000/scrape/linkedin" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&location=New%20York"]}'

# Check results
curl "http://localhost:8000/linkedin/results" | jq '.total_records'
```

### 3. **Run First AI Analysis**

```bash
# Analyze scraped jobs
curl -X POST "http://localhost:8000/agent/enhanced-fit"

# Check classification results
curl "http://localhost:8000/agent/classify-fit/results" | jq '.total_classified'
```

### 4. **Generate First Documents**

```bash
# Get the latest job ID
JOB_ID=$(curl -s "http://localhost:8000/linkedin/results/latest" | jq -r '.job.id')

# Generate documents for the job
curl -X POST "http://localhost:8000/content/generate" \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\", \"document_type\": \"both\"}"
```

## ⚠️ Common Setup Issues

### **Issue 1: Playwright Browser Installation**
```bash
# Symptom: "Browser not found" errors
# Solution: Install browsers explicitly
playwright install webkit chromium firefox
sudo playwright install-deps  # Linux only
```

### **Issue 2: WeasyPrint Font Issues**
```bash
# Linux
sudo apt-get install fonts-liberation fonts-dejavu

# macOS  
brew install --cask font-lato font-oswald

# Windows
# Download and install fonts manually from Google Fonts
```

### **Issue 3: Azure OpenAI Rate Limits**
```bash
# Symptom: "Rate limit exceeded" errors
# Solution: Check your Azure quotas
# Go to Azure Portal > OpenAI > Quotas and limits
# Increase TPM (Tokens Per Minute) if needed
```

### **Issue 4: LinkedIn Cookie Expiration**
```bash
# Symptom: "Redirected to login" errors
# Solution: Update LinkedIn cookie
# 1. Clear browser cache
# 2. Login to LinkedIn fresh
# 3. Export new cookie string
# 4. Update LINKEDIN_COOKIE in .env
```

### **Issue 5: Google Sheets Permission Denied**
```bash
# Symptom: "Permission denied" errors
# Solution: Check service account permissions
# 1. Verify service account email in sheet sharing
# 2. Ensure "Editor" permission level
# 3. Check credentials.json file path
```

## 🔄 Next Steps

After completing the setup:

1. **Read the User Guide**: Understand how to use the system effectively
2. **Configure n8n Automation**: Set up scheduled job discovery
3. **Customize Templates**: Modify resume and cover letter templates
4. **Monitor Performance**: Set up dashboards and alerts
5. **Scale Operations**: Adjust rate limits and application volumes

## 📞 Support

If you encounter issues during setup:

1. **Check Logs**: Review console output and log files
2. **Verify Prerequisites**: Ensure all dependencies are correctly installed
3. **Test Components**: Run individual verification scripts
4. **Review Documentation**: Check component-specific guides
5. **Get Help**: Create an issue with detailed error messages

---

**🎉 Congratulations!** Your LinkedIn Job Application Automation System is now ready to use. Proceed to the User Guide to learn how to operate the system effectively.