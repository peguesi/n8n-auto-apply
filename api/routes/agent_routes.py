from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
from pathlib import Path

# Enhanced job AI pipeline imports
from agents.job_ai_pipeline import (
    JobAIPipeline,
    process_jobs_file,
)

# Import the classify_fit functions with fallback options
try:
    from agents.classify_fit import classify_fit_from_file, classify_job_fit, JobAnalyzer
    CLASSIFY_FUNCTIONS_AVAILABLE = True
    CLASSIFY_FUNCTION_TYPE = "both"
except ImportError:
    try:
        from agents.classify_fit import classify_fit_from_file, JobAnalyzer
        CLASSIFY_FUNCTIONS_AVAILABLE = True
        CLASSIFY_FUNCTION_TYPE = "file_only"
        
        # Create dummy classify_job_fit
        def classify_job_fit(job_data):
            return {"error": "classify_job_fit not available, use file-based classification"}
    except ImportError:
        try:
            from agents.classify_fit import JobAnalyzer
            CLASSIFY_FUNCTIONS_AVAILABLE = False
            CLASSIFY_FUNCTION_TYPE = "analysis_only"
            
            # Create dummy functions
            def classify_fit_from_file(file_path: str):
                return {"error": "Classification functions not available", "processed": 0}
            
            def classify_job_fit(job_data):
                return {"error": "Classification functions not available"}
        except ImportError:
            CLASSIFY_FUNCTIONS_AVAILABLE = False
            CLASSIFY_FUNCTION_TYPE = "none"
            
            # Create all dummy functions
            def classify_fit_from_file(file_path: str):
                return {"error": "classify_fit module not available", "processed": 0}
            
            def classify_job_fit(job_data):
                return {"error": "classify_fit module not available"}
            
            class JobAnalyzer:
                def __init__(self, file_path: str):
                    self.file_path = file_path
                
                def get_summary_stats(self):
                    return {"error": "JobAnalyzer not available"}

# Import utils with fallback
try:
    from utils import load_jsonl
    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False
    # Create fallback function
    def load_jsonl(file_path):
        """Fallback JSONL loader if utils not available"""
        jobs = []
        with open(file_path, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        jobs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return jobs

router = APIRouter()

class ClassifyFitRequest(BaseModel):
    file_path: Optional[str] = None  # Optional, will auto-detect if not provided

class FilterJobsRequest(BaseModel):
    file_path: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    min_probability: Optional[int] = None
    recommendations: Optional[List[str]] = None
    companies: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    limit: Optional[int] = 10

def find_latest_linkedin_file():
    """Find the most recent LinkedIn JSONL file"""
    # Check for symlink first
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    if latest_symlink.exists() and latest_symlink.is_symlink():
        return latest_symlink.resolve()
    
    # Fallback to most recent file
    json_dir = Path("data/linkedin")
    if not json_dir.exists():
        return None
    
    jsonl_files = list(json_dir.rglob("*.jsonl"))
    if not jsonl_files:
        return None
    
    return max(jsonl_files, key=lambda f: f.stat().st_mtime)

@router.post("/agent/classify-fit")
async def classify_fit_handler(request: ClassifyFitRequest):
    """
    Run fit classification on LinkedIn job data.
    If no file_path provided, uses the latest LinkedIn results file.
    """
    if not CLASSIFY_FUNCTIONS_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Classify fit functionality not available. Check imports."
        )
    
    # Determine file path
    if request.file_path:
        file_path = Path(request.file_path)
    else:
        file_path = find_latest_linkedin_file()
        if not file_path:
            raise HTTPException(
                status_code=404, 
                detail="No LinkedIn results file found. Provide explicit file_path or ensure data exists."
            )
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    try:
        # Use the file-based classification function
        result = classify_fit_from_file(str(file_path))
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "status": "completed", 
            "file_processed": str(file_path), 
            "results": result,
            "function_type": CLASSIFY_FUNCTION_TYPE
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Classification failed: {str(e)}"
        )

