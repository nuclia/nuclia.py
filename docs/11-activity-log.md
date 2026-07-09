# Query & download activity logs

Activity originating at Nucliadb (like searches or questions) is stored on the activity log. You can either query it for instant paginated results, or request an asynchronous download of the full result set.

Downloads are asynchronous: you request a query, a file is prepared, and you either wait, poll for status, or get notified via email when it's ready.

## Query Parameters

| Parameter | Description |
|-----------|-------------|
| `year_month` | Year and month of logs to retrieve (e.g., `2024-02`) |
| `show` | Fields to display in the output (`id` is always included) |
| `filters` | Filter criteria (see operators below) |
| `pagination` | Control result size and cursor position |

### Filter Operators

| Operator | Description |
|----------|-------------|
| `eq` | Equal to |
| `gt` / `ge` | Greater than / Greater than or equal to |
| `lt` / `le` | Less than / Less than or equal to |
| `ne` | Not equal to |
| `isnull` | Check for null (`True`/`False`) |
| `like` | SQL-like pattern (string fields only) |
| `ilike` | Case-insensitive SQL-like pattern (string fields only) |
| `isin` | Value is in a given list |
| `isnotin` | Value is not in a given list |

### Pagination

| Parameter | Description |
|-----------|-------------|
| `limit` | Number of items to fetch |
| `starting_after` | Fetch logs after a specific ID (ascending) |
| `ending_before` | Fetch logs before a specific ID (descending) |

## Available Fields

### Common Fields (All Event Types)

`id`, `date`, `user_id`, `user_type`, `client_type`, `total_duration`, `audit_metadata`, `resource_id`, `nuclia_tokens`, `token_details`

### SEARCH Events

Common fields + `question`, `resources_count`, `filter`, `retrieval_rephrased_question`, `vectorset`, `security`, `min_score_bm25`, `min_score_semantic`, `result_per_page`, `retrieval_time`

### CHAT Events

Common fields + `question`, `answer`, `rephrased_question`, `learning_id`, `retrieved_context`, `chat_history`, `feedback_good`, `feedback_comment`, `feedback_good_all`, `feedback_good_any`, `feedback`, `model`, `rag_strategies_names`, `rag_strategies`, `status`, `generative_answer_first_chunk_time`, `generative_reasoning_first_chunk_time`, `generative_answer_time`, `remi_scores`, `user_request`, `reasoning`

### ASK Events

All SEARCH fields + all CHAT fields.

## Query Examples

### CLI

```bash
nuclia kb logs query --type=ASK --query='{
  "year_month": "2024-10",
  "show": ["id", "date", "question", "answer", "feedback_good"],
  "filters": {
    "question": {"ilike": "user question"},
    "feedback_good": {"eq": true}
  },
  "pagination": {"limit": 10}
}'
```

### SDK

```python
from nuclia import sdk
from nuclia_models.events.activity_logs import ActivityLogsAskQuery, EventType, Pagination

kb = sdk.NucliaKB()
query = ActivityLogsAskQuery(
    year_month="2024-10",
    show=["id", "date", "question", "answer"],
    filters={
        "question": {"ilike": "user question"},
        "feedback_good": {"eq": True}
    },
    pagination=Pagination(limit=10)
)
kb.logs.query(type=EventType.ASK, query=query)
```

### Filtering by list values

Use `isin` or `isnotin`:

```python
filters={"answer": {"isin": ["alpha", "gamma"]}}
```

### Filtering by `audit_metadata`

`audit_metadata` is a customizable dictionary. Use the `key` operator to target specific keys:

```python
query = ActivityLogsAskQuery(
    year_month="2024-10",
    show=["audit_metadata.environment"],
    filters={
        "audit_metadata": [{"key": "environment", "eq": "prod"}]
    },
    pagination=Pagination(limit=10)
)
```

## Download

### CLI

```bash
# Wait for the download URL to be generated (blocking)
nuclia kb logs download --wait --type=ASK --format=NDJSON --query='{
  "year_month": "2024-10",
  "show": ["id", "date", "question", "answer", "feedback_good"],
  "filters": {"question": {"ilike": "user question"}}
}'

# Request download and get notified via email
nuclia kb logs download --type=ASK --format=NDJSON --query='{
  "year_month": "2024-10",
  "show": ["id", "date", "question", "answer"],
  "notify_via_email": true,
  "email_address": "address@foo.com"
}'

# Poll for status manually
nuclia kb logs download_status <request_id>
```

### SDK

```python
from nuclia import sdk
from nuclia_models.events.activity_logs import (
    DownloadActivityLogsAskQuery, DownloadFormat, EventType,
)

kb = sdk.NucliaKB()
query = DownloadActivityLogsAskQuery(
    year_month="2024-10",
    show=["id", "date", "question", "answer"],
    filters={
        "question": {"ilike": "user question"},
        "feedback_good": {"eq": True}
    },
)
request = kb.logs.download(
    type=EventType.ASK, query=query, download_format=DownloadFormat.NDJSON, wait=True
)
print(request.download_url)
```

---

## REMi

The REMi module monitors the quality of your RAG pipeline. Use it to query logs by REMi scores and track score evolution over time.

### Query

Retrieve ask activity logs matching REMi score criteria.

#### CLI

```bash
nuclia kb remi query --query='{
    "month": "2024-11",
    "context_relevance": {
        "value": 0,
        "operation": "gt",
        "aggregation": "average"
    }
}'
```

#### SDK

```python
from nuclia import sdk
from nuclia_models.events.remi import RemiQuery, ContextRelevanceQuery

kb = sdk.NucliaKB()
kb.remi.query(
    query=RemiQuery(
        month="2024-11",
        context_relevance=ContextRelevanceQuery(
            value=0, operation="gt", aggregation="average"
        ),
    )
)
```

Optional filters: `feedback_good` (bool) and `status` (`NO_CONTEXT`, `ERROR`, `SUCCESS`):

```python
from nuclia_models.events.remi import RemiQuery, ContextRelevanceQuery, Status

kb.remi.query(
    query=RemiQuery(
        month="2024-11",
        context_relevance=ContextRelevanceQuery(value=0, operation="gt", aggregation="average"),
        feedback_good=True,
        status=Status.SUCCESS,
    )
)
```

### Get Event

Fetch full context and score details for a specific event (from a previous query result):

```bash
nuclia kb remi get_event --event_id=16987522
```

```python
kb.remi.get_event(event_id=16987522)
```

### Get Scores

Retrieve REMi score progression over time, aggregated by `day`, `week`, or `month`:

```bash
nuclia kb remi get_scores --starting_at=2024-05-01 --to=None --aggregation=day
```

```python
from nuclia_models.common.utils import Aggregation
from datetime import datetime

output = kb.remi.get_scores(
    starting_at=datetime(year=2024, month=5, day=1),
    to=None,
    aggregation=Aggregation.DAY,
)
```
