# Jockey Configuration Parameters

## Overview

The Jockey orchestration system now properly implements and uses the configuration parameters for controlling search and analysis behavior.

## Configuration Parameters

### `max_segments_per_query`

**Purpose:** Limits the maximum number of video segments that can be analyzed per query.

**Default:** 10

**Range:** 1-50

**How it's used:**
- Passed to the `Planner` component during initialization
- Acts as a hard cap on the `max_segments` value that Claude suggests in the execution plan
- If Claude suggests analyzing more segments than this limit, it's automatically capped

**Example:**
```yaml
jockey:
  max_segments_per_query: 10  # Analyze at most 10 segments per query
```

**Tuning guidance:**
- **Lower values (5-8):** Faster execution, lower costs, suitable for simple queries
- **Medium values (10-15):** Balanced performance, good for most use cases
- **Higher values (20-50):** More comprehensive analysis, higher costs, for complex queries

### `max_search_results`

**Purpose:** Limits the maximum number of search results retrieved from Marengo per search query.

**Default:** 15

**Range:** 1-100

**How it's used:**
- Passed to the `MarengoWorker` component during initialization
- Controls the `top_k` parameter when searching for relevant video segments
- Helps manage API costs and processing time

**Example:**
```yaml
jockey:
  max_search_results: 15  # Retrieve at most 15 results per search query
```

**Tuning guidance:**
- **Lower values (5-10):** Faster searches, lower costs, may miss relevant content
- **Medium values (15-20):** Balanced coverage, good for most use cases
- **Higher values (30-100):** More comprehensive search, higher costs, better recall

## Implementation Details

### Component Flow

1. **Orchestrator** reads config values and passes them to components:
   ```python
   planner = Planner(
       bedrock_client, 
       claude_model_id,
       max_segments_limit=config.jockey.max_segments_per_query
   )
   
   marengo_worker = MarengoWorker(
       search_service,
       max_results_per_query=config.jockey.max_search_results
   )
   ```

2. **Planner** caps Claude's suggested `max_segments`:
   - Claude suggests a value based on query complexity
   - Planner enforces the configured limit
   - Logs when capping occurs

3. **MarengoWorker** limits search results:
   - Uses `min(max_results_per_query, max_segments * 2)` for each query
   - Ensures we don't retrieve more results than needed
   - Helps with deduplication and ranking

### Code Locations

- **Config definition:** `backend/src/config.py` - `JockeyConfig` class
- **Orchestrator:** `backend/src/orchestration/orchestrator.py` - `__init__` method
- **Planner:** `backend/src/orchestration/planner.py` - `__init__` and `_parse_execution_plan`
- **MarengoWorker:** `backend/src/orchestration/marengo_worker.py` - `__init__` and `search_segments`

## Production Tuning Recommendations

### High Accuracy Configuration
```yaml
jockey:
  max_segments_per_query: 15
  max_search_results: 20
```
- Best for: Complex queries requiring comprehensive analysis
- Trade-off: Higher costs, longer execution time

### Cost Optimized Configuration
```yaml
jockey:
  max_segments_per_query: 5
  max_search_results: 10
```
- Best for: Simple queries, budget-conscious deployments
- Trade-off: May miss some relevant content

### Balanced Configuration (Default)
```yaml
jockey:
  max_segments_per_query: 10
  max_search_results: 15
```
- Best for: Most use cases
- Trade-off: Good balance between cost and quality

## Testing

Updated test files to pass the new parameters:
- `backend/tests/unit/test_planner.py`
- `backend/tests/unit/test_marengo_worker.py`

Run tests to verify:
```bash
cd backend
pytest tests/unit/test_planner.py tests/unit/test_marengo_worker.py -v
```

## Migration Notes

No migration needed - these parameters were already in the config files but weren't being used. The implementation now properly enforces them.

Existing config files will continue to work with the new implementation.
