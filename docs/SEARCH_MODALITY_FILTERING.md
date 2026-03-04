# Search Modality Filtering

## Overview

The Marengo search API now supports filtering by modality, allowing you to limit searches to specific content types: visual, audio, or transcription (speech).

## Feature Description

When performing a search, you can now select which modalities to include:

- **Visual**: Searches visual content including actions, objects, events, on-screen text (OCR), and brand logos
- **Audio**: Searches non-speech audio including music, sound effects, and ambient sounds
- **Transcription**: Searches spoken words and conversations in the video

## User Interface

The search interface includes three checkboxes to control which modalities are searched:

```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 Search videos with natural language...                   │
└─────────────────────────────────────────────────────────────┘

[Add Image]  filename.jpg (123.4 KB)              Results: [5 ▼]

Search in:  ☑ Visual  ☑ Audio  ☑ Transcription

┌─────────────────────────────────────────────────────────────┐
│                         Search                               │
└─────────────────────────────────────────────────────────────┘
```

- All three modalities are enabled by default
- At least one modality must be selected for the search button to be enabled
- Unchecking all modalities will disable the search button

### Search Button Validation

| Query | Image | Visual | Audio | Transcription | Button State |
|-------|-------|--------|-------|---------------|--------------|
| "car" | No    | ☑      | ☑     | ☑             | ✅ Enabled   |
| "car" | No    | ☑      | ☐     | ☐             | ✅ Enabled   |
| "car" | No    | ☐      | ☐     | ☐             | ❌ Disabled  |
| ""    | No    | ☑      | ☑     | ☑             | ❌ Disabled  |
| ""    | Yes   | ☑      | ☑     | ☑             | ✅ Enabled   |
| ""    | Yes   | ☐      | ☐     | ☐             | ❌ Disabled  |

## Use Cases

### Visual-Only Search
Uncheck Audio and Transcription to search only for visual content:
- Finding scenes with specific objects: "red car in parking lot"
- Locating on-screen text: "company logo on building"
- Identifying actions: "person running"

### Audio-Only Search
Uncheck Visual and Transcription to search only for non-speech audio:
- Finding background music: "upbeat electronic music"
- Locating sound effects: "door slamming"
- Identifying ambient sounds: "rainfall"

### Transcription-Only Search
Uncheck Visual and Audio to search only spoken content:
- Finding mentions of topics: "climate change discussion"
- Locating product names: "iPhone 15 Pro Max"
- Identifying speakers discussing concepts: "quarterly revenue growth"

### Combined Modalities
Keep multiple modalities checked to search across them:
- Visual + Transcription: Find scenes where something is shown AND discussed
- Audio + Transcription: Find music playing while someone talks about it
- All three: Comprehensive search across all content types (default)

## Tips for Best Results

1. **Visual-only searches** work best for:
   - Object detection: "red car", "laptop on desk"
   - Scene identification: "outdoor park", "office interior"
   - Text recognition: "company logo", "street sign"

2. **Audio-only searches** work best for:
   - Music identification: "jazz music", "electronic beats"
   - Sound effects: "door closing", "rain sounds"
   - Ambient audio: "crowd noise", "traffic sounds"

3. **Transcription-only searches** work best for:
   - Topic discussions: "climate change", "artificial intelligence"
   - Product mentions: "iPhone 15", "Tesla Model 3"
   - Specific phrases: "quarterly revenue", "market analysis"

4. **Combined searches** work best for:
   - Contextual matching: Find where something is both shown and discussed
   - Comprehensive results: Cast a wider net across multiple modalities
   - Verification: Ensure visual and verbal content align

## API Reference

### Request Examples

**All Modalities (Default)**
```json
{
  "index_id": "index-123",
  "query": "person walking",
  "top_k": 10
}
```

**Visual Only**
```json
{
  "index_id": "index-123",
  "query": "red car",
  "top_k": 10,
  "search_options": ["visual"]
}
```

**Transcription Only**
```json
{
  "index_id": "index-123",
  "query": "quarterly earnings",
  "top_k": 10,
  "search_options": ["transcription"]
}
```

**Visual + Transcription**
```json
{
  "index_id": "index-123",
  "query": "iPhone demonstration",
  "top_k": 10,
  "search_options": ["visual", "transcription"]
}
```

### Implementation Details

### Backend

**SearchRequest Model** (`backend/src/api/search.py`):
- Added `search_options` field: Optional list of strings (visual, audio, transcription)
- Validates that at least one modality is selected if provided
- Validates that only valid modality names are used

**SearchService** (`backend/src/services/search_service.py`):
- Added `search_options` parameter to `search_videos()` method
- Passes search_options to Bedrock client for embedding generation

**BedrockClient** (`backend/src/aws/bedrock_client.py`):
- Added `search_options` parameter to `invoke_marengo_multimodal_embedding()` method
- Includes `searchOptions` in the Marengo API request body when provided

### Frontend

**Types** (`frontend/src/types/index.ts`):
- Added `SearchModality` type: 'visual' | 'audio' | 'transcription'
- Added `SearchModalities` interface for checkbox state management

**SearchBar Component** (`frontend/src/components/Search/SearchBar.tsx`):
- Added modality checkboxes with state management
- Disables search button when no modalities are selected
- Passes selected modalities to search function

**API Service** (`frontend/src/services/api.ts`):
- Added `searchOptions` parameter to `searchVideos()` function
- Includes `search_options` in API request body

**useSearch Hook** (`frontend/src/hooks/useSearch.ts`):
- Added `searchOptions` parameter to `search()` function
- Passes search options through to API service

## Technical Details

### Marengo 3.0 API

The feature uses Marengo 3.0's `searchOptions` parameter in the embedding request:

```json
{
  "inputType": "text",
  "text": {
    "inputText": "person walking"
  },
  "searchOptions": ["visual", "transcription"]
}
```

### Default Behavior

When `search_options` is not provided (or is `null`), the Marengo API uses all available modalities by default, maintaining backward compatibility with existing code.

## Testing

### Frontend Tests

Updated `SearchBar.test.tsx` to include:
- Test for disabled search button when no modalities selected
- Test for including only selected modalities in search call

### Backend Tests

Existing tests continue to work as `search_options` is an optional parameter with backward-compatible defaults.

## Migration Guide

### For Existing Code

No changes required. The feature is backward compatible:
- Existing search calls without `search_options` will search all modalities (default behavior)
- The UI defaults to all modalities checked

### For New Implementations

To use modality filtering:

**Frontend:**
```typescript
const selectedModalities = ['visual', 'transcription'];
await search(indexId, query, topK, imageFile, selectedModalities);
```

**Backend API:**
```python
{
  "index_id": "index-123",
  "query": "person walking",
  "search_options": ["visual", "transcription"]
}
```

## References

- [TwelveLabs Modalities Documentation](https://docs.twelvelabs.io/docs/model-options)
- Marengo 3.0 API separates audio into speech (transcription) and non-speech (audio) content
