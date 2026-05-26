# Memory

Nuclia Memory provides persistent, queryable memory for AI agents backed by Nuclia KnowledgeBoxes.

## Core Concepts

- **Memory**: A memory instance maps to a Nuclia KnowledgeBox. It stores and retrieves discrete units of information.
- **topic**: A discrete unit of memory stored as a Nuclia resource. Each topic has a unique ID, an optional slug, a title, and one or more content fields.
- **Annotation**: A conversational note attached to an topic by a specific user. Annotations are stored as conversation fields on the resource.
- **Recall**: A generative query that returns an AI-generated answer grounded in stored topics.
- **Retrieve**: A semantic search that returns matching topics without generating an answer.

## Usage

### Setup

```python
from nuclia import sdk

memory = sdk.NucliaMemory()
```

### Storing information (`remember`)

Store a new topic:

```python
topic_id = memory.remember("The deployment uses GitHub Actions.")
```

Store with a title and slug:

```python
topic_id = memory.remember(
    "The deployment uses GitHub Actions.",
    title="Deployment process",
    slug="deployment-process",
)
```

Append content to an existing topic:

```python
memory.remember(
    "Rollbacks are handled via git revert.",
    topic="deployment-process",
)
```

### Querying memory (`recall`)

Ask a question and get a generative answer grounded in stored topics:

```python
result = memory.recall("How does deployment work?")
print(result.answer)
# "The deployment uses GitHub Actions. Rollbacks are handled via git revert."
```

Scope the answer to a specific topic:

```python
result = memory.recall("How does deployment work?", topic="deployment-process")
```

### Semantic search (`retrieve`)

Return matching topics without generating an answer:

```python
results = memory.retrieve("deployment")
for r in results:
    print(r.title, r.score, r.text)
```

### Annotating topics (`annotate`)

Append a note to an existing topic:

```python
memory.annotate(topic="deployment-process", text="Confirmed with the team on 2025-01-15.")
```

Specify the author:

```python
memory.annotate(
    topic="deployment-process",
    text="Needs review after next sprint.",
    who="alice",
)
```

### Deleting (`forget`)

Delete a single topic:

```python
memory.forget(topic="deployment-process")
```

Delete a specific annotation:

```python
memory.forget(topic="deployment-process", annotation="annotation-0", who="alice")
```

Delete all annotations by a user on an topic:

```python
memory.forget(topic="deployment-process", annotations=True, who="alice")
```

Delete the entire memory (destructive — requires confirmation):

```python
memory.forget(all=True, confirm=True)
```

### Listing topics (`list`)

```python
page = memory.list(query="deployment", page=0, size=10)
for topic in page.items:
    print(topic.id, topic.title)
print(f"Total: {page.total}, Has next: {page.has_next}")
```

## Data Models

| Class | Description |
|-------|-------------|
| `topic` | A discrete unit of memory (id, slug, title, summary, annotations). |
| `Annotation` | A single annotation message (ident, timestamp, text, who). |
| `RecallResult` | Result of a generative recall (answer, topics, citations). |
| `RetrieveResult` | A single hit from semantic retrieve (id, slug, title, score, text, field). |
| `topicPage` | Paginated listing of topics (items, total, has_next). |

## Async

An async version is available:

```python
from nuclia import sdk

memory = sdk.AsyncNucliaMemory()

topic_id = await memory.remember("The deployment uses GitHub Actions.")
result = await memory.recall("How does deployment work?")
print(result.answer)
```