 # Enhanced pipeline agent imports
from agents.job_ai_pipeline import (
    process_jobs_file,
    JobAIPipeline
)
from fastapi import FastAPI, Request, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import subprocess
import os
import json
from pathlib import Path
from fastapi.responses import JSONResponse
from api.routes.content_routes import router as content_router


# Import the classify_fit functions with proper error handling
try:
    from agents.classify_fit import classify_fit_from_file, JobAnalyzer
    CLASSIFY_FIT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Warning: Could not import classify_fit functions: {e}")
    CLASSIFY_FIT_AVAILABLE = False
    
    # Create dummy functions
    def classify_fit_from_file(file_path: str):
        return {"error": "classify_fit_from_file not available", "processed": 0}
    
    class JobAnalyzer:
        def __init__(self, file_path: str):
            self.file_path = file_path
        
        def get_summary_stats(self):
            return {"error": "JobAnalyzer not available"}

app = FastAPI()

class ScrapeRequest(BaseModel):
    urls: List[str]

class SingleTestRequest(BaseModel):
    url: str

scrape_log = {
    "last_scrape": None
}

@app.get("/status")
def status():
    return {
        "status": "ok",
        "uptime": "running",
        "last_scrape": scrape_log["last_scrape"],
        "classify_fit_available": CLASSIFY_FIT_AVAILABLE
    }

@app.post("/scrape/linkedin")
def scrape_linkedin(request: ScrapeRequest):
    scrape_log["last_scrape"] = datetime.utcnow().isoformat()
    for url in request.urls:
        subprocess.run(["python", "scraper/linkedin_scraper.py", url])
    return {"status": "success", "jobs_scraped": "triggered"}

@app.post("/test/scrape")
def test_single_scrape(request: SingleTestRequest):
    # This assumes the scraper accepts a single URL from CLI for test mode
    result = subprocess.run(["python", "scraper/linkedin_scraper.py", request.url], capture_output=True, text=True)
    return {"output": result.stdout, "error": result.stderr}

@app.get("/linkedin/results")
def get_latest_results(
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    posted_after: Optional[str] = Query(None)
):
    """
    Get the latest LinkedIn scraping results.
    Returns JSONL data as proper JSON response.
    """
    try:
        # Look for the latest symlink first
        latest_symlink = Path("data/linkedin/results/latest.jsonl")
        
        if latest_symlink.exists() and latest_symlink.is_symlink():
            filepath = latest_symlink.resolve()
        else:
            # Fallback: find the most recent JSONL file
            json_dir = Path("data/linkedin")
            if not json_dir.exists():
                raise HTTPException(status_code=404, detail="LinkedIn data directory not found")
            
            jsonl_files = list(json_dir.rglob("*.jsonl"))
            if not jsonl_files:
                raise HTTPException(status_code=404, detail="No JSONL result files found")
            
            filepath = max(jsonl_files, key=lambda f: f.stat().st_mtime)
        
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Results file not found")
        
        # Read and parse JSONL file
        data = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        parsed_line = json.loads(line)
                        data.append(parsed_line)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Invalid JSON on line {line_num}: {e}")
                        continue
        
        if not data:
            raise HTTPException(status_code=404, detail="No valid data found in results file")

        # Apply optional filters
        filtered = []
        for entry in data:
            if company and entry.get("Company", "").lower() != company.lower():
                continue
            if location and entry.get("Location", "").lower() != location.lower():
                continue
            if posted_after:
                # Expect posted_after in ISO format YYYY-MM-DD
                entry_date = entry.get("Posted Date")
                try:
                    if entry_date and entry_date < posted_after:
                        continue
                except:
                    pass
            filtered.append(entry)
        data = filtered

        return JSONResponse(content={
            "status": "success",
            "file_path": str(filepath),
            "total_records": len(data),
            "data": data
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error reading results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read results: {str(e)}")


# --- New endpoints for fetching individual LinkedIn job entries ---


@app.get("/linkedin/results/{job_id}")
def get_linkedin_result_by_id(job_id: str):
    """
    Return exactly one job entry from the latest LinkedIn results, matching the given job_id.
    """
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    if not latest_symlink.exists():
        raise HTTPException(status_code=404, detail="Latest results file not found")
    
    filepath = latest_symlink.resolve()
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("id") == job_id:
                return JSONResponse(content={"status": "success", "job": entry})
    
    raise HTTPException(status_code=404, detail=f"No job found with id={job_id}")



@app.get("/linkedin/results/latest")
def get_latest_linkedin_result():
    """
    Return the most recently added job entry from the latest LinkedIn results JSONL.
    """
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    if not latest_symlink.exists():
        raise HTTPException(status_code=404, detail="Latest results file not found")
    
    filepath = latest_symlink.resolve()
    last_entry = None
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            last_entry = entry
    
    if not last_entry:
        raise HTTPException(status_code=404, detail="No entries found in results file")
    
    return JSONResponse(content={"status": "success", "job": last_entry})


# --- Enhanced single-job process endpoint ---

@app.post("/agent/enhanced-process-single")
def run_enhanced_on_single(job: dict):
    """
    Run the full enhanced‐process pipeline on just one job record,
    returning that job’s enriched JSON immediately.
    """
    try:
        pipeline = JobAIPipeline()
        enriched = pipeline.process_single_job(job)
        return {"status": "ok", "job": enriched}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Single‐job processing failed: {e}")


@app.post("/agent/classify-fit")
def classify_fit_from_results():
    """
    Run the classify fit agent on the latest LinkedIn results.
    """
    if not CLASSIFY_FIT_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Classify fit functionality is not available. Check agent imports."
        )
    
    try:
        # Find the latest results file
        latest_symlink = Path("data/linkedin/results/latest.jsonl")
        
        if latest_symlink.exists() and latest_symlink.is_symlink():
            input_path = str(latest_symlink.resolve())
        else:
            # Fallback: find the most recent JSONL file
            json_dir = Path("data/linkedin")
            if not json_dir.exists():
                raise HTTPException(status_code=404, detail="LinkedIn data directory not found")
            
            jsonl_files = list(json_dir.rglob("*.jsonl"))
            if not jsonl_files:
                raise HTTPException(status_code=404, detail="No JSONL result files found")
            
            input_path = str(max(jsonl_files, key=lambda f: f.stat().st_mtime))
        
        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail="LinkedIn results not found")
        
        # Use the classify_fit_from_file function
        results = classify_fit_from_file(input_path)
        
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])
        
        return {"status": "completed", "results": results}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in classify fit: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.get("/agent/classify-fit/results")
