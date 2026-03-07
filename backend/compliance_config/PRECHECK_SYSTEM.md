# Pre-Check System

The compliance service now supports a generic pre-check system that runs before the full Pegasus analysis. Pre-checks use lexical transcription search to quickly filter videos based on simple criteria.

## Quick Reference

### Execution Order by Sequence

Pre-checks run in order by their `sequence` field:

| ID | Sequence | Check | Pass Condition | Status | Purpose |
|----|----------|-------|----------------|--------|---------|
| content_relevance | 1 | Content Relevance | Product mentioned | BLOCK | Ensure video is about our product |
| profanity | 2 | Profanity | No profanity found | BLOCK | Filter inappropriate language |
| custom_check | 3+ | Custom checks | Varies | Varies | Add your own checks |

**Best Practice:** Use increments of 10 (10, 20, 30) for sequence to allow inserting checks later.

---

## How It Works

1. All files matching `*_check.json` in the compliance config directory are loaded
2. Only checks with `"enabled": true` are executed
3. Pre-checks run in order by their `sequence` field (lower sequence runs first)
4. If ANY pre-check fails, the full Pegasus analysis is skipped and only a summary is generated
5. All failed pre-check issues are included in the final compliance report

## Creating a New Pre-Check

Create a new JSON file in `backend/compliance_config/` with this structure:

```json
{
    "id": "my_check",
    "type": "pre-check",
    "sequence": 10,
    "enabled": true,
    "description": "Description of what this check does",
    "search_config": {
        "search_type": "lexical",
        "search_field": "transcription",
        "search_term": "term to search for",
        "min_results": 1,
        "pass_condition": "found"
    },
    "on_fail": {
        "category": "Category Name",
        "subcategory": "Subcategory Name",
        "status": "BLOCK",
        "description": "Description shown when check fails"
    }
}
```

### Configuration Fields

#### Top Level

- `id`: Unique string identifier for this check (e.g., "content_relevance", "profanity")
- `type`: Must be `"pre-check"` for pre-checks or `"analysis"` for Pegasus analysis categories
- `sequence`: Execution order (lower numbers run first). Use increments of 10 to allow inserting checks later.
- `enabled`: Set to `true` to run this check, `false` to disable
- `description`: Human-readable description of the check

#### search_config

- `search_term`: String or array of strings to search for
  - Supports placeholders: `{product_line}`, `{company}`, etc.
  - Array uses OR logic: any match counts
  
- `min_results`: Minimum number of matches required (default: 1)

- `pass_condition`: When the check passes
  - `"found"`: Pass when terms ARE found (e.g., content relevance)
  - `"not_found"`: Pass when terms are NOT found (e.g., profanity check)

#### on_fail

- `category`: Issue category shown in report
- `subcategory`: Issue subcategory shown in report
- `status`: One of `"BLOCK"`, `"REVIEW"`, or `"APPROVE"`
- `description`: Message shown when check fails (supports placeholders)

## Examples

### Content Relevance Check
Pass if product is mentioned (runs first):

```json
{
    "id": "content_relevance",
    "type": "pre-check",
    "sequence": 1,
    "enabled": true,
    "search_config": {
        "search_term": ["{product_line}", "{product_line} Pro"],
        "pass_condition": "found"
    },
    "on_fail": {
        "status": "BLOCK",
        "description": "Video doesn't mention {product_line}"
    }
}
```

### Profanity Check
Pass if profanity is NOT found (runs second):

```json
{
    "id": "profanity",
    "type": "pre-check",
    "sequence": 2,
    "enabled": true,
    "search_config": {
        "search_term": ["shit", "fuck", "damn"],
        "pass_condition": "not_found"
    },
    "on_fail": {
        "status": "BLOCK",
        "description": "Video contains profanity"
    }
}
```

### Competitor Mention Check
Pass if competitors are NOT mentioned (runs third):

```json
{
    "id": "competitor_check",
    "type": "pre-check",
    "sequence": 3,
    "enabled": true,
    "search_config": {
        "search_term": ["CompetitorA", "CompetitorB", "CompetitorC"],
        "pass_condition": "not_found"
    },
    "on_fail": {
        "status": "REVIEW",
        "description": "Video mentions competitor products"
    }
}
```

## Adding New Pre-Checks to the System

To add a new pre-check, simply create a new JSON file in `backend/compliance_config/` with `type: "pre-check"`. The system will automatically discover and load it - no code changes needed!

The file will be automatically included if:
1. It ends with `.json`
2. It has `"type": "pre-check"`
3. It has `"enabled": true`

Example: Create `competitor_check.json`:

```json
{
    "id": "competitor_check",
    "type": "pre-check",
    "sequence": 3,
    "enabled": true,
    "search_config": {
        "search_term": ["CompetitorA", "CompetitorB"],
        "pass_condition": "not_found"
    },
    "on_fail": {
        "status": "REVIEW",
        "description": "Video mentions competitors"
    }
}
```

Upload to S3 at `compliance_config/competitor_check.json` and it will run automatically!

## Execution Order

Pre-checks execute in order by their `sequence` field (lower numbers first). Best practices:

1. **Use increments of 10** (10, 20, 30) to allow inserting checks later without renumbering
2. **Fast checks first** - Simple term matching before complex logic
3. **Blocking checks early** - Content relevance (sequence=1) before profanity (sequence=2)
4. **Review-level checks last** - Less critical checks run after blockers

Example ordering:
- `sequence: 1` - Content relevance (BLOCK if irrelevant)
- `sequence: 2` - Profanity check (BLOCK if found)
- `sequence: 3` - Competitor mentions (REVIEW if found)
- `sequence: 4` - Brand guidelines (REVIEW if violated)

## Performance Considerations

- Pre-checks use lexical search (fast substring matching)
- Each check searches the entire transcription
- Failed checks skip the expensive Pegasus analysis
- Use pre-checks to filter out obvious failures early