@router.get("/agent/classify-fit/results")
async def get_classify_fit_results(file_path: Optional[str] = None):
    """
    Get LinkedIn results that have been processed by the classify fit agent.
    If no file_path provided, uses the latest LinkedIn results file.
    """
    # Determine file path
    if file_path:
        full_path = Path(file_path)
    else:
        full_path = find_latest_linkedin_file()
        if not full_path:
            raise HTTPException(
                status_code=404, 
                detail="No LinkedIn results file found. Provide explicit file_path or ensure data exists."
            )
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {full_path}")
    
    try:
        matched_jobs = []
        
        for job_data in load_jsonl(full_path):
            # Check for both possible field names
            if "fit_analysis" in job_data:
                matched_jobs.append(job_data)
        
        return {
            "status": "success",
            "file_path": str(full_path),
            "total_classified": len(matched_jobs),
            "results": matched_jobs
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to read results: {str(e)}"
        )

@router.get("/agent/classify-fit/summary")
async def get_classification_summary(file_path: Optional[str] = None):
    """
    Get a summary of classification results with statistics.
    """
    # Determine file path
    if file_path:
        full_path = Path(file_path)
    else:
        full_path = find_latest_linkedin_file()
        if not full_path:
            raise HTTPException(
                status_code=404, 
                detail="No LinkedIn results file found"
            )
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {full_path}")
    
    try:
        # Use JobAnalyzer to get summary stats
        analyzer = JobAnalyzer(str(full_path))
        stats = analyzer.get_summary_stats()
        
        if "error" in stats:
            raise HTTPException(status_code=404, detail=stats["error"])
        
        return {
            "status": "success",
            "file_path": str(full_path),
            "summary": stats
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate summary: {str(e)}"
        )

@router.post("/agent/classify-fit/filter")
async def filter_classified_jobs(request: FilterJobsRequest):
    """
    Filter classified jobs based on various criteria.
    """
    # Determine file path
    if request.file_path:
        file_path = Path(request.file_path)
    else:
        file_path = find_latest_linkedin_file()
        if not file_path:
            raise HTTPException(
                status_code=404, 
                detail="No LinkedIn results file found"
            )
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    try:
        # Use JobAnalyzer to filter jobs
        analyzer = JobAnalyzer(str(file_path))
        filtered_jobs = analyzer.filter_jobs(
            min_score=request.min_score,
            max_score=request.max_score,
            min_probability=request.min_probability,
            recommendations=request.recommendations,
            companies=request.companies,
            keywords=request.keywords
        )
        
        # Apply limit
        if request.limit:
            filtered_jobs = filtered_jobs[:request.limit]
        
        return {
            "status": "success",
            "file_path": str(file_path),
            "filters_applied": {
                "min_score": request.min_score,
                "max_score": request.max_score,
                "min_probability": request.min_probability,
                "recommendations": request.recommendations,
                "companies": request.companies,
                "keywords": request.keywords,
                "limit": request.limit
            },
            "total_filtered": len(filtered_jobs),
            "results": filtered_jobs
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to filter jobs: {str(e)}"
        )

@router.get("/agent/classify-fit/top-opportunities")
async def get_top_opportunities(file_path: Optional[str] = None, limit: int = 10):
    """
    Get top job opportunities based on combined score and probability.
    """
    # Determine file path
    if file_path:
        full_path = Path(file_path)
    else:
        full_path = find_latest_linkedin_file()
        if not full_path:
            raise HTTPException(
                status_code=404, 
                detail="No LinkedIn results file found"
            )
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {full_path}")
    
    try:
        # Use JobAnalyzer to get top opportunities
        analyzer = JobAnalyzer(str(full_path))
        top_jobs = analyzer.get_top_opportunities(limit)
        
        return {
            "status": "success",
            "file_path": str(full_path),
            "limit": limit,
            "total_top_jobs": len(top_jobs),
            "top_opportunities": top_jobs
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get top opportunities: {str(e)}"
        )

