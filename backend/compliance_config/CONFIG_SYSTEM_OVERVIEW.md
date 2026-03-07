# Compliance Config System Overview

The compliance system uses a dynamic, type-based configuration system that automatically discovers and loads config files from S3.

## Config Types

All compliance config files must have a `type` field that determines how they're used:

### `"pre-check"` - Fast Lexical Pre-Checks

Pre-checks run BEFORE the expensive Pegasus analysis to quickly filter out videos that fail basic criteria.

**Characteristics:**
- Use lexical transcription search (fast substring matching)
- Run in sequence order (lower numbers first)
- If ANY pre-check fails, Pegasus analysis is skipped
- Only a summary is generated for failed pre-checks

**Current Pre-Checks:**
- `content_relevance_check.json` (sequence: 1) - Ensures video mentions the product
- `profanity_check.json` (sequence: 2) - Blocks videos with profanity

### `"analysis"` - Pegasus AI Analysis

Analysis configs define categories that are evaluated by the Pegasus AI model during full video analysis.

**Characteristics:**
- Run only if all pre-checks pass
- Use AWS Bedrock Pegasus model for deep video understanding
- Can detect nuanced issues (tone, suitability, context)
- More expensive but more comprehensive

**Current Analysis Categories:**
- `moral_standards_check.json` (sequence: 3) - Hate speech, illegal behavior, profanity, danger
- `video_content_check.json` (sequence: 4) - Suitability, brand exclusivity, product focus, tone

## How It Works

### 1. Discovery Phase

The system automatically discovers configs by:
1. Listing all `.json` files in the S3 compliance config directory
2. Loading each file and checking its `type` field
3. Filtering by `enabled: true`
4. Sorting by `sequence` field

**No hardcoded file lists needed!** Just upload a new config file to S3 and it's automatically included.

### 2. Execution Flow

```
Video Upload
    ↓
Load Pre-Check Configs (type="pre-check")
    ↓
Run Pre-Checks in Sequence Order
    ↓
Any Failed? → Yes → Generate Summary Only → Done
    ↓ No
Load Analysis Configs (type="analysis")
    ↓
Build Pegasus Prompt from Analysis Configs
    ↓
Run Pegasus Analysis
    ↓
Parse Results & Generate Report
    ↓
Done
```

### 3. Adding New Configs

**To add a new pre-check:**

1. Create a JSON file with `type: "pre-check"`
2. Upload to S3 at `compliance_config/your_check.json`
3. It runs automatically!

**To add a new analysis category:**

1. Create a JSON file with `type: "analysis"`
2. Upload to S3 at `compliance_config/your_category.json`
3. It's included in the Pegasus prompt automatically!

## Config File Structure

### Pre-Check Config

```json
{
    "id": "unique_identifier",
    "type": "pre-check",
    "sequence": 10,
    "enabled": true,
    "description": "What this check does",
    "search_config": {
        "search_term": "term or [array, of, terms]",
        "min_results": 1,
        "pass_condition": "found or not_found"
    },
    "on_fail": {
        "category": "Category Name",
        "subcategory": "Subcategory",
        "status": "BLOCK or REVIEW",
        "description": "Failure message"
    }
}
```

### Analysis Config

```json
{
    "id": "unique_identifier",
    "type": "analysis",
    "sequence": 10,
    "name": "Category Name",
    "description": "Instructions for Pegasus AI",
    "subcategories": [
        {
            "name": "Subcategory Name",
            "guidance": "Specific instructions",
            "status": "BLOCK or REVIEW"
        }
    ]
}
```

## Best Practices

### Sequence Numbering

Use increments of 10 to allow inserting configs later:
- Pre-checks: 1, 2, 3... (or 10, 20, 30...)
- Analysis: Start after pre-checks (e.g., 100, 110, 120...)

### Pre-Check vs Analysis

**Use Pre-Checks for:**
- Simple keyword matching
- Fast filtering (content relevance, profanity)
- Binary pass/fail criteria
- Reducing Pegasus API costs

**Use Analysis for:**
- Nuanced evaluation (tone, context, suitability)
- Complex criteria requiring AI understanding
- Multi-factor decisions
- Detailed issue descriptions

### Execution Order

1. **Blocking pre-checks first** (content relevance)
2. **Other pre-checks** (profanity, competitors)
3. **Critical analysis** (moral standards)
4. **Quality analysis** (video content, brand guidelines)

## Migration Notes

### Old System (Hardcoded Lists)

```python
# compliance_service.py
precheck_files = [
    "content_relevance_check.json",
    "profanity_check.json"
]

check_files = [
    "moral_standards_check.json",
    "video_content_check.json"
]
```

### New System (Dynamic Discovery)

```python
# Automatically discovers all configs with:
# - type="pre-check" for pre-checks
# - type="analysis" for analysis categories
# No file lists needed!
```

## Summary

The new system is:
- **Dynamic**: Add configs without code changes
- **Type-based**: Clear separation between pre-checks and analysis
- **Flexible**: Easy to add, remove, or reorder checks
- **Maintainable**: No hardcoded file lists to update
