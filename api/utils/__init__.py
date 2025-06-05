"""
Utility functions for handling JSONL files and job data processing.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Generator
import time

def load_jsonl(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """
    Load and yield job data from a JSONL file.
    
    Args:
        file_path (Path): Path to the JSONL file
        
    Yields:
        Dict[str, Any]: Job data dictionaries
    """
    if not file_path.exists():
        raise FileNotFoundError(f"JSONL file not found: {file_path}")
    
    with open(file_path, "r", encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:  # Skip empty lines
                continue
            
            try:
                job_data = json.loads(line)
                yield job_data
            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON on line {line_num} in {file_path}: {e}")
                continue

def load_jsonl_list(file_path: Path) -> List[Dict[str, Any]]:
    """
    Load all job data from a JSONL file into a list.
    
    Args:
        file_path (Path): Path to the JSONL file
        
    Returns:
        List[Dict[str, Any]]: List of job data dictionaries
    """
    return list(load_jsonl(file_path))

def save_jsonl(data: List[Dict[str, Any]], file_path: Path, backup: bool = True) -> None:
    """
    Save job data to a JSONL file.
    
    Args:
        data (List[Dict[str, Any]]): List of job data dictionaries
        file_path (Path): Path to save the JSONL file
        backup (bool): Whether to create a backup of existing file
    """
    # Create directory if it doesn't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create backup if file exists and backup is requested
    if backup and file_path.exists():
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
        import shutil
        shutil.copy2(file_path, backup_path)
        print(f"Created backup: {backup_path}")
    
    # Write the data
    with open(file_path, "w", encoding='utf-8') as f:
        for job_data in data:
            f.write(json.dumps(job_data, ensure_ascii=False) + "\n")
    
    print(f"Saved {len(data)} jobs to {file_path}")

def count_jsonl_lines(file_path: Path) -> Dict[str, int]:
    """
    Count lines in a JSONL file and categorize them.
    
    Args:
        file_path (Path): Path to the JSONL file
        
    Returns:
        Dict[str, int]: Statistics about the file
    """
    if not file_path.exists():
        return {"error": "File not found"}
    
    stats = {
        "total_lines": 0,
        "valid_jobs": 0,
        "empty_lines": 0,
        "invalid_json": 0,
        "with_fit_analysis": 0,
        "with_agent_fit_result": 0
    }
    
    with open(file_path, "r", encoding='utf-8') as f:
        for line in f:
            stats["total_lines"] += 1
            
            line = line.strip()
            if not line:
                stats["empty_lines"] += 1
                continue
            
            try:
                job_data = json.loads(line)
                stats["valid_jobs"] += 1
                
                if "fit_analysis" in job_data:
                    stats["with_fit_analysis"] += 1
                
                if "agent_fit_result" in job_data:
                    stats["with_agent_fit_result"] += 1
                    
            except json.JSONDecodeError:
                stats["invalid_json"] += 1
    
    return stats

def find_latest_linkedin_file(base_dir: str = "data/linkedin") -> Path | None:
    """
    Find the most recent LinkedIn JSONL file.
    
    Args:
        base_dir (str): Base directory to search in
        
    Returns:
        Path | None: Path to the latest file or None if not found
    """
    # Check for symlink first
    latest_symlink = Path(base_dir) / "results" / "latest.jsonl"
    if latest_symlink.exists() and latest_symlink.is_symlink():
        resolved = latest_symlink.resolve()
        if resolved.exists():
            return resolved
    
    # Fallback to most recent file
    json_dir = Path(base_dir)
    if not json_dir.exists():
        return None
    
    jsonl_files = list(json_dir.rglob("*.jsonl"))
    if not jsonl_files:
        return None
    
    return max(jsonl_files, key=lambda f: f.stat().st_mtime)

def validate_job_data(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize job data structure.
    
    Args:
        job_data (Dict[str, Any]): Raw job data
        
    Returns:
        Dict[str, Any]: Validation result with errors/warnings
    """
    validation = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Required fields
    required_fields = ["id", "title", "company", "description"]
    for field in required_fields:
        if field not in job_data or not job_data[field]:
            validation["errors"].append(f"Missing required field: {field}")
            validation["valid"] = False
    
    # Recommended fields
    recommended_fields = ["url", "location", "posted_time"]
    for field in recommended_fields:
        if field not in job_data or not job_data[field]:
            validation["warnings"].append(f"Missing recommended field: {field}")
    
    # Check description length
    description = job_data.get("description", "")
    if len(description) < 100:
        validation["warnings"].append("Description seems too short (< 100 characters)")
    
    return validation

