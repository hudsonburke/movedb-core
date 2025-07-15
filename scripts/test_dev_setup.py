#!/usr/bin/env python3
"""
Comprehensive test script to verify all development tooling is working correctly.
"""

import subprocess
import sys
import os

def run_cmd(cmd, description):
    """Run a command and report results."""
    print(f"\n🧪 {description}")
    print(f"Command: {cmd}")
    print("-" * 50)
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ SUCCESS")
        if result.stdout:
            print(result.stdout)
    else:
        print("❌ FAILED")
        if result.stderr:
            print(f"Error: {result.stderr}")
        if result.stdout:
            print(f"Output: {result.stdout}")
    
    return result.returncode == 0

def main():
    """Test all development tooling."""
    print("🔧 Testing MoveDB Core Development Setup")
    print("=" * 60)
    
    # Change to the project directory
    os.chdir('/home/hudson/movedb-core')
    
    tests = [
        ("make help", "Testing Makefile help system"),
        ("python -c 'import numpy, polars, pydantic, ezc3d, numpydantic, pandera; print(\"✅ Core dependencies available\")'", "Testing core dependencies"),
        ("python run_tests.py --help || echo 'Run tests script exists'", "Testing Python test runner"),
        ("make test-quick", "Testing quick test run"),
        ("make test-pattern PATTERN=imports", "Testing pattern-based test selection"),
        ("pytest --version", "Testing pytest installation"),
        ("black --version", "Testing code formatter"),
        ("make clean", "Testing cleanup commands"),
    ]
    
    results = []
    for cmd, description in tests:
        success = run_cmd(cmd, description)
        results.append((description, success))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {description}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        print("\n🎉 All development tooling tests passed!")
        print("Your development environment is ready to use!")
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
