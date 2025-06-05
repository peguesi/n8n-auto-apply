def run_stage_with_retries(stage_name, client, prompt, base_thread_id, assistant_id, force_new_thread_on_final_retry=False):
    """Generalized helper to run a pipeline stage with up to 3 retries, optionally forcing a new thread on the last attempt."""
    for attempt in range(3):
        if attempt == 2 and force_new_thread_on_final_retry:
            print(f"🧹 Final retry for {stage_name} → new thread")
            thread = client.beta.threads.create()
            thread_id = thread.id
        else:
            thread_id = base_thread_id
            thread = client.beta.threads.retrieve(thread_id=thread_id)
        try:
            client.beta.threads.messages.create(thread_id=thread_id, role="user", content=prompt)
            run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
            wait_for_run_completion(client, thread_id, run.id)
            return thread_id, run
        except Exception as e:
            print(f"⚠️ {stage_name} attempt {attempt+1} failed: {e}")
            time.sleep(5)
    raise RuntimeError(f"❌ {stage_name} failed after 3 attempts")
#!/usr/bin/env python3
"""
Job AI Pipeline - Enhanced classification + intelligent content generation
Leverages thread context and analysis intelligence for strategic content creation
Enhanced with authenticity controls and company context validation
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from datetime import datetime
import os
import time
import tempfile
import shutil
import re
import logging

# Helper: wait for run completion (threaded)
def wait_for_run_completion(client, thread_id, run_id, max_wait=30):
    """Wait for a run to complete, fail, or be cancelled, with polling."""
    for _ in range(max_wait):
        run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run_status.status in ["completed", "failed", "cancelled"]:
            return run_status
        time.sleep(1)
    raise TimeoutError(f"Run {run_id} did not finish after {max_wait}s")

# Azure OpenAI imports
try:
    from openai import AzureOpenAI
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: Azure OpenAI not available. Pipeline will not work.")
    AZURE_OPENAI_AVAILABLE = False

# Setup logging
def setup_logging():
    """Setup logging for the pipeline"""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "job_ai_pipeline.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Environment variables for Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://wercopenai.openai.azure.com/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "48b0cc7a06d04279a8ae53997526965e")
AZURE_VECTOR_STORE_ID = os.getenv("AZURE_VECTOR_STORE_ID", "vs_X9Zg4NAmhYrlQg9NICEpkgFT")
ASSISTANT_ID = os.getenv("AZURE_ASSISTANT_ID")

class JobAIPipeline:
    def process_single_job(self, job_data: dict) -> dict:
        """
        Process a single job dict through classification and content generation,
        and return the enriched job_data with added fields.
        """
        # Run enhanced classification and content pipeline
        result = self.process_job_complete(job_data.copy())
        
        # Enrich the original job_data with classification results
        enriched_job = job_data.copy()
        fit_analysis = result.get("fit_analysis", {})
        if fit_analysis:
            enriched_job["fit_analysis"] = fit_analysis
        # Add generated_content if available
        generated_content = result.get("generated_content")
        if generated_content:
            enriched_job["generated_content"] = generated_content
        
        return enriched_job
    """Enhanced AI pipeline for job analysis and strategic content generation with authenticity controls"""
    
    def __init__(self):
        self.client = self._create_azure_client()
        self.assistant_id = self._load_assistant_id()
        
        # Role title selection logic
        self.role_title_logic = {
            "large_org_keywords": ["google", "meta", "amazon", "microsoft", "apple", "netflix", "uber", "airbnb", "stripe", "spotify"],
            "execution_keywords": ["execution", "shipping fast", "cross-functional", "pmm", "a/b testing", "experiment", "iterate"],
            "ownership_keywords": ["ownership", "own", "lead", "drive", "responsible for"],
            "avoid_head_keywords": ["head of product", "product strategy", "vp product"],
            "startup_keywords": ["seed", "series a", "pre-series", "first pm", "0→1", "zero to one", "founder", "founding team", "early stage", "scrappy", "wearing multiple hats", "startup experience", "founder dna"],
            "vision_keywords": ["build the vision", "define strategy", "lead a team", "strategic", "visionary", "long-term roadmap", "product vision", "product strategy", "product roadmap"],
            "founder_keywords": ["founder dna", "wearing multiple hats", "startup experience", "scrappy", "early stage", "0→1", "zero to one", "founding team", "first pm", "seed", "series a", "pre-series"],
        }
    
    def _create_azure_client(self):
        """Create Azure OpenAI client"""
        if not AZURE_OPENAI_AVAILABLE:
            return None
        
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
    
    def _load_assistant_id(self):
        """Load assistant ID from environment or file"""
        if ASSISTANT_ID:
            return ASSISTANT_ID
        
        try:
            with open("assistant_id.txt", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.error("No assistant ID found. Please set AZURE_ASSISTANT_ID or create assistant first.")
            return None
    
    def should_generate_content(self, fit_analysis: dict, min_score: int = 6) -> bool:
        """Determine if job qualifies for content generation"""
        if not isinstance(fit_analysis, dict):
            return False
        
        score = fit_analysis.get("overall_score", 0)
        recommendation = fit_analysis.get("recommendation", "")
        
        # Skip low scores
        if score < min_score:
            logger.info(f"Skipping content generation - Score {score} below threshold {min_score}")
            return False
        
        # Skip certain recommendations regardless of score
        if recommendation in ["skip"]:
            logger.info(f"Skipping content generation - Recommendation: {recommendation}")
            return False
        
        return True
    
    def classify_job_fit(self, job_data: dict, resume_from_checkpoint: bool = False, existing_thread_id: str = None) -> dict:
        """Enhanced job classification with company context validation"""
        if not self.client or not self.assistant_id:
            return {"error": "Azure OpenAI or assistant not available", "overall_score": 0}
        
        job_title = job_data.get("title", "Unknown")
        job_company = job_data.get("company", "Unknown")
        job_description = job_data.get("description", "No description")
        
        try:
            # Determine run mode: fresh or resume
            run_mode = "resume" if resume_from_checkpoint else "fresh"
            if run_mode == "resume":
                print(f"🔄 Resuming from thread: {existing_thread_id}")
                thread = self.client.beta.threads.retrieve(thread_id=existing_thread_id)
                thread_id = thread.id
            else:
                print("🆕 Starting fresh run with new thread")
                if AZURE_VECTOR_STORE_ID:
                    thread = self.client.beta.threads.create(
                        tool_resources={
                            "file_search": {
                                "vector_store_ids": [AZURE_VECTOR_STORE_ID]
                            }
                        }
                    )
                else:
                    thread = self.client.beta.threads.create()
                thread_id = thread.id
            # Before creating message, ensure previous run is complete
            run = None
            try:
                runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
                if runs and runs.data:
                    run = runs.data[0]
            except Exception as e:
                logger.debug(f"Could not check previous runs: {e}")
            if run and run.status not in ["completed", "failed", "cancelled"]:
                print(f"⏳ Waiting for previous run {run.id} to complete...")
                wait_for_run_completion(self.client, thread_id, run.id)
            # Enhanced classification prompt with company context validation
            classification_prompt = f"""You are a job application success optimizer with access to my complete resume library. Analyze this job posting and provide both fit assessment AND strategic content planning, while validating your understanding of my company backgrounds.

