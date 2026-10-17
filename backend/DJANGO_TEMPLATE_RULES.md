# Django Template Syntax Rules

## Critical Rules (Django 6.0.1+)

### 1. NO LINE BREAKS IN TEMPLATE TAGS

**❌ WRONG:**
```django
{% if
    condition %}
```

```django
{{
    variable }}
```

**✅ CORRECT:**
```django
{% if condition %}
```

```django
{{ variable }}
```

### 2. SPACES AROUND OPERATORS

**❌ WRONG:**
```django
{% if user.id==work.id %}
```

**✅ CORRECT:**
```django
{% if user.id == work.id %}
```

### 3. ALL LOOPS MUST BE CLOSED

**❌ WRONG:**
```django
{% for item in items %}
    <div>{{ item }}</div>
<!-- Missing {% endfor %} -->
```

**✅ CORRECT:**
```django
{% for item in items %}
    <div>{{ item }}</div>
{% endfor %}
```

### 4. ALL IF BLOCKS MUST BE CLOSED

**❌ WRONG:**
```django
{% if condition %}
    <div>Content</div>
<!-- Missing {% endif %} -->
```

**✅ CORRECT:**
```django
{% if condition %}
    <div>Content</div>
{% endif %}
```

### 5. PROPER NESTING

**❌ WRONG:**
```django
{% for item in items %}
    {% if condition %}
{% endfor %}  <!-- Closes before if! -->
    {% endif %}
```

**✅ CORRECT:**
```django
{% for item in items %}
    {% if condition %}
        <div>Content</div>
    {% endif %}
{% endfor %}
```

## Auto-Formatter Issues

### Disable HTML Formatting

Create `.vscode/settings.json`:
```json
{
  "[html]": {
    "editor.formatOnSave": false,
    "editor.formatOnPaste": false,
    "editor.formatOnType": false
  }
}
```

### After Creating Settings
1. Reload VS Code window (Cmd+Shift+P → "Reload Window")
2. Or close/reopen the workspace folder

## Common Errors

### TemplateSyntaxError: Could not parse the remainder

**Cause:** Missing spaces around operators or incomplete tags

**Fix:**
- Add spaces: `==` → ` == `
- Consolidate split tags to single lines

### TemplateSyntaxError: Invalid block tag, expected 'endfor'

**Cause:** Missing `{% endfor %}` or `{% endif %}` before next tag

**Fix:**
- Count your `{% for %}` vs `{% endfor %}` tags
- Check nesting order
- Ensure every block has proper closing tag

## Validation Checklist

Before deploying template changes:

- [ ] All template tags on single lines
- [ ] Spaces around all operators (==, !=, <, >, <=, >=)
- [ ] Every {% for %} has {% endfor %}
- [ ] Every {% if %} has {% endif %}
- [ ] Proper nesting (close inner blocks before outer blocks)
- [ ] No split {{ variable }} tags across lines
- [ ] Test page loads without TemplateSyntaxError

## Quick Search Commands

Find split tags:
```bash
# In terminal
grep -n "{% \(if\|for\)$" templates/**/*.html
grep -n "{{$" templates/**/*.html
```

Count tags:
```bash
# Count for/endfor
grep -c "{% for" template.html
grep -c "{% endfor" template.html

# Count if/endif
grep -c "{% if" template.html
grep -c "{% endif" template.html
```

## Fixed Files Log

- `templates/dashboards/_assign_work_tab.html` - Lines 260, 131, 142, 148
- `templates/dashboards/admin_user_edit.html` - Lines 30-32, 40
- `templates/dashboards/checklist_detail.html` - Lines 185-186, 110, 165, 225, 267, 271, 448
- `templates/dashboards/engineer_checklist_edit.html` - Lines 15, 69, 79
- `static/core/css/style.css` - Mobile header fixes
- `.vscode/settings.json` - Auto-formatter disabled

## Automated Validation

### Run Validation Script
```bash
python validate_templates.py
```

This script checks:
- ✅ Split Django tags at end of lines
- ✅ Split template variables
- ✅ == operator spacing
- ✅ Balanced for/endfor loops
- ✅ Balanced if/endif blocks

### Install Pre-Commit Hook
```bash
cp pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

This prevents committing templates with syntax errors.
