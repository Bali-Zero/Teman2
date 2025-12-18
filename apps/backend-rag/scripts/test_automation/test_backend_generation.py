#!/usr/bin/env python3
"""
Test script to verify backend test generation works correctly
"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from backend_test_generator import BackendTestGenerator
import yaml

def main():
    print("=" * 80)
    print("TESTBOT - Backend Test Generation Test")
    print("=" * 80)
    print()
    
    # Load config
    config_path = Path(__file__).parent / "testbot_config.yaml"
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {
            "coverage": {"min_threshold": 80},
            "ai": {"max_tests_per_run": 10}
        }
    
    # Initialize generator
    print("Initializing BackendTestGenerator...")
    generator = BackendTestGenerator(config)
    print(f"✅ BackendTestGenerator initialized")
    print(f"   Backend dir: {generator.backend_dir}")
    print(f"   Test dir: {generator.test_dir}")
    print()
    
    # Check if coverage file exists
    coverage_file = generator.backend_dir.parent / "coverage.json"
    if not coverage_file.exists():
        print(f"⚠️  Coverage file not found: {coverage_file}")
        print("   Run pytest with --cov first to generate coverage.json")
        return
    
    print(f"✅ Coverage file found: {coverage_file}")
    print()
    
    # Test finding files with low coverage
    print("Finding files with low coverage...")
    try:
        with open(coverage_file, 'r') as f:
            coverage_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading coverage file: {e}")
        return
    
    # Test for each target type
    for test_type in ["unit", "integration", "api"]:
        print(f"\n--- Testing {test_type} test generation ---")
        files = generator._find_files_with_low_coverage(coverage_data, test_type)
        print(f"Found {len(files)} file(s) with low coverage")
        
        if files:
            print(f"Top 3 files:")
            for file_path, coverage in files[:3]:
                print(f"  - {file_path.name}: {coverage:.1f}%")
            
            # Test generating a test for the first file
            if len(files) > 0:
                test_file_path, coverage = files[0]
                print(f"\nGenerating test for: {test_file_path.name} ({coverage:.1f}% coverage)...")
                try:
                    result = generator._generate_test_for_file(test_file_path, test_type)
                    if result:
                        print(f"✅ Test generated: {result}")
                    else:
                        print(f"⚠️  Test generation returned None")
                except Exception as e:
                    print(f"❌ Error generating test: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print(f"  No files found with low coverage for {test_type}")

if __name__ == "__main__":
    import json
    main()

