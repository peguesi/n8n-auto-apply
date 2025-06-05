#!/usr/bin/env python3
"""
Resume Template Annotator - Properly annotate the HTML template for dynamic updates
Designed for templates with <p> tags and ft* classes (your specific structure)

Usage: python annotate_resume_fixed.py resume-template.html resume-template-annotated.html
"""

import sys
import re
from bs4 import BeautifulSoup

def annotate_resume_template(input_path: str, output_path: str):
    """Annotate the resume template with proper classes for dynamic updates"""
    
    with open(input_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    print(f"🔍 Analyzing template structure...")
    
    # 1. Find and annotate the role title
    # Look for the element that currently says "PRODUCT MANAGEMENT"
    role_candidates = soup.find_all("p", class_=re.compile(r"ft01"))
    for p in role_candidates:
        text = p.get_text(strip=True)
        if text in ["PRODUCT MANAGEMENT", "SENIOR PRODUCT MANAGER", "PRODUCT MANAGER"]:
            if "role-title" not in p.get("class", []):
                p["class"] = p.get("class", []) + ["role-title"]
                print(f"✅ Annotated role title: {text}")
            break
    
    # 2. Find and annotate section headers
    section_headers = ["Profile", "Employment History", "Education", "Details", "Skills", "Links", "Languages"]
    
    for header_text in section_headers:
        header_elements = soup.find_all("p", string=header_text)
        for elem in header_elements:
            if "section-header" not in elem.get("class", []):
                elem["class"] = elem.get("class", []) + ["section-header"]
                print(f"✅ Annotated section header: {header_text}")
    
    # 3. Annotate bullet points - PRECISE APPROACH using exact line numbers
    # Based on manual analysis, bullets start at these specific lines:
    bullet_line_numbers = {
        "wercflow": [124, 128, 132, 136, 141],           # 5 bullets
        "resolution": [145, 149, 152, 154],              # 4 bullets  
        "glossom": [160, 167, 169, 202],                 # 4 bullets
        "19th_park": [206, 212, 215, 223],               # 4 bullets
        # Note: S&P and Goldman Sachs bullets are on page 2 - need to find those line numbers
    }
    
    total_expected_bullets = sum(len(bullets) for bullets in bullet_line_numbers.values())
    print(f"📍 Targeting bullets at specific line numbers (Page 1: {total_expected_bullets} bullets)")
    
    # Split HTML into lines for precise targeting
    html_lines = str(soup).split('\n')
    bullet_count = 0
    
    # Process each known bullet line
    for company, line_numbers in bullet_line_numbers.items():
        print(f"   Processing {company}: lines {line_numbers}")
        
        for line_num in line_numbers:
            if line_num < len(html_lines):
                line_content = html_lines[line_num]
                
                # Find the <p> tag in this line and add bullet-point class
                if '<p' in line_content and 'class=' in line_content:
                    # Parse this specific line to find the <p> element
                    line_soup = BeautifulSoup(line_content, 'html.parser')
                    p_tag = line_soup.find('p')
                    
                    if p_tag:
                        # Find the same element in the main soup by matching attributes
                        style_attr = p_tag.get('style', '')
                        class_attr = p_tag.get('class', [])
                        
                        # Find matching element in main soup
                        for p in soup.find_all('p'):
                            if (p.get('style', '') == style_attr and 
                                p.get('class', []) == class_attr):
                                
                                if "bullet-point" not in p.get("class", []):
                                    p["class"] = p.get("class", []) + ["bullet-point"]
                                    p["data-section"] = "employment"
                                    p["data-company"] = company  # Add company tracking
                                    bullet_count += 1
                                    
                                    # Show what we found
                                    text_preview = p.get_text(strip=True)[:50]
                                    print(f"      ✅ Line {line_num}: {text_preview}...")
                                break
    
    # For Page 2 bullets (S&P and Goldman), we'll need to find them differently
    # Let's search for them by content patterns on page 2
    page2_div = soup.find("div", id="page2-div")
    if page2_div:
        # S&P Capital IQ bullets (expected 4)
        sp_patterns = [
            "Led financial analysis",
            "Oversaw the R&D", 
            "Analyzed and streamlined",
            "Defined business requirements"
        ]
        
        # Goldman Sachs bullets (expected 3)
        goldman_patterns = [
            "Partnered with Talent Acquisition",
            "Designed and developed advanced",
            "Led root cause analyses"
        ]
        
        page2_patterns = sp_patterns + goldman_patterns
        
        for pattern in page2_patterns:
            for p in page2_div.find_all('p'):
                text = p.get_text(strip=True)
                if pattern in text and "•" in text:
                    if "bullet-point" not in p.get("class", []):
                        p["class"] = p.get("class", []) + ["bullet-point"]
                        p["data-section"] = "employment"
                        
                        # Determine company
                        if pattern in sp_patterns:
                            p["data-company"] = "sp_capital"
                        else:
                            p["data-company"] = "goldman_sachs"
                            
                        bullet_count += 1
                        print(f"      ✅ Page 2: {text[:50]}...")
    
    total_expected = 25  # 5+4+4+4+4+3 = 24, but you said 25, so there might be one more
    print(f"✅ Annotated {bullet_count} bullet points (expected ~{total_expected})")
    
    # 4. Annotate the exact 11 skills using precise positioning
    # Based on PDF analysis, here are the exact skills in order:
    expected_skills = [
        "Product-Led Growth (PLG)",
        "Zero-to-One Product Development",  # May span 2 lines
        "Go-to-Market Strategy",
        "Mobile Acquisition Channels", 
        "User-Centric Design",
        "Data Analysis - SQL / Excel / Tableau",  # May span 2 lines
        "Push Notifications / In-App Messaging",  # May span 2 lines
        "Automation & Workflow Optimization",     # May span 2 lines
        "Agile & Lean Methodologies",
        "Virality / Referral Loops",             # May span 2 lines
        "Product Roadmapping & Execution"        # May span 2 lines
    ]
    
    skill_count = 0
    processed_skill_positions = set()
    
    for p in soup.find_all("p"):
        style = p.get("style", "")
        classes = p.get("class", [])
        text = p.get_text(strip=True)
        
        # Skills are at left:656px, not headers, in skills section
        if "left:656px" in style and "ft011" not in classes and text:
            position_match = re.search(r'top:(\d+)px', style)
            
            if position_match:
                position = int(position_match.group(1))
                
                # Skills section range (from Skills header to Languages header)
                if 454 <= position <= 919:  # Refined range based on PDF
                    # Check if this text matches any expected skill
                    for skill in expected_skills:
                        # Handle partial matches for multi-line skills
                        skill_words = skill.lower().split()
                        text_words = text.lower().split()
                        
                        # Check if this text contains significant words from the skill
                        word_overlap = len(set(skill_words) & set(text_words))
                        
                        if word_overlap >= 2 or skill.lower() in text.lower() or text.lower() in skill.lower():
                            # Group multi-line skills
                            is_new_skill = True
                            for existing_pos in processed_skill_positions:
                                if abs(position - existing_pos) <= 25:
                                    is_new_skill = False
                                    break
                            
                            if is_new_skill:
                                if "skill-item" not in p.get("class", []):
                                    p["class"] = p.get("class", []) + ["skill-item"]
                                    skill_count += 1
                                    processed_skill_positions.add(position)
                                    print(f"      ✅ Skill {skill_count}: {text} (matches: {skill})")
                            break
    
    print(f"✅ Annotated {skill_count} skill items (expected 11)")
    
    # 5. Annotate contact links (these might already be annotated)
    contact_link_count = 0
    for a in soup.find_all("a"):
        href = a.get("href", "")
        
        # Add contact-link class if not present
        if "contact-link" not in a.get("class", []):
            a["class"] = a.get("class", []) + ["contact-link"]
        
        # Add data-type attributes
        if href.startswith("mailto:"):
            a["data-type"] = "email"
            contact_link_count += 1
        elif href.startswith("tel:"):
            a["data-type"] = "phone"
            contact_link_count += 1
        elif "linkedin.com" in href:
            a["data-type"] = "linkedin"
            contact_link_count += 1
        elif "github.com" in href:
            a["data-type"] = "github"
            contact_link_count += 1
        elif "isaiah.pegues.io" in href or "portfolio" in href.lower():
            a["data-type"] = "portfolio"
            contact_link_count += 1
    
    print(f"✅ Annotated {contact_link_count} contact links")
    
    # 6. Add IDs and wrapper divs for better targeting
    
    # Add ID to skills section wrapper
    skills_header = soup.find("p", string="Skills")
    if skills_header:
        # Find the parent div that contains the skills
        page_div = skills_header.find_parent("div")
        if page_div and "skills-section" not in page_div.get("class", []):
            page_div["class"] = page_div.get("class", []) + ["skills-section"]
            print("✅ Added skills-section class to container")
    
    # 7. Annotate job titles and company names in employment section
    job_title_count = 0
    employment_patterns = [
        r"Founder & Head of Product, (.+)",
        r"Senior Product Manager, (.+)",
        r"Innovation Manager, (.+)",
        r"Business Analyst, (.+)",
        r"Analyst, (.+)"
    ]
    
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        
        # Check if this looks like a job title line
        for pattern in employment_patterns:
            if re.match(pattern, text):
                if "job-title-line" not in p.get("class", []):
                    p["class"] = p.get("class", []) + ["job-title-line"]
                    job_title_count += 1
                break
    
    print(f"✅ Annotated {job_title_count} job title lines")
    
    # 8. Add a marker to show this template has been annotated
    html_tag = soup.find("html")
    if html_tag:
        html_tag["data-annotated"] = "true"
        html_tag["data-annotation-version"] = "1.0"
    
    # Write the annotated HTML
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup.prettify()))
    
    print(f"\n✅ Annotation complete!")
    print(f"📄 Annotated template saved to: {output_path}")
    print(f"\n📊 Summary:")
    print(f"   - 1 role title")
    print(f"   - {len(section_headers)} section headers") 
    print(f"   - {bullet_count} bullet points")
    print(f"   - {skill_count} skill items")
    print(f"   - {contact_link_count} contact links")
    print(f"   - {job_title_count} job title lines")

