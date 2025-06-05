from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from pathlib import Path
import json
import logging

# Import the Enhanced Content Generator
try:
    from agents.content_generator import EnhancedContentGenerator
    CONTENT_GENERATOR_AVAILABLE = True
except ImportError as e:
    logging.error(f"Failed to import EnhancedContentGenerator: {e}")
    CONTENT_GENERATOR_AVAILABLE = False
    
    # Dummy class for when import fails
    class EnhancedContentGenerator:
        def __init__(self):
            pass
        def generate_resume(self, job_data):
            return None
        def generate_cover_letter(self, job_data):
            return None
        def generate_both(self, job_data):
            return {"resume": None, "cover_letter": None, "status": "failed"}

router = APIRouter(prefix="/content", tags=["content-generation"])

class GenerateContentRequest(BaseModel):
    job_id: Optional[str] = None
    job_data: Optional[Dict[str, Any]] = None
    document_type: str = "both"  # "resume", "cover_letter", or "both"

class BatchGenerateRequest(BaseModel):
    file_path: Optional[str] = None
    job_ids: Optional[List[str]] = None
    document_type: str = "both"
    max_jobs: Optional[int] = 10

@router.get("/status")
async def content_generator_status():
    """Check if content generator is available and working"""
    return {
        "available": CONTENT_GENERATOR_AVAILABLE,
        "templates": {
            "resume": Path("resume-template-annotated.html").exists(),
            "cover_letter": Path("cover-letter-template-annotated.html").exists()
        },
        "output_directory": str(Path("data/resumes")),
        "weasyprint_available": CONTENT_GENERATOR_AVAILABLE
    }

@router.post("/generate")
async def generate_content(request: GenerateContentRequest):
    """Generate resume and/or cover letter for a single job"""
    if not CONTENT_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="Content generator not available")
    
    try:
        generator = EnhancedContentGenerator()
        
        # Get job data from request or load from file
        if request.job_data:
            job_data = request.job_data
        elif request.job_id:
            # Load from latest results file
            job_data = await load_job_by_id(request.job_id)
            if not job_data:
                raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        else:
            raise HTTPException(status_code=400, detail="Either job_data or job_id must be provided")
        
        # Check if job has generated content
        if "generated_content" not in job_data:
            raise HTTPException(
                status_code=400, 
                detail="Job does not have generated_content. Run enhanced-fit analysis first."
            )
        
        # Generate documents based on type
        if request.document_type == "resume":
            result_path = generator.generate_resume(job_data)
            result = {
                "status": "success" if result_path else "failed",
                "resume": str(result_path) if result_path else None,
                "cover_letter": None
            }
            return {
                "status": "success",
                "input": job_data,
                "job_id": job_data.get("id"),
                "job_title": job_data.get("title"),
                "company": job_data.get("company"),
                "documents": result
            }
        elif request.document_type == "cover_letter":
            result_path = generator.generate_cover_letter(job_data)
            result = {
                "status": "success" if result_path else "failed",
                "resume": None,
                "cover_letter": str(result_path) if result_path else None
            }
            return {
                "status": "success",
                "input": job_data,
                "job_id": job_data.get("id"),
                "job_title": job_data.get("title"),
                "company": job_data.get("company"),
                "documents": result
            }
        else:  # both
            results = generator.generate_both(job_data)
            result = results
            return {
                "status": "success",
                "input": job_data,
                "job_id": job_data.get("id"),
                "job_title": job_data.get("title"),
                "company": job_data.get("company"),
                "documents": result
            }
        
    except Exception as e:
        logging.error(f"Content generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/batch")
