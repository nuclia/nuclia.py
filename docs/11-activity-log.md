# Query & download activity logs

Activity originating at Nucliadb (like searches or questions) is stored on the activity log so you can query it. Depending on the data and format that you want to retrieve you can either query and get instant results or ask for a download to be prepared for you.

How the query is performed is exactly the same, the only difference is on the pagination, that for downloads you'll get the full results of the query.

Downloads are asyncronous, so by using the download feature, you request a query to be done, and a file will be prepared to download, You can choose either to be notified via email when the download is ready, or poll for the download status.

See the examples for more information


### Query Parameters

1. `year_month`: Specify the year and month of logs to retrieve (e.g., `2024-02`).
2. `show`: List fields to display in the output (Note: `id` is always displayed).
3. `filters`: Apply filters using these operators:
   - `eq`: Equal to (`=`)
   - `gt`: Greater than (`>`)
   - `ge`: Greater than or equal to (`>=`)
   - `lt`: Less than (`<`)
   - `le`: Less than or equal to (`<=`)
   - `ne`: Not equal to (`!=`)
   - `isnull`: Check for null (`True`/`False`)
   - `like`: SQL-like operator (string fields only)
   - `ilike`: Case-insensitive SQL-like operator (string fields only)
4. `pagination`: Control the number of logs retrieved:
   - `limit`: Number of items to fetch
   - `starting_after`: Fetch logs after a specific ID (ascending order)
   - `ending_before`: Fetch logs before a specific ID (descending order)

### Available Fields

#### Common Fields (All Event Types)
- `id`, `date`, `user_id`, `user_type`, `client_type`, `total_duration`, `audit_metadata`

#### Event-Specific Fields
- `SEARCH` events: Common fields + `question`, `resources_count`, `filter`, `learning_id`
- `CHAT` events: Common fields + Search fields + `rephrased_question`, `answer`, `retrieved_context`, `chat_history`, `feedback_good`, `feedback_comment`, `model`, `rag_strategies_names`, `rag_strategies`, `status`, `time_to_first_char`


### Query Examples

#### CLI Example

```bash
nuclia kb logs query --type=CHAT --query='{
  "year_month": "2024-10",
  "show": ["id", "date", "question", "answer", "feedback_good"],
  "filters": {
    "question": {"ilike": "user question"},
    "feedback_good": {"eq": true}
  },
  "pagination": {"limit": 10}
}'
```

#### SDK Example

```python
from nuclia import sdk
from nuclia.lib.kb import LogType
from nuclia_models.events.activity_logs import ActivityLogsChatQuery, Pagination

kb = sdk.NucliaKB()
query = ActivityLogsChatQuery(
    year_month="2024-10",
    show=["id", "date", "question", "answer"],
    filters={
        "question": {"ilike": "user question"},
        "feedback_good": {"eq": True}
    },
    pagination=Pagination(limit=10)
)
kb.logs.query(type=LogType.CHAT, query=query)
```
### Special Field: `audit_metadata`
The `audit_metadata` field is a customizable dictionary. Use the `key` operator to target specific keys within the dictionary.

#### Example to filter by `audit_metadata`:

```json
{
  "year_month": "2024-10",
  "show": ["audit_metadata.environment"],
  "filters": {
    "audit_metadata": [
      {
        "key": "environment",
        "eq": "prod"
      }
    ]
  },
  "pagination": {
    "limit": 10
  }
}
```

### Download Examples

#### CLI Examples

Request download and wait until the download url is generated

```bash
>>> nuclia kb logs download --wait --type=CHAT --format=NDJSON --query='{
  "year_month": "2024-10",
  "show": ["id", "date", "question", "answer", "feedback_good"],
  "filters": {
    "question": {"ilike": "user question"},
    "feedback_good": {"eq": true}
  },
}'

(...)
request_id='dcbb6da6-92c0-11ef-8450-36cf85ca1604'
download_url=https://your-download-url
```