@router.post("/agent/classify-fit/single")
async def classify_single_job(request: Request):
    """
    Classify a single job provided in the request body.
    Useful for testing or real-time classification.
    """
    if CLASSIFY_FUNCTION_TYPE not in ["both", "single_only"]:
        raise HTTPException(
            status_code=503, 
            detail="Single job classification not available with current configuration"
        )
    
    try:
        job_data = await request.json()
        
        result = classify_job_fit(job_data)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "status": "success",
            "job_title": job_data.get("title", "Unknown"),
            "job_company": job_data.get("company", "Unknown"),
            "classification_result": result
        }
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Classification failed: {str(e)}"
        )


# --- Enhanced Job AI Pipeline endpoints ---

@router.post("/agent/enhanced-fit")
async def enhanced_fit_handler(request: Request):
    """
    Analyze job fit and strategic profile match using enhanced pipeline (no resume gen).
    """
    try:
        job_data = await request.json()
        pipeline = JobAIPipeline()
        result = pipeline.classify_job_fit(job_data)
        return {
            "status": "success",
            "job_id": job_data.get("id"),
            "job_title": job_data.get("title"),
            "company": job_data.get("company"),
            "fit_analysis": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enhanced fit analysis failed: {str(e)}")


@router.post("/agent/enhanced-content")
async def enhanced_content_handler(request: Request):
    """
    Generate strategic resume content for a job using an existing thread + fit analysis.
    """
    try:
        data = await request.json()
        job = data.get("job")
        thread_id = data.get("thread_id")
        fit_analysis = data.get("fit_analysis")
        
        if not all([job, thread_id, fit_analysis]):
            raise HTTPException(status_code=400, detail="Missing required fields: job, thread_id, fit_analysis")

        pipeline = JobAIPipeline()
        content = pipeline.generate_content_strategic(thread_id, job, fit_analysis)
        return {
            "status": "success",
            "job_id": job.get("id"),
            "generated_content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enhanced content generation failed: {str(e)}")


@router.post("/agent/enhanced-process")
async def enhanced_process_handler(request: Request):
    """
    Run the full job AI pipeline (fit analysis + content generation).
    """
    import traceback
    from fastapi.responses import JSONResponse

    try:
        job_data = await request.json()
        print(f"[DEBUG] Received job data: {json.dumps(job_data, indent=2)}")

        pipeline = JobAIPipeline()
        result = pipeline.process_job_complete(job_data)

        print(f"[DEBUG] Process result for job {job_data.get('id')}: {json.dumps(result, indent=2)}")

        return {
            "status": "success",
            "job_id": job_data.get("id"),
            "full_analysis": result
        }
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] Enhanced process failed: {str(e)}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": tb}
        )


