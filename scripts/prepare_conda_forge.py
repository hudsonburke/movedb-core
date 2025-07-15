#!/usr/bin/env python3
"""
Conda-forge submission preparation script for movedb-core.
This script helps prepare your package for conda-forge submission.
"""

import os
import subprocess
import sys
import hashlib
import urllib.request
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and return output."""
    if description:
        print(f"🔧 {description}")
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return None

def get_file_hash(filepath):
    """Get SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def get_url_hash(url):
    """Get SHA256 hash of a file from URL."""
    try:
        with urllib.request.urlopen(url) as response:
            sha256_hash = hashlib.sha256()
            for chunk in iter(lambda: response.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"❌ Error downloading {url}: {e}")
        return None

def check_current_state():
    """Check current package state."""
    print("📋 Checking current package state...")
    
    # Check version consistency
    pyproject_version = None
    conda_version = None
    
    with open("pyproject.toml", "r") as f:
        content = f.read()
        for line in content.split("\n"):
            if line.startswith("version ="):
                pyproject_version = line.split('"')[1]
                break
    
    with open("conda-recipe/meta.yaml", "r") as f:
        content = f.read()
        for line in content.split("\n"):
            if "set version =" in line:
                conda_version = line.split('"')[1]
                break
    
    if pyproject_version is None or conda_version is None:
        print("❌ Could not find version information!")
        return False
    
    print(f"📦 pyproject.toml version: {pyproject_version}")
    print(f"📦 conda-recipe version: {conda_version}")
    
    if pyproject_version != conda_version:
        print("⚠️  Version mismatch detected!")
        return False
    
    # Check if tests pass
    print("🧪 Running tests...")
    test_result = run_command("python -m pytest tests/ --tb=short")
    if test_result is None:
        print("❌ Tests failed!")
        return False
    
    print("✅ All checks passed!")
    return True

def prepare_pypi_upload():
    """Prepare for PyPI upload."""
    print("\n🚀 Preparing for PyPI upload...")
    
    # Build wheel and sdist
    print("📦 Building packages...")
    run_command("python -m build", "Building wheel and source distribution")
    
    # Check packages
    run_command("python -m twine check dist/*", "Checking packages")
    
    print("\n📋 Next steps for PyPI upload:")
    print("1. Install twine if not installed: pip install twine")
    print("2. Upload to TestPyPI first: twine upload --repository testpypi dist/*")
    print("3. Test installation: pip install --index-url https://test.pypi.org/simple/ movedb-core")
    print("4. Upload to PyPI: twine upload dist/*")

def generate_conda_forge_recipe(version, sha256_hash, source_url):
    """Generate conda-forge recipe."""
    # Use raw string to avoid f-string template conflicts
    recipe_content = '''{% set name = "movedb-core" %}
{% set version = "''' + version + '''" %}

package:
  name: {{ name|lower }}
  version: {{ version }}

source:
  url: ''' + source_url + '''
  sha256: ''' + sha256_hash + '''

build:
  number: 0
  noarch: python
  script: {{ PYTHON }} -m pip install . -vv

requirements:
  host:
    - python >=3.8
    - pip
    - hatchling
  run:
    - python >=3.8
    - numpy >=1.20.0
    - polars >=0.20.0
    - pydantic >=2.0.0
    - ezc3d >=1.5.0
    - opensim

test:
  imports:
    - movedb
    - movedb.core
    - movedb.file_io
    - movedb.utils
  commands:
    - python -c "import movedb; print('movedb version:', movedb.__version__)"

about:
  home: https://github.com/SOMA-Bionics/movedb-core
  license: MIT
  license_family: MIT
  license_file: LICENSE
  summary: Core library for movement database operations
  description: |
    MoveDB Core is a Python library for handling movement/biomechanics data including:
    - C3D file I/O operations
    - OpenSim integration  
    - Time series data processing
    - Motion capture data management
  doc_url: https://github.com/SOMA-Bionics/movedb-core
  dev_url: https://github.com/SOMA-Bionics/movedb-core

extra:
  recipe-maintainers:
    - hudsonburke
'''
    
    os.makedirs("conda-forge-recipe", exist_ok=True)
    with open("conda-forge-recipe/meta.yaml", "w") as f:
        f.write(recipe_content)
    
    print(f"✅ Conda-forge recipe created at conda-forge-recipe/meta.yaml")

def main():
    """Main function."""
    print("🏗️  Conda-forge Submission Preparation for movedb-core")
    print("=" * 60)
    
    if not check_current_state():
        print("\n❌ Please fix issues before proceeding with conda-forge submission.")
        sys.exit(1)
    
    # Get current version
    version = None
    with open("pyproject.toml", "r") as f:
        content = f.read()
        for line in content.split("\n"):
            if line.startswith("version ="):
                version = line.split('"')[1]
                break
    
    if version is None:
        print("❌ Could not find version in pyproject.toml")
        sys.exit(1)
    
    print(f"\n📦 Current version: {version}")
    
    # Check if this is a pre-release version
    if "dev" in version or "a" in version or "b" in version or "rc" in version:
        print("⚠️  This appears to be a pre-release version.")
        print("   Consider bumping to a stable release for conda-forge submission.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("👋 Exiting. Use 'make bump-version VERSION=1.0.0' for stable release.")
            sys.exit(0)
    
    print("\n🔄 Choose submission approach:")
    print("1. PyPI first (recommended)")
    print("2. GitHub release")
    choice = input("Enter choice (1/2): ")
    
    if choice == "1":
        # PyPI approach
        prepare_pypi_upload()
        
        # Ask for PyPI URL and hash
        print(f"\nAfter uploading to PyPI, get the source distribution URL:")
        pypi_url = f"https://pypi.io/packages/source/m/movedb-core/movedb_core-{version}.tar.gz"
        print(f"Expected URL: {pypi_url}")
        
        response = input(f"\\nHas version {version} been uploaded to PyPI? (y/N): ")
        if response.lower() == 'y':
            print("🔍 Getting SHA256 hash from PyPI...")
            sha256_hash = get_url_hash(pypi_url)
            if sha256_hash:
                generate_conda_forge_recipe(version, sha256_hash, pypi_url)
            else:
                print("❌ Could not get hash from PyPI. Please upload first.")
        
    elif choice == "2":
        # GitHub release approach
        github_url = f"https://github.com/SOMA-Bionics/movedb-core/archive/v{version}.tar.gz"
        print(f"GitHub release URL: {github_url}")
        
        print("🔍 Getting SHA256 hash from GitHub...")
        sha256_hash = get_url_hash(github_url)
        if sha256_hash:
            generate_conda_forge_recipe(version, sha256_hash, github_url)
        else:
            print("❌ Could not get hash from GitHub. Please create release first.")
    
    print("\\n📋 Next Steps:")
    print("1. Review the generated recipe at conda-forge-recipe/meta.yaml")
    print("2. Fork https://github.com/conda-forge/staged-recipes")
    print("3. Copy the recipe to recipes/movedb-core/ in your fork")
    print("4. Test the recipe locally: conda build conda-forge-recipe/")
    print("5. Submit PR to conda-forge/staged-recipes")
    print("\\n📚 See docs/CONDA_FORGE_SUBMISSION.md for detailed instructions")

if __name__ == "__main__":
    main()