Request download and ask to be notified
```bash
>>> nuclia kb logs download --type=CHAT --format=NDJSON --query='{
  "year_month": "2024-10",
  "show": ["id", "date", "question", "answer", "feedback_good"],
  "filters": {
    "question": {"ilike": "user question"},
    "feedback_good": {"eq": true}
  },
  "notify_via_email": true,
  "email_address": "address@foo.com"
}'

(...)
request_id='dcbb6da6-92c0-11ef-8450-36cf85ca1604'
download_url=null
```
Request download and poll for the status
```bash
>>> nuclia kb logs download --type=CHAT --format=NDJSON --query='{
  "year_month": "2024-10",
  "show": ["id", "date", "question", "answer", "feedback_good"],
  "filters": {
    "question": {"ilike": "user question"},
    "feedback_good": {"eq": true}
  },
}'

(...)
request_id='dcbb6da6-92c0-11ef-8450-36cf85ca1604'
download_url=null

>>> nuclia kb logs download_status dcbb6da6-92c0-11ef-8450-36cf85ca1604
(...)
request_id='dcbb6da6-92c0-11ef-8450-36cf85ca1604'
download_url=https://your-download-url
```

#### SDK Example

```python
from nuclia import sdk
from nuclia.lib.kb import LogType
from nuclia_models.events.activity_logs import DownloadActivityLogsChatQuery

kb = sdk.NucliaKB()
query = DownloadActivityLogsChatQuery(
    year_month="2024-10",
    show=["id", "date", "question", "answer"],
    filters={
        "question": {"ilike": "user question"},
        "feedback_good": {"eq": True}
    },
)
request = kb.logs.download(type=LogType.CHAT, query=query, wait=True)
return request.download_url
```


## REMi

The REMi module provides tools to monitor the quality of your RAG pipeline to get the best answers. Use these commands to query logs with REMi data and monitor score evolution over time.

## REMi Query

Use `remi query` to retrieve a list of chat activity logs that match specified criteria for REMi scores.

### Basic Query

Retrieve logs for a specific month and apply context relevance filters.

#### CLI Example
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

#### SDK Example
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

---

### Filtering by Feedback

Further refine the query to include only logs with positive (or negative) feedback.

#### CLI Example
```bash
nuclia kb remi query --query='{
    "month": "2024-11",
    "context_relevance": {
        "value": 0,
        "operation": "gt",
        "aggregation": "average"
    },
    "feedback_good": true
}'
```

#### SDK Example
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
        feedback_good=True
    )
)
```

---

### Filtering by Model Status

Filter logs by REMi model status. Available status options are `NO_CONTEXT`, `ERROR`, and `SUCCESS`.

#### CLI Example
```bash
nuclia kb remi query --query='{
    "month": "2024-11",
    "status": "NO_CONTEXT"
}'
```

#### SDK Example
```python
from nuclia import sdk
from nuclia_models.events.remi import RemiQuery, Status

kb = sdk.NucliaKB()
kb.remi.query(
    query=RemiQuery(
        month="2024-11",
        status=Status.NO_CONTEXT
    )
)
```

---

### REMi Get

Use `remi get_event` to fetch detailed information for a specific chat activity log. This command is useful for retrieving full context and score details of an entry obtained from a previous REMi query.

#### CLI Example
```bash
nuclia kb remi get_event --event_id=16987522
```

#### SDK Example
```python
from nuclia import sdk

kb = sdk.NucliaKB()
kb.remi.get_event(event_id=16987522)
```

---

### REMi Scores

Use `remi get_scores` to retrieve the progression of REMi scores over a specified time period, with options to aggregate scores by day, month, or other intervals.

#### CLI Example
```bash
nuclia kb remi get_scores --starting_at=2024-05-01 --to=None --aggregation=day
```

#### SDK Example
```python
from nuclia import sdk
from nuclia_models.common.utils import Aggregation
from datetime import datetime

kb = sdk.NucliaKB()
output2 = kb.remi.get_scores(
    starting_at=datetime(year=2024, month=5, day=1),
    to=None,
    aggregation=Aggregation.DAY,
)
```
