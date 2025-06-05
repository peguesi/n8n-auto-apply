# LinkedIn Job Application Automation System

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green.svg)](https://fastapi.tiangolo.com/)
[![Azure OpenAI](https://img.shields.io/badge/Azure-OpenAI-orange.svg)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)

A comprehensive AI-powered system that automatically discovers LinkedIn job opportunities, analyzes job fit using advanced AI, generates personalized application materials, and submits applications across multiple ATS platforms.

## 🚀 Key Features

### **Intelligent Job Discovery**
- **Advanced LinkedIn Scraping**: Enhanced pagination support with multi-strategy job extraction
- **Smart Filtering**: AI-powered relevance scoring (1-10 scale) with detailed fit analysis
- **Business Hours Automation**: Scheduled discovery across EMEA/NYC timezones

### **AI-Powered Content Generation**
- **Strategic Analysis**: Company context validation and role-specific positioning
- **Personalized Documents**: Dynamic resume and cover letter generation with exact template mapping
- **Authenticity Controls**: Metric usage tracking and company accuracy validation
- **UTM Tracking**: Portfolio link optimization for application tracking

### **Automated Application Submission**
- **Multi-ATS Support**: Ashby, Greenhouse, Workday, Lever, BambooHR
- **Intelligent Form Filling**: AI-powered question answering with memory bank
- **Smart Rate Limiting**: Business hours controls with daily application limits
- **Comprehensive Tracking**: Google Sheets integration with real-time status updates

### **Enterprise Monitoring**
- **Error Detection**: Telegram notifications for system issues
- **Debug Capabilities**: Screenshot capture and HTML analysis for troubleshooting
- **Performance Metrics**: Application success rates and ATS compatibility tracking
- **Data Backup**: Automatic backups with recovery procedures

## 📋 Prerequisites

### **System Requirements**
- Python 3.8 or higher
- Node.js 16+ (for n8n automation)
- 4GB+ RAM recommended
- 2GB+ storage for job data and documents

### **Required Accounts & APIs**
- **Azure OpenAI**: GPT-4 access with Assistant API
- **Google Sheets API**: Service account credentials
- **Telegram Bot**: For error notifications
- **LinkedIn**: Active account (automation compliant)
- **n8n**: Self-hosted or cloud instance

## ⚡ Quick Start

### 1. **Clone and Setup Environment**

```bash
# Clone the repository
git clone <repository-url>
cd linkedin-job-automation

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install webkit chromium
```

### 2. **Configure Environment Variables**

Create a `.env` file in the project root:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_VECTOR_STORE_ID=vs_your_vector_store_id
AZURE_ASSISTANT_ID=asst_your_assistant_id

# LinkedIn Configuration
LINKEDIN_COOKIE="your-linkedin-session-cookie"
USER_AGENT="Mozilla/5.0 (compatible browser string)"
SEARCH_URLS="https://www.linkedin.com/jobs/search/?keywords=Senior%20Product%20Manager&location=New%20York"

# Google Sheets Integration
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_SHEET_ID=your-google-sheet-id
GOOGLE_SHEET_NAME="Job Applications Tracker"

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Application Settings
MAX_DAILY_APPS=50
BUSINESS_HOURS_ONLY=true
WEBHOOK_URL=http://localhost:5678/webhook/new-job
```

### 3. **Setup Azure OpenAI Assistant**

```bash
# Create the AI assistant with vector store
python setup_assistant.py

# This will output your AZURE_ASSISTANT_ID and AZURE_VECTOR_STORE_ID
# Add these to your .env file
```

### 4. **Test the System**

```bash
# Start the API server
python main.py

# Test LinkedIn scraping
curl -X POST "http://localhost:8000/scrape/linkedin" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://www.linkedin.com/jobs/search/?keywords=Product%20Manager"]}'

# Check results
curl "http://localhost:8000/linkedin/results"

# Test AI analysis on a single job
curl -X POST "http://localhost:8000/agent/enhanced-process-single" \
  -H "Content-Type: application/json" \
  -d '{"id": "test", "title": "Senior Product Manager", "company": "Test Corp", "description": "Test job description"}'
```

### 5. **Setup n8n Automation (Optional)**

```bash
# Import the n8n workflow
# Copy contents of n8n_autoapply.json to your n8n instance

# Configure webhook URL in n8n to point to your API
# Enable the workflow for automated scheduling
```

## 🔄 Basic Usage Workflow

### **Manual Operation**

```bash
# 1. Scrape jobs from LinkedIn
python linkedin_scraper.py "https://www.linkedin.com/jobs/search/?keywords=Senior%20Product%20Manager"

# 2. Analyze jobs with AI
python job_ai_pipeline.py data/linkedin/results/latest.jsonl

# 3. Generate documents for high-scoring jobs
python content_generator.py data/linkedin/results/latest.jsonl --type both

# 4. Apply to jobs (with human supervision)
python auto_apply.py --once
```

### **API Operation**

```python
import requests

# Process a single job through the full pipeline
job_data = {
    "id": "linkedin_123456",
    "title": "Senior Product Manager", 
    "company": "Amazing Company",
    "description": "We're looking for a Senior PM...",
    "url": "https://linkedin.com/jobs/view/123456"
}

# Run complete analysis and document generation
response = requests.post(
    "http://localhost:8000/agent/enhanced-process-single",
    json=job_data
)

result = response.json()
print(f"Score: {result['job']['fit_analysis']['overall_score']}/10")
print(f"Resume: {result['job']['resume_link']}")
print(f"Cover Letter: {result['job']['cover_letter_link']}")
```

### **Automated Operation**

1. **Import n8n workflow**: Use `n8n_autoapply.json`
2. **Configure schedules**: EMEA (5-19h) and NYC (7-21h) business hours
3. **Monitor via Telegram**: Error notifications and application updates
4. **Track in Google Sheets**: Real-time application pipeline status

## 📊 Understanding the AI Analysis

The system provides detailed scoring across multiple dimensions:

### **Fit Analysis Scores (1-10 scale)**
- **Overall Score**: Combined assessment of job compatibility
- **ATS Screening**: Keyword matching and qualification alignment  
- **Human Appeal**: Relevant experience and career progression
- **Domain Expertise**: Industry and technical skill alignment
- **Role Fit**: Seniority and compensation compatibility

### **Recommendations**
- `apply_now`: High-confidence match, immediate application
- `apply_different_level`: Good company, consider adjusted role
- `network_first`: Strategic opportunity, relationship building recommended
- `skip`: Poor fit, automated filtering

### **Content Strategy**
- **Company Relevance**: HIGH/MEDIUM/LOW based on domain alignment
- **Keyword Integration**: Natural ATS optimization
- **Authenticity Controls**: Prevents metric fabrication and ensures accuracy

## 🛠️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   LinkedIn      │────│   AI Analysis    │────│   Document      │
│   Scraper       │    │   Pipeline       │    │   Generation    │
│                 │    │                  │    │                 │
│ • Pagination    │    │ • Fit Scoring    │    │ • Resume PDF    │
│ • Job Extract   │    │ • Content Plan   │    │ • Cover Letter  │
│ • Description   │    │ • Company Valid  │    │ • UTM Tracking  │
│   Cleaning      │    │ • Authenticity   │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                     ┌─────────────────┐
                     │   Auto-Apply    │
                     │   System        │
                     │                 │
                     │ • ATS Detection │
                     │ • Form Filling  │
                     │ • AI Q&A        │
                     │ • Tracking      │
                     └─────────────────┘
```

## 📁 Project Structure

```
linkedin-job-automation/
├── agents/                          # Core AI and automation logic
│   ├── linkedin_scraper.py         # Enhanced LinkedIn job scraping
│   ├── job_ai_pipeline.py          # AI analysis and content generation
│   ├── content_generator.py        # PDF document generation
│   └── auto_apply.py               # Automated application submission
├── api/                            # FastAPI application and routes
│   ├── main.py                     # Main API server
│   ├── agent_routes.py             # AI pipeline endpoints
│   └── content_routes.py           # Document generation endpoints
├── templates/                      # HTML templates for documents
│   ├── resume-template-annotated.html
│   └── cover-letter-template-annotated.html
├── data/                          # Generated data and results
│   ├── linkedin/                  # Scraped job data (JSONL)
│   ├── resumes/                   # Generated PDF documents
│   └── logs/                      # System logs and debug info
├── workflows/                     # n8n automation workflows  
│   └── n8n_autoapply.json        # Complete automation workflow
├── docs/                          # Documentation
└── requirements.txt               # Python dependencies
```

## 🔧 Configuration Options

### **Scraping Configuration**
- `MAX_PAGES`: Maximum pages to scrape per search (default: 20)
- `RATE_LIMIT`: Delay between requests in seconds (default: 1-3)
- `USER_AGENT`: Browser user agent string
- `SEARCH_URLS`: Comma-separated LinkedIn search URLs

### **AI Analysis Configuration**  
- `MIN_SCORE_THRESHOLD`: Minimum score for content generation (default: 6)
- `COMPANY_CONTEXTS`: Custom company descriptions for validation
- `METRIC_LIMITS`: Authenticity controls for content generation

### **Application Configuration**
- `MAX_DAILY_APPS`: Daily application limit (default: 50)
- `BUSINESS_HOURS_ONLY`: Restrict to business hours (default: true)  
- `ATS_TIMEOUT`: Form submission timeout in seconds (default: 30)

## 🚨 Troubleshooting

### **Common Issues**

#### **LinkedIn Access Issues**
```bash
# Symptom: "Redirected to login" errors
# Solution: Update LINKEDIN_COOKIE in .env
# Get cookie from browser dev tools after logging in
```

#### **Azure OpenAI Errors**
```bash
# Symptom: "Assistant not found" or API errors
# Solution: Verify assistant setup and API keys
python setup_assistant.py --verify
```

#### **PDF Generation Failures**
```bash
# Symptom: WeasyPrint errors or malformed PDFs
# Solution: Check template syntax and install fonts
sudo apt-get install fonts-liberation  # Linux
brew install --cask font-lato font-oswald  # macOS
```

#### **Application Submission Failures**
```bash
# Symptom: Forms not submitting or ATS detection issues
# Solution: Check screenshots in data/apply_screenshots/
# Enable debug mode for detailed form analysis
python auto_apply.py --debug-url "https://jobs.ashbyhq.com/example"
```

### **Debug Procedures**

1. **Enable Debug Logging**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Check System Status**
   ```bash
   curl "http://localhost:8000/status"
   ```

3. **Analyze Screenshots**
   - Scraping issues: `data/linkedin/{date}/screenshots/`
   - Application issues: `data/apply_screenshots/`

4. **Review Logs**
   - Main system: `linkedin_scraper.log`
   - Applications: `auto_apply.log`
   - API server: Console output

## 🛡️ Security & Compliance

### **Data Privacy**
- All job data stored locally in JSONL format
- No sensitive data transmitted to third parties
- Google Sheets integration uses service account credentials
- Telegram notifications contain minimal personally identifiable information

### **LinkedIn Compliance**
- Respects rate limiting and robots.txt
- Uses realistic user agent strings
- Implements random delays between requests
- No aggressive scraping or ToS violations

### **Best Practices**
- Store API keys in environment variables
- Use service account credentials for Google Sheets
- Regularly rotate authentication tokens
- Monitor application success rates to avoid detection

## 📈 Performance & Scaling

### **Current Capacity**
- **Jobs/Hour**: ~200-300 job analyses
- **Applications/Day**: Up to 50 (configurable)
- **Concurrent Processing**: Single-threaded by design for stability
- **Storage**: ~1GB per 10,000 jobs processed

### **Optimization Tips**
- Use SSD storage for faster JSONL processing
- Increase `MAX_DAILY_APPS` gradually to test limits
- Monitor Azure OpenAI token usage and costs
- Implement job deduplication for efficiency

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Documentation**: [Full Documentation](docs/)
- **Community**: [Discussions](https://github.com/your-repo/discussions)

---

**⚠️ Disclaimer**: This tool is for personal use only. Users are responsible for compliance with LinkedIn's Terms of Service and applicable laws. Use responsibly and ethically.