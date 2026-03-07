# Search Term Configuration Examples

The `search_term` field in compliance config files supports both single and multiple alternative search terms.

## Single Term (Original Behavior)

```json
{
  "search_config": {
    "search_term": "{product_line}"
  }
}
```

This searches for an exact match of the product line in transcriptions.

## Multiple Alternative Terms (OR Logic)

```json
{
  "search_config": {
    "search_term": [
      "{product_line}",
      "{product_line} Pro",
      "{product_line} Plus"
    ]
  }
}
```

This searches for ANY of the terms in the array. If any term is found, the check passes.

## Common Use Cases

### Product Name Variations
```json
{
  "search_term": [
    "Product X",
    "Product-X",
    "ProductX",
    "Product X Pro"
  ]
}
```

### Brand Names with Abbreviations
```json
{
  "search_term": [
    "{company}",
    "ACME",
    "ACME Corp"
  ]
}
```

### Technical Terms with Alternatives
```json
{
  "search_term": [
    "artificial intelligence",
    "AI",
    "machine learning",
    "ML"
  ]
}
```

## How It Works

- **Single string**: Performs a case-insensitive substring match
- **Array of strings**: Checks each term with OR logic - any match counts as success
- **Placeholders**: All terms support `{product_line}`, `{company}`, etc. from compliance_params.json
- **Matching**: Case-insensitive, substring matching (e.g., "AI" matches "AI technology")
