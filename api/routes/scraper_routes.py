from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
from scraper import linkedin_scraper
from scraper.linkedin_scraper import run_linkedin_scraper_batch
from fastapi.responses import JSONResponse
from pathlib import Path
import os
import httpx
import json

router = APIRouter()

class ScrapeRequest(BaseModel):
    urls: list[str]

@router.post("/linkedin/scrape")
async def linkedin_scrape_endpoint(payload: ScrapeRequest):
    try:
        linkedin_scraper.scrape_jobs.override_urls = payload.urls  # Inject override
        results = await run_linkedin_scraper_batch(payload.urls)

        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            async with httpx.AsyncClient() as client:
                for result in results:
                    await client.post(webhook_url, json=result)

        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/linkedin/results")
async def get_scraped_results(
    filename: str = Query(None, description="Optional: Filename of the JSONL file to retrieve from data/linkedin directory")
):
    """
    Retrieve LinkedIn scraping results from JSONL files.
    Returns the latest file if no filename is specified.
    """
    try:
        # Define the base directory for LinkedIn results
        json_dir = Path("data/linkedin")
        
        if not json_dir.exists():
            raise HTTPException(status_code=404, detail="LinkedIn data directory not found")

        if filename:
            # Look for specific file in any subdirectory
            filepath = None
            for jsonl_file in json_dir.rglob(filename):
                if jsonl_file.is_file():
                    filepath = jsonl_file
                    break
            
            if not filepath:
                raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
        else:
            # Find the most recent JSONL file across all subdirectories
            jsonl_files = list(json_dir.rglob("*.jsonl"))
            if not jsonl_files:
                raise HTTPException(status_code=404, detail="No JSONL result files found")
            
            # Sort by modification time, most recent first
            filepath = max(jsonl_files, key=lambda f: f.stat().st_mtime)

        # Read and parse the JSONL file
        data = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        parsed_line = json.loads(line)
                        data.append(parsed_line)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Invalid JSON on line {line_num} in {filepath}: {e}")
                        continue
        
        if not data:
            raise HTTPException(status_code=404, detail="No valid data found in the results file")

        return JSONResponse(content={
            "status": "success",
            "file_path": str(filepath),
            "total_records": len(data),
            "data": data
        })
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error reading results file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read results file: {str(e)}")