
import os
import subprocess
import sys

def test_scraper_dry_run():
    print("🚀 NUZANTARA: Testing Bali Intel Scraper (Dry Run) ...")
    
    # Path to scraper directory
    scraper_dir = os.path.join("apps", "bali-intel-scraper")
    
    # Path to orchestrator script
    script_path = os.path.join(scraper_dir, "scripts", "orchestrator.py")
    
    if not os.path.exists(script_path):
        print(f"❌ Error: Scraper script not found at {script_path}")
        return

    # Construct command: Run orchestrator with dry-run from within the scraper directory
    # We must change CWD to apps/bali-intel-scraper for it to find config/categories.json
    cmd = [
        "python3", 
        "scripts/orchestrator.py",
        "--stage", "all",
        "--dry-run"
    ]
    
    print(f"📂 Working Directory: {scraper_dir}")
    print(f"💻 Command: {' '.join(cmd)}")
    print("-" * 50)

    try:
        # Run subprocess
        result = subprocess.run(
            cmd, 
            cwd=scraper_dir, 
            capture_output=True, 
            text=True
        )
        
        # Print output
        print(result.stdout)
        
        if result.stderr:
            print("⚠️ STDERR:")
            print(result.stderr)
            
        if result.returncode == 0:
            print("-" * 50)
            print("✅ Dry Run Successful: Scraper pipeline is correctly wired.")
        else:
            print("-" * 50)
            print("❌ Dry Run Failed: See output above.")
            
    except Exception as e:
        print(f"❌ Execution failed: {e}")

if __name__ == "__main__":
    test_scraper_dry_run()
