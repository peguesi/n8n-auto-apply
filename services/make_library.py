#!/usr/bin/env python3
"""
Content Library Builder - Extract all content from resume PDFs to create comprehensive JSON library
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse

# PDF extraction libraries
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

class ContentLibraryBuilder:
    """Build comprehensive content library from resume PDFs"""
    
    def __init__(self, resume_dir: str = "resumes"):
        self.resume_dir = Path(resume_dir)
        self.content_library = {
            "metadata": {
                "created_at": "",
                "total_resumes_processed": 0,
                "extraction_method": ""
            },
            "personal_info": {
                "name": "Isaiah Pegues",
                "locations": ["Berlin, Germany", "New York | Berlin"],
                "phones": {
                    "eu": "+4915112205900",
                    "us": "+19176094473"
                },
                "email": "isaiah@pegues.io",
                "portfolio_base": "https://isaiah.pegues.io"
            },
            "profile_variants": [],
            "role_title_variants": [],
            "employment_history": {},
            "skills_by_domain": {
                "general": [],
                "technical": [],
                "payments": [],
                "growth": [],
                "marketplace": [],
                "automation": [],
                "leadership": []
            },
            "focus_abbreviations": {
                "plg": "Product-Led Growth",
                "pii": "Payments & Infrastructure", 
                "mkt": "Marketplace & Platforms",
                "rnk": "Ranking & Algorithms",
                "ugc": "User-Generated Content",
                "infra": "Infrastructure & DevTools",
                "gov": "Government & Compliance"
            }
        }
    
    def extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF using best available method"""
        text = ""
        
        # Try PyPDF2 first
        if PYPDF2_AVAILABLE:
            try:
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                if text.strip():
                    return text.strip()
            except Exception as e:
                print(f"⚠️ PyPDF2 failed for {pdf_path.name}: {e}")
        
        # Try pdfplumber
        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                if text.strip():
                    return text.strip()
            except Exception as e:
                print(f"⚠️ pdfplumber failed for {pdf_path.name}: {e}")
        
        # Try PyMuPDF
        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(pdf_path)
                for page in doc:
                    text += page.get_text() + "\n"
                doc.close()
                if text.strip():
                    return text.strip()
            except Exception as e:
                print(f"⚠️ PyMuPDF failed for {pdf_path.name}: {e}")
        
        print(f"❌ All PDF extraction methods failed for {pdf_path.name}")
        return ""
    
    def parse_resume_sections(self, text: str, filename: str) -> Dict[str, Any]:
        """Parse resume text into structured sections"""
        resume_data = {
            "filename": filename,
            "profile": "",
            "role_title": "",
            "employment": [],
            "skills": [],
            "education": [],
            "languages": []
        }
        
        # Clean text - remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Extract role title (usually in caps after name)
        role_title_match = re.search(r'Isaiah Pegues\s*([A-Z\s&]+)(?:Profile|Employment|Built)', text, re.IGNORECASE)
        if role_title_match:
            resume_data["role_title"] = role_title_match.group(1).strip()
        
        # Extract profile section
        profile_patterns = [
            r'Profile\s*(.*?)(?:Employment History|Skills|Education)',
            r'Built self-sustaining(.*?)(?:Employment|Skills|Education)',
            r'Product leader(.*?)(?:Employment|Skills|Education)'
        ]
        
        for pattern in profile_patterns:
            profile_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if profile_match:
                profile_text = profile_match.group(1).strip()
                # Clean up the profile text
                profile_text = re.sub(r'\s+', ' ', profile_text)
                if len(profile_text) > 50:  # Reasonable profile length
                    resume_data["profile"] = profile_text
                    break
        
        # Extract employment history
        employment_section = self.extract_employment_section(text)
        resume_data["employment"] = employment_section
        
        # Extract skills
        skills = self.extract_skills_section(text)
        resume_data["skills"] = skills
        
        # Extract education
        education = self.extract_education_section(text)
        resume_data["education"] = education
        
        # Extract languages
        languages = self.extract_languages_section(text)
        resume_data["languages"] = languages
        
        return resume_data
    
    def extract_employment_section(self, text: str) -> List[Dict[str, Any]]:
        """Extract employment history with company, title, dates, and bullets"""
        employment = []
        
        # Pattern to find job entries - company names we know
        companies = ["Wercflow", "Resolution", "Atlassian", "Glossom", "19th and Park", "Treauu", "S&P Capital", "Goldman Sachs", "Saint John"]
        
        for company in companies:
            # Look for company mentions with titles
            company_pattern = rf'([^,\n]+),?\s*{re.escape(company)}[^,\n]*(?:,\s*([^,\n]+))?\s*([A-Z]+\s*\d{{4}}\s*[—-]\s*[A-Z]*\s*\d{{4}})?'
            company_matches = re.finditer(company_pattern, text, re.IGNORECASE)
            
            for match in company_matches:
                job_title = match.group(1).strip() if match.group(1) else ""
                location = match.group(2).strip() if match.group(2) else ""
                dates = match.group(3).strip() if match.group(3) else ""
                
                # Clean up job title
                job_title = re.sub(r'^[•\-\s]+', '', job_title)
                
                # Find bullets for this job (look ahead in text)
                bullets = self.extract_bullets_for_job(text, match.end(), company)
                
                if job_title and len(bullets) > 0:
                    employment.append({
                        "company": company,
                        "title": job_title,
                        "location": location,
                        "dates": dates,
                        "bullets": bullets
                    })
        
        return employment
    
    def extract_bullets_for_job(self, text: str, start_pos: int, company: str) -> List[str]:
        """Extract bullet points for a specific job"""
        bullets = []
        
        # Look for text after the job header until next job or section
        next_section_pos = len(text)
        
        # Find next company or major section
        companies = ["Wercflow", "Resolution", "Atlassian", "Glossom", "19th and Park", "Goldman Sachs", "S&P Capital"]
        sections = ["Education", "Skills", "Languages", "Details"]
        
        for company_name in companies:
            pos = text.find(company_name, start_pos + 50)  # Skip immediate company mention
            if pos != -1 and pos < next_section_pos:
                next_section_pos = pos
        
        for section in sections:
            pos = text.find(section, start_pos)
            if pos != -1 and pos < next_section_pos:
                next_section_pos = pos
        
        # Extract bullet points from this section
        job_text = text[start_pos:next_section_pos]
        
        # Find bullet patterns
        bullet_patterns = [
            r'•\s*([^•\n]+)',
            r'^\s*[-]\s*([^-\n]+)',
            r'Led\s+([^.\n]+\.?)',
            r'Designed\s+([^.\n]+\.?)',
            r'Built\s+([^.\n]+\.?)',
            r'Launched\s+([^.\n]+\.?)',
            r'Created\s+([^.\n]+\.?)'
        ]
        
        for pattern in bullet_patterns:
            matches = re.finditer(pattern, job_text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                bullet_text = match.group(1).strip()
                if len(bullet_text) > 20 and bullet_text not in bullets:  # Reasonable bullet length
                    bullets.append(bullet_text)
        
        return bullets[:8]  # Limit to reasonable number
    
    def extract_skills_section(self, text: str) -> List[str]:
        """Extract skills from the skills section"""
        skills = []
        
        # Find skills section
        skills_match = re.search(r'Skills\s*(.*?)(?:Languages|Education|Details|\Z)', text, re.IGNORECASE | re.DOTALL)
        if skills_match:
            skills_text = skills_match.group(1)
            
            # Extract individual skills
            skill_patterns = [
                r'([A-Za-z\s&\-/]+(?:Optimization|Development|Strategy|Management|Leadership|Integration|Automation|Analytics|Testing|Platforms|Methodologies))',
                r'([A-Z][A-Za-z\s&\-/]+(?:AWS|Azure|API|SaaS|UX/UI|A/B|KPI|OKR))',
                r'(?:^|\n)\s*([A-Z][A-Za-z\s&\-/]{5,30}?)(?:\s|$|\n)'
            ]
            
            for pattern in skill_patterns:
                matches = re.finditer(pattern, skills_text, re.MULTILINE)
                for match in matches:
                    skill = match.group(1).strip()
                    if len(skill) > 3 and skill not in skills:
                        skills.append(skill)
        
        return skills
    
    def extract_education_section(self, text: str) -> List[Dict[str, str]]:
        """Extract education information"""
        education = []
        
        education_match = re.search(r'Education\s*(.*?)(?:Skills|Languages|Details|\Z)', text, re.IGNORECASE | re.DOTALL)
        if education_match:
            edu_text = education_match.group(1)
            
            # Look for degree patterns
            degree_pattern = r'([A-Za-z\s]+),?\s*([A-Za-z\s\']+University[^,\n]*),?\s*([A-Za-z\s,]+)?\s*(\d{4}[^,\n]*)?'
            degree_match = re.search(degree_pattern, edu_text)
            
            if degree_match:
                education.append({
                    "degree": degree_match.group(1).strip(),
                    "institution": degree_match.group(2).strip(),
                    "location": degree_match.group(3).strip() if degree_match.group(3) else "",
                    "dates": degree_match.group(4).strip() if degree_match.group(4) else ""
                })
        
        return education
    
    def extract_languages_section(self, text: str) -> List[str]:
        """Extract languages"""
        languages = []
        
        lang_match = re.search(r'Languages\s*(.*?)(?:Skills|Education|Details|\Z)', text, re.IGNORECASE | re.DOTALL)
        if lang_match:
            lang_text = lang_match.group(1)
            
            # Common languages
            common_languages = ["English", "German", "Spanish", "French", "Italian", "Portuguese", "Mandarin", "Japanese"]
            
            for lang in common_languages:
                if re.search(rf'\b{lang}\b', lang_text, re.IGNORECASE):
                    languages.append(lang)
        
        return languages
    
    def categorize_skills(self, all_skills: List[str]) -> Dict[str, List[str]]:
        """Categorize skills by domain"""
        categorized = {
            "general": [],
            "technical": [],
            "payments": [],
            "growth": [],
            "marketplace": [],
            "automation": [],
            "leadership": []
        }
        
        # Categorization patterns
        categories = {
            "payments": ["payment", "billing", "fintech", "financial", "transaction", "gateway", "embedded"],
            "growth": ["growth", "acquisition", "retention", "conversion", "a/b testing", "analytics", "plg"],
            "marketplace": ["marketplace", "platform", "two-sided", "matching", "ranking", "search"],
            "automation": ["automation", "workflow", "integration", "api", "devtools", "infrastructure"],
            "leadership": ["leadership", "management", "cross-functional", "stakeholder", "team"],
            "technical": ["aws", "azure", "saas", "cloud", "agile", "scrum", "api", "sdk", "technical"]
        }
        
        for skill in all_skills:
            skill_lower = skill.lower()
            categorized_flag = False
            
            for category, keywords in categories.items():
                if any(keyword in skill_lower for keyword in keywords):
                    categorized[category].append(skill)
                    categorized_flag = True
                    break
            
            if not categorized_flag:
                categorized["general"].append(skill)
        
        return categorized
    
    def determine_focus_from_filename(self, filename: str) -> str:
        """Determine focus abbreviation from filename"""
        filename_lower = filename.lower()
        
        if "_plg" in filename_lower:
            return "plg"
        elif "_pii" in filename_lower:
            return "pii"
        elif "_mkt" in filename_lower:
            return "mkt"
        elif "_rnk" in filename_lower:
            return "rnk"
        elif "_ugc" in filename_lower:
            return "ugc"
        elif "_infra" in filename_lower:
            return "infra"
        elif "_gov" in filename_lower:
            return "gov"
        else:
            return "general"
    
    def build_library(self) -> Dict[str, Any]:
        """Build the complete content library from all resume PDFs"""
        if not self.resume_dir.exists():
            print(f"❌ Resume directory not found: {self.resume_dir}")
            return self.content_library
        
        pdf_files = list(self.resume_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"❌ No PDF files found in {self.resume_dir}")
            return self.content_library
        
        print(f"📄 Found {len(pdf_files)} PDF files to process")
        
        all_profiles = []
        all_role_titles = []
        all_skills = []
        processed_count = 0
        
        for pdf_path in pdf_files:
            print(f"🔍 Processing: {pdf_path.name}")
            
            # Extract text
            text = self.extract_pdf_text(pdf_path)
            if not text:
                print(f"⚠️ No text extracted from {pdf_path.name}")
                continue
            
            # Parse sections
            resume_data = self.parse_resume_sections(text, pdf_path.name)
            
            # Determine focus
            focus = self.determine_focus_from_filename(pdf_path.name)
            
            # Collect unique content
            if resume_data["profile"] and resume_data["profile"] not in all_profiles:
                all_profiles.append(resume_data["profile"])
            
            if resume_data["role_title"] and resume_data["role_title"] not in all_role_titles:
                all_role_titles.append(resume_data["role_title"])
            
            # Add employment data
            for job in resume_data["employment"]:
                company = job["company"]
                if company not in self.content_library["employment_history"]:
                    self.content_library["employment_history"][company] = {
                        "title_variants": [],
                        "location_variants": [],
                        "date_ranges": [],
                        "all_bullets": [],
                        "focus_associations": []
                    }
                
                company_data = self.content_library["employment_history"][company]
                
                # Add unique variants
                if job["title"] and job["title"] not in company_data["title_variants"]:
                    company_data["title_variants"].append(job["title"])
                
                if job["location"] and job["location"] not in company_data["location_variants"]:
                    company_data["location_variants"].append(job["location"])
                
                if job["dates"] and job["dates"] not in company_data["date_ranges"]:
                    company_data["date_ranges"].append(job["dates"])
                
                if focus not in company_data["focus_associations"]:
                    company_data["focus_associations"].append(focus)
                
                # Add unique bullets
                for bullet in job["bullets"]:
                    if bullet not in company_data["all_bullets"]:
                        company_data["all_bullets"].append(bullet)
            
            # Collect skills
            all_skills.extend(resume_data["skills"])
            
            processed_count += 1
            print(f"✅ Processed {pdf_path.name} (focus: {focus})")
        
        # Update content library
        self.content_library["profile_variants"] = all_profiles
        self.content_library["role_title_variants"] = all_role_titles
        
        # Categorize skills
        unique_skills = list(set(all_skills))
        self.content_library["skills_by_domain"] = self.categorize_skills(unique_skills)
        
        # Update metadata
        self.content_library["metadata"]["total_resumes_processed"] = processed_count
        self.content_library["metadata"]["extraction_method"] = "PyPDF2/pdfplumber/PyMuPDF"
        
        from datetime import datetime
        self.content_library["metadata"]["created_at"] = datetime.now().isoformat()
        
        print(f"\n🎯 Library build complete!")
        print(f"   Profiles: {len(all_profiles)}")
        print(f"   Role titles: {len(all_role_titles)}")
        print(f"   Companies: {len(self.content_library['employment_history'])}")
        print(f"   Total unique skills: {len(unique_skills)}")
        
        return self.content_library
    
    def save_library(self, output_path: str = "content_library.json"):
        """Save the content library to JSON file"""
        output_file = Path(output_path)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.content_library, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Content library saved to: {output_file}")
        print(f"📊 Size: {output_file.stat().st_size / 1024:.1f} KB")
        
        return output_file
    
    def preview_library(self):
        """Print a preview of the content library"""
        print("\n📖 Content Library Preview:")
        print("=" * 50)
        
        print(f"\n👤 Profile Variants ({len(self.content_library['profile_variants'])}):")
        for i, profile in enumerate(self.content_library['profile_variants'][:3], 1):
            print(f"  {i}. {profile[:80]}...")
        
        print(f"\n🏷️ Role Title Variants ({len(self.content_library['role_title_variants'])}):")
        for title in self.content_library['role_title_variants']:
            print(f"  • {title}")
        
        print(f"\n🏢 Employment History ({len(self.content_library['employment_history'])} companies):")
        for company, data in list(self.content_library['employment_history'].items())[:3]:
            print(f"  {company}:")
            print(f"    Titles: {data['title_variants']}")
            print(f"    Bullets: {len(data['all_bullets'])} total")
            print(f"    Focus: {data['focus_associations']}")
        
        print(f"\n🔧 Skills by Domain:")
        for domain, skills in self.content_library['skills_by_domain'].items():
            if skills:
                print(f"  {domain}: {len(skills)} skills")

def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(description="Build comprehensive content library from resume PDFs")
    parser.add_argument("--resume-dir", default="resumes", help="Directory containing resume PDFs")
    parser.add_argument("--output", default="content_library.json", help="Output JSON file path")
    parser.add_argument("--preview", action="store_true", help="Show preview of extracted content")
    
    args = parser.parse_args()
    
    # Build library
    builder = ContentLibraryBuilder(args.resume_dir)
    library = builder.build_library()
    
    # Show preview if requested
    if args.preview:
        builder.preview_library()
    
    # Save library
    if library["metadata"]["total_resumes_processed"] > 0:
        output_path = builder.save_library(args.output)
        print(f"\n🎉 Ready to upload {output_path} to your vector store!")
    else:
        print("❌ No resumes processed successfully")

if __name__ == "__main__":
    main()