def get_classify_fit_results():
    """
    Get LinkedIn results that have been processed by the classify fit agent.
    """
    try:
        # Find the latest results file
        latest_symlink = Path("data/linkedin/results/latest.jsonl")
        
        if latest_symlink.exists() and latest_symlink.is_symlink():
            input_path = str(latest_symlink.resolve())
        else:
            # Fallback: find the most recent JSONL file
            json_dir = Path("data/linkedin")
            if not json_dir.exists():
                raise HTTPException(status_code=404, detail="LinkedIn data directory not found")
            
            jsonl_files = list(json_dir.rglob("*.jsonl"))
            if not jsonl_files:
                raise HTTPException(status_code=404, detail="No JSONL result files found")
            
            input_path = str(max(jsonl_files, key=lambda f: f.stat().st_mtime))
        
        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail="LinkedIn results not found")
        
        # Read and filter for entries with fit_analysis
        data = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        parsed_line = json.loads(line)
                        # Check for fit_analysis field
                        if "fit_analysis" in parsed_line:
                            data.append(parsed_line)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Invalid JSON on line {line_num}: {e}")
                        continue
        
        return JSONResponse(content={
            "status": "success",
            "total_classified": len(data),
            "results": data
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error reading classify fit results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read results: {str(e)}")

@app.get("/agent/classify-fit/summary")
def get_classification_summary():
    """
    Get a summary of classification results with statistics.
    """
    if not CLASSIFY_FIT_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Classify fit functionality is not available"
        )
    
    try:
        # Find the latest results file
        latest_symlink = Path("data/linkedin/results/latest.jsonl")
        
        if latest_symlink.exists() and latest_symlink.is_symlink():
            input_path = str(latest_symlink.resolve())
        else:
            # Fallback: find the most recent JSONL file
            json_dir = Path("data/linkedin")
            if not json_dir.exists():
                raise HTTPException(status_code=404, detail="LinkedIn data directory not found")
            
            jsonl_files = list(json_dir.rglob("*.jsonl"))
            if not jsonl_files:
                raise HTTPException(status_code=404, detail="No JSONL result files found")
            
            input_path = str(max(jsonl_files, key=lambda f: f.stat().st_mtime))
        
        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail="LinkedIn results not found")
        
        # Use JobAnalyzer to get summary stats
        analyzer = JobAnalyzer(input_path)
        stats = analyzer.get_summary_stats()
        
        if "error" in stats:
            raise HTTPException(status_code=404, detail=stats["error"])
        
        return JSONResponse(content={
            "status": "success",
            "file_path": input_path,
            "summary": stats
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

@app.get("/agent/classify-fit/top-opportunities")
def get_top_opportunities(limit: int = 10):
    """
    Get top job opportunities based on combined score and probability.
    """
    if not CLASSIFY_FIT_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Classify fit functionality is not available"
        )
    
    try:
        # Find the latest results file
        latest_symlink = Path("data/linkedin/results/latest.jsonl")
        
        if latest_symlink.exists() and latest_symlink.is_symlink():
            input_path = str(latest_symlink.resolve())
        else:
            # Fallback: find the most recent JSONL file
            json_dir = Path("data/linkedin")
            if not json_dir.exists():
                raise HTTPException(status_code=404, detail="LinkedIn data directory not found")
            
            jsonl_files = list(json_dir.rglob("*.jsonl"))
            if not jsonl_files:
                raise HTTPException(status_code=404, detail="No JSONL result files found")
            
            input_path = str(max(jsonl_files, key=lambda f: f.stat().st_mtime))
        
        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail="LinkedIn results not found")
        
        # Use JobAnalyzer to get top opportunities
        analyzer = JobAnalyzer(input_path)
        top_jobs = analyzer.get_top_opportunities(limit)
        
        return JSONResponse(content={
            "status": "success",
            "file_path": input_path,
            "limit": limit,
            "total_top_jobs": len(top_jobs),
            "top_opportunities": top_jobs
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting top opportunities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get top opportunities: {str(e)}")

# --- Enhanced pipeline endpoints ---

@app.post("/agent/enhanced-fit")
def run_enhanced_fit():
    """
    Run enhanced fit analysis on latest job scrape file.
    """
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    if not latest_symlink.exists():
        raise HTTPException(status_code=404, detail="Latest results file not found")
    try:
        path = str(latest_symlink.resolve())
        result = process_jobs_file(path)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enhanced fit failed: {str(e)}")


@app.post("/agent/enhanced-process")
def run_enhanced_process():
    """
    Run enhanced job processing with resume generation on each entry.
    """
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    if not latest_symlink.exists():
        raise HTTPException(status_code=404, detail="Latest results file not found")
    try:
        path = str(latest_symlink.resolve())
        print(f"[DEBUG] Enhanced processing started. Using file: {path}")
        result = process_jobs_file(path)
        print(f"[DEBUG] Enhanced processing completed. Result summary: {result}")
        return {"status": "ok", "result": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Enhanced processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Enhanced processing failed: {str(e)}")


@app.post("/agent/enhanced-process-file")
def run_enhanced_process_file():
    """
    Process all jobs in a given file using the full enhanced pipeline.
    """
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    if not latest_symlink.exists():
        raise HTTPException(status_code=404, detail="Latest results file not found")
    try:
        path = str(latest_symlink.resolve())
        result = process_jobs_file(path)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enhanced file processing failed: {str(e)}")


# New endpoint: /agent/processed-jobs
@app.get("/agent/processed-jobs")
def get_processed_jobs():
    """
    Return only jobs that have full analysis + docs:
      • resume_link must exist
      • cover_letter_link must exist
      • Score (or another core analysis key) must exist
    """
    latest_symlink = Path("data/linkedin/results/latest.jsonl")
    if not latest_symlink.exists():
        raise HTTPException(status_code=404, detail="No results file found")
    filepath = latest_symlink.resolve()

    processed = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Define “fully processed”–check for required keys:
            has_resume = bool(entry.get("resume_link"))
            has_cover  = bool(entry.get("cover_letter_link"))
            has_score  = entry.get("Score") is not None
            if has_resume and has_cover and has_score:
                processed.append(entry)

    if not processed:
        raise HTTPException(status_code=404, detail="No fully processed jobs found")

    return JSONResponse({
        "status": "success",
        "total_processed": len(processed),
        "jobs": processed
    })

# Debug endpoints
@app.get("/debug/imports")
def debug_imports():
    """Debug endpoint to check import status"""
    import_status = {}
    
    # Check classify_fit imports
    try:
        from agents.classify_fit import classify_fit_from_file
        import_status["classify_fit_from_file"] = "available"
    except ImportError as e:
        import_status["classify_fit_from_file"] = f"error: {str(e)}"
    
    try:
        from agents.classify_fit import JobAnalyzer
        import_status["JobAnalyzer"] = "available"
    except ImportError as e:
        import_status["JobAnalyzer"] = f"error: {str(e)}"
    
    # Check if agents directory exists
    agents_dir = Path("agents")
    import_status["agents_directory_exists"] = agents_dir.exists()
    
    if agents_dir.exists():
        import_status["agents_files"] = [f.name for f in agents_dir.iterdir() if f.is_file()]
    
    import_status["classify_fit_available"] = CLASSIFY_FIT_AVAILABLE
    
    return import_status

@app.get("/debug/file-structure")
def debug_file_structure():
    """Debug endpoint to check file structure"""
    base_dir = Path("data/linkedin")
    
    if not base_dir.exists():
        return {"error": "data/linkedin directory does not exist"}
    
    files = []
    for file_path in base_dir.rglob("*"):
        if file_path.is_file():
            files.append({
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime,
                "is_symlink": file_path.is_symlink()
            })
    
    return {
        "base_directory": str(base_dir),
        "total_files": len(files),
        "files": sorted(files, key=lambda x: x["modified"], reverse=True)[:20]  # Show latest 20
    }

app.include_router(content_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)