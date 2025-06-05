#!/usr/bin/env python3
"""
Enhanced Content Generator - Resume + Cover Letter
Backward compatible with existing ExactMappingGenerator while adding cover letter support
FIXED: PDF margin/padding issues, added cover letter support
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
   from weasyprint import HTML, CSS
   WEASYPRINT_AVAILABLE = True
except ImportError:
   print("❌ WeasyPrint not available. Install with: pip install weasyprint")
   WEASYPRINT_AVAILABLE = False

class EnhancedContentGenerator:
   """Enhanced generator for both resumes and cover letters using exact template structure mapping"""
   
   def __init__(self):
       self.resume_dir = Path("data/resumes")
       self.resume_dir.mkdir(parents=True, exist_ok=True)
       
       # Find templates
       self._locate_templates()
       
       # EXACT template content mappings (from our analysis) - resume
       self.template_mappings = {
           "role_title": {
               "find": "PRODUCT MANAGEMENT",
               "pattern": '<div class="role-title">PRODUCT MANAGEMENT</div>'
           },
           "profile_text": {
               "find": "Built self-sustaining SaaS and mobile platforms that eliminated manual ops, triggered network effects, and scaled without bloated teams or engineering drag. I design clean UX, automate backend workflows, and launch monetization systems that drive activation, retention, and revenue—across web, iOS, and Android. I thrive in complex, full-stack product challenges—blending data, growth strategy, and technical intuition to ship fast and scale smart.",
               "pattern": '<div class="profile-text">\n                    TEXT\n                </div>'
           },
           "job_bullets": {
               "wercflow": {
                   "bullets": [
                       "Built and scaled a two-sided marketplace for creative professionals and brands, automating onboarding, trust, and workflow processes to remove friction and drive engagement.",
                       "Designed AI-powered tools that eliminated manual production tasks, enabling faster project collaboration and content delivery across global teams.",
                       "Implemented product-led growth loops, growing to 20,000 users organically by embedding automation and data-driven engagement triggers.",
                       "Created verification systems using real-world production data (projects + OCR), ensuring platform credibility without manual reviews—keeping the ecosystem trusted and scalable."
                   ]
               },
               "atlassian": {
                   "bullets": [
                       "Led product strategy across core authentication, provisioning, and security apps, serving 2.5M+ users within the Atlassian ecosystem.",
                       "Shifted product focus to cloud-native, user-friendly marketplace solution, moving away from legacy enterprise tooling to scalable SaaS offerings—accelerating adoption and retention.",
                       "Introduced AI-driven automation to simplify complex security workflows, reducing setup time and boosting customer satisfaction.",
                       "Championed a data-driven roadmap, embedding KPI/OKR frameworks to align cross-functional teams around growth, usability, and cloud migration goals."
                   ]
               },
               "glossom": {
                   "bullets": [
                       "Pioneered AR-integrated UGC commerce experiences in partnership with L'Oréal, enabling beauty influencers to create interactive, shoppable content—years before social platforms adopted AR effects for retail.",
                       "Launched and scaled a mobile platform to 500K+ downloads organically, driving user acquisition through product-led growth tactics, viral sharing mechanics, and retention-focused design—all achieved with a $0 budget.",
                       "Built a rapid experimentation framework, running over 50 A/B tests across onboarding, paywalls, and engagement flows—driving a 30% increase in activation rates and improving 7-day retention by 22% through data-driven optimizations.",
                       "Leveraged data and automation to personalize user experiences, boosting retention and turning creative expression into a scalable growth engine."
                   ]
               },
               "nineteenth_park": {
                   "bullets": [
                       "Launched Treauu, a creative content, experiential, and production agency delivering projects across New York, LA, Atlanta, London, and Paris, establishing a global footprint in the media and production industry.",
                       "Led end-to-end development of Treauu's iOS platform and marketplace, managing the full product lifecycle from ideation and strategy to design, development, and launch—connecting production professionals worldwide.",
                       "Partnered with top-tier clients including Nike, Frank Ocean, Asics, Le Book, and Colgate, driving concept development and strategy for digital, omni-channel campaigns, experiential activations, and innovative products.",
                       "Collaborated with creative and production teams to deliver high-impact pitch materials—crafting RFP responses, proposals, pitch decks, SOWs, and interactive prototypes that secured key projects and client engagements."
                   ]
               },
               "s_and_p": {
                   "bullets": [
                       "Led financial analysis and forecasting for a multi-million dollar PC refresh project, resulting in a projected $15 million quarterly cost reduction.",
                       "Oversaw the R&D and Section 1099 Tax Credit initiative in collaboration with PricewaterhouseCoopers, engaging senior stakeholders to secure significant IRS tax credits.",
                       "Analyzed and streamlined internal project management and budgeting processes, enhancing reporting accuracy and operational efficiency.",
                       "Defined business requirements and coordinated with technical teams to deliver timely system updates and off-cycle releases, improving workflow continuity."
                   ]
               },
               "goldman_sachs": {
                   "bullets": [
                       "Partnered with Talent Acquisition, HR, and business leaders to deliver data-driven insights that optimized workforce strategy and informed executive decision-making across the Securities division.",
                       "Designed and developed advanced visualizations to illuminate key workforce trends, uncovering opportunities that drove strategic initiatives within the global organization.",
                       "Led root cause analyses on critical operational and talent-related issues, implementing data-backed solutions and establishing tracking mechanisms to ensure measurable, continuous improvement."
                   ]
               }
           },
           "skills": [
               "Product-Led Growth (PLG)",
               "Zero-to-One Product Development", 
               "Go-to-Market Strategy",
               "Mobile Acquisition Channels",
               "User-Centric Design",
               "Data Analysis - SQL / Excel / Tableau",
               "Push Notifications / In-App Messaging",
               "Automation & Workflow Optimization",
               "Agile & Lean Methodologies",
               "Virality / Referral Loops",
               "Product Roadmapping & Execution"
           ]
       }
       
       # Cover letter template mappings
       self.cover_letter_mappings = {
           "role_title": "ROLE_TITLE",
           "company_name": "COMPANY_NAME", 
           "paragraph_1": "PARAGRAPH_1",
           "paragraph_2": "PARAGRAPH_2",
           "paragraph_3": "PARAGRAPH_3", 
           "paragraph_4": "PARAGRAPH_4"
       }
   
   def _locate_templates(self):
       """Locate resume and cover letter templates"""
       # Resume template
       resume_templates = [
           Path("resume-template-annotated.html"),
           Path("data/resumes/html/resume-template-annotated.html"),
       ]
       
       self.html_template_path = None
       for template_path in resume_templates:
           if template_path.exists():
               self.html_template_path = template_path
               break
       
       if not self.html_template_path:
           raise FileNotFoundError(f"Resume template not found in: {resume_templates}")
       
       # Cover letter template
       cover_letter_templates = [
           Path("cover-letter-template-annotated.html"),
           Path("data/resumes/html/cover-letter-template-annotated.html"),
       ]
       
       self.cover_letter_template_path = None
       for template_path in cover_letter_templates:
           if template_path.exists():
               self.cover_letter_template_path = template_path
               break
       
       if not self.cover_letter_template_path:
           print(f"⚠️ Cover letter template not found in: {cover_letter_templates}")
           self.cover_letter_template_path = None
           
       print(f"📄 Resume template: {self.html_template_path}")
       if self.cover_letter_template_path:
           print(f"📄 Cover letter template: {self.cover_letter_template_path}")
   
   def load_template(self, template_type: str = "resume") -> str:
       """Load the HTML template"""
       if template_type == "resume":
           return self.html_template_path.read_text(encoding='utf-8')
       elif template_type == "cover_letter":
           if not self.cover_letter_template_path:
               raise FileNotFoundError("Cover letter template not available")
           return self.cover_letter_template_path.read_text(encoding='utf-8')
       else:
           raise ValueError(f"Unknown template type: {template_type}")
   
   def _get_utm_link_from_context(self, data: Dict) -> str:
       """Generate UTM link from job context - FIXED VERSION"""
       # Try to get job data from various places in the structure
       job_data = None
       if "job_data" in data:
           job_data = data["job_data"]
       elif "title" in data or "company" in data:
           job_data = data
       else:
           # Look for job context in calling stack
           import inspect
           try:
               for frame_info in inspect.stack():
                   frame_locals = frame_info.frame.f_locals
                   if "job_data" in frame_locals:
                       job_data = frame_locals["job_data"]
                       break
                   elif "job_title" in frame_locals and "company" in frame_locals:
                       job_data = {
                           "title": frame_locals["job_title"],
                           "company": frame_locals["company"]
                       }
                       break
           except Exception:
               pass
       
       if not job_data:
           return "https://isaiah.pegues.io"
       
       def slugify(name: str) -> str:
           # More robust slugification
           import re
           # Convert to lowercase and replace problematic characters
           slug = name.lower()
           slug = re.sub(r'[&\-–—]', '_', slug)  # Replace various dashes and ampersands
           slug = re.sub(r'[^\w\s]', '', slug)   # Remove other special characters
           slug = re.sub(r'\s+', '_', slug)      # Replace spaces with underscores
           slug = re.sub(r'_+', '_', slug)       # Collapse multiple underscores
           slug = slug.strip('_')                # Remove leading/trailing underscores
           return slug

       def role_abbreviation(title: str) -> str:
           title_lower = title.lower()
           if "senior" in title_lower and "product manager" in title_lower:
               return "spm"
           elif "product manager" in title_lower:
               return "pm"
           elif "founder" in title_lower:
               return "fnd"
           elif "head of product" in title_lower:
               return "hop"
           elif "director" in title_lower:
               return "dir"
           elif "lead" in title_lower:
               return "lead"
           else:
               # More robust abbreviation for complex titles
               words = re.sub(r'[^\w\s]', ' ', title_lower).split()[:3]
               return '_'.join(w[:3] for w in words if w)

       try:
           company_slug = slugify(job_data.get("company", "unknown"))
           role_abbr = role_abbreviation(job_data.get("title", "unknown"))
           
           # Ensure valid URL components
           if not company_slug:
               company_slug = "unknown"
           if not role_abbr:
               role_abbr = "role"
               
           utm_link = f"https://isaiah.pegues.io?utm_source=resume&utm_medium=pdf&utm_campaign={company_slug}-{role_abbr}"
           
           # Validate URL length (prevent extremely long URLs)
           if len(utm_link) > 200:
               utm_link = f"https://isaiah.pegues.io?utm_source=resume&utm_medium=pdf&utm_campaign={company_slug[:20]}-{role_abbr}"
           
           return utm_link
       except Exception as e:
           print(f"⚠️ UTM link generation failed: {e}")
           return "https://isaiah.pegues.io"

   def replace_content_exact(self, html_content: str, generated_content: Dict) -> str:
       """Replace content using exact string matching (backward compatibility)"""
       return self.replace_resume_content(html_content, generated_content)
   
   def replace_resume_content(self, html_content: str, generated_content: Dict) -> str:
       """Replace resume content using exact string matching"""

       print("🎯 Starting exact mapping replacement...")

       # Extract content from generated_content
       role_title = generated_content.get("role_title", "Senior Product Manager")
       profile_section = generated_content.get("profile_section", "")
       employment_bullets = generated_content.get("employment_bullets", {})
       skills_section = generated_content.get("skills_section", [])

       print(f"   📝 Content to replace:")
       print(f"      Role: {role_title}")
       print(f"      Profile: {len(profile_section)} chars")
       print(f"      Companies: {list(employment_bullets.keys())}")
       print(f"      Skills: {len(skills_section)} items")

       updated_html = html_content

       # 1. EXACT Role Title Replacement
       print(f"\n   🎯 Step 1: Role Title")
       old_role = self.template_mappings["role_title"]["find"]
       if old_role in updated_html:
           updated_html = updated_html.replace(old_role, role_title.upper())
           print(f"      ✅ Replaced '{old_role}' → '{role_title.upper()}'")
       else:
           print(f"      ❌ Could not find '{old_role}'")

       # 2. EXACT Profile Replacement
       print(f"\n   🎯 Step 2: Profile")
       if profile_section:
           old_profile = self.template_mappings["profile_text"]["find"]
           if old_profile in updated_html:
               updated_html = updated_html.replace(old_profile, profile_section)
               print(f"      ✅ Replaced profile ({len(old_profile)} → {len(profile_section)} chars)")
           else:
               print(f"      ❌ Could not find original profile text")
       else:
           print(f"      ⏭️ No profile content provided")

       # 2.5 Replace Portfolio Link (Hyperlink UTM injection)
       utm_link = self._get_utm_link_from_context(generated_content)
       print(f"      🔗 UTM link to inject: {utm_link}")
       old_href = 'href="https://isaiah.pegues.io"'
       new_href = f'href="{utm_link}"'
       if old_href in updated_html:
           updated_html = updated_html.replace(old_href, new_href)
           print(f"      ✅ Replaced portfolio href with UTM link")
       else:
           print(f"      ❌ No portfolio href found to replace")
       
       # 3. EXACT Job Bullets Replacement
       print(f"\n   🎯 Step 3: Employment Bullets")
       def normalize_company_key(company: str) -> str:
           return company.strip().lower().replace(" ", "_")

       for company, new_bullets in employment_bullets.items():
           normalized_key = normalize_company_key(company)
           if normalized_key in self.template_mappings["job_bullets"]:
               print(f"      🏢 {company}: {len(new_bullets)} bullets")
               old_bullets = self.template_mappings["job_bullets"][normalized_key]["bullets"]

               # Replace each bullet individually to maintain structure
               bullets_replaced = 0
               for i, (old_bullet, new_bullet) in enumerate(zip(old_bullets, new_bullets)):
                   if old_bullet in updated_html:
                       # Clean the new bullet
                       clean_bullet = new_bullet.strip()
                       if clean_bullet.startswith('•'):
                           clean_bullet = clean_bullet[1:].strip()
                       if not clean_bullet.endswith('.'):
                           clean_bullet += '.'

                       updated_html = updated_html.replace(old_bullet, clean_bullet)
                       bullets_replaced += 1

               print(f"         ✅ Replaced {bullets_replaced}/{len(old_bullets)} bullets")
           else:
               print(f"      ⏭️ {company}: Not in template mapping")
       
       # 4. EXACT Skills Replacement
       print(f"\n   🎯 Step 4: Skills")
       if skills_section:
           # Replace each skill individually
           old_skills = self.template_mappings["skills"]
           skills_replaced = 0
           
           for i, (old_skill, new_skill) in enumerate(zip(old_skills, skills_section)):
               # Find the exact skill item div
               old_skill_html = f'<div class="skill-item">{old_skill}</div>'
               new_skill_html = f'<div class="skill-item">{new_skill}</div>'
               
               if old_skill_html in updated_html:
                   updated_html = updated_html.replace(old_skill_html, new_skill_html)
                   skills_replaced += 1
           
           print(f"      ✅ Replaced {skills_replaced}/{len(old_skills)} skills")
       else:
           print(f"      ⏭️ No skills content provided")
       
       print(f"\n✅ Exact mapping replacement completed")
       return updated_html
   
   def replace_cover_letter_content(self, html_content: str, job_data: Dict, cover_letter_data: Dict) -> str:
       """Replace cover letter content using exact string matching - FIXED VERSION"""
       print("📝 Starting cover letter content replacement...")
       
       # Extract data
       job_title = job_data.get("title", "Unknown Position")
       company = job_data.get("company", "Unknown Company")
       
       # Handle both structured and unstructured cover letter data
       if isinstance(cover_letter_data, dict) and "paragraph_1" in cover_letter_data:
           # Structured format from updated pipeline
           paragraphs = {
               "paragraph_1": cover_letter_data.get("paragraph_1", ""),
               "paragraph_2": cover_letter_data.get("paragraph_2", ""), 
               "paragraph_3": cover_letter_data.get("paragraph_3", ""),
               "paragraph_4": cover_letter_data.get("paragraph_4", "")
           }
           print(f"   📝 Using structured paragraph format")
       else:
           # Fallback: split full text into paragraphs
           full_text = ""
           if isinstance(cover_letter_data, dict):
               full_text = cover_letter_data.get("cover_letter", str(cover_letter_data))
           else:
               full_text = str(cover_letter_data)
           
           # Clean up any HTML artifacts that might be in the text
           import re
           if not isinstance(full_text, str):
               print("❌ Invalid full_text format - expected string. Trying to extract inner text...")
               # If it's a dict without 'cover_letter' key, merge all paragraph-like values
               if isinstance(full_text, dict):
                   full_text = "\n\n".join(str(v) for v in full_text.values() if isinstance(v, str))
               else:
                   full_text = str(full_text)
           full_text = re.sub(r'<[^>]+>', '', full_text)  # Remove any HTML tags
           full_text = re.sub(r'utm_source=resume&utm_medium=pdf&utm_campaign=[^"]*"[^>]*>', '', full_text)  # Clean malformed UTM
           
           # Split by double newlines or paragraph breaks
           text_paragraphs = [p.strip() for p in re.split(r'\n\s*\n|\n\n', full_text) if p.strip()]
           
           # Ensure we have exactly 4 paragraphs
           while len(text_paragraphs) < 4:
               text_paragraphs.append("")
           if len(text_paragraphs) > 4:
               # Combine extra paragraphs into the last one
               text_paragraphs[3] = " ".join(text_paragraphs[3:])
               text_paragraphs = text_paragraphs[:4]
           
           paragraphs = {
               "paragraph_1": text_paragraphs[0],
               "paragraph_2": text_paragraphs[1],
               "paragraph_3": text_paragraphs[2], 
               "paragraph_4": text_paragraphs[3]
           }
           print(f"   📝 Split full text into {len(text_paragraphs)} paragraphs")
       
       # Clean all paragraphs of potential HTML artifacts and malformed content
       for key, text in paragraphs.items():
           if text:
               # Remove HTML tags
               text = re.sub(r'<[^>]+>', '', text)
               # Clean malformed UTM links
               text = re.sub(r'utm_source=resume&utm_medium=pdf&utm_campaign=[^"]*"[^>]*>', '', text)
               # Clean extra whitespace
               text = ' '.join(text.split())
               paragraphs[key] = text
       
       print(f"   📝 Content to replace:")
       print(f"      Job Title: {job_title}")
       print(f"      Company: {company}")
       for i, (key, text) in enumerate(paragraphs.items(), 1):
           print(f"      Paragraph {i}: {len(text)} chars - '{text[:50]}...'")

       updated_html = html_content

       # Step 1: Replace role title
       print(f"\n   🎯 Step 1: Role Title")
       if self.cover_letter_mappings["role_title"] in updated_html:
           updated_html = updated_html.replace(self.cover_letter_mappings["role_title"], job_title)
           print(f"      ✅ Replaced role title with '{job_title}'")
       else:
           print(f"      ❌ Could not find role title placeholder '{self.cover_letter_mappings['role_title']}'")

       # Step 2: Replace company name (appears twice in template)
       print(f"\n   🎯 Step 2: Company Name")
       company_replacements = updated_html.count(self.cover_letter_mappings["company_name"])
       updated_html = updated_html.replace(self.cover_letter_mappings["company_name"], company)
       print(f"      ✅ Replaced company name '{company}' {company_replacements} times")

       # Step 3: Replace paragraphs one by one with validation
       print(f"\n   🎯 Step 3: Paragraphs")
       for i in range(1, 5):
           placeholder = self.cover_letter_mappings[f"paragraph_{i}"]
           content = paragraphs[f"paragraph_{i}"]
           
           print(f"      📝 Paragraph {i}:")
           print(f"         Placeholder: '{placeholder}'")
           print(f"         Content: '{content[:100]}...' ({len(content)} chars)")
           
           if placeholder in updated_html:
               updated_html = updated_html.replace(placeholder, content)
               print(f"         ✅ Replaced paragraph {i}")
           else:
               print(f"         ❌ Could not find paragraph {i} placeholder")

       # Step 4: Portfolio UTM Link
       utm_link = self._get_utm_link_from_context({"job_data": job_data})
       print(f"      🔗 UTM link to inject: {utm_link}")
       old_href = 'href="https://isaiah.pegues.io"'
       new_href = f'href="{utm_link}"'
       if old_href in updated_html:
           updated_html = updated_html.replace(old_href, new_href)
           print(f"      ✅ Replaced portfolio href with UTM link")
       else:
           print(f"      ❌ No portfolio href found to replace")

       # Step 5: Fix any remaining salutation issues
       print(f"\n   🎯 Step 5: Fix Salutation")
       # Remove duplicate salutations if they exist
       salutation_pattern = r'Dear [^,]+,\s*Dear [^,]+,'
       if re.search(salutation_pattern, updated_html):
           updated_html = re.sub(r'Dear [^,]+,\s*Dear Hiring Manager,', f'Dear {company} Hiring Team,', updated_html)
           print(f"      ✅ Fixed duplicate salutation")
       
       # Ensure proper salutation format
       if f"Dear {company}," in updated_html and "Dear Hiring Manager," in updated_html:
           updated_html = updated_html.replace("Dear Hiring Manager,", "")
           print(f"      ✅ Removed duplicate 'Dear Hiring Manager'")

       print(f"\n✅ Cover letter content replacement completed")
       
       # Debug: Check for any remaining template placeholders
       remaining_placeholders = []
       for placeholder in self.cover_letter_mappings.values():
           if placeholder in updated_html:
               remaining_placeholders.append(placeholder)
       
       if remaining_placeholders:
           print(f"⚠️ Warning: Remaining placeholders: {remaining_placeholders}")
       
       return updated_html
   
   def generate_filename(self, job_title: str, document_type: str = "resume") -> str:
       """Generate unique filename"""
       clean_title = re.sub(r'[^a-zA-Z\s]', '', job_title)
       clean_title = '_'.join(clean_title.split())
       
       if document_type == "resume":
           base_name = f"Isaiah_Pegues_{clean_title}_exact"
       else:
           base_name = f"Isaiah_Pegues_{clean_title}_{document_type}"
       
       # Find next available number
       counter = 1
       while True:
           filename = f"{base_name}_{counter}.pdf"
           if not (self.resume_dir / filename).exists():
               return filename
           counter += 1
   
   def convert_to_pdf(self, html_content: str, output_path: Path, document_type: str = "resume") -> bool:
       """Convert HTML to PDF optimized for WeasyPrint"""
       if not WEASYPRINT_AVAILABLE:
           print("❌ WeasyPrint not available for PDF conversion")
           return False
       
       try:
           # Add PDF-specific class to body for CSS targeting
           html_content = html_content.replace('<body>', f'<body class="pdf-mode {document_type}">')
           
           if document_type == "resume":
               # Resume-specific CSS (existing)
               pdf_css = CSS(string='''
                   @page {
                       size: A4;
                       margin: 0;
                   }
                   
                   body {
                       margin: 0;
                       padding: 0;
                       background-color: white !important;
                   }
                   
                   .page {
                       width: 210mm;
                       height: 297mm;
                       display: grid !important;
                       grid-template-columns: 1fr 55mm !important;
                       page-break-after: always;
                       overflow: hidden;
                       background: linear-gradient(to right, #ffffff 0%, #ffffff 70%, #1e3a0f 70%, #1e3a0f 100%) !important;
                   }
                   
                   .page:last-child {
                       page-break-after: auto;
                   }
                   
                   .main-content {
                       overflow: hidden !important;
                       padding: 15mm 5mm 15mm 12mm !important;
                   }
                   
                   .sidebar {
                       overflow: hidden !important;
                       background-color: #1e3a0f !important;
                       color: #ffffff !important;
                       padding: 35mm 5mm 8mm 5mm !important;
                   }
                   
                   /* Force font rendering */
                   * {
                       -webkit-print-color-adjust: exact !important;
                       color-adjust: exact !important;
                   }
                   
                   /* Ensure text doesn't break out of containers */
                   .bullet-point, .profile-text, .contact-info {
                       word-wrap: break-word !important;
                       overflow-wrap: break-word !important;
                       hyphens: auto !important;
                   }
               ''')
           else:
               # Cover letter-specific CSS: compressed layout, no vertical spacing, accommodates removed "to-from" section
               pdf_css = CSS(string='''
                   @page {
                       size: A4;
                       margin: 0;
                   }

                   body {
                       margin: 0;
                       padding: 0;
                       background-color: white !important;
                   }

                   html, body {
                       height: 100%;
                       margin: 0;
                       padding: 0;
                       box-sizing: border-box;
                   }

                   .letter-content {
                       padding: 0;
                       margin: 0;
                       overflow: hidden;
                   }

                   /* Ensure layout is compressed since "to-from" block is removed */
                   .header {
                       margin-bottom: 10mm;
                   }

                   /* Force font rendering */
                   * {
                       -webkit-print-color-adjust: exact !important;
                       color-adjust: exact !important;
                   }

                   .paragraph, .letter-content {
                       word-wrap: break-word !important;
                       overflow-wrap: break-word !important;
                       hyphens: auto !important;
                   }
               ''')
           
           print(f"🔧 Converting {document_type} to PDF...")
           base_url = self.html_template_path.parent if document_type == "resume" else self.cover_letter_template_path.parent
           HTML(string=html_content, base_url=str(base_url)).write_pdf(
               str(output_path), 
               stylesheets=[pdf_css]
           )
           print(f"✅ PDF conversion successful: {output_path}")
           return True
           
       except Exception as e:
           print(f"❌ PDF conversion failed: {e}")
           import traceback
           traceback.print_exc()
           return False
   
   def validate_html_structure(self, html_content: str, document_type: str = "resume") -> bool:
       """Basic validation of HTML structure"""
       
       print(f"🔍 Validating {document_type} HTML structure...")
       
       # Count opening and closing divs
       open_divs = html_content.count('<div')
       close_divs = html_content.count('</div>')
       
       print(f"   📊 DIV tags: {open_divs} opening, {close_divs} closing")
       
       if open_divs != close_divs:
           print(f"   ❌ Mismatched DIV tags: {open_divs - close_divs} difference")
           return False
       
       if document_type == "resume":
           # Check for key resume sections
           checks = [
               ('role-title', '<div class="role-title">'),
               ('profile-text', '<div class="profile-text">'),
               ('job sections', 'data-company='),
               ('sidebar', '<div class="sidebar">'),
               ('skills section', '<div class="skill-item">')
           ]
       else:
           # Check for key cover letter sections
           checks = [
               ('header', '<div class="header">'),
               ('to-from', '<div class="to-from">'),
               ('letter content', '<div class="letter-content">'),
               ('paragraphs', '<div class="paragraph">'),
               ('closing', '<div class="closing">')
           ]
       
       all_good = True
       for desc, pattern in checks:
           count = html_content.count(pattern)
           print(f"   📋 {desc}: {count} found")
           if count == 0:
               print(f"      ❌ Missing {desc}")
               all_good = False
       
       if all_good:
           print(f"   ✅ {document_type} HTML structure validation passed")
       else:
           print(f"   ❌ {document_type} HTML structure validation failed")
       
       return all_good
   
   def generate_resume(self, job_data: Dict) -> Optional[Path]:
       """Generate resume using exact mapping (backward compatibility)"""
       
       generated_content = job_data.get("generated_content")
       if not generated_content:
           print("❌ No generated_content found")
           return None
       
       job_title = job_data.get("title", "Unknown")
       company = job_data.get("company", "Unknown")
       
       print(f"\n🎯 Generating resume for: {job_title} at {company}")
       print("=" * 60)
       
       try:
           # Load template
           html_template = self.load_template("resume")
           print(f"📄 Template loaded: {len(html_template):,} characters")
           
           # Replace content using exact mapping
           updated_html = self.replace_content_exact(html_template, generated_content)
           
           # Validate structure
           if not self.validate_html_structure(updated_html, "resume"):
               print("⚠️ HTML structure validation failed, but continuing...")
           
           # Generate filename
           filename = self.generate_filename(job_title, "resume")
           output_path = self.resume_dir / filename
           
           # Save HTML for debugging
           html_path = output_path.with_suffix('.html')
           html_path.write_text(updated_html, encoding='utf-8')
           print(f"💾 HTML saved: {html_path}")
           
           # Convert to PDF with proper margins
           if self.convert_to_pdf(updated_html, output_path, "resume"):
               print(f"✅ Resume generated: {output_path}")
               return output_path
           else:
               print("❌ PDF generation failed")
               return None
               
       except Exception as e:
           print(f"❌ Error: {e}")
           import traceback
           traceback.print_exc()
           return None
   
   def generate_cover_letter(self, job_data: Dict) -> Optional[Path]:
       """Generate cover letter using exact mapping"""
       
       if not self.cover_letter_template_path:
           print("❌ Cover letter template not available")
           return None
       
       # Extract cover letter data
       generated_content = job_data.get("generated_content", {})
       cover_letter_data = generated_content.get("cover_letter")
       
       # Type guard: ensure cover_letter_data is a string or dict
       if not isinstance(cover_letter_data, (str, dict)) or not cover_letter_data:
           print("❌ Invalid or empty cover letter data found in generated_content")
           return None
       
       job_title = job_data.get("title", "Unknown")
       company = job_data.get("company", "Unknown")
       
       print(f"\n📝 Generating cover letter for: {job_title} at {company}")
       print("=" * 60)
       
       try:
           # Load template
           html_template = self.load_template("cover_letter")
           print(f"📄 Cover letter template loaded: {len(html_template):,} characters")
           
           # Replace content using exact mapping
           updated_html = self.replace_cover_letter_content(html_template, job_data, cover_letter_data)
           
           # Validate structure
           if not self.validate_html_structure(updated_html, "cover_letter"):
               print("⚠️ HTML structure validation failed, but continuing...")
           
           # Generate filename
           filename = self.generate_filename(job_title, "cover_letter")
           output_path = self.resume_dir / filename
           
           # Save HTML for debugging
           html_path = output_path.with_suffix('.html')
           html_path.write_text(updated_html, encoding='utf-8')
           print(f"💾 HTML saved: {html_path}")
           
           # Convert to PDF
           if self.convert_to_pdf(updated_html, output_path, "cover_letter"):
               print(f"✅ Cover letter generated: {output_path}")
               return output_path
           else:
               print("❌ PDF generation failed")
               return None
               
       except Exception as e:
           print(f"❌ Error: {e}")
           import traceback
           traceback.print_exc()
           return None

   def generate_both(self, job_data: Dict) -> Dict[str, Optional[Path]]:
       """Generate both resume and cover letter"""
       results = {
           "resume": None,
           "cover_letter": None,
           "status": "pending"
       }
       
       print(f"\n🎯 Generating both documents for: {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown')}")
       print("=" * 80)
       
       # Generate resume
       try:
           resume_path = self.generate_resume(job_data)
           results["resume"] = resume_path
           if resume_path:
               print(f"✅ Resume: {resume_path}")
           else:
               print("❌ Resume generation failed")
       except Exception as e:
           print(f"❌ Resume generation error: {e}")
       
       print("\n" + "-" * 60)
       
       # Generate cover letter
       try:
           cover_letter_path = self.generate_cover_letter(job_data)
           results["cover_letter"] = cover_letter_path
           if cover_letter_path:
               print(f"✅ Cover letter: {cover_letter_path}")
           else:
               print("❌ Cover letter generation failed")
       except Exception as e:
           print(f"❌ Cover letter generation error: {e}")
       
       # Determine overall status
       if results["resume"] and results["cover_letter"]:
           results["status"] = "success"
           print(f"\n🎉 Both documents generated successfully!")
       elif results["resume"] or results["cover_letter"]:
           results["status"] = "partial"
           print(f"\n⚠️ Partial success - only one document generated")
       else:
           results["status"] = "failed"
           print(f"\n❌ Both documents failed to generate")
       
       return results


   def process_single_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
       """
       Process a single job dict: generate resume and cover letter PDFs,
       update the job_data with links to those files, and return the enriched dict.
       """
       # Generate both documents
       results = self.generate_both(job_data)
       
       # Attach resume link if generated
       if results.get("resume"):
           job_data["resume_link"] = str(results["resume"])
       else:
           job_data["resume_link"] = None
       
       # Attach cover letter link if generated
       if results.get("cover_letter"):
           job_data["cover_letter_link"] = str(results["cover_letter"])
       else:
           job_data["cover_letter_link"] = None
       
       # Attach generation status
       job_data["document_status"] = results.get("status", "failed")
       
       return job_data


# Backward compatibility - alias the old class name
ExactMappingGenerator = EnhancedContentGenerator


def main():
   """Main function"""
   import argparse
   
   parser = argparse.ArgumentParser(description="Generate resume and/or cover letter using exact template mapping")
   parser.add_argument("jobs_file", help="JSONL file with job data")
   parser.add_argument("--job-id", help="Specific job ID to process")
   parser.add_argument("--type", choices=["resume", "cover_letter", "both"], default="both", 
                      help="Type of document to generate")
   
   args = parser.parse_args()
   
   # Initialize generator
   try:
       generator = EnhancedContentGenerator()
   except FileNotFoundError as e:
       print(f"❌ Error: {e}")
       return
   
   # Load job data
   jobs_path = Path(args.jobs_file)
   if not jobs_path.exists():
       print(f"❌ Jobs file not found: {jobs_path}")
       return

   print(f"📊 Processing: {jobs_path}")

   # Support both .jsonl and .json files
   if jobs_path.suffix == '.jsonl':
       with open(jobs_path, 'r', encoding='utf-8') as f:
           lines = f.readlines()
   elif jobs_path.suffix == '.json':
       with open(jobs_path, 'r', encoding='utf-8') as f:
           try:
               single_job = json.load(f)
               lines = [json.dumps(single_job)]
           except json.JSONDecodeError:
               print("❌ Error: Invalid JSON format.")
               return
   else:
       print("❌ Unsupported file type. Please provide a .jsonl or .json file.")
       return

   for line_num, line in enumerate(lines, 1):
       line = line.strip()
       if not line:
           continue

       try:
           job_data = json.loads(line)

           # Filter by job ID if specified
           if args.job_id and job_data.get("id") != args.job_id:
               continue

           # Generate documents based on type
           if args.type == "resume":
               result = generator.generate_resume(job_data)
               if result:
                   print("\n🎉 SUCCESS! Resume generated with exact mapping.")
               else:
                   print("\n❌ FAILED! Check the logs above.")
               results = {"resume": result}  # for uniformity below
           elif args.type == "cover_letter":
               result = generator.generate_cover_letter(job_data)
               if result:
                   print("\n🎉 SUCCESS! Cover letter generated.")
               else:
                   print("\n❌ FAILED! Check the logs above.")
               results = {"cover_letter": result}
           else:  # both
               results = generator.generate_both(job_data)
               print(f"\n📊 Results: {results['status']}")
               if results["resume"]:
                   print(f"   📄 Resume: {results['resume']}")
               if results["cover_letter"]:
                   print(f"   📝 Cover letter: {results['cover_letter']}")

           # After generating documents, update source JSON with links
           # Attach generated file paths (if any)
           if args.type in ("resume", "both") and results.get("resume"):
               job_data["resume_link"] = str(results["resume"] if isinstance(results, dict) else result)
           if args.type in ("cover_letter", "both") and results.get("cover_letter"):
               job_data["cover_letter_link"] = str(results["cover_letter"] if isinstance(results, dict) else result)

           # Write back to JSON or JSONL source
           if jobs_path.suffix == '.json':
               with open(jobs_path, 'w', encoding='utf-8') as f:
                   json.dump(job_data, f, ensure_ascii=False, indent=2)
           else:  # .jsonl
               updated_lines = []
               for orig_line in lines:
                   try:
                       obj = json.loads(orig_line)
                   except:
                       updated_lines.append(orig_line)
                       continue
                   if obj.get("id") == job_data.get("id"):
                       updated_lines.append(json.dumps(job_data) + "\n")
                   else:
                       updated_lines.append(orig_line)
               with open(jobs_path, 'w', encoding='utf-8') as f:
                   f.writelines(updated_lines)

           break  # Process only first matching job

       except json.JSONDecodeError:
           print(f"❌ Invalid JSON on line {line_num}")
           continue

   print("\n" + "=" * 60)
   print("🏁 Processing complete")


if __name__ == "__main__":
   main()