def validate_annotations(html_path: str):
    """Validate that the template has been properly annotated"""
    
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    print(f"\n🔍 Validating annotations in {html_path}...")
    
    # Check for required annotations
    validations = {
        "role-title": soup.find_all(class_="role-title"),
        "section-header": soup.find_all(class_="section-header"), 
        "bullet-point": soup.find_all(class_="bullet-point"),
        "skill-item": soup.find_all(class_="skill-item"),
        "contact-link": soup.find_all(class_="contact-link")
    }
    
    all_good = True
    for annotation_type, elements in validations.items():
        count = len(elements)
        if count > 0:
            print(f"✅ {annotation_type}: {count} elements")
            
            # Special validation for expected counts
            if annotation_type == "bullet-point" and count < 20:
                print(f"   ⚠️ Expected ~25 bullets, found {count} (may need manual review)")
            elif annotation_type == "skill-item" and count < 10:
                print(f"   ⚠️ Expected ~11 skills, found {count} (may need manual review)")
        else:
            print(f"❌ {annotation_type}: 0 elements found!")
            all_good = False
    
    # Check if template is marked as annotated
    html_tag = soup.find("html")
    if html_tag and html_tag.get("data-annotated") == "true":
        print("✅ Template is marked as annotated")
    else:
        print("⚠️ Template not marked as annotated")
        all_good = False
    
    # Additional diagnostic info
    print(f"\n📊 Detailed analysis:")
    
    # Count actual bullet markers in employment section
    bullet_markers = soup.find_all("p", string="•")
    print(f"   • Bullet markers (•): {len(bullet_markers)}")
    
    # Count sidebar elements
    sidebar_elements = []
    for p in soup.find_all("p"):
        style = p.get("style", "")
        if "left:656px" in style:
            text = p.get_text(strip=True)
            if text and text not in ["Details", "Links", "Skills", "Languages"]:
                sidebar_elements.append(text)
    print(f"   • Sidebar content items: {len(sidebar_elements)}")
    
    if all_good and len(bullet_markers) >= 20 and len(sidebar_elements) >= 10:
        print("\n🎉 Template validation passed! Ready for dynamic updates.")
    else:
        print("\n⚠️ Template validation completed with notes. Check counts above.")
    
