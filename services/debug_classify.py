#!/usr/bin/env python3
"""
Debug script to check classify_fit import and function availability
"""

import sys
from pathlib import Path
import traceback

def check_agents_directory():
    """Check if agents directory and files exist"""
    agents_dir = Path("agents")
    
    print("=== AGENTS DIRECTORY CHECK ===")
    print(f"Agents directory exists: {agents_dir.exists()}")
    
    if agents_dir.exists():
        files = list(agents_dir.iterdir())
        print(f"Files in agents/: {[f.name for f in files if f.is_file()]}")
        
        classify_fit_file = agents_dir / "classify_fit.py"
        print(f"classify_fit.py exists: {classify_fit_file.exists()}")
        
        if classify_fit_file.exists():
            print(f"classify_fit.py size: {classify_fit_file.stat().st_size} bytes")
    else:
        print("❌ agents/ directory does not exist")
    
    print()

def check_python_path():
    """Check Python path and current directory"""
    print("=== PYTHON PATH CHECK ===")
    print(f"Current working directory: {Path.cwd()}")
    print(f"Python path includes current dir: {'.' in sys.path or str(Path.cwd()) in sys.path}")
    
    # Add current directory to path if not there
    if "." not in sys.path and str(Path.cwd()) not in sys.path:
        sys.path.insert(0, ".")
        print("✅ Added current directory to Python path")
    
    print()

def test_classify_fit_imports():
    """Test various import combinations"""
    print("=== IMPORT TESTS ===")
    
    # Test 1: classify_fit_from_file
    try:
        from agents.classify_fit import classify_fit_from_file
        print("✅ Successfully imported classify_fit_from_file")
        
        # Test if it's callable
        if callable(classify_fit_from_file):
            print("✅ classify_fit_from_file is callable")
        else:
            print("❌ classify_fit_from_file is not callable")
            
    except ImportError as e:
        print(f"❌ Failed to import classify_fit_from_file: {e}")
    except Exception as e:
        print(f"❌ Unexpected error importing classify_fit_from_file: {e}")
        traceback.print_exc()
    
    # Test 2: classify_job_fit
    try:
        from agents.classify_fit import classify_job_fit
        print("✅ Successfully imported classify_job_fit")
        
        if callable(classify_job_fit):
            print("✅ classify_job_fit is callable")
        else:
            print("❌ classify_job_fit is not callable")
            
    except ImportError as e:
        print(f"❌ Failed to import classify_job_fit: {e}")
    except Exception as e:
        print(f"❌ Unexpected error importing classify_job_fit: {e}")
        traceback.print_exc()
    
    # Test 3: Import the module and list available functions
    try:
        import agents.classify_fit as cf_module
        print("✅ Successfully imported agents.classify_fit module")
        
        # List all functions in the module
        functions = [name for name in dir(cf_module) if callable(getattr(cf_module, name)) and not name.startswith('_')]
        print(f"Available functions: {functions}")
        
    except ImportError as e:
        print(f"❌ Failed to import agents.classify_fit module: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Unexpected error importing module: {e}")
        traceback.print_exc()
    
    print()

def check_file_content():
    """Check the actual content of classify_fit.py"""
    print("=== FILE CONTENT CHECK ===")
    
    classify_fit_file = Path("agents/classify_fit.py")
    
    if not classify_fit_file.exists():
        print("❌ agents/classify_fit.py does not exist")
        return
    
    try:
        with open(classify_fit_file, "r", encoding='utf-8') as f:
            content = f.read()
        
        print(f"File length: {len(content)} characters")
        
        # Check for function definitions
        if "def classify_fit_from_file" in content:
            print("✅ Found 'def classify_fit_from_file' in file")
        else:
            print("❌ 'def classify_fit_from_file' not found in file")
        
        if "def classify_job_fit" in content:
            print("✅ Found 'def classify_job_fit' in file")
        else:
            print("❌ 'def classify_job_fit' not found in file")
        
        # Check for syntax errors
        try:
            compile(content, classify_fit_file, 'exec')
            print("✅ File compiles without syntax errors")
        except SyntaxError as e:
            print(f"❌ Syntax error in file: {e}")
            print(f"Error at line {e.lineno}: {e.text}")
        
        # Show first few lines
        lines = content.split('\n')[:10]
        print("\nFirst 10 lines of file:")
        for i, line in enumerate(lines, 1):
            print(f"{i:2d}: {line}")
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
    
    print()

def test_router_compatibility():
    """Test if the router can detect functions"""
    print("=== ROUTER COMPATIBILITY TEST ===")
    
    # Simulate the router's import logic
    CLASSIFY_FUNCTION = None
    
    try:
        from agents.classify_fit import classify_fit_from_file
        CLASSIFY_FUNCTION = "classify_fit_from_file"
        print("✅ Router would detect classify_fit_from_file")
    except ImportError:
        try:
            from agents.classify_fit import classify_job_fit
            CLASSIFY_FUNCTION = "classify_job_fit"
            print("✅ Router would detect classify_job_fit")
        except ImportError:
            CLASSIFY_FUNCTION = None
            print("❌ Router would not detect any classify functions")
    
    print(f"Router CLASSIFY_FUNCTION would be: {CLASSIFY_FUNCTION}")
    
    if CLASSIFY_FUNCTION:
        print("✅ Router should work (503 error shouldn't occur)")
    else:
        print("❌ Router would return 503 Service Unavailable")
    
    print()

def create_minimal_classify_fit():
    """Create a minimal classify_fit.py file if none exists"""
    print("=== CREATING MINIMAL FILE ===")
    
    agents_dir = Path("agents")
    classify_fit_file = agents_dir / "classify_fit.py"
    
    if classify_fit_file.exists():
        print("File already exists, not overwriting")
        return
    
    # Create agents directory
    agents_dir.mkdir(exist_ok=True)
    
    # Create minimal file
    minimal_content = '''"""
Minimal classify_fit module for testing
"""

def classify_fit_from_file(file_path: str) -> dict:
    """
    Minimal test function
    """
    return {
        "status": "test_success",
        "message": "Minimal classify_fit_from_file is working",
        "file_path": file_path,
        "processed": 0
    }

def classify_job_fit(job_data: dict) -> dict:
    """
    Minimal test function for single job
    """
    return {
        "status": "test_success",
        "message": "Minimal classify_job_fit is working",
        "job_title": job_data.get("title", "Unknown")
    }

if __name__ == "__main__":
    print("Minimal classify_fit module loaded")
'''
    
    try:
        with open(classify_fit_file, "w", encoding='utf-8') as f:
            f.write(minimal_content)
        
        print(f"✅ Created minimal classify_fit.py at {classify_fit_file}")
        print("You can now test if the 503 error is resolved")
        
    except Exception as e:
        print(f"❌ Failed to create minimal file: {e}")

def main():
    """Run all debug checks"""
    print("🔍 CLASSIFY_FIT DEBUG TOOL")
    print("=" * 50)
    
    check_agents_directory()
    check_python_path()
    test_classify_fit_imports()
    check_file_content()
    test_router_compatibility()
    
    # Ask if user wants to create minimal file
    response = input("Would you like to create a minimal classify_fit.py file? (y/n): ")
    if response.lower().startswith('y'):
        create_minimal_classify_fit()
    
    print("\n🏁 Debug complete!")
    print("Next steps:")
    print("1. If 503 error persists, restart your FastAPI server")
    print("2. Test the endpoint again")
    print("3. Check the /debug/imports endpoint in your API")

if __name__ == "__main__":
    main()