#!/usr/bin/env python3
"""
Pre-commit hook to prevent accidental secret commits.
Install: cp .git-pre-commit-check.py .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

This hook checks for:
- Environment variables and secrets
- API keys and tokens
- Database credentials
- Private URLs
"""

import sys
import re
import subprocess
from pathlib import Path

# Patterns that indicate secrets
SECRET_PATTERNS = [
    (r'password\s*=\s*["\'](?!.*example|.*null|.*pass).*["\']', "Potential password found"),
    (r'api[_-]?key\s*=\s*["\'].*["\']', "Potential API key found"),
    (r'secret\s*=\s*["\'](?!.*example).*["\']', "Potential secret found"),
    (r'token\s*=\s*["\'](?!.*example).*["\']', "Potential token found"),
    (r'apikey\s*=\s*["\'].*["\']', "Potential API key found"),
    (r'auth\s*=\s*["\'].*["\']', "Potential auth credential found"),
    (r'Bearer\s+[A-Za-z0-9._\-]*', "Potential Bearer token found"),
    (r'https?://[^/\s]*:.*@', "Potential URL with credentials"),
    (r'\b[A-Za-z0-9]{32,}\b', "Potential long hash/secret"),
]

# Files to never commit
FORBIDDEN_FILES = [
    '.env',
    '.env.*.local',
    'backend/config/ai_config.json',
    'backend/config/nextcloud_config.json',
    'backend/config/indexing_config.json',
    'backend/config/openweather_config.json',
    'backend/config/nina_config.json',
]

def check_diff():
    """Check staged changes for secrets."""
    try:
        # Get staged changes
        result = subprocess.run(
            ['git', 'diff', '--cached', '-U3'],
            capture_output=True,
            text=True,
            check=False
        )
        diff_output = result.stdout
    except Exception as e:
        print(f"Error running git diff: {e}")
        return True  # Allow commit on error
    
    found_secrets = False
    lines = diff_output.split('\n')
    
    for line_num, line in enumerate(lines, 1):
        # Skip diff metadata
        if line.startswith('@@') or line.startswith('+++ ') or line.startswith('--- '):
            continue
        
        # Skip additions of example/template files
        if '.example' in line or '#' in line:
            continue
        
        # Check for secret patterns
        for pattern, description in SECRET_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                print(f"🚨 POTENTIAL SECRET DETECTED (line {line_num}):")
                print(f"   Pattern: {description}")
                print(f"   Content: {line[:100]}")
                found_secrets = True
    
    # Check for forbidden files
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True,
            check=False
        )
        staged_files = result.stdout.strip().split('\n')
        
        for staged_file in staged_files:
            for forbidden in FORBIDDEN_FILES:
                if staged_file.endswith(forbidden) and not staged_file.endswith('.example'):
                    print(f"🚨 FORBIDDEN FILE DETECTED: {staged_file}")
                    print(f"   These files should NOT be committed!")
                    found_secrets = True
    except Exception as e:
        print(f"Warning: Could not check file names: {e}")
    
    return found_secrets

def main():
    print("🔍 Checking for secrets in staged changes...")
    
    if check_diff():
        print()
        print("=" * 70)
        print("❌ COMMIT REJECTED - Potential secrets detected!")
        print("=" * 70)
        print()
        print("If this is a false positive:")
        print("  1. Review the flagged content")
        print("  2. Use example/template files instead")
        print("  3. Use environment variables for secrets")
        print()
        print("To override (NOT RECOMMENDED):")
        print("  git commit --no-verify")
        print()
        sys.exit(1)
    else:
        print("✅ No secrets detected - proceeding with commit")
        sys.exit(0)

if __name__ == "__main__":
    main()
