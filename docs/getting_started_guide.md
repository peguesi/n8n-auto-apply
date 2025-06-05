# Getting Started Guide

Welcome to the LinkedIn Job Application Automation System! This guide will walk you through using the system effectively, from your first job search to understanding AI analysis and monitoring your application pipeline.

## 🎯 Prerequisites

Before starting, ensure you have:
- ✅ Completed the [Environment Setup](environment-setup.md)
- ✅ System passing health checks
- ✅ API server running (`python main.py`)
- ✅ Basic understanding of the [system architecture](README.md#system-architecture)

## 🚀 Your First Job Search

### Step 1: Configure Your Search Criteria

The quality of your results depends heavily on well-configured search URLs. Let's create effective LinkedIn search URLs:

```bash
# Basic search structure
https://www.linkedin.com/jobs/search/?keywords={JOB_TITLE}&location={LOCATION}&{FILTERS}

# Example: Senior Product Manager in NYC, remote OK, posted in last 24 hours
https://www.linkedin.com/jobs/search/?keywords=Senior%20Product%20Manager&location=New%20York&f_WT=2&f_TPR=r86400
```

**Key Search Parameters:**
- `keywords`: Your target job title (URL encoded)
- `location`: Geographic preference
- `f_WT=2`: Include remote work options
- `f_TPR=r86400`: Posted in last 24 hours (r604800 = 7 days)
- `f_E=4`: Senior level positions
- `f_C=123456`: Specific company (get ID from LinkedIn)

### Step 2: Update Your Search URLs

```bash
# Edit your .env file
SEARCH_URLS="https://www.linkedin.com/jobs/search/?keywords=Senior%20Product%20Manager&location=New%20York&f_WT=2&f_TPR=r86400,https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&location=San%20Francisco&f_WT=2&f_TPR=r86400"
```

**Pro Tips for Search URLs:**
- Start with 2-3 URLs maximum for testing
- Use recent time filters (`f_TPR=r86400`) to avoid duplicate applications
- Include remote work filter (`f_WT=2`) to expand opportunities
- Test URLs manually in browser first to ensure they return results

### Step 3: Run Your First Scrape

```bash
# Start with a test scrape
curl -X POST "http://localhost:8000/scrape/linkedin" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&location=New%20York&f_TPR=r86400"]}'

# Check the results
curl "http://localhost:8000/linkedin/results" | jq '.total_records'
```

**What to Expect:**
- First scrape may take 5-10 minutes for 2-3 pages of results
- You should see 25-75 jobs from a typical search
- Debug screenshots saved if issues occur
- JSONL file created with job data

### Step 4: Verify Your Data

```bash
# Get the latest job to verify scraping worked
curl "http://localhost:8000/linkedin/results/latest" | jq '.job | {title, company, description_length: (.description | length)}'

# Check data quality
curl "http://localhost:8000/linkedin/results" | jq '.data | length'  # Total jobs
curl "http://localhost:8000/linkedin/results" | jq '.data | map(select(.description | length > 100)) | length'  # Jobs with good descriptions
```

## 🧠 Understanding AI Analysis

### Step 5: Run AI Analysis on Your Jobs

```bash
# Analyze all scraped jobs with AI
curl -X POST "http://localhost:8000/agent/enhanced-fit"

# Check analysis results
curl "http://localhost:8000/agent/classify-fit/results" | jq '.total_classified'
```

### Understanding the AI Scoring System

The AI analyzes each job across multiple dimensions with a **1-10 scoring system**:

#### **Overall Score (1-10)**
- **9-10**: Exceptional fit, apply immediately
- **7-8**: Strong fit, high priority application
- **5-6**: Moderate fit, consider based on other factors
- **3-4**: Weak fit, likely not worth pursuing
- **1-2**: Poor fit, automated skip

#### **Component Scores Breakdown**

```json
{
  "overall_score": 8,
  "interview_probability": 75,
  "recommendation": "apply_now",
  "analysis": {
    "ats_screening": {
      "score": 8,
      "critical_missing_keywords": [],
      "years_experience_match": true,
      "education_match": true
    },
    "human_reviewer_appeal": {
      "score": 9,
      "relevant_companies": true,
      "career_progression": true,
      "quantified_achievements": true
    },
    "domain_expertise": {
      "score": 7,
      "industry_match": "strong",
      "technical_alignment": "moderate",
      "true_gaps": ["specific domain knowledge"],
      "inferrable_from_experience": ["leadership in fintech"]
    },
    "role_fit": {
      "score": 8,
      "seniority_match": "appropriate",
      "compensation_alignment": "likely",
      "location_compatible": true
    }
  }
}
```

**ATS Screening (1-10)**: How well you match automated keyword filters
- Checks years of experience, education requirements
- Identifies critical missing keywords
- Predicts ATS pass-through likelihood

**Human Reviewer Appeal (1-10)**: How attractive your profile is to human recruiters
- Evaluates company relevance and career progression
- Assesses quantified achievements and impact metrics
- Considers cultural and team fit indicators

**Domain Expertise (1-10)**: Technical and industry knowledge alignment
- Measures industry experience match
- Identifies true skill gaps vs. learnable skills
- Assesses technical tool and methodology alignment

**Role Fit (1-10)**: Overall position compatibility
- Evaluates seniority level appropriateness
- Predicts salary/compensation alignment
- Considers location and work arrangement fit

### AI Recommendations Explained

#### **`apply_now`** (Scores 7-10)
- High-confidence match across multiple dimensions
- Strong likelihood of interview if application submitted
- AI will generate strategic, customized content
- Priority for immediate application

#### **`apply_different_level`** (Scores 5-8)
- Good company/culture fit but role level mismatch
- Consider reaching out for adjacent roles
- May be worth networking contact instead of direct application
- Review similar roles at the same company

#### **`network_first`** (Scores 4-7)
- Interesting opportunity but not immediate fit
- Relationship building recommended before applying
- Consider LinkedIn outreach or industry events
- May be good future opportunity

#### **`skip`** (Scores 1-4)
- Poor fit across multiple dimensions
- Low likelihood of positive response
- Time better spent on higher-scoring opportunities
- Automated filtering recommendation

### Step 6: Review AI Analysis Results

```bash
# Get top opportunities
curl "http://localhost:8000/agent/classify-fit/top-opportunities?limit=5" | jq '.top_opportunities[] | {title, company, score: .fit_analysis.overall_score, recommendation: .fit_analysis.recommendation}'

# Get jobs by recommendation type
curl "http://localhost:8000/agent/classify-fit/results" | jq '.results | map(select(.fit_analysis.recommendation == "apply_now")) | length'

# Review specific high-scoring job
JOB_ID=$(curl -s "http://localhost:8000/agent/classify-fit/top-opportunities?limit=1" | jq -r '.top_opportunities[0].id')
curl "http://localhost:8000/linkedin/results/${JOB_ID}" | jq '.job.fit_analysis'
```

## 📄 Document Generation

### Step 7: Generate Your First Application Documents

```bash
# Get a high-scoring job for document generation
HIGH_SCORE_JOB=$(curl -s "http://localhost:8000/agent/classify-fit/top-opportunities?limit=1" | jq -r '.top_opportunities[0].id')

# Generate both resume and cover letter
curl -X POST "http://localhost:8000/content/generate" \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$HIGH_SCORE_JOB\", \"document_type\": \"both\"}"
```

**Understanding Document Generation:**

The system creates two types of documents:
1. **Strategic Resume**: Tailored to the specific job with optimized bullet points
2. **Personalized Cover Letter**: Company-specific content with strategic positioning

#### **Resume Generation Process**
```json
{
  "role_title": "Senior Product Manager",  // Optimized for job
  "profile_section": "Strategic 450-character profile with keywords",
  "employment_bullets": {
    "wercflow": ["AI-powered bullet point 1", "Metric-driven bullet 2"],
    "atlassian": ["Enterprise-focused bullet 1", "Scale-focused bullet 2"]
  },
  "skills_section": ["Skill 1", "Skill 2", "..."]  // 10 optimized skills
}
```

#### **Cover Letter Generation Process**
- **Paragraph 1**: Why this specific job/company appeals to you
- **Paragraph 2**: Most relevant experience with metrics
- **Paragraph 3**: Additional qualifications and strategic fit
- **Paragraph 4**: Call to action and next steps

### Step 8: Review Generated Documents

```bash
# Check generated documents location
curl "http://localhost:8000/content/documents?limit=5" | jq '.documents[] | {filename, type, size, created}'

# Validate document generation was successful
ls -la data/resumes/*.pdf | head -5
```

**Quality Checks for Generated Documents:**
- ✅ Resume PDF opens and displays correctly
- ✅ Cover letter contains company-specific references
- ✅ No template placeholders left unfilled
- ✅ UTM links work in portfolio references
- ✅ Professional formatting maintained

## 📊 Monitoring Your Application Pipeline

### Step 9: Set Up Application Tracking

The system integrates with Google Sheets for comprehensive tracking:

```bash
# Check Google Sheets integration
curl "http://localhost:8000/status" | jq '.google_sheets_connected'

# Verify jobs are being tracked
# Check your Google Sheet - jobs should appear with:
# - Job details (title, company, location)
# - AI scores and recommendations  
# - Document links
# - Application status
```

**Google Sheets Columns Explained:**
- **Score**: AI overall score (1-10)
- **Interview Probability**: Likelihood of getting interview (0-100%)
- **Recommendation**: AI recommendation (apply_now, etc.)
- **Status**: Current application status (Ready, Applying, Applied, Failed)
- **Resume Link**: Path to generated resume PDF
- **Cover Letter Link**: Path to generated cover letter PDF
- **Why Good Fit**: AI explanation of fit reasoning

### Step 10: Understand Application Status Flow

```bash
Ready → Applying → Applied ✅
  ↓         ↓         ↓
Skip    Failed ❌   Follow-up
```

**Status Meanings:**
- **Ready**: Has documents, score ≥6, ready for application
- **Applying**: Currently being processed by auto-apply system
- **Applied**: Successfully submitted application
- **Failed**: Application submission failed (check screenshots)
- **Skip**: Below threshold or manual skip decision

## 🎯 Best Practices for Success

### Search Strategy Best Practices

1. **Start Narrow, Then Expand**
   ```bash
   # Week 1: Test with specific, high-intent searches
   "Senior Product Manager" + "SaaS" + specific location
   
   # Week 2: Expand to adjacent roles  
   "Product Manager" + "Technical PM" + broader location
   
   # Week 3: Add industry variations
   "Product Lead" + "Product Owner" + remote
   ```

2. **Time-Based Filtering**
   ```bash
   # Daily runs: Last 24 hours only
   f_TPR=r86400
   
   # Weekly runs: Last 7 days
   f_TPR=r604800
   
   # Avoid: No time filter (creates duplicates)
   ```

3. **Location Strategy**
   ```bash
   # Primary market
   location=New%20York
   
   # Secondary market with remote
   location=San%20Francisco&f_WT=2
   
   # Pure remote
   f_WT=2&location=United%20States
   ```

### AI Analysis Optimization

1. **Score Interpretation Guidelines**
   - **Apply to scores 7+**: High likelihood of success
   - **Review scores 5-6**: Manual evaluation recommended
   - **Skip scores <5**: Focus time on better opportunities

2. **Recommendation Actions**
   ```bash
   apply_now → Generate docs + apply immediately
   apply_different_level → Research other roles at company
   network_first → LinkedIn outreach + industry events
   skip → Ignore unless criteria change
   ```

3. **Content Strategy Understanding**
   - AI identifies which companies to emphasize in bullets
   - Keywords integrated naturally (max 1 per bullet)
   - Metrics used strategically (each metric used only once)
   - Company contexts maintained accurately

### Document Quality Control

1. **Pre-Application Checklist**
   - [ ] Resume PDF opens correctly
   - [ ] Cover letter mentions specific company
   - [ ] No "TEMPLATE_PLACEHOLDER" text remaining
   - [ ] Portfolio UTM links work
   - [ ] Contact information accurate

2. **Template Customization**
   ```bash
   # Customize for your background
   # Edit: resume-template-annotated.html
   # Update: contact information, portfolio links
   # Modify: color scheme and fonts if needed
   ```

3. **A/B Testing Approach**
   - Generate documents for similar roles
   - Compare content strategies
   - Track application success rates
   - Iterate on template and prompting

### Performance Monitoring

1. **Key Metrics to Track**
   ```bash
   # Application funnel
   Jobs Scraped → AI Analyzed → Docs Generated → Applications Sent → Responses
   
   # Success rates
   Application Success Rate = Applied / Ready
   Response Rate = Responses / Applied
   Interview Rate = Interviews / Responses
   ```

2. **Quality Indicators**
   ```bash
   # Daily monitoring
   curl "http://localhost:8000/agent/classify-fit/summary" | jq '.summary'
   
   # Check for system health
   curl "http://localhost:8000/status"
   
   # Review error rates
   grep -c "ERROR" linkedin_scraper.log
   ```

## 🔄 Daily/Weekly Workflows

### Daily Workflow (10 minutes)

```bash
# 1. Check system status
curl "http://localhost:8000/status"

# 2. Review new high-scoring jobs
curl "http://localhost:8000/agent/classify-fit/top-opportunities?limit=3"

# 3. Generate documents for apply_now jobs
# (Done automatically if using n8n)

# 4. Review Google Sheet for any failed applications
# Check screenshots for debugging

# 5. Update search criteria if needed
# Add new keywords or locations based on results
```

### Weekly Workflow (30 minutes)

```bash
# 1. Analyze performance metrics
python analyze_logs.py

# 2. Review application success rates in Google Sheets
# Calculate: Applied / Ready ratio
# Track: Response rates and interview conversions

# 3. Optimize search criteria
# Remove low-performing search URLs
# Add new search terms based on successful applications

# 4. Clean up old data files
# Archive job data older than 30 days
# Clean debug screenshots and logs

# 5. Update LinkedIn cookie if needed
# Check for login redirect errors
# Refresh session cookie monthly
```

## 🚨 When Things Go Wrong

### Quick Diagnosis

```bash
# System not working at all?
python health_check.py

# No new jobs being found?
# Check LinkedIn cookie expiration
# Verify search URLs return results manually

# AI analysis failing?
# Check Azure OpenAI API key and quotas
# Verify assistant ID configuration

# Documents not generating?
# Check WeasyPrint installation
# Verify template files exist

# Applications failing?
# Review screenshots in data/apply_screenshots/
# Check Google Sheets integration
```

### Getting Help

1. **Check the logs first**: `linkedin_scraper.log`, `auto_apply.log`
2. **Run diagnostics**: Use health check and debug scripts
3. **Review recent changes**: What changed since it last worked?
4. **Check external services**: Azure, Google Sheets, LinkedIn access
5. **Gather debug info**: Use `gather_debug_info.py` script

## 🎯 Success Metrics & Goals

### Week 1 Goals
- [ ] Successfully scrape 50+ relevant jobs
- [ ] Generate AI analysis for all jobs
- [ ] Create documents for 5+ high-scoring positions
- [ ] Submit 3-5 applications (manually or automated)

### Month 1 Goals
- [ ] Establish consistent daily/weekly workflows
- [ ] Achieve 80%+ application success rate (no technical failures)
- [ ] Generate 20+ tailored resumes and cover letters
- [ ] Track 5+ interview opportunities from applications

### Ongoing Optimization
- [ ] Refine search criteria based on success patterns
- [ ] Customize templates for better personal branding
- [ ] Optimize AI prompts for better content generation
- [ ] Scale to multiple job markets or roles

---

**🎉 Congratulations!** You now have a comprehensive understanding of how to use the LinkedIn Job Application Automation System effectively. The key to success is starting with focused search criteria, understanding the AI analysis, and iteratively optimizing based on results.

**Next Steps**: Review the [AI Pipeline Documentation](ai-pipeline.md) for deeper insights into how the system analyzes jobs and generates content.