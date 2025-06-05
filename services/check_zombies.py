#!/usr/bin/env python3
import os
from openai import AzureOpenAI
import time
from datetime import datetime, timedelta

client = AzureOpenAI(
    azure_endpoint="https://wercopenai.openai.azure.com/",
    api_key="48b0cc7a06d04279a8ae53997526965e",
    api_version="2024-12-01-preview"
)

print("🔍 Checking for active/zombie runs...\n")

# The issue is that we can't list all threads without storing them
# Let's check if there's a specific thread from your current run

# Option 1: Check specific thread if you have the ID
def check_thread(thread_id):
    """Check a specific thread for active runs"""
    try:
        print(f"Checking thread: {thread_id}")
        
        # List runs for this thread
        runs = client.beta.threads.runs.list(thread_id=thread_id)
        
        active_runs = []
        for run in runs.data:
            if run.status in ["in_progress", "queued", "requires_action", "cancelling"]:
                run_age = datetime.now() - datetime.fromtimestamp(run.created_at)
                
                print(f"\n⚠️  Active Run Found:")
                print(f"  Run ID: {run.id}")
                print(f"  Status: {run.status}")
                print(f"  Created: {datetime.fromtimestamp(run.created_at)}")
                print(f"  Age: {run_age}")
                
                if run_age > timedelta(minutes=5):
                    print(f"  ⚠️  This run seems stuck!")
                
                active_runs.append(run)
        
        if not active_runs:
            print("✅ No active runs in this thread")
        
        return active_runs
        
    except Exception as e:
        print(f"Error checking thread: {e}")
        return []

# Option 2: Extract thread IDs from your log file
def find_thread_ids_from_logs():
    """Extract thread IDs from recent logs"""
    thread_ids = set()
    
    # Check the log file
    log_file = "linkedin_scraper.log"
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            for line in f:
                if 'thread_' in line:
                    # Extract thread ID (format: thread_XXXXX)
                    import re
                    matches = re.findall(r'thread_[a-zA-Z0-9]+', line)
                    thread_ids.update(matches)
    
    # Also check the recent pipeline log
    pipeline_log = "data/logs/job_ai_pipeline.log"
    if os.path.exists(pipeline_log):
        with open(pipeline_log, 'r') as f:
            for line in f:
                if 'thread_' in line:
                    import re
                    matches = re.findall(r'thread_[a-zA-Z0-9]+', line)
                    thread_ids.update(matches)
    
    return list(thread_ids)

# Option 3: Check the most recent thread from your last run
def check_recent_threads():
    """Check threads mentioned in recent runs"""
    
    # From your log output, I can see this thread:
    recent_thread = "thread_yxavevCgr7ejpqn3rANTfpls"
    
    print(f"Checking recent thread from logs: {recent_thread}")
    check_thread(recent_thread)
    
    # Find more from logs
    print("\n📋 Looking for more threads in logs...")
    thread_ids = find_thread_ids_from_logs()
    
    if thread_ids:
        print(f"Found {len(thread_ids)} unique threads in logs")
        for tid in thread_ids[-5:]:  # Check last 5
            print(f"\nChecking {tid}...")
            check_thread(tid)
            time.sleep(0.5)  # Avoid rate limits
    else:
        print("No threads found in logs")

# Option 4: Simple way to check if API is being rate limited
def check_api_health():
    """Quick check if API is responding"""
    try:
        # Create a new thread as a test
        thread = client.beta.threads.create()
        print(f"✅ API is responsive - created test thread: {thread.id}")
        
        # Check this thread
        check_thread(thread.id)
        
        # Clean up
        try:
            client.beta.threads.delete(thread_id=thread.id)
            print("🧹 Cleaned up test thread")
        except:
            pass
            
    except Exception as e:
        print(f"❌ API Error: {e}")

if __name__ == "__main__":
    print("1️⃣ Checking API health...")
    check_api_health()
    
    print("\n2️⃣ Checking recent threads...")
    check_recent_threads()
    
    print("\n💡 To check a specific thread, run:")
    print('   python check_zombies.py "thread_YOUR_THREAD_ID"')
    
    # If command line argument provided, check that thread
    import sys
    if len(sys.argv) > 1:
        thread_id = sys.argv[1]
        print(f"\n3️⃣ Checking specified thread: {thread_id}")
        check_thread(thread_id)