JOB CONTEXT:
- Title: {job_title}
- Company: {job_company}
- Description: {job_description}

FIRST, validate your understanding of my company backgrounds using your vector store access. These MUST be accurate:

COMPANY CONTEXT VALIDATION (use exact descriptions from vector store):
- Wercflow: AI-powered workflow platform that helps creative teams find talent and companies, generate documents, and manage media production workflows using natural language
- Glossom: Social commerce platform built for beauty enthusiasts, offering video editing tools for creating and sharing user-generated content (makeup, hair, nail, fashion tutorials), enabling product discovery and shopping directly through video
- resolution: German software development company specializing in Atlassian ecosystem apps that enhance user management, authentication, and productivity within Atlassian products
- 19th & Park: New York City-based creative marketing and production agency specializing in content and experiences for cross-cultural and cross-generational audiences

Now provide comprehensive analysis as JSON:

{{
  "overall_score": <number 1-10>,
  "interview_probability": <number 0-100>,
  "recommendation": "<apply_now|apply_different_level|network_first|skip>",
  "confidence": "<high|medium|low>",
  
  "analysis": {{
    "ats_screening": {{
      "score": <number 1-10>,
      "critical_missing_keywords": ["specific terms job requires"],
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
      "true_gaps": ["actual skill/experience gaps"],
      "inferrable_from_experience": ["gaps that can be bridged with existing experience"]
    }},
    "role_fit": {{
      "score": <number 1-10>,
      "seniority_match": "<over|appropriate|under>",
      "compensation_alignment": "<likely|possible|unlikely>",
      "location_compatible": <boolean>
    }}
  }},

  "company_context_validation": {{
    "wercflow": "AI-powered workflow platform that helps creative teams find talent and companies, generate documents, and manage media production workflows using natural language",
    "glossom": "Social commerce platform built for beauty enthusiasts, offering video editing tools for creating and sharing user-generated content (makeup, hair, nail, fashion tutorials), enabling product discovery and shopping directly through video", 
    "resolution": "German software development company specializing in Atlassian ecosystem apps that enhance user management, authentication, and productivity within Atlassian products",
    "nineteenth_park": "New York City-based creative marketing and production agency specializing in content and experiences for cross-cultural and cross-generational audiences"
  }},
  
  "content_strategy": {{
    "role_title_recommendation": "<exact title from my library variants>",
    "profile_positioning": "how to position my background for this role",
    "key_experiences_to_emphasize": ["which of my roles are most relevant"],
    "metrics_to_highlight": ["specific numbers from my background to feature"],
    "required_keywords_for_ats": ["15-20 critical terms from job description"],
    "gap_bridging_strategy": "how to frame my experience to address gaps",
    "wercflow_focus": "what aspects of Wercflow to emphasize",
    "glossom_focus": "what aspects of Glossom to emphasize", 
    "atlassian_focus": "what aspects of Atlassian to emphasize",
    "nineteenth_park_focus": "what aspects of 19th and Park to emphasize",
    "authenticity_rules": {{
      "metric_usage": "Each metric (20k users, €620K funding, 45% activation, 500K users, 2.5M users) used ONCE maximum across all content",
      "company_accuracy": "Company contexts must remain factually accurate - no inventing business models",
      "keyword_limits": "Maximum 1 job-specific keyword per bullet for natural integration",
      "content_preference": "Enhance existing library content over creating new content unless high relevance"
    }}
  }},
  
  "deal_breakers": ["actual blocking issues"],
  "strategic_notes": "specific actionable advice for this application",
  "processing_timestamp": "{time.time()}"
}}

Be realistic with scores. Focus on creating actionable content strategy that leverages my actual experience while maintaining factual accuracy about company contexts."""
            
            # Add message and run
            message = self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=classification_prompt
            )
            # Ensure previous run is complete before creating new run
            run = None
            try:
                runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
                if runs and runs.data:
                    run = runs.data[0]
            except Exception as e:
                logger.debug(f"Could not check previous runs: {e}")
            if run and run.status not in ["completed", "failed", "cancelled"]:
                print(f"⏳ Waiting for previous run {run.id} to complete...")
                wait_for_run_completion(self.client, thread_id, run.id)
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )
            # Wait for completion with retry logic
            result = self._wait_for_completion(thread_id, run.id, max_wait=120)
            if result:
                result["thread_id"] = thread_id
                result["run_id"] = run.id
            return result
        except Exception as e:
            logger.error(f"Enhanced classification error: {e}")
            return {"error": str(e), "overall_score": 0}
    
    def assess_company_relevance(self, thread_id: str, job_data: dict, fit_analysis: dict) -> Optional[dict]:
        """Assess company relevance and determine content approach"""
        content_strategy = fit_analysis.get("content_strategy", {})
        company_contexts = fit_analysis.get("company_context_validation", {})
        
        relevance_prompt = f"""Using your validated company contexts and the job requirements, determine the relevance of each company experience and the appropriate content approach.

VALIDATED COMPANY CONTEXTS (from previous analysis):
- Wercflow: {company_contexts.get('wercflow', '')}
- Glossom: {company_contexts.get('glossom', '')}
- resolution: {company_contexts.get('resolution', '')}
- 19th & Park: {company_contexts.get('nineteenth_park', '')}

JOB REQUIREMENTS ANALYSIS:
- Title: {job_data.get('title', '')}
- Core responsibilities: [Extract from job description]
- Required skills: [Extract from job description] 
- Industry/domain: [Extract from job description]
- Key success metrics: [Extract from job description]

AUTHENTICITY RULES (established):
{content_strategy.get('authenticity_rules', {})}

SCORING CRITERIA:
- HIGH (Strategic new content): Direct domain match, strong skill alignment with job requirements
- MEDIUM (Enhanced library): Transferable skills, can naturally integrate keywords without forcing
- LOW (Library as-is): Minimal relevance, use best existing bullets unchanged
- SKIP (Not featured): No meaningful relevance to role requirements

RETURN comprehensive assessment:

{{
  "relevance_assessment": {{
    "wercflow": {{
      "score": "<high|medium|low|skip>",
      "reasoning": "Detailed explanation based on job requirements vs actual company context",
      "content_approach": "<strategic_new|enhance_library|use_existing|skip>",
      "skill_alignment": ["specific skills that align"],
      "domain_fit": "<strong|moderate|weak|none>"
    }},
    "glossom": {{
      "score": "<high|medium|low|skip>",
      "reasoning": "Detailed explanation based on job requirements vs actual company context", 
      "content_approach": "<strategic_new|enhance_library|use_existing|skip>",
      "skill_alignment": ["specific skills that align"],
      "domain_fit": "<strong|moderate|weak|none>"
    }},
    "resolution": {{
      "score": "<high|medium|low|skip>",
      "reasoning": "Detailed explanation based on job requirements vs actual company context",
      "content_approach": "<strategic_new|enhance_library|use_existing|skip>", 
      "skill_alignment": ["specific skills that align"],
      "domain_fit": "<strong|moderate|weak|none>"
    }},
    "nineteenth_park": {{
      "score": "<high|medium|low|skip>",
      "reasoning": "Detailed explanation based on job requirements vs actual company context",
      "content_approach": "<strategic_new|enhance_library|use_existing|skip>",
      "skill_alignment": ["specific skills that align"], 
      "domain_fit": "<strong|moderate|weak|none>"
    }}
  }},
  
  "content_distribution": {{
    "strategic_focus": ["companies requiring new strategic content"],
    "enhancement_targets": ["companies where library content can be enhanced"], 
    "library_usage": ["companies using existing library content as-is"],
    "skip": ["companies not featured in this application"]
  }},
  
  "keyword_distribution": {{
    "wercflow_keywords": ["if enhancing, which 1 keyword max"],
    "glossom_keywords": ["if enhancing, which 1 keyword max"],
    "resolution_keywords": ["if enhancing, which 1 keyword max"], 
    "nineteenth_park_keywords": ["if enhancing, which 1 keyword max"]
  }},
  
  "content_strategy_notes": "How this approach will create authentic, relevant content while maintaining company accuracy"
}}

