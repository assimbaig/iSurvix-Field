#!/bin/bash
# Pre-commit hook to validate Django templates
# Install: cp pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

echo "🔍 Validating Django templates..."

# Run the validation script
python validate_templates.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Template validation failed!"
    echo "Fix the errors above before committing."
    echo ""
    echo "To skip this check (not recommended):"
    echo "  git commit --no-verify"
    exit 1
fi

echo "✅ All templates valid!"
exit 0
