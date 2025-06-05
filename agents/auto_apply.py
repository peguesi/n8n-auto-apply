#!/usr/bin/env python3
"""
LinkedIn Auto-Apply Module
Leverages existing scraper configuration and Playwright setup
"""

import asyncio
import json
import os
import re
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from playwright.async_api import async_playwright, Page, BrowserContext
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Import Azure OpenAI
try:
    from openai import AzureOpenAI
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("⚠️ Azure OpenAI not available")

load_dotenv()

# Reuse configuration from linkedin_scraper.py
COOKIE = os.getenv("LINKEDIN_COOKIE")
USER_AGENT = os.getenv("USER_AGENT")

# Azure OpenAI Configuration (from your scraper)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# Auto-apply specific config
MAX_DAILY_APPLICATIONS = int(os.getenv("MAX_DAILY_APPS", 50))
CONCURRENT_WINDOWS = int(os.getenv("CONCURRENT_WINDOWS", 3))
BUSINESS_HOURS_ONLY = os.getenv("BUSINESS_HOURS_ONLY", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Google Sheets config
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Job Applications Tracker")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_apply.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QAMemoryBank:
    """Manages question-answer pairs for reuse"""
    
    def __init__(self, sheet_client):
        self.sheet = sheet_client
        self.cache = {}
        self.load_from_sheet()
    
    def load_from_sheet(self):
        """Load Q&A pairs from Google Sheets"""
        try:
            # Assume "QA Memory" tab exists
            worksheet = self.sheet.worksheet("QA Memory")
            records = worksheet.get_all_records()
            
            for record in records:
                question = record.get("Question", "").lower().strip()
                answer = record.get("Answer", "")
                context = record.get("Context", "")
                
                if question and answer:
                    self.cache[question] = {
                        "answer": answer,
                        "context": context,
                        "use_count": record.get("Use Count", 0)
                    }
            
            logger.info(f"Loaded {len(self.cache)} Q&A pairs from memory")
            
        except Exception as e:
            logger.warning(f"Could not load Q&A memory: {e}")
            # Create the sheet if it doesn't exist
            try:
                self.sheet.add_worksheet(title="QA Memory", rows=1000, cols=5)
                self.sheet.worksheet("QA Memory").update('A1:E1', 
                    [["Question", "Answer", "Context", "Use Count", "Last Used"]])
            except:
                pass
    
    def get_answer(self, question: str, context: Dict = None) -> Optional[str]:
        """Get answer from memory if exists"""
        q_lower = question.lower().strip()
        
        # Direct match
        if q_lower in self.cache:
            return self.cache[q_lower]["answer"]
        
        # Fuzzy match (contains key phrases)
        for cached_q, data in self.cache.items():
            if self._similar_question(q_lower, cached_q):
                return data["answer"]
        
        return None
    
    def save_answer(self, question: str, answer: str, context: str = ""):
        """Save new Q&A pair to memory"""
        self.cache[question.lower().strip()] = {
            "answer": answer,
            "context": context,
            "use_count": 1
        }
        
        # Append to sheet
        try:
            worksheet = self.sheet.worksheet("QA Memory")
            worksheet.append_row([
                question,
                answer,
                context,
                1,
                datetime.now().isoformat()
            ])
        except Exception as e:
            logger.error(f"Failed to save Q&A to sheet: {e}")
    
    def _similar_question(self, q1: str, q2: str) -> bool:
        """Check if questions are similar enough"""
        # Simple similarity check - can be enhanced
        key_phrases = ["why", "interest", "experience", "salary", "start", "location"]
        
        for phrase in key_phrases:
            if phrase in q1 and phrase in q2:
                return True
        
        return False


class LinkedInAutoApply:
    """Main auto-apply engine"""
    
    async def debug_form_fields(self, page: Page):
        """Debug mode to print all form fields and their metadata"""
        logger.info("🔍 Debugging form fields on page...")
        # Updated selector: also look for label[for] for better label matching
        inputs = await page.query_selector_all('input, select, textarea')
        for i, field in enumerate(inputs, 1):
            name = await field.get_attribute("name")
            fid = await field.get_attribute("id")
            placeholder = await field.get_attribute("placeholder")
            ftype = await field.get_attribute("type")
            label = None
            try:
                # Try to find label by proximity or labels property, fallback to label[for]
                # Replacement logic as requested
                fid = await field.get_attribute("id")
                label = None
                try:
                    label_el = await field.evaluate_handle("e => e.closest('label') || e.labels?.[0]")
                    if label_el:
                        label = await label_el.evaluate("el => el.innerText")
                    elif fid:
                        label_el = await page.query_selector(f'label[for="{fid}"]')
                        if label_el:
                            label = await label_el.inner_text()
                except:
                    pass
            except:
                pass
            logger.info(f"#{i}: name={name}, id={fid}, placeholder={placeholder}, type={ftype}, label={label}")
    
    def __init__(self):
        self.setup_google_sheets()
        self.setup_azure_client()
        self.qa_memory = QAMemoryBank(self.sheets_client)
        self.screenshots_dir = Path("data/apply_screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.daily_count = self.get_todays_application_count()
        self.session_stats = {
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "unsupported_ats": 0
        }
    
    def setup_google_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                     'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_PATH, scopes=scope)
            self.sheets_client = gspread.authorize(creds).open_by_key(os.environ["GOOGLE_SHEET_ID"])
            self.main_sheet = self.sheets_client.sheet1
            logger.info("✅ Google Sheets connected")
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise
    
    def setup_azure_client(self):
        """Initialize Azure OpenAI client"""
        if AZURE_AVAILABLE and AZURE_OPENAI_KEY:
            self.azure_client = AzureOpenAI(
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_KEY,
                api_version=AZURE_OPENAI_API_VERSION
            )
            self.cheap_model = "gpt-35-turbo"
            self.vision_model = "gpt-4o"
            logger.info("✅ Azure OpenAI connected")
        else:
            self.azure_client = None
            logger.warning("⚠️ Azure OpenAI not configured")
    
    def get_todays_application_count(self) -> int:
        """Get count of today's applications"""
        try:
            records = self.main_sheet.get_all_records()
            today = datetime.now().date()
            count = 0
            
            for record in records:
                if record.get("Status") == "Applied":
                    applied_date = record.get("Applied Date", "")
                    if applied_date and datetime.fromisoformat(applied_date).date() == today:
                        count += 1
            
            return count
        except:
            return 0
    
    def can_apply_now(self) -> Tuple[bool, str]:
        """Check if we can apply now based on limits and schedule"""
        # Daily limit check
        if self.daily_count >= MAX_DAILY_APPLICATIONS:
            return False, f"Daily limit reached ({MAX_DAILY_APPLICATIONS})"
        
        # Business hours check
        if BUSINESS_HOURS_ONLY:
            current_hour = datetime.now().hour
            if current_hour < 9 or current_hour > 18:
                return False, "Outside business hours"
        
        return True, "OK"
    
    async def create_browser_context(self, playwright) -> BrowserContext:
        """Create browser context using persistent session via WebKit (headful)"""
        user_data_path = str(Path.home() / ".pw-session-apply")
        try:
            context = await playwright.webkit.launch_persistent_context(
                user_data_dir=user_data_path,
                headless=False,
                viewport={"width": 1280, "height": 800}
            )
            logger.info("🖥️ Browser launched in headful mode")
            return context
        except Exception as e:
            logger.warning(f"WebKit persistent context failed: {e} — falling back to Chromium")

            # Fallback to Chromium persistent context
            try:
                context = await playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_path,
                    headless=False,
                    viewport={"width": 1280, "height": 800}
                )
                logger.info("🖥️ Browser launched in headful mode")
                return context
            except Exception as e2:
                logger.error(f"Chromium persistent context also failed: {e2}")
                raise
    
    async def get_next_job(self) -> Optional[Dict]:
        """Get next job from sheet marked as 'Ready'"""
        try:
            records = self.main_sheet.get_all_records()

            # Debug: List all job statuses and their row numbers
            for i, record in enumerate(records, start=2):
                status = record.get("Status")
                logger.debug(f"Row {i}: Status='{status}'")

            # Filter and sort jobs
            ready_jobs = []
            for i, record in enumerate(records, start=2):  # Sheet rows start at 2
                if record.get("Status") == "unknown" or record.get("Status") == "Ready":
                    # Calculate priority
                    score = float(record.get("Score", 0))
                    posted_days = self._parse_posted_time(record.get("Posted Time", ""))
                    priority = score * 0.7 + (10 - min(posted_days, 10)) * 0.3

                    ready_jobs.append({
                        "row": i,
                        "data": record,
                        "priority": priority
                    })

            if not ready_jobs:
                return None

            # Sort by priority
            ready_jobs.sort(key=lambda x: x["priority"], reverse=True)
            return ready_jobs[0]

        except Exception as e:
            logger.error(f"Failed to get next job: {e}")
            return None
    
    def _parse_posted_time(self, time_str: str) -> int:
        """Parse LinkedIn posted time to days"""
        if "hour" in time_str:
            return 0
        elif "day" in time_str:
            match = re.search(r'(\d+)', time_str)
            return int(match.group(1)) if match else 1
        elif "week" in time_str:
            match = re.search(r'(\d+)', time_str)
            return int(match.group(1)) * 7 if match else 7
        else:
            return 30  # Assume old
    
    async def apply_to_job(self, page: Page, job_data: Dict) -> Dict[str, Any]:
        """Main application flow"""
        result = {
            "success": False,
            "ats_type": "unknown",
            "error": None,
            "screenshot": None
        }
        
        try:
            # Navigate to LinkedIn job
            job_url = job_data["data"]["Job URL"]
            logger.info(f"📍 Navigating to: {job_url}")

            try:
                await page.goto(job_url, wait_until="domcontentloaded", timeout=15000)
                logger.info(f"✅ Page loaded with domcontentloaded")
            except Exception as e:
                logger.warning(f"domcontentloaded failed: {e}, trying load instead...")
                await page.goto(job_url, wait_until="load", timeout=10000)

            await page.wait_for_timeout(3000)  # Let page settle
            
            
            # Log first 200 chars of page content for debugging
            content_snippet = (await page.content())[:200]
            logger.debug(f"Page content snippet: {content_snippet}")
            await page.wait_for_timeout(2000)

            # Detect if job_url directly points to an ATS page (e.g., Ashby)
            initial_ats = await self.detect_ats(page)
            logger.info(f"🔍 Detected ATS on initial page: {initial_ats}")
            if initial_ats == "ashby":
                logger.info("🧪 Direct ATS page detected, invoking apply_ashby")
                result["ats_type"] = "ashby"
                result["success"] = await self.apply_ashby(page, job_data)
                return result

            # Debug: list all form-related elements before finding buttons
            all_fields = await page.query_selector_all('input, select, textarea, button')
            for idx, elem in enumerate(all_fields, 1):
                tag = await elem.evaluate("e => e.tagName")
                name = await elem.get_attribute("name")
                # Playwright async API: need to handle exceptions for .evaluate
                try:
                    text = await elem.evaluate("e => e.innerText")
                except Exception:
                    text = ""
                logger.debug(f"Field #{idx}: tag={tag}, name={name}, text='{text[:30]}'")

            # Check if Easy Apply
            easy_apply_button = await page.query_selector('button:has-text("Easy Apply")')
            if easy_apply_button:
                result["ats_type"] = "linkedin_easy"
                result["success"] = await self.handle_easy_apply(page, job_data)
                return result
            
            # Click regular Apply button
            apply_button = await page.query_selector('button:has-text("Apply")')
            if not apply_button:
                apply_button = await page.query_selector('a:has-text("Apply")')
            
            if not apply_button:
                shot = await self.capture_screenshot(page, f"no_apply_btn_{job_data['data']['Job ID']}")
                logger.warning(f"⚠️ Screenshot saved due to missing apply button: {shot}")
                result["error"] = "No apply button found"
                return result
            
            # Click and handle new tab/window
            async with page.context.expect_page() as new_page_info:
                await apply_button.click()
                new_page = await new_page_info.value
            
            # Wait for new page to load
            await new_page.wait_for_load_state("networkidle")
            await new_page.wait_for_timeout(3000)
            
            # Detect ATS
            result["ats_type"] = await self.detect_ats(new_page)
            logger.info(f"🔍 Detected ATS: {result['ats_type']}")
            if result["ats_type"] == "ashby":
                logger.info("🧪 Entering Ashby application handler")
            
            # Apply based on ATS type
            if result["ats_type"] == "ashby":
                result["success"] = await self.apply_ashby(new_page, job_data)
                logger.info(f"🧪 Ashby apply result: {result['success']}")
            elif result["ats_type"] == "greenhouse":
                result["success"] = await self.apply_greenhouse(new_page, job_data)
            elif result["ats_type"] == "workday":
                result["success"] = await self.apply_workday(new_page, job_data)
            else:
                result["error"] = f"Unsupported ATS: {result['ats_type']}"
                self.session_stats["unsupported_ats"] += 1
            
            # Take screenshot if failed
            if not result["success"]:
                screenshot_path = await self.capture_screenshot(new_page, job_data["data"]["Job ID"])
                result["screenshot"] = screenshot_path
            
            # Close the application tab
            await new_page.close()
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            result["error"] = str(e)
            result["screenshot"] = await self.capture_screenshot(page, job_data["data"]["Job ID"])
        
        return result
    
    async def detect_ats(self, page: Page) -> str:
        """Detect which ATS system is being used"""
        url = page.url.lower()
        
        # URL-based detection
        if "ashbyhq.com" in url:
            return "ashby"
        elif "greenhouse.io" in url or "boards.greenhouse" in url:
            return "greenhouse"
        elif "myworkdayjobs.com" in url:
            return "workday"
        elif "lever.co" in url:
            return "lever"
        elif "bamboohr.com" in url:
            return "bamboohr"
        
        # Content-based detection
        try:
            content = await page.content()
            content_lower = content.lower()
            
            if "ashby" in content_lower and "ashbyhq" in content_lower:
                return "ashby"
            elif "greenhouse" in content_lower:
                return "greenhouse"
            elif "workday" in content_lower:
                return "workday"
        except:
            pass
        
        return "unknown"
    
    async def apply_ashby(self, page: Page, job_data: Dict) -> bool:
        """Enhanced Ashby application handler with improved form validation and submission"""
        try:
            logger.info("🎯 Applying via Ashby")
            logger.info("🧪 Starting Ashby form field detection and filling sequence")

            # Wait for form to be fully loaded
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)

            # List all detected fields for debugging
            form_inputs = await page.query_selector_all('input, select, textarea')
            for idx, field in enumerate(form_inputs, 1):
                name = await field.get_attribute("name")
                field_id = await field.get_attribute("id")
                ftype = await field.get_attribute("type")
                placeholder = await field.get_attribute("placeholder")
                logger.info(f"🧾 Field #{idx}: name={name}, id={field_id}, type={ftype}, placeholder={placeholder}")

            # Check for any error messages first
            error_messages = await page.query_selector_all('[role="alert"], .error, .warning, [class*="error"]')
            if error_messages:
                for error in error_messages:
                    error_text = await error.inner_text()
                    logger.warning(f"⚠️ Form error detected: {error_text}")

            # Fill basic fields with validation
            success_count = 0
            
            # Name field
            name_field = await page.query_selector(
                'input[name="_systemfield_name"], input[name="name"], input[placeholder*="name" i]'
            )
            if name_field:
                await name_field.scroll_into_view_if_needed()
                await name_field.fill("")  # Clear existing content
                await name_field.fill("Isaiah Pegues")
                # Validate the field was filled
                filled_value = await name_field.input_value()
                if filled_value == "Isaiah Pegues":
                    logger.info("✅ Name field filled and validated")
                    success_count += 1
                else:
                    logger.warning(f"⚠️ Name field validation failed: expected 'Isaiah Pegues', got '{filled_value}'")
            else:
                logger.warning("⚠️ Name field not found")

            # Email field
            email_field = await page.query_selector(
                'input[name="_systemfield_email"], input[name="email"], input[type="email"]'
            )
            if email_field:
                await email_field.scroll_into_view_if_needed()
                await email_field.fill("")  # Clear existing content
                await email_field.fill("isaiah@pegues.io")
                # Validate email field
                filled_value = await email_field.input_value()
                if filled_value == "isaiah@pegues.io":
                    logger.info("✅ Email field filled and validated")
                    success_count += 1
                else:
                    logger.warning(f"⚠️ Email field validation failed: expected 'isaiah@pegues.io', got '{filled_value}'")
            else:
                logger.warning("⚠️ Email field not found")

            # Phone field (if available)
            phone_field = await page.query_selector('input[name="phone"], input[type="tel"], input[placeholder*="phone" i]')
            if phone_field:
                await phone_field.scroll_into_view_if_needed()
                await phone_field.fill("")  # Clear existing content
                await phone_field.fill("+4915112205900")
                logger.info("✅ Phone field filled")
                success_count += 1

            # LinkedIn field (if available)
            linkedin_field = await page.query_selector('input[name="linkedin"], input[placeholder*="linkedin" i]')
            if linkedin_field:
                await linkedin_field.scroll_into_view_if_needed()
                await linkedin_field.fill("")  # Clear existing content
                await linkedin_field.fill("https://linkedin.com/in/isaiahupegues")
                logger.info("✅ LinkedIn field filled")
                success_count += 1

            # Portfolio field (if available)
            portfolio_field = await page.query_selector(
                'input[name="portfolio"], input[name="website"], input[placeholder*="portfolio" i], input[placeholder*="website" i]'
            )
            if portfolio_field:
                await portfolio_field.scroll_into_view_if_needed()
                await portfolio_field.fill("")  # Clear existing content
                utm_link = self.generate_utm_link(job_data["data"])
                await portfolio_field.fill(utm_link)
                logger.info(f"✅ Portfolio field filled with UTM link")
                success_count += 1

            # Resume upload with enhanced validation
            resume_input = await page.query_selector(
                'input[type="file"][name="resume"], input[type="file"]#_systemfield_resume, input[type="file"]'
            )
            resume_link = job_data["data"].get("Resume Link")
            if resume_input and resume_link:
                resume_path = Path(resume_link)
                if resume_path.exists():
                    logger.info(f"📄 Uploading resume from: {resume_path}")
                    await resume_input.set_input_files(str(resume_path))
                    
                    # Wait for upload to complete and validate
                    await page.wait_for_timeout(2000)
                    
                    # Check if file was uploaded (look for file name display)
                    uploaded_file_indicator = await page.query_selector_all('a:has-text(".pdf"), [class*="file"], [class*="upload"]')
                    if uploaded_file_indicator:
                        logger.info("✅ Resume upload validated")
                        success_count += 1
                    else:
                        logger.warning("⚠️ Resume upload may have failed - no confirmation found")
                else:
                    logger.warning(f"⚠️ Resume file not found at {resume_path}")

            # Handle all types of questions (text, dropdown, radio)
            await self.handle_all_questions(page, job_data)

            # Pre-submission validation
            logger.info(f"📊 Form filling summary: {success_count} fields successfully filled")
            
            # Check for required field validation
            required_field_errors = await page.query_selector_all('[aria-invalid="true"], .required.error, [class*="required"][class*="error"]')
            if required_field_errors:
                logger.warning(f"⚠️ Found {len(required_field_errors)} required field errors")
                for error_field in required_field_errors:
                    field_name = await error_field.get_attribute("name") or await error_field.get_attribute("id") or "unknown"
                    logger.warning(f"   - Required field error: {field_name}")

            # Enhanced submit button handling
            await page.wait_for_timeout(1000)  # Let form settle
            
            # Try multiple submit button selectors
            submit_selectors = [
                'button:has-text("Submit Application")',
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Submit")',
                '[role="button"]:has-text("Submit")'
            ]
            
            submit_button = None
            for selector in submit_selectors:
                submit_button = await page.query_selector(selector)
                if submit_button:
                    button_text = await submit_button.inner_text()
                    logger.info(f"🔍 Found submit button with selector '{selector}': '{button_text}'")
                    break
            
            if not submit_button:
                logger.error("❌ No submit button found with any selector")
                await self.debug_form_fields(page)
                debug_shot = await self.capture_screenshot(page, f"no_submit_btn_{job_data['data']['Job ID']}")
                logger.info(f"📸 Debug screenshot: {debug_shot}")
                return False

            # Enhanced submission process
            logger.info("📋 Preparing for form submission...")
            
            # Scroll submit button into view
            await submit_button.scroll_into_view_if_needed()
            
            # Check button state
            is_visible = await submit_button.is_visible()
            is_enabled = await submit_button.is_enabled()
            is_disabled = await submit_button.get_attribute("disabled")
            
            logger.info(f"🔍 Submit button state: visible={is_visible}, enabled={is_enabled}, disabled={is_disabled}")
            
            if not is_visible or not is_enabled or is_disabled:
                logger.warning("⚠️ Submit button not ready for clicking")
                # Try to identify what's blocking submission
                form_validation_errors = await page.query_selector_all('[class*="error"], [aria-invalid="true"]')
                if form_validation_errors:
                    logger.warning("🚫 Form has validation errors:")
                    for error in form_validation_errors:
                        error_text = await error.inner_text()
                        logger.warning(f"   - {error_text}")
                
                # Take screenshot for debugging
                debug_shot = await self.capture_screenshot(page, f"submit_blocked_{job_data['data']['Job ID']}")
                logger.info(f"📸 Submit blocked screenshot: {debug_shot}")
                return False

            # Capture pre-submission state
            pre_submit_url = page.url
            logger.info(f"📍 Pre-submission URL: {pre_submit_url}")
            
            # Try submission with multiple strategies
            submission_successful = False
            
            # Strategy 1: Normal click
            try:
                logger.info("🖱️ Attempting normal click on submit button...")
                await submit_button.click()
                await page.wait_for_timeout(3000)
                
                post_click_url = page.url
                logger.info(f"📍 Post-click URL: {post_click_url}")
                
                if post_click_url != pre_submit_url:
                    logger.info("✅ URL changed after click - potential success")
                    submission_successful = True
                else:
                    logger.warning("⚠️ URL unchanged after normal click")
            
            except Exception as e:
                logger.warning(f"⚠️ Normal click failed: {e}")
            
            # Strategy 2: Force click if normal click failed
            if not submission_successful:
                try:
                    logger.info("🖱️ Attempting force click...")
                    await submit_button.click(force=True)
                    await page.wait_for_timeout(3000)
                    
                    post_force_url = page.url
                    logger.info(f"📍 Post-force-click URL: {post_force_url}")
                    
                    if post_force_url != pre_submit_url:
                        logger.info("✅ URL changed after force click")
                        submission_successful = True
                    else:
                        logger.warning("⚠️ URL unchanged after force click")
                
                except Exception as e:
                    logger.warning(f"⚠️ Force click failed: {e}")
            
            # Strategy 3: JavaScript click if both previous failed
            if not submission_successful:
                try:
                    logger.info("🖱️ Attempting JavaScript click...")
                    await submit_button.evaluate("element => element.click()")
                    await page.wait_for_timeout(3000)
                    
                    post_js_url = page.url
                    logger.info(f"📍 Post-JS-click URL: {post_js_url}")
                    
                    if post_js_url != pre_submit_url:
                        logger.info("✅ URL changed after JS click")
                        submission_successful = True
                    else:
                        logger.warning("⚠️ URL unchanged after JS click")
                
                except Exception as e:
                    logger.warning(f"⚠️ JavaScript click failed: {e}")

            # Strategy 4: Double click if previous clicks failed
            if not submission_successful:
                try:
                    logger.info("🖱️ Attempting double click on submit button...")
                    await submit_button.dblclick()
                    await page.wait_for_timeout(3000)
                    post_double_url = page.url
                    logger.info(f"📍 Post-double-click URL: {post_double_url}")
                    if post_double_url != pre_submit_url:
                        logger.info("✅ URL changed after double click")
                        submission_successful = True
                    else:
                        logger.warning("⚠️ URL unchanged after double click")
                except Exception as e:
                    logger.warning(f"⚠️ Double click failed: {e}")
            
            # Enhanced success detection
            final_url = page.url
            logger.info(f"🌐 Final URL: {final_url}")
            
            # Multiple success indicators
            success_indicators = [
                "thank" in final_url.lower(),
                "success" in final_url.lower(),
                "confirmation" in final_url.lower(),
                "submitted" in final_url.lower(),
                await page.query_selector('text*="thank you"') is not None,
                await page.query_selector('text*="received"') is not None,
                await page.query_selector('text*="submitted"') is not None,
                await page.query_selector('text*="application sent"') is not None,
                await page.query_selector('[class*="success"]') is not None,
                await page.query_selector('[class*="confirmation"]') is not None,
                await page.query_selector('text*="your application was successfully submitted"') is not None
            ]
            
            if any(success_indicators):
                logger.info("✅ Application submission detected - SUCCESS!")
                
                # Capture success screenshot
                success_shot = await self.capture_screenshot(page, f"success_{job_data['data']['Job ID']}")
                logger.info(f"📸 Success screenshot: {success_shot}")
                
                return True
            
            else:
                logger.warning("⚠️ No submission success indicators found")
                
                # Look for specific error messages
                error_messages = await page.query_selector_all('[role="alert"], .error, [class*="error"]')
                if error_messages:
                    logger.error("❌ Form submission errors found:")
                    for error in error_messages:
                        error_text = await error.inner_text()
                        logger.error(f"   - {error_text}")
                
                # Capture failure screenshot
                failure_shot = await self.capture_screenshot(page, f"submission_failed_{job_data['data']['Job ID']}")
                logger.info(f"📸 Failure screenshot: {failure_shot}")
                
                return False

        except Exception as e:
            logger.error(f"❌ Ashby application error: {e}")
            error_shot = await self.capture_screenshot(page, f"error_{job_data['data']['Job ID']}")
            logger.info(f"📸 Error screenshot: {error_shot}")
            return False
    
    async def fill_basic_info(self, page: Page, job_data: Dict):
        """Fill basic information fields"""
        # Name
        name_field = await page.query_selector(
            'input[name="name"], input[name="_systemfield_name"], input[placeholder*="name" i]'
        )
        if name_field:
            logger.info(f"🎯 Name field detected: {await name_field.get_attribute('name')}")
            await name_field.scroll_into_view_if_needed()
            await name_field.fill("Isaiah Pegues")
            logger.info("✅ Filled name field with Isaiah Pegues")
        else:
            logger.warning("⚠️ Name field not found")

        # Email
        email_field = await page.query_selector(
            'input[name="email"], input[name="_systemfield_email"], input[type="email"]'
        )
        if email_field:
            logger.info(f"🎯 Email field detected: {await email_field.get_attribute('name')}")
            await email_field.scroll_into_view_if_needed()
            await email_field.fill("isaiah@pegues.io")
            logger.info("✅ Filled email field with isaiah@pegues.io")
        else:
            logger.warning("⚠️ Email field not found")

        # Phone
        phone_field = await page.query_selector('input[name="phone"], input[type="tel"]')
        if phone_field:
            logger.info(f"🎯 Phone field detected: {await phone_field.get_attribute('name')}")
            await phone_field.scroll_into_view_if_needed()
            await phone_field.fill("+4915112205900")
            logger.info("✅ Filled phone field with +4915112205900")
        else:
            logger.warning("⚠️ Phone field not found")

        # LinkedIn
        linkedin_field = await page.query_selector('input[name="linkedin"], input[placeholder*="linkedin" i]')
        if linkedin_field:
            logger.info(f"🎯 LinkedIn field detected: {await linkedin_field.get_attribute('name')}")
            await linkedin_field.scroll_into_view_if_needed()
            await linkedin_field.fill("https://linkedin.com/in/isaiahupegues")
            logger.info("✅ Filled LinkedIn field with https://linkedin.com/in/isaiahupegues")
        else:
            logger.warning("⚠️ LinkedIn field not found")

        # Portfolio with UTM
        portfolio_field = await page.query_selector(
            'input[name="portfolio"], input[name="website"], input[placeholder*="portfolio" i]'
        )
        if portfolio_field:
            logger.info(f"🎯 Portfolio field detected: {await portfolio_field.get_attribute('name')}")
            await portfolio_field.scroll_into_view_if_needed()
            utm_link = self.generate_utm_link(job_data["data"])
            await portfolio_field.fill(utm_link)
            logger.info(f"✅ Filled portfolio/website field with {utm_link}")
        else:
            logger.warning("⚠️ Portfolio/website field not found")
    
    async def handle_custom_questions(self, page: Page, job_data: Dict):
        """Handle custom questions using AI"""
        # Find all question containers
        question_containers = await page.query_selector_all(
            'div:has(> label):has(> textarea), div:has(> label):has(> input[type="text"])'
        )

        for container in question_containers:
            try:
                # Get question text
                label = await container.query_selector('label')
                if not label:
                    continue

                question_text = await label.inner_text()
                logger.info(f"💬 Found question: {question_text}")

                # Skip if already filled
                input_field = await container.query_selector('textarea, input[type="text"]')
                if not input_field:
                    continue

                existing_value = await input_field.get_attribute('value')
                if existing_value and existing_value.strip():
                    continue

                # Check memory first
                answer = self.qa_memory.get_answer(question_text, job_data)
                if answer is not None:
                    logger.info("♻️ Reused answer from memory")
                else:
                    # Generate new answer
                    answer = await self.generate_answer(question_text, job_data)
                    logger.info("🤖 Generated new answer via AI")
                    # Save to memory
                    self.qa_memory.save_answer(
                        question_text,
                        answer,
                        f"{job_data['data']['Company']} - {job_data['data']['Title']}"
                    )

                # Fill answer
                await input_field.fill(answer)
                logger.info(f"✅ Answered question: {question_text[:50]}... → {answer[:50]}...")

            except Exception as e:
                logger.error(f"Error handling question: {e}")
                continue
    
    async def handle_all_questions(self, page: Page, job_data: Dict):
        """
        Finds text‐inputs, dropdowns, and radio groups with a <label>
        and uses AI (plus memory) to fill/choose answers.
        """
        logger.info("💬 Running AI‐driven question handler...")

        job_context = {
            "company": job_data["data"]["Company"],
            "title": job_data["data"]["Title"],
            "score": job_data["data"].get("Score", 0),
            "why_good_fit": job_data["data"].get("Why Good Fit", "")
        }

        # 1) FREE‐TEXT QUESTIONS (textarea or input[type="text"])
        text_containers = await page.query_selector_all(
            'div:has(> label):has(> textarea), div:has(> label):has(> input[type="text"])'
        )
        for container in text_containers:
            try:
                label_el = await container.query_selector("label")
                if not label_el:
                    continue
                question_label = (await label_el.inner_text()).strip()
                if not question_label:
                    continue

                input_el = await container.query_selector("textarea, input[type='text']")
                if not input_el:
                    continue

                # skip if already filled
                existing_val = await input_el.input_value()
                if existing_val and existing_val.strip():
                    continue

                # Check memory first
                mem_key = question_label.lower().strip()
                answer = self.qa_memory.get_answer(mem_key)
                if not answer:
                    # Build prompt including personal & job context
                    personal_context = (
                        "Personal Context: I live in Germany and hold a valid visa, "
                        "I am authorized to work in the US without restriction, "
                        "I can start one month from today's date, "
                        "and my salary expectation should align with the role and company."
                    )
                    prompt = (
                        f"You are helping complete a job application. {personal_context}\n\n"
                        f"Job Context:\n"
                        f"- Company: {job_context['company']}\n"
                        f"- Role: {job_context['title']}\n"
                        f"- Fit Score: {job_context['score']}/10\n"
                        f"- Key Strengths: {job_context['why_good_fit']}\n\n"
                        f"Question: {question_label}\n\n"
                        "Provide a direct answer (max 100 words) that addresses this question."
                    )
                    try:
                        resp = await self.azure_client.chat.completions.create(
                            model=self.cheap_model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=120,
                            temperature=0.7
                        )
                        answer = resp.choices[0].message.content.strip()
                    except Exception as e:
                        logger.warning(f"AI failed for {question_label}: {e}")
                        answer = self.fallback_answer(question_label)

                    # Save to memory
                    self.qa_memory.save_answer(mem_key, answer, f"{job_context['company']} - {job_context['title']}")

                # Fill the field
                await input_el.scroll_into_view_if_needed()
                await input_el.fill(answer)
                logger.info(f"✅ Filled text question: {question_label} → {answer[:50]}")

            except Exception as e:
                logger.error(f"Error in free‐text question handler: {e}")
                continue

        # 2) DROPDOWN QUESTIONS (<select>)
        dropdown_containers = await page.query_selector_all(
            'div:has(> label):has(> select)'
        )
        for container in dropdown_containers:
            try:
                label_el = await container.query_selector("label")
                if not label_el:
                    continue
                question_label = (await label_el.inner_text()).strip()
                if not question_label:
                    continue

                select_el = await container.query_selector("select")
                if not select_el:
                    continue

                # Gather all visible options, ignoring empty/placeholder
                opts = await select_el.query_selector_all("option")
                option_texts = [
                    (await opt.inner_text()).strip()
                    for opt in opts
                    if (await opt.inner_text()).strip() and not (await opt.get_attribute("disabled"))
                ]
                if not option_texts:
                    continue

                # Check memory (use question_label + joined options as key)
                opt_key = question_label.lower().strip() + "||" + "|".join(option_texts)
                answer_text = self.qa_memory.get_answer(opt_key)
                if not answer_text:
                    # Ask AI to pick one
                    personal_context = (
                        "Personal Context: I live in Germany and hold a valid visa, "
                        "I am authorized to work in the US without restriction, "
                        "I can start one month from today's date, "
                        "and my salary expectation should align with the role and company."
                    )
                    prompt = (
                        f"You are helping complete a job application for {job_context['title']} at {job_context['company']}.\n"
                        f"{personal_context}\n"
                        f"Question: {question_label}\n"
                        f"Choices: {option_texts}\n"
                        "Reply with exactly the one choice that best fits."
                    )
                    ai_choice = None
                    try:
                        resp = await self.azure_client.chat.completions.create(
                            model=self.cheap_model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=30,
                            temperature=0.5
                        )
                        candidate = resp.choices[0].message.content.strip()
                        for txt in option_texts:
                            if candidate.lower() in txt.lower() or txt.lower() in candidate.lower():
                                ai_choice = txt
                                break
                    except Exception as e:
                        logger.warning(f"AI failed for dropdown {question_label}: {e}")

                    if not ai_choice:
                        ai_choice = option_texts[0]
                        logger.warning(f"Defaulting dropdown “{question_label}” → “{ai_choice}”")

                    answer_text = ai_choice
                    # Save memory
                    self.qa_memory.save_answer(opt_key, answer_text, f"{job_context['company']} - {job_context['title']}")

                # Finally, select that option
                await select_el.scroll_into_view_if_needed()
                await select_el.select_option({"label": answer_text})
                logger.info(f"✅ Selected dropdown {question_label} → {answer_text}")

            except Exception as e:
                logger.error(f"Error in dropdown handler: {e}")
                continue

        # 3) RADIO BUTTON GROUPS (<input type="radio">)
        radio_containers = await page.query_selector_all(
            'div:has(> label):has(> input[type="radio"]), fieldset:has(> legend):has(> input[type="radio"])'
        )
        for container in radio_containers:
            try:
                # Get the question label (either <legend> inside a fieldset, or the first <label>)
                legend = await container.query_selector("legend")
                if legend:
                    question_label = (await legend.inner_text()).strip()
                else:
                    lbl = await container.query_selector("label")
                    question_label = (await lbl.inner_text()).strip() if lbl else None
                if not question_label:
                    continue

                # Gather all (input, label) pairs
                radios = await container.query_selector_all("input[type='radio']")
                radio_options = []
                for r in radios:
                    rid = await r.get_attribute("id")
                    if rid:
                        lbl = await page.query_selector(f"label[for='{rid}']")
                        if lbl:
                            txt = (await lbl.inner_text()).strip()
                            radio_options.append((r, txt))
                    else:
                        # fallback: use value or aria-label
                        val = await r.get_attribute("value") or await r.get_attribute("aria-label")
                        if val:
                            radio_options.append((r, val.strip()))

                if not radio_options:
                    continue

                # Form a key for memory: label + joined option texts
                opts = [txt for (_e, txt) in radio_options]
                opt_key = question_label.lower().strip() + "||" + "|".join(opts)
                answer_text = self.qa_memory.get_answer(opt_key)
                if not answer_text:
                    # Ask AI to choose
                    personal_context = (
                        "Personal Context: I live in Germany and hold a valid visa, "
                        "I am authorized to work in the US without restriction, "
                        "I can start one month from today's date, "
                        "and my salary expectation should align with the role and company."
                    )
                    prompt = (
                        f"You are helping complete a job application for {job_context['title']} at {job_context['company']}.\n"
                        f"{personal_context}\n"
                        f"Question: {question_label}\n"
                        f"Options: {opts}\n"
                        "Reply with exactly the best one."
                    )
                    ai_choice = None
                    try:
                        resp = await self.azure_client.chat.completions.create(
                            model=self.cheap_model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=30,
                            temperature=0.5
                        )
                        candidate = resp.choices[0].message.content.strip()
                        for txt in opts:
                            if candidate.lower() in txt.lower() or txt.lower() in candidate.lower():
                                ai_choice = txt
                                break
                    except Exception as e:
                        logger.warning(f"AI failed for radio {question_label}: {e}")

                    if not ai_choice:
                        ai_choice = opts[0]
                        logger.warning(f"Defaulting radio {question_label} → {ai_choice}")

                    answer_text = ai_choice
                    # Save memory
                    self.qa_memory.save_answer(opt_key, answer_text, f"{job_context['company']} - {job_context['title']}")

                # Click the matching radio
                for (radio_el, txt) in radio_options:
                    if txt == answer_text:
                        await radio_el.scroll_into_view_if_needed()
                        await radio_el.check()
                        logger.info(f"✅ Checked radio {question_label} → {answer_text}")
                        break

            except Exception as e:
                logger.error(f"Error in radio handler: {e}")
                continue

    async def generate_answer(self, question: str, job_data: Dict) -> str:
        """Generate answer using Azure OpenAI"""
        if not self.azure_client:
            return self.fallback_answer(question)
        
        try:
            # Prepare context
            job_context = {
                "company": job_data["data"]["Company"],
                "title": job_data["data"]["Title"],
                "score": job_data["data"]["Score"],
                "cover_letter": job_data["data"].get("Cover Letter Link", ""),
                "why_good_fit": job_data["data"].get("Why Good Fit", "")
            }

            personal_context = (
                "Personal Context: I live in Germany and hold a valid visa, "
                "I am authorized to work in the US without restriction, "
                "I can start one month from today's date, "
                "and my salary expectation should align with the role and company."
            )

            prompt = (
                f"You are helping complete a job application. {personal_context}\n\n"
                f"Job Context:\n"
                f"- Company: {job_context['company']}\n"
                f"- Role: {job_context['title']}\n"
                f"- Fit Score: {job_context['score']}/10\n"
                f"- Key Strengths: {job_context['why_good_fit']}\n\n"
                f"Question: {question}\n\n"
                "Provide a direct answer (max 150 words) that:\n"
                "1. Addresses the question specifically\n"
                "2. Highlights relevant experience\n"
                "3. Shows enthusiasm for this specific role\n"
                "4. Uses keywords from the job description if available\n\n"
                "Answer:"
            )

            response = self.azure_client.chat.completions.create(
                model=self.cheap_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            return answer
            
        except Exception as e:
            logger.error(f"Azure OpenAI error: {e}")
            return self.fallback_answer(question)
    
    def fallback_answer(self, question: str) -> str:
        """Fallback answers when AI is unavailable"""
        q_lower = question.lower()
        
        if "why" in q_lower and ("interested" in q_lower or "apply" in q_lower):
            return "I'm excited about this role because it aligns perfectly with my experience in product management and my passion for building innovative solutions. The opportunity to contribute to your team's mission while growing my skills in this area is exactly what I'm looking for."
        
        elif "salary" in q_lower or "compensation" in q_lower:
            return "I'm open to discussing compensation based on the full scope of the role and total compensation package. I'm confident we can find a mutually beneficial arrangement."
        
        elif "start" in q_lower or "available" in q_lower:
            return "I can start within 2-3 weeks of accepting an offer, allowing time for a smooth transition."
        
        elif "visa" in q_lower or "authorization" in q_lower:
            return "I am authorized to work in the EU (Germany) and am exploring opportunities that may offer visa sponsorship for other locations."
        
        else:
            return "I would be happy to discuss this further during the interview process."
    
    def generate_utm_link(self, job_data: Dict) -> str:
        """Generate UTM link for tracking"""
        company_slug = re.sub(r'[^a-z0-9]+', '-', job_data["Company"].lower()).strip('-')
        role_slug = re.sub(r'[^a-z0-9]+', '-', job_data["Title"].lower()).strip('-')[:20]
        
        return f"https://isaiah.pegues.io?utm_source=job_app&utm_medium=ashby&utm_campaign={company_slug}-{role_slug}"
    
    async def capture_screenshot(self, page: Page, job_id: str) -> str:
        """Capture screenshot for debugging"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{job_id}_{timestamp}.png"
            filepath = self.screenshots_dir / filename
            
            await page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"📸 Screenshot saved: {filename}")
            
            # TODO: Upload to Google Drive
            
            return str(filepath)
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return ""
    
    def update_sheet_status(self, row: int, status: str, ats_type: str = "", error: str = ""):
        """Update job status in Google Sheet"""
        try:
            updates = [
                (f"F{row}", status),  # Status column
                (f"J{row}", ats_type),  # ATS Type column
                (f"Q{row}", f"Applied: {datetime.now().isoformat()}")  # Notes
            ]

            if status == "Applied":
                updates.append((f"P{row}", datetime.now().date().isoformat()))  # Applied Date

            if error:
                updates.append((f"Q{row}", f"Error: {error}"))

            for cell, value in updates:
                self.main_sheet.update(range_name=cell, values=[[value]])

        except Exception as e:
            logger.error(f"Failed to update sheet: {e}")
    
    async def send_telegram_notification(self, message: str):
        """Send Telegram notification"""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                data = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML"
                }
                await client.post(url, json=data)
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
    
    async def run_application_cycle(self):
        """Run one application cycle"""
        # Check if we can apply
        can_apply, reason = self.can_apply_now()
        if not can_apply:
            logger.info(f"⏸️ Cannot apply: {reason}")
            return
        
        # Get next job
        job = await self.get_next_job()
        if not job:
            logger.info("📭 No jobs ready to apply")
            return
        
        job_info = job["data"]
        logger.info(f"🎯 Applying to: {job_info['Title']} at {job_info['Company']}")
        logger.info(f"Job data: Title='{job_info.get('Title')}', Company='{job_info.get('Company')}', Job URL='{job_info.get('Job URL')}'")
        
        # Update status to "Applying"
        self.update_sheet_status(job["row"], "Applying")
        self.session_stats["attempted"] += 1
        
        # Launch Playwright and browser context without auto-closing
        p = await async_playwright().start()
        context = await self.create_browser_context(p)
        page = await context.new_page()
        
        result = await self.apply_to_job(page, job)
        
        logger.info("ℹ️ Keeping browser open for inspection after submit.")
        # Note: Not closing context or Playwright, so browser remains open for debugging
        
        # Update results
        if result["success"]:
            self.update_sheet_status(job["row"], "Applied", result["ats_type"])
            self.session_stats["successful"] += 1
            self.daily_count += 1
            logger.info("✅ Application successful!")
            
        else:
            self.update_sheet_status(job["row"], "Failed", result["ats_type"], result["error"])
            self.session_stats["failed"] += 1
            
            # Send notification
            message = f"""❌ <b>Application Failed</b>
            
Job: {job_info['Title']}
Company: {job_info['Company']}
ATS: {result['ats_type']}
Error: {result['error']}

<a href="{job_info['Job URL']}">View Job</a>"""
            
            await self.send_telegram_notification(message)
    
    async def run_continuous(self, interval_minutes: int = 10):
        """Run continuously with interval"""
        logger.info(f"🚀 Starting auto-apply service (interval: {interval_minutes} min)")
        
        while True:
            try:
                await self.run_application_cycle()
                
                # Log session stats periodically
                if self.session_stats["attempted"] % 10 == 0:
                    logger.info(f"📊 Session stats: {self.session_stats}")
                
            except Exception as e:
                logger.error(f"Cycle error: {e}")
            
            # Wait for next cycle
            logger.info(f"⏳ Waiting {interval_minutes} minutes...")
            await asyncio.sleep(interval_minutes * 60)

    async def debug_submission_state(self, page: Page, job_id: str):
        """Comprehensive debugging for submission issues"""
        logger.info("🔍 Running comprehensive form submission debug...")
        
        # 1. Check all form elements
        logger.info("📋 Form Elements Analysis:")
        form = await page.query_selector('form')
        if form:
            form_action = await form.get_attribute('action')
            form_method = await form.get_attribute('method')
            logger.info(f"   Form action: {form_action}, method: {form_method}")
        else:
            logger.warning("   No <form> element found")
        
        # 2. Check required fields
        required_fields = await page.query_selector_all('[required], [aria-required=\"true\"], [class*=\"required\"]')
        logger.info(f"📝 Required Fields ({len(required_fields)}):")
        for i, field in enumerate(required_fields):
            name = await field.get_attribute('name') or await field.get_attribute('id') or f"field_{i}"
            value = await field.input_value() if await field.evaluate('el => el.tagName') in ['INPUT', 'TEXTAREA'] else 'N/A'
            is_filled = bool(value and value.strip())
            logger.info(f"   - {name}: {'✅ filled' if is_filled else '❌ empty'} (value: '{value[:30]}')")
        
        # 3. Check validation errors
        validation_errors = await page.query_selector_all('[aria-invalid=\"true\"], .error, [class*=\"error\"]')
        logger.info(f"🚫 Validation Errors ({len(validation_errors)}):")
        for error in validation_errors:
            error_text = await error.inner_text()
            field_name = await error.get_attribute('name') or await error.get_attribute('id') or 'unknown'
            logger.info(f"   - {field_name}: {error_text}")
        
        # 4. Check submit buttons
        all_buttons = await page.query_selector_all('button, input[type=\"submit\"], [role=\"button\"]')
        logger.info(f"🔘 All Buttons ({len(all_buttons)}):")
        for i, btn in enumerate(all_buttons):
            text = await btn.inner_text()
            btn_type = await btn.get_attribute('type')
            disabled = await btn.get_attribute('disabled')
            visible = await btn.is_visible()
            enabled = await btn.is_enabled()
            logger.info(f"   Button {i+1}: '{text}' type={btn_type} disabled={disabled} visible={visible} enabled={enabled}")
        
        # 5. Check for reCAPTCHA
        recaptcha = await page.query_selector('[class*=\"recaptcha\"], [id*=\"recaptcha\"], iframe[src*=\"recaptcha\"]')
        if recaptcha:
            logger.warning("🤖 reCAPTCHA detected - may need manual intervention")
        
        # 6. Check JavaScript errors
        try:
            js_errors = await page.evaluate("""
                () => {
                    const errors = window.jsErrors || [];
                    return errors.map(e => e.toString());
                }
            """)
            if js_errors:
                logger.warning(f"⚠️ JavaScript errors detected: {js_errors}")
        except:
            pass
        
        # 7. Take comprehensive screenshot
        debug_shot = await self.capture_screenshot(page, f"debug_comprehensive_{job_id}")
        logger.info(f"📸 Comprehensive debug screenshot: {debug_shot}")

    async def wait_for_submission_completion(self, page: Page, timeout: int = 10000):
        """Wait for form submission to complete with multiple indicators"""
        logger.info("⏳ Waiting for submission completion...")
        
        start_url = page.url
        start_time = time.time()
        
        while (time.time() - start_time) * 1000 < timeout:
            current_url = page.url
            
            # Check for URL change
            if current_url != start_url:
                logger.info(f"✅ URL changed: {start_url} → {current_url}")
                return True
            
            # Check for success indicators
            success_selectors = [
                'text*="thank you"',
                'text*="received"', 
                'text*="submitted"',
                'text*="application sent"',
                '[class*="success"]',
                '[class*="confirmation"]'
            ]
            
            for selector in success_selectors:
                if await page.query_selector(selector):
                    logger.info(f"✅ Success indicator found: {selector}")
                    return True
            
            # Check for error indicators
            error_selectors = [
                '[role="alert"]',
                '.error',
                '[class*="error"]',
                'text*="error"',
                'text*="failed"'
            ]
            
            for selector in error_selectors:
                error_element = await page.query_selector(selector)
                if error_element:
                    error_text = await error_element.inner_text()
                    logger.warning(f"⚠️ Error indicator found: {error_text}")
                    return False
            
            await page.wait_for_timeout(500)
        
        logger.warning("⏳ Submission timeout reached")
        return False

    async def handle_recaptcha(self, page: Page) -> bool:
        """Handle reCAPTCHA if present"""
        recaptcha_frame = await page.query_selector('iframe[src*="recaptcha"]')
        if not recaptcha_frame:
            return True  # No reCAPTCHA, continue
        
        logger.info("🤖 reCAPTCHA detected, attempting to handle...")
        
        try:
            # Switch to reCAPTCHA frame
            recaptcha_content = await recaptcha_frame.content_frame()
            
            # Look for "I'm not a robot" checkbox
            checkbox = await recaptcha_content.query_selector('[role="checkbox"]')
            if checkbox:
                logger.info("🖱️ Clicking 'I'm not a robot' checkbox...")
                await checkbox.click()
                
                # Wait for verification
                await page.wait_for_timeout(3000)
                
                # Check if challenge appeared
                challenge_frame = await page.query_selector('iframe[src*="recaptcha"][src*="bframe"]')
                if challenge_frame:
                    logger.warning("🧩 reCAPTCHA challenge appeared - manual intervention needed")
                    
                    # Pause for manual solving
                    logger.info("⏸️ Please solve the reCAPTCHA manually. Waiting 60 seconds...")
                    await page.wait_for_timeout(60000)
                    
                    return True  # Assume user solved it
                else:
                    logger.info("✅ reCAPTCHA verified automatically")
                    return True
            
        except Exception as e:
            logger.error(f"❌ reCAPTCHA handling error: {e}")
            return False
        
        return True

    
async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LinkedIn Auto-Apply Bot")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=10, help="Minutes between applications")
    parser.add_argument("--url", type=str, help="LinkedIn job URL to test directly")
    parser.add_argument("--debug-url", type=str, help="URL to debug form fields")

    args = parser.parse_args()

    if args.debug_url:
        applier = LinkedInAutoApply()
        async with async_playwright() as p:
            context = await applier.create_browser_context(p)
            page = await context.new_page()
            logger.info(f"🧪 Debugging form at: {args.debug_url}")
            await page.goto(args.debug_url, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            await applier.debug_form_fields(page)
            await context.close()
        return

    if args.url:
        applier = LinkedInAutoApply()
        async with async_playwright() as p:
            context = await applier.create_browser_context(p)
            page = await context.new_page()
            logger.info(f"🧪 Testing direct job URL: {args.url}")
            await page.goto(args.url, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            ats_type = await applier.detect_ats(page)
            print(f"Detected ATS: {ats_type}")
            await context.close()
        return

    # Initialize
    applier = LinkedInAutoApply()

    if args.once:
        await applier.run_application_cycle()
    else:
        await applier.run_continuous(args.interval)


if __name__ == "__main__":
    asyncio.run(main())