Focus on authentic relevance - don't force companies into narratives that don't fit their actual business models."""

        # Ensure previous run is complete before sending new message
        run = None
        try:
            runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
            if runs and runs.data:
                run = runs.data[0]
        except Exception as e:
            logger.debug(f"Could not check previous runs: {e}")
        if run and run.status not in ["completed", "failed", "cancelled"]:
            print(f"⏳ Waiting for previous run {run.id} to complete...")
            wait_for_run_completion(self.client, thread_id, run.id)
        return self._send_message_and_wait(thread_id, relevance_prompt, "Company relevance assessment")

    def generate_strategic_profile(self, thread_id: str, content_strategy: dict, relevance_data: dict) -> Optional[dict]:
        """Generate strategic profile using analysis guidance"""
        high_relevance_companies = relevance_data.get("content_distribution", {}).get("strategic_focus", [])
        
        profile_prompt = f"""Generate PROFILE section using the strategic guidance from our job analysis and company relevance assessment.

STRATEGIC GUIDANCE:
- Role Title: {content_strategy.get('role_title_recommendation', 'Senior Product Manager')}
- Positioning: {content_strategy.get('profile_positioning', '')}
- Key Metrics: {content_strategy.get('metrics_to_highlight', [])}
- Required Keywords: {content_strategy.get('required_keywords_for_ats', [])[:10]}

COMPANY RELEVANCE (from previous analysis):
- Strategic Focus Companies: {high_relevance_companies}

STRICT AUTHENTICITY RULES:
- Use each metric ONLY ONCE across ALL content (profile + all bullets)
- Available metrics: 20k users, €620K funding, 45% activation, 500K users, 2.5M users
- Company contexts MUST remain factually accurate
- NO invented metrics or percentages allowed

REQUIREMENTS:
- Extract from my profile variants in vector store
- Must be 450-500 characters (template constraint)
- Integrate 50-80% of required keywords naturally
- Emphasize positioning strategy for this specific role
- Include maximum 2 metrics from guidance (save others for employment bullets)
- Focus on HIGH relevance companies only
- Maintain accurate company contexts

RETURN FORMAT:
{{
  "role_title": "{content_strategy.get('role_title_recommendation', 'Senior Product Manager')}",
  "profile_section": "450-500 character profile optimized for this role",
  "character_count": "exact character count",
  "companies_featured": ["which companies mentioned in profile"],
  "metrics_used": ["which specific metrics used - maximum 2"],
  "keywords_integrated": ["keywords naturally included"],
  "positioning_focus": "how profile positions candidate for this specific role",
  "authenticity_check": "confirmation that company contexts remain accurate"
}}

Focus on creating a compelling narrative that authentically represents experience while optimizing for this specific role."""

        # Ensure previous run is complete before sending new message
        run = None
        try:
            runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
            if runs and runs.data:
                run = runs.data[0]
        except Exception as e:
            logger.debug(f"Could not check previous runs: {e}")
        if run and run.status not in ["completed", "failed", "cancelled"]:
            print(f"⏳ Waiting for previous run {run.id} to complete...")
            wait_for_run_completion(self.client, thread_id, run.id)
        return self._send_message_and_wait(thread_id, profile_prompt, "Strategic profile generation")

    def generate_high_relevance_content(self, thread_id: str, relevance_data: dict, content_strategy: dict, used_metrics: list = None) -> Optional[dict]:
        """Generate strategic content for high-relevance companies only"""
        if used_metrics is None:
            used_metrics = []
            
        strategic_companies = relevance_data.get("content_distribution", {}).get("strategic_focus", [])
        if not strategic_companies:
            logger.info("No high-relevance companies found, skipping strategic content generation")
            return {"strategic_content": {}, "remaining_metrics": ["20k users", "€620K funding", "45% activation", "500K users", "2.5M users"]}
        
        available_metrics = [m for m in ["20k users", "€620K funding", "45% activation", "500K users", "2.5M users"] if m not in used_metrics]
        
        high_relevance_prompt = f"""Generate strategic content ONLY for companies scored as HIGH relevance in our assessment.

HIGH-RELEVANCE COMPANIES: {strategic_companies}

MANDATORY COMPANY CONTEXTS (maintain these exactly):
- Wercflow: AI-powered workflow platform that helps creative teams find talent and companies, generate documents, and manage media production workflows using natural language
- Glossom: Social commerce platform built for beauty enthusiasts, offering video editing tools for creating and sharing user-generated content (makeup, hair, nail, fashion tutorials), enabling product discovery and shopping directly through video
- resolution: German software development company specializing in Atlassian ecosystem apps that enhance user management, authentication, and productivity within Atlassian products
- 19th & Park: New York City-based creative marketing and production agency specializing in content and experiences for cross-cultural and cross-generational audiences

METRICS ALREADY USED: {used_metrics}
REMAINING AVAILABLE METRICS: {available_metrics}

STRATEGIC REQUIREMENTS:
- Keywords Available: {content_strategy.get('required_keywords_for_ats', [])}
- Positioning Focus: {content_strategy.get('profile_positioning', '')}

STRICT AUTHENTICITY ENFORCEMENT:
- Use ONLY metrics from resume library: 20k users, €620K funding, 45% activation, 500K users, 2.5M users
- Each metric can be used ONLY ONCE across ALL content
- NO invented percentages (no "30% improvement", "25% reduction", etc.)
- Company business models MUST remain factually accurate
- Use existing resume library bullets as foundation, then adapt

COMPANY-SPECIFIC FOCUS:
- Wercflow Focus: {content_strategy.get('wercflow_focus', 'AI workflow automation and creative team collaboration')}
- Glossom Focus: {content_strategy.get('glossom_focus', 'Video UGC social commerce for beauty enthusiasts')}
- Atlassian Focus: {content_strategy.get('atlassian_focus', 'Enterprise SaaS apps within Atlassian ecosystem')}
- 19th Park Focus: {content_strategy.get('nineteenth_park_focus', 'Creative marketing and production for diverse audiences')}

