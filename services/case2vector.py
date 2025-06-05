import os
from pathlib import Path

DATA_DIR = "portfolio/text_versions"

def extract_metadata(filepath):
    """Extract title and subtitle from the first two lines of the file"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if len(lines) >= 2:
            title = lines[0].strip()
            subtitle = lines[1].strip()
        elif len(lines) == 1:
            title = lines[0].strip()
            subtitle = ""
        else:
            # Fallback to filename
            title = os.path.basename(filepath).replace(".txt", "").replace("_", " ").title()
            subtitle = ""
        
        return title, subtitle
    
    except Exception as e:
        print(f"⚠️ Error reading metadata from {filepath}: {e}")
        # Fallback to filename
        title = os.path.basename(filepath).replace(".txt", "").replace("_", " ").title()
        return title, ""

def main():
    """Rename all .txt files by prefixing with 'case_study_' if not already prefixed, and print new filenames."""
    data_path = Path(DATA_DIR)
    if not data_path.exists():
        print(f"❌ Directory not found: {DATA_DIR}")
        return
    
    txt_files = list(data_path.glob("*.txt"))
    if not txt_files:
        print(f"❌ No .txt files found in {DATA_DIR}")
        return
    
    for filepath in txt_files:
        original_filename = filepath.name
        if not original_filename.startswith("case_study_"):
            new_filename = f"case_study_{original_filename}"
            new_filepath = filepath.with_name(new_filename)
            os.rename(filepath, new_filepath)
            filepath = new_filepath
        
        title, subtitle = extract_metadata(str(filepath))
        print(f"Renamed file: {filepath.name}")
        print(f"   Title: {title}")
        print(f"   Subtitle: {subtitle}")

if __name__ == "__main__":
    main()