def merge_jsonl_files(input_files: List[Path], output_file: Path, deduplicate: bool = True) -> Dict[str, int]:
    """
    Merge multiple JSONL files into one.
    
    Args:
        input_files (List[Path]): List of input JSONL files
        output_file (Path): Output file path
        deduplicate (bool): Whether to remove duplicates based on job ID
        
    Returns:
        Dict[str, int]: Statistics about the merge operation
    """
    seen_ids = set()
    merged_jobs = []
    stats = {
        "input_files": len(input_files),
        "total_jobs_processed": 0,
        "duplicates_removed": 0,
        "jobs_merged": 0,
        "errors": 0
    }
    
    for file_path in input_files:
        if not file_path.exists():
            print(f"Warning: File not found: {file_path}")
            stats["errors"] += 1
            continue
        
        print(f"Processing: {file_path}")
        
        try:
            for job_data in load_jsonl(file_path):
                stats["total_jobs_processed"] += 1
                
                job_id = job_data.get("id", "")
                
                if deduplicate and job_id in seen_ids:
                    stats["duplicates_removed"] += 1
                    continue
                
                seen_ids.add(job_id)
                merged_jobs.append(job_data)
                stats["jobs_merged"] += 1
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            stats["errors"] += 1
    
    # Save merged results
    save_jsonl(merged_jobs, output_file)
    
    print(f"Merge complete: {stats['jobs_merged']} jobs saved to {output_file}")
    return stats

def filter_jobs_by_criteria(
    file_path: Path,
    min_score: int = None,
    recommendations: List[str] = None,
    companies: List[str] = None,
    keywords: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Filter jobs based on various criteria.
    
    Args:
        file_path (Path): Path to the JSONL file
        min_score (int): Minimum overall score
        recommendations (List[str]): List of acceptable recommendations
        companies (List[str]): List of company names to include
        keywords (List[str]): Keywords to search for in title/description
        
    Returns:
        List[Dict[str, Any]]: Filtered job list
    """
    filtered_jobs = []
    
    for job_data in load_jsonl(file_path):
        # Check if job has analysis
        fit_analysis = job_data.get("fit_analysis") or job_data.get("agent_fit_result")
        if not fit_analysis:
            continue
        
        # Score filter
        if min_score is not None:
            if isinstance(fit_analysis, dict):
                score = fit_analysis.get("overall_score", 0)
                if score < min_score:
                    continue
        
        # Recommendation filter
        if recommendations:
            if isinstance(fit_analysis, dict):
                recommendation = fit_analysis.get("recommendation", "")
                if recommendation not in recommendations:
                    continue
        
        # Company filter
        if companies:
            job_company = job_data.get("company", "").lower()
            if not any(comp.lower() in job_company for comp in companies):
                continue
        
        # Keywords filter
        if keywords:
            title = job_data.get("title", "").lower()
            description = job_data.get("description", "").lower()
            content = f"{title} {description}"
            
            if not any(keyword.lower() in content for keyword in keywords):
                continue
        
        filtered_jobs.append(job_data)
    
    return filtered_jobs

# Convenience function for backward compatibility
def load_jsonl_jobs(file_path):
    """Backward compatibility wrapper for load_jsonl"""
    return load_jsonl(Path(file_path))