@router.post("/agent/enhanced-process-file")
async def enhanced_process_file_handler(request: ClassifyFitRequest):
    """
    Run the enhanced pipeline on a full JSONL file of jobs.
    """
    try:
        from agents.job_ai_pipeline import process_file_pipeline
        file_path = request.file_path or find_latest_linkedin_file()
        if not file_path or not Path(file_path).exists():
            raise HTTPException(status_code=404, detail="No valid file path provided or file not found")
        
        result = process_file_pipeline(str(file_path))
        return {
            "status": "success",
            "file_processed": str(file_path),
            "result_summary": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@router.get("/agent/classify-fit/export")
async def export_classified_jobs(
    file_path: Optional[str] = None, 
    format: str = "csv",
    include_analysis: bool = True
):
    """
    Export classified jobs to CSV or other formats.
    """
    if format not in ["csv"]:
        raise HTTPException(status_code=400, detail="Only CSV format is currently supported")
    
    # Determine file path
    if file_path:
        full_path = Path(file_path)
    else:
        full_path = find_latest_linkedin_file()
        if not full_path:
            raise HTTPException(
                status_code=404, 
                detail="No LinkedIn results file found"
            )
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {full_path}")
    
    try:
        # Use JobAnalyzer to export data
        analyzer = JobAnalyzer(str(full_path))
        
        # Create output filename
        output_path = full_path.with_suffix('.csv')
        
        df = analyzer.export_to_csv(
            output_path=str(output_path),
            include_analysis=include_analysis
        )
        
        return {
            "status": "success",
            "file_path": str(full_path),
            "export_path": str(output_path),
            "format": format,
            "total_records": len(df),
            "include_analysis": include_analysis
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to export data: {str(e)}"
        )

@router.get("/agent/classify-fit/status")
async def get_classification_status():
    """
    Get the status of the classification system.
    """
    latest_file = find_latest_linkedin_file()
    
    status_info = {
        "classify_functions_available": CLASSIFY_FUNCTIONS_AVAILABLE,
        "function_type": CLASSIFY_FUNCTION_TYPE,
        "utils_available": UTILS_AVAILABLE,
        "latest_file": str(latest_file) if latest_file else None,
        "latest_file_exists": latest_file.exists() if latest_file else False
    }
    
    # If we have a file, get some basic stats
    if latest_file and latest_file.exists():
        try:
            total_jobs = 0
            classified_jobs = 0
            
            for job_data in load_jsonl(latest_file):
                total_jobs += 1
                if "fit_analysis" in job_data:
                    classified_jobs += 1
            
            status_info.update({
                "total_jobs": total_jobs,
                "classified_jobs": classified_jobs,
                "classification_rate": f"{(classified_jobs/max(total_jobs,1)*100):.1f}%" if total_jobs > 0 else "0%"
            })
        except Exception as e:
            status_info["file_read_error"] = str(e)
    
    # List available operations based on what's imported
    operations = ["status"]
    
    if CLASSIFY_FUNCTIONS_AVAILABLE:
        operations.extend(["classify-fit", "results", "summary", "filter", "top-opportunities", "export"])
    
    if CLASSIFY_FUNCTION_TYPE in ["both"]:
        operations.append("single")
    
    status_info["available_operations"] = operations
    
    return status_info

# Additional utility endpoints
@router.get("/agent/classify-fit/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "classify-fit-agent",
        "functions_available": CLASSIFY_FUNCTIONS_AVAILABLE,
        "function_type": CLASSIFY_FUNCTION_TYPE
    }

@router.get("/agent/classify-fit/files")
async def list_available_files():
    """
    List all available JSONL files in the LinkedIn data directory.
    """
    json_dir = Path("data/linkedin")
    
    if not json_dir.exists():
        raise HTTPException(status_code=404, detail="LinkedIn data directory not found")
    
    files = []
    for file_path in json_dir.rglob("*.jsonl"):
        if file_path.is_file():
            try:
                # Count jobs in file
                job_count = 0
                classified_count = 0
                
                with open(file_path, "r", encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                job_data = json.loads(line)
                                job_count += 1
                                if "fit_analysis" in job_data:
                                    classified_count += 1
                            except json.JSONDecodeError:
                                continue
                
                files.append({
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                    "job_count": job_count,
                    "classified_count": classified_count,
                    "classification_rate": f"{(classified_count/max(job_count,1)*100):.1f}%" if job_count > 0 else "0%"
                })
            except Exception as e:
                files.append({
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                    "error": str(e)
                })
    
    # Sort by modification time, most recent first
    files.sort(key=lambda x: x.get("modified", 0), reverse=True)
    
    return {
        "status": "success",
        "base_directory": str(json_dir),
        "total_files": len(files),
        "files": files
    }

@router.delete("/agent/classify-fit/clear-analysis")
async def clear_analysis_data(file_path: Optional[str] = None, confirm: bool = False):
    """
    Clear fit_analysis data from a JSONL file (for reprocessing).
    Requires confirmation parameter to prevent accidental data loss.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="This operation requires confirmation. Add ?confirm=true to proceed."
        )
    
    # Determine file path
    if file_path:
        full_path = Path(file_path)
    else:
        full_path = find_latest_linkedin_file()
        if not full_path:
            raise HTTPException(
                status_code=404, 
                detail="No LinkedIn results file found"
            )
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {full_path}")
    
    try:
        # Read all jobs and remove fit_analysis fields
        cleaned_jobs = []
        removed_count = 0
        
        with open(full_path, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        job_data = json.loads(line)
                        
                        # Remove analysis fields if they exist
                        if "fit_analysis" in job_data:
                            del job_data["fit_analysis"]
                            removed_count += 1
                        
                        if "fit_analysis_timestamp" in job_data:
                            del job_data["fit_analysis_timestamp"]
                        
                        if "overall_score" in job_data:
                            del job_data["overall_score"]
                        
                        if "recommendation" in job_data:
                            del job_data["recommendation"]
                        
                        if "interview_probability" in job_data:
                            del job_data["interview_probability"]
                        
                        cleaned_jobs.append(job_data)
                        
                    except json.JSONDecodeError:
                        continue
        
        # Create backup before writing
        backup_path = full_path.with_suffix(f"{full_path.suffix}.pre_clear_backup")
        import shutil
        shutil.copy2(full_path, backup_path)
        
        # Write cleaned data back
        with open(full_path, "w", encoding='utf-8') as f:
            for job in cleaned_jobs:
                f.write(json.dumps(job, ensure_ascii=False) + "\n")
        
        return {
            "status": "success",
            "file_path": str(full_path),
            "backup_path": str(backup_path),
            "total_jobs": len(cleaned_jobs),
            "analysis_records_removed": removed_count,
            "message": "Analysis data cleared. File is ready for reprocessing."
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to clear analysis data: {str(e)}"
        )

# Add these endpoints to agent_routes.py

@router.get("/agent/enhanced-pipeline/jobs-ready")
async def get_jobs_ready_for_generation(file_path: Optional[str] = None, limit: int = 20):
    """Get jobs that have fit analysis and are ready for content generation"""
    if file_path:
        full_path = Path(file_path)
    else:
        full_path = find_latest_linkedin_file()
        if not full_path:
            raise HTTPException(status_code=404, detail="No LinkedIn results file found")
    
    try:
        ready_jobs = []
        with open(full_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    job_data = json.loads(line)
                    if "fit_analysis" in job_data and "generated_content" in job_data:
                        # Check if score meets threshold
                        score = job_data["fit_analysis"].get("overall_score", 0)
                        if score >= 6:
                            ready_jobs.append({
                                "id": job_data.get("id"),
                                "title": job_data.get("title"),
                                "company": job_data.get("company"),
                                "score": score,
                                "has_content": True,
                                "has_documents": False  # Would need to check filesystem
                            })
                except json.JSONDecodeError:
                    continue
        
        # Sort by score
        ready_jobs.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "status": "success",
            "total_ready": len(ready_jobs),
            "jobs": ready_jobs[:limit]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/enhanced-pipeline/full")
async def run_full_pipeline(request: Request):
    """Run the complete pipeline: scrape -> classify -> generate content -> create documents"""
    try:
        data = await request.json()
        job_data = data.get("job_data")
        generate_documents = data.get("generate_documents", True)
        
        if not job_data:
            raise HTTPException(status_code=400, detail="job_data required")
        
        # Step 1: Run enhanced pipeline
        pipeline = JobAIPipeline()
        result = pipeline.process_job_complete(job_data)
        
        response = {
            "job_id": job_data.get("id"),
            "pipeline_result": result,
            "documents": None
        }
        
        # Step 2: Generate documents if requested and content was generated
        if generate_documents and result.get("generated_content"):
            try:
                from agents.content_generator import EnhancedContentGenerator
                generator = EnhancedContentGenerator()
                
                # Add generated content to job data
                job_data["generated_content"] = result["generated_content"]
                job_data["fit_analysis"] = result["fit_analysis"]
                
                # Generate both documents
                doc_results = generator.generate_both(job_data)
                response["documents"] = doc_results
            except Exception as e:
                response["documents"] = {"error": str(e), "status": "failed"}
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))