REQUIREMENTS PER COMPANY:
- EXACTLY 4 bullets, 128-150 characters each
- Use real achievements from my resume library as foundation
- Integrate keywords naturally (max 1 per bullet)
- Maintain accurate company business context
- Use available metrics strategically (each metric used only once across all companies)
- Connect to job requirements through authentic experience
- NO FABRICATED METRICS OR ACHIEVEMENTS

RETURN FORMAT:
{{
  "strategic_content": {{
    "company_name": {{
      "bullets": ["bullet1", "bullet2", "bullet3", "bullet4"],
      "metrics_used": ["which specific metrics used"], 
      "keywords_integrated": ["keywords naturally included"],
      "company_context_maintained": "confirmation of accurate business context",
      "library_source": "which library bullets inspired this content"
    }}
  }},
  "remaining_metrics": ["unused metrics available for other companies"],
  "authenticity_validation": "confirmation that all content maintains factual accuracy"
}}

Remember: Build on authentic achievements from resume library, don't invent new business models or capabilities for companies."""

        # Ensure previous run is complete before sending new message
        run = None
        try:
            runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
            if runs and runs.data:
                run = runs.data[0]
        except Exception as e:
            logger.debug(f"Could not check previous runs: {e}")
        if run and run.status not in ["completed", "failed", "cancelled"]:
            print(f"⏳ Waiting for previous run {run.id} to complete...")
            wait_for_run_completion(self.client, thread_id, run.id)
        return self._send_message_and_wait(thread_id, high_relevance_prompt, "High-relevance strategic content")

    def generate_medium_low_content(self, thread_id: str, relevance_data: dict, remaining_keywords: list, remaining_metrics: list) -> Optional[dict]:
        """Generate content for medium and low relevance companies using library as foundation"""
        medium_companies = relevance_data.get("content_distribution", {}).get("enhancement_targets", [])
        low_companies = relevance_data.get("content_distribution", {}).get("library_usage", [])
        
        if not medium_companies and not low_companies:
            logger.info("No medium or low relevance companies to process")
            return {"enhanced_content": {"medium_companies": {}}, "library_content": {"low_companies": {}}}
        
        library_prompt = f"""Process MEDIUM and LOW relevance companies using library content as the foundation.

MEDIUM-RELEVANCE COMPANIES: {medium_companies}
LOW-RELEVANCE COMPANIES: {low_companies}

MANDATORY COMPANY CONTEXTS (maintain these exactly):
- Wercflow: AI-powered workflow platform that helps creative teams find talent and companies, generate documents, and manage media production workflows using natural language
- Glossom: Social commerce platform built for beauty enthusiasts, offering video editing tools for creating and sharing user-generated content (makeup, hair, nail, fashion tutorials), enabling product discovery and shopping directly through video
- resolution: German software development company specializing in Atlassian ecosystem apps that enhance user management, authentication, and productivity within Atlassian products
- 19th & Park: New York City-based creative marketing and production agency specializing in content and experiences for cross-cultural and cross-generational audiences

METRICS ALREADY USED: {[]}  # Will be populated with used metrics
REMAINING KEYWORDS: {remaining_keywords}
REMAINING METRICS: {remaining_metrics}

STRICT AUTHENTICITY ENFORCEMENT:
- Use ONLY documented metrics from resume library: 20k users, €620K funding, 45% activation, 500K users, 2.5M users
- NO INVENTED PERCENTAGES OR METRICS (no "30% improvement", "25% reduction", etc.)
- Company contexts must remain factually accurate
- Use exact resume library bullets as foundation

APPROACH BY RELEVANCE LEVEL:

FOR MEDIUM-RELEVANCE COMPANIES:
- Find 4 best existing bullets from library for each company
- Enhance with maximum 1 keyword per bullet (natural integration only)
- Can use remaining metrics if they fit authentically with existing achievements
- Maintain core achievement and context accuracy
- NO FABRICATED IMPROVEMENTS OR METRICS

FOR LOW-RELEVANCE COMPANIES:  
- Find 4 strongest existing bullets from library for each company
- Use exactly as written from library (no modifications)
- These represent authentic achievements without forced relevance

CONTENT QUALITY CRITERIA:
- Prioritize bullets with quantified achievements from resume library
- Select bullets that show progression and impact
- Maintain authentic company contexts
- Avoid forcing irrelevant keywords
- NO INVENTED METRICS OR ACHIEVEMENTS

RETURN FORMAT:
{{
  "enhanced_content": {{
    "medium_companies": {{
      "company_name": {{
        "bullets": ["enhanced bullets with light keyword integration"],
        "source_bullets": ["original library bullets used as base"],
        "enhancements_made": ["what keywords/minor changes were added"],
        "metrics_used": ["any documented metrics added"],
        "authenticity_maintained": "yes/no with explanation"
      }}
    }}
  }},
  "library_content": {{
    "low_companies": {{
      "company_name": {{
        "bullets": ["exact library bullets, unmodified"],
        "library_reference": "source of these bullets in library",
        "selection_reasoning": "why these bullets were chosen"
      }}
    }}
  }},
  "content_strategy_notes": "How this approach maintains authenticity while supporting application"
}}

Focus on showcasing authentic achievements from resume library rather than forcing relevance through keyword stuffing or invented metrics."""

        # Ensure previous run is complete before sending new message
        run = None
        try:
            runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
            if runs and runs.data:
                run = runs.data[0]
        except Exception as e:
            logger.debug(f"Could not check previous runs: {e}")
        if run and run.status not in ["completed", "failed", "cancelled"]:
            print(f"⏳ Waiting for previous run {run.id} to complete...")
            wait_for_run_completion(self.client, thread_id, run.id)
        return self._send_message_and_wait(thread_id, library_prompt, "Medium/Low relevance content")

    def generate_skills_and_validate(self, thread_id: str, content_strategy: dict, all_generated_content: dict) -> Optional[dict]:
        """Generate skills section and validate all content for authenticity"""
        # Ensure previous run is complete before sending new message
        run = None
        try:
            runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
            if runs and runs.data:
                run = runs.data[0]
        except Exception as e:
            logger.debug(f"Could not check previous runs: {e}")
        if run and run.status not in ["completed", "failed", "cancelled"]:
            print(f"⏳ Waiting for previous run {run.id} to complete...")
            wait_for_run_completion(self.client, thread_id, run.id)
        skills_prompt = f"""Generate SKILLS section and validate all content for authenticity compliance.

STRATEGIC REQUIREMENTS:
- Keywords from analysis: {content_strategy.get('required_keywords_for_ats', [])}
- Gap bridging strategy: {content_strategy.get('gap_bridging_strategy', '')}
- Role positioning: {content_strategy.get('profile_positioning', '')}

MANDATORY COMPANY CONTEXTS (for validation):
- Wercflow: AI-powered workflow platform that helps creative teams find talent and companies, generate documents, and manage media production workflows using natural language
- Glossom: Social commerce platform built for beauty enthusiasts, offering video editing tools for creating and sharing user-generated content (makeup, hair, nail, fashion tutorials), enabling product discovery and shopping directly through video
- resolution: German software development company specializing in Atlassian ecosystem apps that enhance user management, authentication, and productivity within Atlassian products
- 19th & Park: New York City-based creative marketing and production agency specializing in content and experiences for cross-cultural and cross-generational audiences

ALL GENERATED CONTENT TO VALIDATE:
{json.dumps(all_generated_content, indent=2)}

SKILLS GENERATION APPROACH:
- Start with my proven skills from resume library
- Enhance skills to naturally match required keywords
- Infer logical skills from my actual experience  
- Bridge identified gaps through authentic skill positioning
- NO invented capabilities

REQUIREMENTS:
- EXACTLY 10 skills, 19-35 characters each
- Prioritize required keywords from analysis
- Maintain authenticity to my background
- Support strategic positioning for this role

CONTENT VALIDATION CHECKLIST:

1. METRIC USAGE AUDIT:
   - Track usage of: 20k users, €620K funding, 45% activation, 500K users, 2.5M users
   - Ensure each metric used maximum once across all content
   - FLAG any duplicate usage

2. COMPANY ACCURACY AUDIT:
   - Verify Wercflow described as AI workflow platform (NOT e-commerce)
   - Verify Glossom described as video UGC social commerce for beauty (NOT general marketing)
   - Verify resolution described as Atlassian apps (NOT generic IT solutions)
   - Verify 19th Park described as creative marketing agency (NOT product company)

3. INVENTED METRICS AUDIT:
   - Flag any fabricated percentages like "30% improvement", "25% reduction"
   - Ensure all metrics come from documented resume library only

4. KEYWORD DENSITY AUDIT:
   - Check for keyword stuffing or unnatural integration
   - Verify maximum 1 job keyword per bullet

RETURN FORMAT:
{{
  "skills_section": ["skill1", "skill2", "skill3", "skill4", "skill5", "skill6", "skill7", "skill8", "skill9", "skill10"],
  "skills_strategy": "how skills support positioning and bridge gaps",
  "gaps_addressed": ["gaps bridged through authentic skills"],
  
  "content_validation": {{
    "metric_usage_audit": {{
      "20k_users": "used in: [specific location or 'unused']",
      "45_activation": "used in: [specific location or 'unused']", 
      "620k_funding": "used in: [specific location or 'unused']",
      "500k_users": "used in: [specific location or 'unused']",
      "2_5m_users": "used in: [specific location or 'unused']"
    }},
    "company_accuracy_audit": {{
      "wercflow": "maintains AI workflow context: yes/no - explanation",
      "glossom": "maintains video UGC social commerce context: yes/no - explanation",
      "resolution": "maintains Atlassian apps context: yes/no - explanation", 
      "nineteenth_park": "maintains creative agency context: yes/no - explanation"
    }},
    "invented_metrics_audit": {{
      "fabricated_percentages_found": ["list any invented metrics like '30% improvement'"],
      "undocumented_achievements": ["list any achievements not in resume library"]
    }},
    "keyword_density_check": "appropriate/excessive - explanation",
    "authenticity_score": "1-10 with reasoning",
    "violations_found": ["any authenticity rule violations"],
    "recommendations": ["fixes needed if violations found"]
  }}
}}

This validation ensures our content remains credible and authentic while optimizing for the role."""

        return self._send_message_and_wait(thread_id, skills_prompt, "Skills generation and validation")

    def generate_cover_letter(self, thread_id: str, job_data: dict, fit_analysis: dict, relevance_data: dict, final_content: dict) -> Optional[dict]:
        """Generate cover letter using complete strategic context"""
        content_strategy = fit_analysis.get("content_strategy", {})
        company_contexts = fit_analysis.get("company_context_validation", {})
        high_relevance_companies = relevance_data.get("content_distribution", {}).get("strategic_focus", [])
        medium_relevance_companies = relevance_data.get("content_distribution", {}).get("enhancement_targets", [])
        
        cover_letter_prompt = f"""Generate a tailored cover letter using ALL the strategic context from our analysis, maintaining company accuracy and including case study evaluation.

    JOB DETAILS:
    - Title: {job_data.get('title', 'Unknown')}
    - Company: {job_data.get('company', 'Unknown')}
    - Full Description: {job_data.get('description', '')}

    STRATEGIC CONTEXT FROM ANALYSIS:
    - Role Title: {content_strategy.get('role_title_recommendation', 'Senior Product Manager')}
    - Positioning: {content_strategy.get('profile_positioning', '')}
    - Key Metrics: {content_strategy.get('metrics_to_highlight', [])}
    - Keywords: {content_strategy.get('required_keywords_for_ats', [])[:10]}
    - Gap Bridging: {content_strategy.get('gap_bridging_strategy', '')}

    COMPANY RELEVANCE SCORING (focus on these):
    - High Relevance: {high_relevance_companies}
    

    VALIDATED COMPANY CONTEXTS (maintain accuracy):
    {json.dumps(company_contexts, indent=2)}

    GENERATED RESUME CONTENT:
    - Profile: {final_content.get('profile_section', '')}
    - Experience Bullets: {json.dumps(final_content.get('employment_bullets', {}), indent=2)}
    - Skills: {final_content.get('skills_section', [])}

    TONE & STYLE:
    Confident, direct, pragmatic, and bullshit-free. Avoid fluff or generic phrases—speak with purpose, clarity, and credibility that reflects my natural writing style.

    CASE STUDY INTEGRATION INSTRUCTIONS:

    You have access to my case studies in the vector store. Each follows this structure:
    - Prefix: `case_study_`  
    - Filename slug (e.g., `case_study_title-name.txt` → slug: `title-name`)
    - Line 1: Case Study Title  
    - Line 2: Case Study Subtitle  
    - Lines 3+: Full case study body (max 300 words)

    ✴️ WHEN TO INCLUDE A CASE STUDY:
    Only include ONE case study if it meets one criteria:
    1. Strongly relevant to job's required outcomes, metrics, or domain
    2. Helps bridge a skill, industry, or experience gap flagged in our fit analysis—especially gaps marked as "inferrable from experience"

    If no case study meets this bar, skip inclusion entirely.

    ✍️ HOW TO REFERENCE:
    If including one, add this sentence at the END of the second paragraph:
    "This approach is documented in my case study, _\\"Case Study Title\\"_ available at https://isaiah.pegues.io/case-study-slug."

    Replace:
    - `Case Study Title` with line 1 of the file  
    - `case-study-slug` with filename slug (no extension or prefix)

    Integrate gracefully, don't bolt on. Keep tone aligned.

    STRUCTURE REQUIREMENTS:
    - 200 - 250 words total
    - Para 1: Why this job and positioning (use strategic context)
    - Para 2-3: Most relevant experience and metrics (focus on HIGH relevance companies)
    - Para 4: Closing with CTA

    AUTHENTICITY CONSTRAINTS:
    - Use only real resume data (no fabricated metrics)
    - Maintain accurate company contexts 
    - Use 3–8 keywords naturally (NO keyword stuffing)
    - Reference strategic positioning from our analysis

    RETURN FORMAT:
    {{
    "cover_letter": {{
        "paragraph_1": "First paragraph text",
        "paragraph_2": "Second paragraph text",
        "paragraph_3": "Third paragraph text", 
        "paragraph_4": "Fourth paragraph text"
    }},
    "cover_letter_full": "Complete letter as single text for reference",
    "case_study_link_used": "https://isaiah.pegues.io/case-study-slug or null",
    "case_study_justification": "Why this case study was chosen or why none was included",
    "companies_featured": ["which companies mentioned"],
    "strategic_alignment": "how letter aligns with our positioning strategy",
    "authenticity_maintained": "confirmation of accurate company contexts"
    }}

    Create a compelling narrative that authentically represents my experience while strategically positioning for this specific role."""

        return self._send_message_and_wait(thread_id, cover_letter_prompt, "Cover letter generation")

    def generate_content_strategic(self, thread_id: str, job_data: dict, fit_analysis: dict) -> Optional[dict]:
        """Generate content using strategic intelligence from classification"""
        if not self.client or not self.assistant_id:
            logger.error("Azure OpenAI or assistant not available")
            return None
        
        content_strategy = fit_analysis.get("content_strategy", {})
        
        try:
            # Step 1: Company Relevance Assessment
            logger.info("🎯 Step 1: Assessing company relevance...")
            relevance_result = self.assess_company_relevance(thread_id, job_data, fit_analysis)
            if not relevance_result:
                logger.error("Company relevance assessment failed")
                return None
            
            # Step 2: Strategic Profile Generation
            logger.info("📝 Step 2: Generating strategic profile...")
            profile_result = self.generate_strategic_profile(thread_id, content_strategy, relevance_result)
            if not profile_result:
                logger.error("Profile generation failed")
                return None
            
            used_metrics = profile_result.get("metrics_used", [])
            
            # Step 3: High-Relevance Company Content
            logger.info("🏢 Step 3: Generating high-relevance company content...")
            high_relevance_result = self.generate_high_relevance_content(
                thread_id, relevance_result, content_strategy, used_metrics
            )
            if not high_relevance_result:
                logger.error("High-relevance content generation failed")
                return None
            
            # Update used metrics
            for company_data in high_relevance_result.get("strategic_content", {}).values():
                used_metrics.extend(company_data.get("metrics_used", []))
            
            remaining_metrics = [m for m in ["20k users", "€620K funding", "45% activation", "500K users", "2.5M users"] 
                               if m not in used_metrics]
            remaining_keywords = [k for k in content_strategy.get("required_keywords_for_ats", []) 
                                if k not in [kw for company_data in high_relevance_result.get("strategic_content", {}).values() 
                                           for kw in company_data.get("keywords_integrated", [])]]
            
            # Step 4: Medium/Low Relevance Content
            logger.info("📚 Step 4: Processing medium/low relevance content...")
            library_result = self.generate_medium_low_content(
                thread_id, relevance_result, remaining_keywords, remaining_metrics
            )
            if not library_result:
                logger.error("Library content generation failed")
                return None
            
            # Combine all employment bullets
            employment_bullets = {}
            
            # Add strategic content (HIGH relevance)
            for company, data in high_relevance_result.get("strategic_content", {}).items():
                employment_bullets[company] = data.get("bullets", [])
            
            # Add enhanced content (MEDIUM relevance)
            for company, data in library_result.get("enhanced_content", {}).get("medium_companies", {}).items():
                employment_bullets[company] = data.get("bullets", [])
            
            # Add library content (LOW relevance)
            for company, data in library_result.get("library_content", {}).get("low_companies", {}).items():
                employment_bullets[company] = data.get("bullets", [])
            
            # Step 5: Skills Generation and Validation
            logger.info("🔧 Step 5: Generating skills and validating content...")
            all_content = {
                "profile": profile_result,
                "employment": employment_bullets,
                "relevance_data": relevance_result
            }
            
            skills_result = self.generate_skills_and_validate(thread_id, content_strategy, all_content)
            if not skills_result:
                logger.error("Skills generation failed")
                return None
            
            # Step 6: Assemble Final Content for Cover Letter
            final_content = {
                "role_title": profile_result.get("role_title", "Senior Product Manager"),
                "profile_section": profile_result.get("profile_section", ""),
                "employment_bullets": employment_bullets,
                "skills_section": skills_result.get("skills_section", [])
            }
            
            # Step 7: Cover Letter Generation
            logger.info("✉️ Step 6: Generating cover letter...")
            cover_letter_result = self.generate_cover_letter(
                thread_id, job_data, fit_analysis, relevance_result, final_content
            )
            if not cover_letter_result:
                logger.warning("Cover letter generation failed, continuing without it")
                cover_letter_result = {
                    "cover_letter": "Cover letter generation failed",
                    "case_study_link_used": None,
                    "case_study_justification": "Generation failed"
                }
            
            # Final Assembly
            return self._parse_strategic_content_enhanced(
                profile_result, high_relevance_result, library_result, skills_result, 
                cover_letter_result, relevance_result, content_strategy
            )
            
        except Exception as e:
            logger.error(f"Strategic content generation error: {e}")
            return None
    
    def _send_message_and_wait(self, thread_id: str, prompt: str, step_name: str, max_wait: int = 120, max_retries: int = 3) -> Optional[dict]:
        """Send message and wait for completion with retry logic"""
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 {step_name} - Attempt {attempt + 1}/{max_retries}")
                # On the final retry attempt, start a new thread to avoid zombie runs
                if attempt == 2:
                    print("🧹 Final retry attempt → starting new thread")
                    thread = self.client.beta.threads.create()
                    thread_id = thread.id
                # Ensure previous run is complete before sending new message
                run = None
                try:
                    runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
                    if runs and runs.data:
                        run = runs.data[0]
                except Exception as e:
                    logger.debug(f"Could not check previous runs: {e}")
                if run and run.status not in ["completed", "failed", "cancelled"]:
                    print(f"⏳ Waiting for previous run {run.id} to complete...")
                    wait_for_run_completion(self.client, thread_id, run.id)
                # Send message
                message = self.client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=prompt
                )
                logger.debug(f"Message created: {message.id}")
                # Ensure previous run is complete before creating new run
                run = None
                try:
                    runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
                    if runs and runs.data:
                        run = runs.data[0]
                except Exception as e:
                    logger.debug(f"Could not check previous runs: {e}")
                if run and run.status not in ["completed", "failed", "cancelled"]:
                    print(f"⏳ Waiting for previous run {run.id} to complete...")
                    wait_for_run_completion(self.client, thread_id, run.id)
                # Create run
                run = self.client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=self.assistant_id
                )
                logger.debug(f"Run created: {run.id}")
                # Wait for completion
                result = self._wait_for_completion(thread_id, run.id, max_wait)
                if result and "error" not in result:
                    logger.info(f"✅ {step_name} complete on attempt {attempt + 1}")
                    return result
                else:
                    error_details = result.get("error", "Unknown error") if result else "No result returned"
                    logger.warning(f"⚠️ {step_name} failed on attempt {attempt + 1}: {error_details}")
                    if result:
                        logger.debug(f"Error result details: {json.dumps(result, indent=2)}")
            except Exception as e:
                logger.warning(f"⚠️ Exception in {step_name} attempt {attempt + 1}: {type(e).__name__}: {str(e)}")
                if hasattr(e, 'response'):
                    logger.debug(f"API Response status: {getattr(e.response, 'status_code', 'Unknown')}")
                    logger.debug(f"API Response text: {getattr(e.response, 'text', 'Unknown')}")
            # Exponential backoff before retry (unless it's the last attempt)
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5  # 5, 10, 20 seconds
                logger.info(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        logger.error(f"❌ {step_name} failed after {max_retries} attempts")
        return None
    
    def _wait_for_completion(self, thread_id: str, run_id: str, max_wait: int = 120) -> Optional[dict]:
        """Wait for run completion and return parsed result with detailed error logging"""
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < max_wait:
            try:
                run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
                
                # Log status changes
                if run.status != last_status:
                    logger.debug(f"Run {run_id} status: {last_status} → {run.status}")
                    last_status = run.status
                
                if run.status == 'completed':
                    # Get latest assistant message
                    messages = self.client.beta.threads.messages.list(thread_id=thread_id, limit=1)
                    assistant_messages = [msg for msg in messages.data if msg.role == "assistant"]
                    
                    if assistant_messages:
                        response_content = assistant_messages[0].content[0].text.value
                        logger.debug(f"Assistant response length: {len(response_content)} chars")
                        result = self._extract_json_from_response(response_content)
                        
                        # Check if parsing was successful
                        if "error" in result and "Could not parse response" in result.get("error", ""):
                            logger.warning(f"JSON parsing failed. Raw response preview: {response_content[:200]}...")
                        
                        return result
                    else:
                        logger.error("No assistant response found in completed run")
                        return {"error": "No assistant response found"}
                        
                elif run.status == 'failed':
                    error_details = {
                        "status": "failed",
                        "error_code": run.last_error.code if run.last_error else "unknown",
                        "error_message": run.last_error.message if run.last_error else "Unknown error",
                        "run_id": run_id,
                        "thread_id": thread_id
                    }
                    logger.error(f"Run failed - Code: {error_details['error_code']}, Message: {error_details['error_message']}")
                    return {"error": f"Run failed: {error_details['error_message']}", "details": error_details}
                
                elif run.status == 'requires_action':
                    logger.warning(f"Run requires action: {run.required_action}")
                    return {"error": f"Run requires action: {run.required_action}"}
                
                elif run.status in ['cancelled', 'cancelling']:
                    logger.error(f"Run was cancelled: {run.status}")
                    return {"error": f"Run was cancelled: {run.status}"}
                
                elif run.status == 'expired':
                    logger.error("Run expired")
                    return {"error": "Run expired"}
                
                # Continue waiting for in_progress, queued states
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error checking run status: {type(e).__name__}: {str(e)}")
                return {"error": f"Error checking run status: {str(e)}"}
        
        logger.error(f"Timeout waiting for response after {max_wait}s")
        return {"error": f"Timeout waiting for response after {max_wait}s"}
    
    def _extract_json_from_response(self, response_text: str) -> dict:
        """Extract and parse JSON from assistant response with detailed error logging"""
        
        # First, try direct JSON parsing
        try:
            result = json.loads(response_text.strip())
            logger.debug("✅ Direct JSON parsing successful")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"Direct JSON parsing failed: {e}")
        
        # Look for JSON blocks with multiple patterns
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
        ]
        
        for i, pattern in enumerate(json_patterns):
            try:
                matches = re.findall(pattern, response_text, re.DOTALL)
                logger.debug(f"Pattern {i+1} found {len(matches)} matches")
                
                for j, match in enumerate(matches):
                    try:
                        result = json.loads(match.strip())
                        logger.debug(f"✅ JSON parsing successful with pattern {i+1}, match {j+1}")
                        return result
                    except json.JSONDecodeError as e:
                        logger.debug(f"Pattern {i+1}, match {j+1} parsing failed: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Pattern {i+1} failed: {e}")
                continue
        
        # If all parsing fails, return error with context
        logger.error("❌ All JSON parsing attempts failed")
        logger.debug(f"Response preview (first 500 chars): {response_text[:500]}")
        logger.debug(f"Response preview (last 500 chars): {response_text[-500:]}")
        
        return {
            "error": "Could not parse response as JSON",
            "raw_response": response_text[:1000] + "..." if len(response_text) > 1000 else response_text,
            "response_length": len(response_text),
            "parsing_attempts": len(json_patterns)
        }
    
    def _parse_strategic_content_enhanced(self, profile_result: dict, high_relevance_result: dict, 
                                        library_result: dict, skills_result: dict, cover_letter_result: dict,
                                        relevance_result: dict, content_strategy: dict) -> dict:
        """Parse and assemble enhanced strategic content generation results"""
        try:
            # Assemble employment bullets from all sources
            employment_bullets = {}
            
            # Strategic content (HIGH relevance)
            for company, data in high_relevance_result.get("strategic_content", {}).items():
                employment_bullets[company] = data.get("bullets", [])
            
            # Enhanced content (MEDIUM relevance)
            for company, data in library_result.get("enhanced_content", {}).get("medium_companies", {}).items():
                employment_bullets[company] = data.get("bullets", [])
            
            # Library content (LOW relevance)
            for company, data in library_result.get("library_content", {}).get("low_companies", {}).items():
                employment_bullets[company] = data.get("bullets", [])
            
            return {
                # Final content package
                "role_title": profile_result.get("role_title", "Senior Product Manager"),
                "profile_section": profile_result.get("profile_section", ""),
                "employment_bullets": employment_bullets,
                "skills_section": skills_result.get("skills_section", []),
                "cover_letter": cover_letter_result,
                
                # Strategic intelligence used
                "content_strategy_used": content_strategy,
                "company_relevance_assessment": relevance_result,
                "required_keywords": content_strategy.get("required_keywords_for_ats", []),
                "gap_bridging_strategy": content_strategy.get("gap_bridging_strategy", ""),
                
                # Content generation metadata
                "content_sources": {
                    "strategic_new": list(high_relevance_result.get("strategic_content", {}).keys()),
                    "enhanced_library": list(library_result.get("enhanced_content", {}).get("medium_companies", {}).keys()),
                    "library_unchanged": list(library_result.get("library_content", {}).get("low_companies", {}).keys())
                },
                
                # Validation results
                "authenticity_validation": skills_result.get("content_validation", {}),
                "skills_strategy": skills_result.get("skills_strategy", ""),
                "gaps_addressed": skills_result.get("gaps_addressed", []),
                
                # Generation metadata
                "total_bullets_expected": 16,
                "generation_timestamp": time.time(),
                "pipeline_version": "enhanced_with_authenticity_controls"
            }
            
        except Exception as e:
            logger.error(f"Error parsing enhanced strategic content: {e}")
            return {
                "error": f"Failed to parse enhanced strategic content: {str(e)}",
                "raw_results": {
                    "profile": profile_result,
                    "high_relevance": high_relevance_result,
                    "library": library_result,
                    "skills": skills_result,
                    "cover_letter": cover_letter_result
                },
                "content_strategy": content_strategy
            }
    
    def process_job_complete(self, job_data: dict, resume_from_checkpoint: bool = False, existing_thread_id: str = None) -> dict:
        """Complete processing: enhanced classification + strategic content generation"""
        job_title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        
        logger.info(f"🎯 Processing: {job_title} at {company}")
        
        # Step 1: Enhanced Classification with Content Strategy
        fit_analysis = self.classify_job_fit(job_data, resume_from_checkpoint=resume_from_checkpoint, existing_thread_id=existing_thread_id)
        
        if "error" in fit_analysis:
            logger.error(f"Classification failed: {fit_analysis['error']}")
            return {
                "job_data": job_data,
                "fit_analysis": fit_analysis,
                "generated_content": None,
                "status": "classification_failed"
            }
        
        score = fit_analysis.get("overall_score", 0)
        logger.info(f"📊 Classification score: {score}/10")
        
        # Step 2: Check if we should generate content
        if not self.should_generate_content(fit_analysis):
            logger.info(f"⏭️ Skipping content generation - insufficient score or recommendation")
            return {
                "job_data": job_data,
                "fit_analysis": fit_analysis,
                "generated_content": None,
                "status": "skipped_content_generation",
                "reason": f"Score {score} below threshold or recommendation skip"
            }
        
        # Step 3: Strategic Content Generation
        thread_id = fit_analysis.get("thread_id")
        if not thread_id:
            logger.error("No thread_id in fit_analysis")
            return {
                "job_data": job_data,
                "fit_analysis": fit_analysis,
                "generated_content": None,
                "status": "missing_thread_id"
            }
        
        logger.info("🎨 Generating strategic content...")
        generated_content = self.generate_content_strategic(thread_id, job_data, fit_analysis)
        
        if generated_content:
            logger.info("✅ Strategic content generation successful")
            return {
                "job_data": job_data,
                "fit_analysis": fit_analysis,
                "generated_content": generated_content,
                "status": "complete"
            }
        else:
            logger.error("Strategic content generation failed")
            return {
                "job_data": job_data,
                "fit_analysis": fit_analysis,
                "generated_content": None,
                "status": "content_generation_failed"
            }

