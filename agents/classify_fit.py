#!/usr/bin/env python3
"""
Job Analysis Tools - Query and filter structured fit analysis results
+ Job Classification Functions - Generate fit_analysis data using Azure OpenAI
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime
import os
import time
import tempfile
import shutil
import re

# Azure OpenAI imports
try:
    from openai import AzureOpenAI
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: Azure OpenAI not available. Classification functions will not work.")
    AZURE_OPENAI_AVAILABLE = False

# Environment variables for Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://wercopenai.openai.azure.com/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "48b0cc7a06d04279a8ae53997526965e")
AZURE_VECTOR_STORE_ID = os.getenv("AZURE_VECTOR_STORE_ID", "vs_X9Zg4NAmhYrlQg9NICEpkgFT")
ASSISTANT_ID = os.getenv("AZURE_ASSISTANT_ID")

class JobAnalyzer:
    """Tools for analyzing structured job fit data"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.jobs = self.load_jobs()
    
    def load_jobs(self) -> List[Dict[str, Any]]:
        """Load jobs from JSONL file"""
        jobs = []
        
        if not self.file_path.exists():
            print(f"❌ File not found: {self.file_path}")
            return jobs
        
        with open(self.file_path, "r", encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    job_data = json.loads(line)
                    jobs.append(job_data)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Skipping line {line_num}: {e}")
                    continue
        
        print(f"📊 Loaded {len(jobs)} jobs from {self.file_path}")
        return jobs
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of the job analysis"""
        analyzed_jobs = [job for job in self.jobs if "fit_analysis" in job]
        
        if not analyzed_jobs:
            return {"error": "No jobs with fit_analysis found"}
        
        scores = []
        probabilities = []
        recommendations = {}
        
        for job in analyzed_jobs:
            fit_analysis = job.get("fit_analysis", {})
            
            if isinstance(fit_analysis, dict):
                score = fit_analysis.get("overall_score", 0)
                prob = fit_analysis.get("interview_probability", 0)
                rec = fit_analysis.get("recommendation", "unknown")
                
                if isinstance(score, (int, float)) and score > 0:
                    scores.append(score)
                if isinstance(prob, (int, float)) and prob >= 0:
                    probabilities.append(prob)
                
                recommendations[rec] = recommendations.get(rec, 0) + 1
        
        return {
            "total_jobs": len(self.jobs),
            "analyzed_jobs": len(analyzed_jobs),
            "score_stats": {
                "mean": sum(scores) / len(scores) if scores else 0,
                "median": sorted(scores)[len(scores)//2] if scores else 0,
                "min": min(scores) if scores else 0,
                "max": max(scores) if scores else 0,
                "distribution": {
                    "high_7_10": len([s for s in scores if s >= 7]),
                    "medium_4_6": len([s for s in scores if 4 <= s < 7]),
                    "low_1_3": len([s for s in scores if s < 4])
                }
            },
            "probability_stats": {
                "mean": sum(probabilities) / len(probabilities) if probabilities else 0,
                "median": sorted(probabilities)[len(probabilities)//2] if probabilities else 0,
                "high_70_plus": len([p for p in probabilities if p >= 70]),
                "medium_30_69": len([p for p in probabilities if 30 <= p < 70]),
                "low_under_30": len([p for p in probabilities if p < 30])
            },
            "recommendations": recommendations
        }
    
    def filter_jobs(self, 
                   min_score: int = None,
                   max_score: int = None,
                   min_probability: int = None,
                   recommendations: List[str] = None,
                   companies: List[str] = None,
                   keywords: List[str] = None) -> List[Dict[str, Any]]:
        """Filter jobs based on various criteria"""
        
        filtered = []
        
        for job in self.jobs:
            # Skip jobs without analysis
            if "fit_analysis" not in job:
                continue
            
            fit_analysis = job.get("fit_analysis", {})
            if not isinstance(fit_analysis, dict):
                continue
            
            # Score filters
            score = fit_analysis.get("overall_score", 0)
            if min_score is not None and score < min_score:
                continue
            if max_score is not None and score > max_score:
                continue
            
            # Probability filter
            probability = fit_analysis.get("interview_probability", 0)
            if min_probability is not None and probability < min_probability:
                continue
            
            # Recommendation filter
            recommendation = fit_analysis.get("recommendation", "")
            if recommendations and recommendation not in recommendations:
                continue
            
            # Company filter
            company = job.get("company", "").lower()
            if companies:
                if not any(comp.lower() in company for comp in companies):
                    continue
            
            # Keywords filter (search in title and description)
            if keywords:
                title = job.get("title", "").lower()
                description = job.get("description", "").lower()
                content = f"{title} {description}"
                
                if not any(keyword.lower() in content for keyword in keywords):
                    continue
            
            filtered.append(job)
        
        return filtered
    
    def get_top_opportunities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top job opportunities based on score and probability"""
        
        analyzed_jobs = [job for job in self.jobs if "fit_analysis" in job]
        
        # Sort by combined score (score * probability)
        def combined_score(job):
            fit_analysis = job.get("fit_analysis", {})
            score = fit_analysis.get("overall_score", 0)
            prob = fit_analysis.get("interview_probability", 0)
            return score * (prob / 100)  # Normalize probability to 0-1
        
        top_jobs = sorted(analyzed_jobs, key=combined_score, reverse=True)
        
        return top_jobs[:limit]
    
    def export_to_csv(self, output_path: str = None, include_analysis: bool = True):
        """Export job data to CSV for further analysis"""
        
        if output_path is None:
            output_path = self.file_path.with_suffix('.csv')
        
        rows = []
        
        for job in self.jobs:
            row = {
                'job_id': job.get('id', ''),
                'title': job.get('title', ''),
                'company': job.get('company', ''),
                'location': job.get('location', ''),
                'url': job.get('url', ''),
                'posted_time': job.get('posted_time', ''),
                'scraped_at': job.get('scraped_at', ''),
            }
            
            if include_analysis and 'fit_analysis' in job:
                fit_analysis = job.get('fit_analysis', {})
                
                if isinstance(fit_analysis, dict):
                    row.update({
                        'overall_score': fit_analysis.get('overall_score', 0),
                        'interview_probability': fit_analysis.get('interview_probability', 0),
                        'recommendation': fit_analysis.get('recommendation', ''),
                        'confidence': fit_analysis.get('confidence', ''),
                        'ats_score': fit_analysis.get('analysis', {}).get('ats_screening', {}).get('score', 0),
                        'domain_score': fit_analysis.get('analysis', {}).get('domain_expertise', {}).get('score', 0),
                        'role_fit_score': fit_analysis.get('analysis', {}).get('role_fit', {}).get('score', 0),
                        'deal_breakers': len(fit_analysis.get('deal_breakers', [])),
                        'strategic_notes': fit_analysis.get('strategic_notes', '')
                    })
                else:
                    # Handle old text-based analysis
                    row.update({
                        'overall_score': 0,
                        'interview_probability': 0,
                        'recommendation': 'legacy_format',
                        'confidence': 'unknown',
                        'ats_score': 0,
                        'domain_score': 0,
                        'role_fit_score': 0,
                        'deal_breakers': 0,
                        'strategic_notes': 'Legacy text format'
                    })
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
        print(f"📊 Exported {len(rows)} jobs to {output_path}")
        
        return df
    
    def generate_report(self, output_path: str = None) -> str:
        """Generate a comprehensive analysis report"""
        
        if output_path is None:
            output_path = self.file_path.with_suffix('.md')
        
        stats = self.get_summary_stats()
        top_ops = self.get_top_opportunities(5)
        
        # Generate report content
        report = f"""# Job Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source File: {self.file_path}

## Summary Statistics

- **Total Jobs**: {stats.get('total_jobs', 0)}
- **Analyzed Jobs**: {stats.get('analyzed_jobs', 0)}
- **Analysis Coverage**: {stats.get('analyzed_jobs', 0) / max(stats.get('total_jobs', 1), 1) * 100:.1f}%

### Score Distribution
- **High (7-10)**: {stats.get('score_stats', {}).get('distribution', {}).get('high_7_10', 0)} jobs
- **Medium (4-6)**: {stats.get('score_stats', {}).get('distribution', {}).get('medium_4_6', 0)} jobs  
- **Low (1-3)**: {stats.get('score_stats', {}).get('distribution', {}).get('low_1_3', 0)} jobs

- **Average Score**: {stats.get('score_stats', {}).get('mean', 0):.1f}
- **Median Score**: {stats.get('score_stats', {}).get('median', 0):.1f}

### Interview Probability
- **High (70%+)**: {stats.get('probability_stats', {}).get('high_70_plus', 0)} jobs
- **Medium (30-69%)**: {stats.get('probability_stats', {}).get('medium_30_69', 0)} jobs
- **Low (<30%)**: {stats.get('probability_stats', {}).get('low_under_30', 0)} jobs

- **Average Probability**: {stats.get('probability_stats', {}).get('mean', 0):.1f}%

### Recommendations
"""
        
        for rec, count in stats.get('recommendations', {}).items():
            report += f"- **{rec.replace('_', ' ').title()}**: {count} jobs\n"
        
        report += "\n## Top 5 Opportunities\n\n"
        
        for i, job in enumerate(top_ops, 1):
            fit_analysis = job.get('fit_analysis', {})
            score = fit_analysis.get('overall_score', 0)
            prob = fit_analysis.get('interview_probability', 0)
            
            report += f"""### {i}. {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}

- **Score**: {score}/10
- **Interview Probability**: {prob}%
- **Recommendation**: {fit_analysis.get('recommendation', 'unknown').replace('_', ' ').title()}
- **URL**: {job.get('url', 'N/A')}

**Strategic Notes**: {fit_analysis.get('strategic_notes', 'No notes available')}

"""
        
        # Write report to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"📄 Generated report: {output_path}")
        return report

# ===============================================
# CLASSIFICATION FUNCTIONS (Azure OpenAI)
# ===============================================

def load_assistant_id():
    """Load assistant ID from file if not in environment"""
    if ASSISTANT_ID:
        return ASSISTANT_ID
    
    try:
        with open("assistant_id.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print("❌ No assistant ID found. Please set AZURE_ASSISTANT_ID or create assistant first.")
        return None

def create_azure_client():
    """Create Azure OpenAI client with working API version"""
    api_version = "2024-12-01-preview"
    try:
        with open("assistant_config.txt", "r") as f:
            for line in f:
                if line.startswith("API_VERSION="):
                    api_version = line.split("=")[1].strip()
                    break
    except FileNotFoundError:
        pass
    
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=api_version
    )

def extract_json_from_response(response_text: str) -> dict:
    """Extract and parse JSON from the assistant's response"""
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass
    
    # Look for JSON blocks in the response
    json_patterns = [
        r'```json\s*(\{.*?\})\s*```',
        r'```\s*(\{.*?\})\s*```',
        r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, response_text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    return {
        "error": "Could not parse structured response",
        "raw_response": response_text,
        "overall_score": 0,
        "recommendation": "manual_review_required"
    }

def classify_job_fit(job_data: dict) -> dict:
    """
    Classify a single job's fit using Azure OpenAI Assistant.
    
    Args:
        job_data (dict): Job data with title, company, description
        
    Returns:
        dict: Structured fit analysis
    """
    if not AZURE_OPENAI_AVAILABLE:
        return {"error": "Azure OpenAI not available"}
    
    assistant_id = load_assistant_id()
    if not assistant_id:
        return {"error": "No assistant ID available"}
    
    client = create_azure_client()
    
    job_title = job_data.get("title", "Unknown")
    job_company = job_data.get("company", "Unknown")
    job_description = job_data.get("description", "No description")

    # Dynamically list available resume files from /resumes directory
    resume_dir = Path("resumes")
    resume_list = []
    if resume_dir.exists():
        for f in resume_dir.iterdir():
            if f.is_file() and f.suffix == ".pdf":
                resume_list.append(f.name)
    resume_entries = "\n".join([f"- {r}" for r in resume_list])
    resume_section = (
        f"Choose from the following resume files:\n{resume_entries}\n\n"
        "These resumes are embedded in your file search vector store and must be used for semantic context. "
        "You have file search capabilities enabled. Use them to compare the resumes to the job description.\n"
        "Select the top 3 most semantically relevant resumes, then perform detailed evaluation across ATS score, role fit, and domain match.\n"
        "Choose a single best-fit resume to use downstream.\n"
        "⚠️ The selected resume filename must exactly match one of the filenames listed above. Do not invent or alter filenames. Only listed resume filenames are valid and must be used without modification."
    )

    try:
        # Create thread with vector store access
        if AZURE_VECTOR_STORE_ID and AZURE_VECTOR_STORE_ID != "":
            thread = client.beta.threads.create(
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [AZURE_VECTOR_STORE_ID]
                    }
                }
            )
        else:
            thread = client.beta.threads.create()
        
        # Create structured prompt for JSON output, include resume_section before JSON block
        structured_prompt = f"""You are a job application success optimizer. Analyze this job posting and return your assessment as a JSON object with the exact structure shown below.

JOB CONTEXT:
- Title: {job_title}
- Company: {job_company}
- Description: {job_description}

{resume_section}

RETURN ONLY VALID JSON in this exact structure (no additional text):

{{
  "overall_score": <number 1-10>,
  "interview_probability": <number 0-100>,
  "recommendation": "<apply_now|apply_different_level|network_first|skip>",
  "confidence": "<high|medium|low>",
  "analysis": {{
    "ats_screening": {{
      "score": <number 1-10>,
      "missing_keywords": ["keyword1", "keyword2"],
      "years_experience_match": <boolean>,
      "education_match": <boolean>
    }},
    "human_reviewer_appeal": {{
      "score": <number 1-10>,
      "relevant_companies": <boolean>,
      "career_progression": <boolean>,
      "quantified_achievements": <boolean>
    }},
    "domain_expertise": {{
      "score": <number 1-10>,
      "industry_match": "<strong|moderate|weak|none>",
      "technical_alignment": "<strong|moderate|weak|none>",
      "critical_gaps": ["gap1", "gap2"]
    }},
    "role_fit": {{
      "score": <number 1-10>,
      "seniority_match": "<over|appropriate|under>",
      "compensation_alignment": "<likely|possible|unlikely>",
      "location_compatible": <boolean>
    }}
  }},
  "resume_recommendations": [
    {{
      "resume_name": "resume_filename.pdf",
      "match_score": <number 1-10>,
      "strengths": ["strength1", "strength2"],
      "weaknesses": ["weakness1", "weakness2"],
      "recommended": <boolean>
    }}
    // up to 3 entries allowed, sorted by match quality
  ],
  "deal_breakers": ["issue1", "issue2"],
  "strategic_notes": "Brief actionable advice for this application",
  "processing_timestamp": "{time.time()}"
}}

Be realistic and conservative with scores. Most applications should score 3-6, not 7-10."""

        # Add message to thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=structured_prompt
        )
        
        # Create and run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )
        
        # Wait for completion
        max_wait_time = 60
        start_time = time.time()
        
        while run.status in ['queued', 'in_progress', 'cancelling']:
            if time.time() - start_time > max_wait_time:
                return {"error": "Timeout waiting for response", "overall_score": 0}
            
            time.sleep(3)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            
            if run.status == 'completed':
                break
            elif run.status == 'failed':
                error_msg = run.last_error.message if run.last_error else "Unknown error"
                return {"error": f"Run failed: {error_msg}", "overall_score": 0}
        
        # Retrieve response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        assistant_messages = [msg for msg in messages.data if msg.role == "assistant"]
        
        if assistant_messages:
            response_content = assistant_messages[0].content[0].text.value
            structured_result = extract_json_from_response(response_content)
            structured_result["thread_id"] = thread.id
            structured_result["run_id"] = run.id
            return structured_result
        else:
            return {"error": "No assistant response found", "overall_score": 0}
        
    except Exception as e:
        return {"error": str(e), "overall_score": 0}