def debug_template_structure(html_path: str):
    """Debug mode: analyze the actual template structure to understand bullet/skill counts"""
    
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    print(f"\n🔬 DEBUG: Analyzing template structure in {html_path}")
    print("="*60)
    
    # Count bullet markers by page
    total_bullets = 0
    for page_id in ["page1-div", "page2-div"]:
        page_div = soup.find("div", id=page_id)
        if page_div:
            bullet_markers = page_div.find_all("p", string="•")
            print(f"📍 {page_id} bullet markers (•): {len(bullet_markers)}")
            total_bullets += len(bullet_markers)
            
            for i, marker in enumerate(bullet_markers[:3]):  # Show first 3 per page
                style = marker.get("style", "")
                position = re.search(r'top:(\d+)px', style)
                pos = position.group(1) if position else "unknown"
                print(f"   {i+1}. Position top:{pos}px")
            if len(bullet_markers) > 3:
                print(f"   ... and {len(bullet_markers) - 3} more")
    
    print(f"\n📊 Total bullet markers across both pages: {total_bullets}")
    print()
    
    # Analyze sidebar content with better filtering
    print(f"📍 Sidebar content analysis (left:656px):")
    sidebar_items = []
    
    for p in soup.find_all("p"):
        style = p.get("style", "")
        if "left:656px" in style:
            text = p.get_text(strip=True)
            position = re.search(r'top:(\d+)px', style)
            pos = int(position.group(1)) if position else 0
            
            if text:
                sidebar_items.append((pos, text))
    
    # Sort by position
    sidebar_items.sort(key=lambda x: x[0])
    
    # Categorize sidebar content
    sections = {
        "details": (150, 300),      # Contact info
        "links": (300, 400),        # Social links  
        "skills": (400, 990),       # Actual skills
        "languages": (990, 1200)    # Languages
    }
    
    for section_name, (start_pos, end_pos) in sections.items():
        section_items = [item for item in sidebar_items if start_pos <= item[0] <= end_pos]
        print(f"\n📂 {section_name.upper()} section ({start_pos}-{end_pos}px):")
        
        if section_name == "skills":
            # Group skills by proximity for multi-line skills
            skill_groups = []
            current_group = []
            last_position = -1
            
            for position, text in section_items:
                if last_position >= 0 and position - last_position > 30:
                    if current_group:
                        skill_groups.append(current_group)
                    current_group = [(position, text)]
                else:
                    current_group.append((position, text))
                last_position = position
            
            if current_group:
                skill_groups.append(current_group)
            
            print(f"   📊 {len(skill_groups)} skill groups identified:")
            for i, group in enumerate(skill_groups):
                combined_text = " ".join([text for _, text in group])
                first_pos = group[0][0]
                print(f"   {i+1}. {combined_text} (top:{first_pos}px)")
        else:
            for i, (pos, text) in enumerate(section_items[:5]):  # Show first 5
                print(f"   {i+1}. {text[:50]}... (top:{pos}px)")
            if len(section_items) > 5:
                print(f"   ... and {len(section_items) - 5} more")
    
    # Calculate proper counts
    skills_section_items = [item for item in sidebar_items if 450 <= item[0] <= 990]
    skill_groups = []
    current_group = []
    last_position = -1
    
    for position, text in skills_section_items:
        if last_position >= 0 and position - last_position > 30:
            if current_group:
                skill_groups.append(current_group)
            current_group = [(position, text)]
        else:
            current_group.append((position, text))
        last_position = position
    
    if current_group:
        skill_groups.append(current_group)
    
    print(f"\n📊 SUMMARY:")
    print(f"   • Total bullet markers: {total_bullets}")
    print(f"   • Actual skill groups (in skills section): {len(skill_groups)}")
    print(f"   • Total sidebar items: {len(sidebar_items)}")
    
    return total_bullets, len(skill_groups)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python annotate_resume_fixed.py <input-template.html> <output-annotated.html>")
        print("  python annotate_resume_fixed.py --validate <template.html>")
        print("  python annotate_resume_fixed.py --debug <template.html>")
        sys.exit(1)
    
    if sys.argv[1] == "--validate":
        if len(sys.argv) < 3:
            print("Usage: python annotate_resume_fixed.py --validate <template.html>")
            sys.exit(1)
        validate_annotations(sys.argv[2])
    elif sys.argv[1] == "--debug":
        if len(sys.argv) < 3:
            print("Usage: python annotate_resume_fixed.py --debug <template.html>")
            sys.exit(1)
        debug_template_structure(sys.argv[2])
    else:
        if len(sys.argv) < 3:
            print("Usage: python annotate_resume_fixed.py <input-template.html> <output-annotated.html>")
            sys.exit(1)
            
        input_path = sys.argv[1]
        output_path = sys.argv[2]
        
        try:
            # First debug the original structure
            print("🔬 Analyzing original template structure...")
            debug_template_structure(input_path)
            
            print("\n" + "="*60)
            print("🔧 Starting annotation process...")
            annotate_resume_template(input_path, output_path)
            
            # Auto-validate the result
            print("\n" + "="*60)
            validate_annotations(output_path)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)