def process_jobs_file(file_path: str, job_id: str = None, resume_from_checkpoint: bool = False, existing_thread_id: str = None) -> dict:
    """Process jobs from JSON or JSONL file with enhanced pipeline (supports both formats)"""
    pipeline = JobAIPipeline()

    input_path = Path(file_path)
    if not input_path.exists():
        return {"error": f"File not found: {input_path}"}

    logger.info(f"🔍 Processing file with enhanced pipeline: {input_path}")

    results = {
        "total_processed": 0,
        "classification_only": 0,
        "content_generated": 0,
        "skipped": 0,
        "errors": 0,
        "results": []
    }

    # Read jobs from file (support both JSON and JSONL)
    jobs = []
    try:
        with open(file_path, 'r') as f:
            first_line = f.readline().strip()
            f.seek(0)
            if first_line.startswith('{') and file_path.endswith('.json'):
                try:
                    jobs = [json.load(f)]  # Single JSON object wrapped in a list
                    logger.info("📄 Loaded single job JSON file")
                except Exception as e:
                    logger.error(f"❌ Failed to load single job JSON: {e}")
                    return {"error": f"Failed to load single job JSON: {e}"}
            else:
                jobs = []
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        jobs.append(json.loads(line))
                    except Exception as e:
                        logger.error(f"JSON decode error line {i+1}: {e}")
                        results["errors"] += 1
                        continue
    except Exception as e:
        logger.error(f"Failed to read input file: {e}")
        return {"error": f"Failed to read input file: {e}"}

    # Create temporary file for updates
    temp_file = tempfile.NamedTemporaryFile(
        mode='w',
        delete=False,
        dir=input_path.parent,
        prefix=f"{input_path.stem}_temp_",
        suffix=input_path.suffix,
        encoding='utf-8'
    )

    try:
        for idx, job_data in enumerate(jobs):
            try:
                # Filter by job ID if specified
                if job_id and job_data.get("id") != job_id:
                    temp_file.write(json.dumps(job_data, ensure_ascii=False) + "\n")
                    continue

                # Check if already processed (be more specific about complete analysis)
                existing_analysis = job_data.get("fit_analysis")
                if (existing_analysis and isinstance(existing_analysis, dict) and
                    existing_analysis.get("overall_score", 0) > 0 and
                    existing_analysis.get("content_strategy") and
                    existing_analysis.get("company_context_validation")):
                    logger.info(f"⏭️ Job {idx+1} already has enhanced fit_analysis with company validation")
                    results["skipped"] += 1
                    temp_file.write(json.dumps(job_data, ensure_ascii=False) + "\n")
                    continue

                # Process job with enhanced pipeline
                result = pipeline.process_job_complete(
                    job_data,
                    resume_from_checkpoint=resume_from_checkpoint,
                    existing_thread_id=existing_thread_id
                )

                # Update job data with results
                job_data["fit_analysis"] = result["fit_analysis"]
                job_data["fit_analysis_timestamp"] = time.time()

                if result["generated_content"]:
                    job_data["generated_content"] = result["generated_content"]
                    job_data["content_generation_timestamp"] = time.time()
                    results["content_generated"] += 1
                elif result["status"] == "skipped_content_generation":
                    results["classification_only"] += 1
                else:
                    # Still save classification even if content generation failed
                    results["classification_only"] += 1
                    logger.warning(f"Content generation failed but classification saved: {result['status']}")

                results["total_processed"] += 1
                results["results"].append(result)

                # Write updated job data
                temp_file.write(json.dumps(job_data, ensure_ascii=False) + "\n")
                temp_file.flush()

            except Exception as e:
                logger.error(f"Error processing job {idx+1}: {e}")
                results["errors"] += 1
                continue

        # Replace original file
        temp_file.close()
        backup_path = input_path.with_suffix(f"{input_path.suffix}.backup")
        shutil.copy2(input_path, backup_path)
        shutil.move(temp_file.name, input_path)

        logger.info(f"📊 Enhanced processing complete:")
        logger.info(f"   Total processed: {results['total_processed']}")
        logger.info(f"   Content generated: {results['content_generated']}")
        logger.info(f"   Classification only: {results['classification_only']}")
        logger.info(f"   Skipped: {results['skipped']}")
        logger.info(f"   Errors: {results['errors']}")

        return results

    except Exception as e:
        if hasattr(temp_file, 'name') and os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        logger.error(f"Fatal error: {e}")
        return {"error": str(e)}

def main():
    """Command line interface for enhanced pipeline"""
    parser = argparse.ArgumentParser(description="Enhanced Job AI Pipeline - Strategic Classification + Content Generation with Authenticity Controls")
    parser.add_argument("file", help="JSONL file with job data")
    parser.add_argument("--job-id", help="Process specific job ID only")
    parser.add_argument("--min-score", type=int, default=6, help="Minimum score for content generation")
    parser.add_argument("--resume-from-checkpoint", action="store_true", help="Resume from an existing thread checkpoint")
    parser.add_argument("--existing-thread-id", type=str, default=None, help="Existing thread ID to resume from")
    args = parser.parse_args()
    result = process_jobs_file(
        args.file,
        args.job_id,
        resume_from_checkpoint=args.resume_from_checkpoint,
        existing_thread_id=args.existing_thread_id
    )
    if "error" in result:
        print(f"❌ Enhanced processing failed: {result['error']}")
        exit(1)
    else:
        print(f"✅ Enhanced processing completed successfully")

if __name__ == "__main__":
    main()