def classify_fit_from_file(file_path: str) -> dict:
    """
    Process a JSONL file and add structured fit_analysis to each job entry.
    
    Args:
        file_path (str): Path to the JSONL file to process
        
    Returns:
        dict: Summary of processing results
    """
    if not AZURE_OPENAI_AVAILABLE:
        return {"error": "Azure OpenAI not available", "processed": 0}
    
    input_path = Path(file_path)
    if not input_path.exists():
        return {"error": f"File not found: {input_path}", "processed": 0}

    print(f"🔍 Processing file: {input_path}")
    
    temp_file = None
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    try:
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', 
            delete=False, 
            dir=input_path.parent,
            prefix=f"{input_path.stem}_temp_",
            suffix=input_path.suffix,
            encoding='utf-8'
        )
        
        # Process each line
        with open(input_path, "r", encoding='utf-8') as infile:
            for line_num, line in enumerate(infile, start=1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    job_data = json.loads(line)
                    
                    # Check if already has fit_analysis
                    if "fit_analysis" in job_data and job_data["fit_analysis"]:
                        print(f"⏭️ Skipping job {line_num}: already has fit_analysis.")
                        skipped_count += 1
                        temp_file.write(json.dumps(job_data, ensure_ascii=False) + "\n")
                        continue

                    job_title = job_data.get("title", "Unknown")
                    job_company = job_data.get("company", "Unknown")
                    
                    print(f"📊 Analyzing job {line_num}: {job_title} at {job_company}")
                    
                    # Run structured analysis
                    result = classify_job_fit(job_data)
                    
                    # Add structured fit analysis
                    job_data["fit_analysis"] = result
                    job_data["fit_analysis_timestamp"] = time.time()
                    
                    # Add quick access fields for filtering/sorting
                    job_data["overall_score"] = result.get("overall_score", 0)
                    job_data["recommendation"] = result.get("recommendation", "unknown")
                    job_data["interview_probability"] = result.get("interview_probability", 0)
                    
                    if "error" in result:
                        print(f"❌ Error analyzing job {line_num}: {result['error']}")
                        error_count += 1
                    else:
                        processed_count += 1
                        print(f"✅ Successfully analyzed job {line_num} (Score: {result.get('overall_score', 'N/A')})")
                    
                    # Write updated job data
                    temp_file.write(json.dumps(job_data, ensure_ascii=False) + "\n")
                    temp_file.flush()
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️ Skipping line {line_num}: JSON decode error - {e}")
                    error_count += 1
                    continue
                except Exception as e:
                    print(f"⚠️ Error processing line {line_num}: {e}")
                    error_count += 1
                    continue
        
        # Close temp file and replace original
        temp_file.close()
        
        # Create backup
        backup_path = input_path.with_suffix(f"{input_path.suffix}.backup")
        shutil.copy2(input_path, backup_path)
        print(f"📄 Created backup: {backup_path}")
        
        # Replace original
        shutil.move(temp_file.name, input_path)
        print(f"✅ Updated original file: {input_path}")
        
        # Summary
        total_lines = processed_count + skipped_count + error_count
        summary = {
            "status": "completed",
            "total_lines": total_lines,
            "processed": processed_count,
            "skipped": skipped_count,
            "errors": error_count,
            "backup_created": str(backup_path)
        }
        
        print(f"\n📊 Processing Summary:")
        print(f"   Total lines: {total_lines}")
        print(f"   Processed: {processed_count}")
        print(f"   Skipped: {skipped_count}")
        print(f"   Errors: {error_count}")
        
        return summary
        
    except Exception as e:
        error_msg = f"❌ Fatal error processing file: {str(e)}"
        print(error_msg)
        
        # Clean up temp file
        if temp_file and hasattr(temp_file, 'name') and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except:
                pass
        
        return {
            "error": error_msg,
            "processed": processed_count,
            "skipped": skipped_count,
            "errors": error_count
        }

def main():
    """Command line interface for job analysis tools"""
    parser = argparse.ArgumentParser(description="Analyze structured job fit data")
    parser.add_argument("file", help="JSONL file with job analysis data")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show summary statistics")
    
    # Filter command
    filter_parser = subparsers.add_parser("filter", help="Filter jobs by criteria")
    filter_parser.add_argument("--min-score", type=int, help="Minimum overall score")
    filter_parser.add_argument("--max-score", type=int, help="Maximum overall score")
    filter_parser.add_argument("--min-probability", type=int, help="Minimum interview probability")
    filter_parser.add_argument("--recommendations", nargs="+", 
                              choices=["apply_now", "apply_different_level", "network_first", "skip"],
                              help="Filter by recommendations")
    filter_parser.add_argument("--companies", nargs="+", help="Filter by company names")
    filter_parser.add_argument("--keywords", nargs="+", help="Filter by keywords in title/description")
    filter_parser.add_argument("--limit", type=int, default=10, help="Limit number of results")
    
    # Top command
    top_parser = subparsers.add_parser("top", help="Show top opportunities")
    top_parser.add_argument("--limit", type=int, default=10, help="Number of top jobs to show")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export to CSV")
    export_parser.add_argument("--output", help="Output CSV file path")
    export_parser.add_argument("--no-analysis", action="store_true", help="Exclude analysis columns")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate comprehensive report")
    report_parser.add_argument("--output", help="Output markdown file path")
    
    # Classify command
    classify_parser = subparsers.add_parser("classify", help="Run classification on file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "classify":
        # Run classification
        result = classify_fit_from_file(args.file)
        if "error" in result:
            print(f"❌ Classification failed: {result['error']}")
        else:
            print(f"✅ Classification completed: {result}")
        return
    
    # Create analyzer for other commands
    analyzer = JobAnalyzer(args.file)
    
    if args.command == "stats":
        stats = analyzer.get_summary_stats()
        print("\n📊 Summary Statistics:")
        print(f"Total Jobs: {stats.get('total_jobs', 0)}")
        print(f"Analyzed Jobs: {stats.get('analyzed_jobs', 0)}")
        
        score_stats = stats.get('score_stats', {})
        print(f"\nScore Distribution:")
        print(f"  High (7-10): {score_stats.get('distribution', {}).get('high_7_10', 0)}")
        print(f"  Medium (4-6): {score_stats.get('distribution', {}).get('medium_4_6', 0)}")
        print(f"  Low (1-3): {score_stats.get('distribution', {}).get('low_1_3', 0)}")
        print(f"  Average: {score_stats.get('mean', 0):.1f}")
        
        prob_stats = stats.get('probability_stats', {})
        print(f"\nInterview Probability:")
        print(f"  High (70%+): {prob_stats.get('high_70_plus', 0)}")
        print(f"  Medium (30-69%): {prob_stats.get('medium_30_69', 0)}")
        print(f"  Low (<30%): {prob_stats.get('low_under_30', 0)}")
        print(f"  Average: {prob_stats.get('mean', 0):.1f}%")
        
        print(f"\nRecommendations:")
        for rec, count in stats.get('recommendations', {}).items():
            print(f"  {rec.replace('_', ' ').title()}: {count}")
    
    elif args.command == "filter":
        filtered = analyzer.filter_jobs(
            min_score=args.min_score,
            max_score=args.max_score,
            min_probability=args.min_probability,
            recommendations=args.recommendations,
            companies=args.companies,
            keywords=args.keywords
        )
        
        print(f"\n🔍 Found {len(filtered)} jobs matching criteria:")
        
        for i, job in enumerate(filtered[:args.limit], 1):
            fit_analysis = job.get('fit_analysis', {})
            score = fit_analysis.get('overall_score', 0)
            prob = fit_analysis.get('interview_probability', 0)
            rec = fit_analysis.get('recommendation', 'unknown')
            
            print(f"\n{i}. {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
            print(f"   Score: {score}/10, Probability: {prob}%, Recommendation: {rec}")
            print(f"   URL: {job.get('url', 'N/A')}")
    
    elif args.command == "top":
        top_jobs = analyzer.get_top_opportunities(args.limit)
        
        print(f"\n🎯 Top {len(top_jobs)} Opportunities:")
        
        for i, job in enumerate(top_jobs, 1):
            fit_analysis = job.get('fit_analysis', {})
            score = fit_analysis.get('overall_score', 0)
            prob = fit_analysis.get('interview_probability', 0)
            combined = score * (prob / 100)
            
            print(f"\n{i}. {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
            print(f"   Score: {score}/10, Probability: {prob}%, Combined: {combined:.1f}")
            print(f"   Recommendation: {fit_analysis.get('recommendation', 'unknown')}")
            print(f"   Notes: {fit_analysis.get('strategic_notes', 'No notes')[:100]}...")
            print(f"   URL: {job.get('url', 'N/A')}")
    
    elif args.command == "export":
        df = analyzer.export_to_csv(
            output_path=args.output,
            include_analysis=not args.no_analysis
        )
        print(f"✅ Exported {len(df)} jobs to CSV")
    
    elif args.command == "report":
        report = analyzer.generate_report(args.output)
        print("✅ Generated comprehensive report")

if __name__ == "__main__":
    main()