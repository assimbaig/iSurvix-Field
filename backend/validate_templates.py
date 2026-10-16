#!/usr/bin/env python3
"""
Django Template Validator
Checks for common template syntax errors that break Django 6.0.1+
"""
import os
import sys
import re

def validate_template(filepath):
    """Validate a single Django template file"""
    errors = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Track block counts
    for_count = 0
    endfor_count = 0
    if_count = 0
    endif_count = 0
    
    for line_num, line in enumerate(lines, 1):
        # Check for split Django tags at end of line
        if re.search(r'\{%\s+(if|for|elif|with)\s*$', line):
            errors.append(f"Line {line_num}: Split Django tag at end of line")
        
        # Check for split template variables at end of line
        if re.search(r'\{\{\s*$', line):
            errors.append(f"Line {line_num}: Split template variable at end of line")
        
        # Check for == without spaces in if statements
        if '{% if' in line and '==' in line:
            # Extract the condition part
            match = re.search(r'\{%\s*if\s+(.+?)\s*%\}', line)
            if match:
                condition = match.group(1)
                # Check if == doesn't have spaces around it
                if re.search(r'\S==\S', condition):
                    errors.append(f"Line {line_num}: == operator needs spaces: ' == ' not '=='")
        
        # Count blocks
        for_count += line.count('{% for ')
        endfor_count += line.count('{% endfor %}')
        if_count += line.count('{% if ')
        endif_count += line.count('{% endif %}')
    
    # Check block balance
    if for_count != endfor_count:
        errors.append(f"Unbalanced for/endfor: {for_count} for, {endfor_count} endfor")
    
    if if_count != endif_count:
        errors.append(f"Unbalanced if/endif: {if_count} if, {endif_count} endif")
    
    return errors

def scan_templates(root_dir='templates'):
    """Scan all template files in directory"""
    all_errors = {}
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.html'):
                filepath = os.path.join(dirpath, filename)
                errors = validate_template(filepath)
                if errors:
                    all_errors[filepath] = errors
    
    return all_errors

if __name__ == '__main__':
    print("🔍 Scanning Django templates for syntax errors...\n")
    
    errors = scan_templates()
    
    if not errors:
        print("✅ All templates are valid!")
        sys.exit(0)
    else:
        print(f"❌ Found errors in {len(errors)} template(s):\n")
        for filepath, error_list in errors.items():
            print(f"📄 {filepath}")
            for error in error_list:
                print(f"   • {error}")
            print()
        sys.exit(1)