async def generate_batch(request: BatchGenerateRequest):
    """Generate documents for multiple jobs"""
    if not CONTENT_GENERATOR_AVAILABLE:
        raise HTTPException(status_code=503, detail="Content generator not available")
    
    try:
        generator = EnhancedContentGenerator()
        
        # Load jobs from file
        if request.file_path:
            file_path = Path(request.file_path)
        else:
            file_path = find_latest_linkedin_file()
        
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="No jobs file found")
        
        results = []
        processed = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if processed >= (request.max_jobs or 10):
                    break
                    
                line = line.strip()
                if not line:
                    continue
                
                try:
                    job_data = json.loads(line)
                    
                    # Filter by job IDs if provided
                    if request.job_ids and job_data.get("id") not in request.job_ids:
                        continue
                    
                    # Skip if no generated content
                    if "generated_content" not in job_data:
                        continue
                    
                    # Generate documents
                    if request.document_type == "both":
                        result = generator.generate_both(job_data)
                    elif request.document_type == "resume":
                        path = generator.generate_resume(job_data)
                        result = {"resume": str(path) if path else None, "status": "success" if path else "failed"}
                    else:
                        path = generator.generate_cover_letter(job_data)
                        result = {"cover_letter": str(path) if path else None, "status": "success" if path else "failed"}
                    
                    results.append({
                        "job_id": job_data.get("id"),
                        "job_title": job_data.get("title"),
                        "company": job_data.get("company"),
                        "result": result
                    })
                    processed += 1
                    
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logging.error(f"Error processing job: {e}")
                    continue
        
        return {
            "status": "completed",
            "total_processed": processed,
            "results": results
        }
        
    except Exception as e:
        logging.error(f"Batch generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents")
async def list_generated_documents(
    limit: int = 50,
    job_id: Optional[str] = None,
    company: Optional[str] = None
):
    """List generated documents"""
    try:
        resume_dir = Path("data/resumes")
        if not resume_dir.exists():
            return {"documents": [], "total": 0}
        
        documents = []
        for file_path in resume_dir.glob("*.pdf"):
            # Parse filename to extract info
            file_info = {
                "filename": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "created": file_path.stat().st_mtime,
                "type": "cover_letter" if "cover_letter" in file_path.name else "resume"
            }
            
            # Filter by criteria
            if job_id and job_id not in file_path.name:
                continue
            if company and company.lower() not in file_path.name.lower():
                continue
            
            documents.append(file_info)
        
        # Sort by creation time, newest first
        documents.sort(key=lambda x: x["created"], reverse=True)
        
        return {
            "documents": documents[:limit],
            "total": len(documents),
            "directory": str(resume_dir)
        }
        
    except Exception as e:
        logging.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate")
async def validate_content(request: GenerateContentRequest):
    """Validate that a job has all required content for document generation"""
    try:
        # Get job data
        if request.job_data:
            job_data = request.job_data
        elif request.job_id:
            job_data = await load_job_by_id(request.job_id)
            if not job_data:
                raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        else:
            raise HTTPException(status_code=400, detail="Either job_data or job_id must be provided")
        
        # Validate required fields
        validation = {
            "has_generated_content": "generated_content" in job_data,
            "has_fit_analysis": "fit_analysis" in job_data,
            "has_job_details": all(key in job_data for key in ["title", "company", "description"]),
            "ready_for_generation": False
        }
        
        if validation["has_generated_content"]:
            content = job_data["generated_content"]
            validation.update({
                "has_role_title": "role_title" in content,
                "has_profile": "profile_section" in content,
                "has_employment_bullets": "employment_bullets" in content and len(content["employment_bullets"]) > 0,
                "has_skills": "skills_section" in content and len(content.get("skills_section", [])) > 0,
                "has_cover_letter": "cover_letter" in content
            })
            
            # Check if ready for generation
            validation["ready_for_generation"] = all([
                validation["has_role_title"],
                validation["has_profile"],
                validation["has_employment_bullets"],
                validation["has_skills"]
            ])
        
        return {
            "job_id": job_data.get("id"),
            "validation": validation,
            "message": "Ready for document generation" if validation["ready_for_generation"] else "Missing required content"
        }
        
    except Exception as e:
        logging.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def load_job_by_id(job_id: str) -> Optional[Dict]:
    """Load a specific job by ID from the latest results file"""
    file_path = find_latest_linkedin_file()
    if not file_path or not file_path.exists():
        return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                job_data = json.loads(line)
                if job_data.get("id") == job_id:
                    return job_data
            except json.JSONDecodeError:
                continue
    return None

def find_latest_linkedin_file() -> Optional[Path]:
    """Find the most recent LinkedIn JSONL file"""
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    if latest_symlink.exists() and latest_symlink.is_symlink():
        return latest_symlink.resolve()
    
    json_dir = Path("data/linkedin")
    if not json_dir.exists():
        return None
    
    jsonl_files = list(json_dir.rglob("*.jsonl"))
    if not jsonl_files:
        return None
    
    return max(jsonl_files, key=lambda f: f.stat().st_mtime)