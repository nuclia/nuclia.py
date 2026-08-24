# NucliaMemory

`NucliaMemory` is a high-level SDK component that turns any Nuclia Knowledge Box into a **personalised, multi-session memory store**. It lets you:

- Organise knowledge into **resources** (discrete memory domains backed by KB resources).
- Attach **entries** (annotated observations, decisions, or notes) to resources on behalf of specific sessions.
- Automatically extract distilled **facts** and a **knowledge graph** from each entry via a background data-augmentation task.
- **Recall** grounded, personalised answers for any session without mixing up other sessions' context.

All examples assume you have [authenticated](02-auth.md) and set a [default Knowledge Box](03-kb.md).

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Resource** | A named memory domain stored as a KB resource. It can contain reference documents (policy text, guidelines, etc.) and collects the entries of all sessions. |
| **Entry** | A timestamped text entry belonging to a resource. It records any content to be remembered. For example, decisions, observations, or conversation transcripts. It may also contain optional `reasoning`, `context` messages, and structured `metadata`. |
| **Fact** | A short, distilled statement automatically extracted from an entry by the Memory data augmentation task. Facts act as a compressed, searchable index of entries. |
| **Graph** | An entity–relation graph extracted from both the resource's reference content and a session's entries, giving a personalised knowledge graph view. |
| **Global entry** | An entry not tied to any specific resource. Stored under a per-session resource. Useful for cross-resource or agent-level memory. |

---

## Initializing Memory

Before using `NucliaMemory` you must call `initialize()` once per Knowledge Box. This registers the background task that extracts facts and knowledge graphs from new entries.

```python
from nuclia.sdk.memory import NucliaMemory

memory = NucliaMemory()
memory.initialize()
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rules` | `list[str] \| None` | `None` | Custom rules for the fact-extraction task (e.g. formatting constraints, additional context, restrictions). |
| `graph_extraction` | `bool \| None` | `True` | Whether to extract a knowledge graph from the generated facts. |
| `entity_defs` | `list[EntityDefinition] \| None` | `None` | Custom entity type definitions for the graph extractor. |
| `examples` | `list[GraphExtractionExample] \| None` | `None` | Few-shot examples to guide graph extraction. |
| `llm_config` | `LLMConfig \| None` | `None` | Override the LLM used for extraction. |
| `overwrite` | `bool` | `False` | If `True`, replace an existing task configuration with the new one. |

```python
from nuclia_models.worker.proto import LLMConfig
from nuclia.sdk.memory import NucliaMemory

memory = NucliaMemory()
memory.initialize(
    rules=[
        "Facts must be self-contained and reference the employee ID where available.",
        "Do not include personal opinions — only verifiable actions and decisions.",
    ],
    graph_extraction=True,
    llm_config=LLMConfig(generative_model="claude-4-6-sonnet")
    overwrite=False,
)
```

### CLI

```bash
nuclia memory initialize
nuclia memory initialize --rules='["Facts must be objective."]' --graph_extraction=true
```

---

## Managing Resources

### Create a resource

Resources are the named memory domains. Create one before writing entries to it.

```python
resource_id = memory.create_resource(
    title="Vacation Policy",
    slug="vacation-policy",          # optional; auto-generated from title if omitted
    summary="Rules governing PTO.",  # optional
    texts={"policy": "...full policy text..."},  # optional reference documents
)
```

You can also attach remote URLs or local files as reference content:

```python
memory.create_resource(
    title="Employee Handbook",
    urls={"handbook": "https://example.com/handbook.pdf"},
)

memory.create_resource(
    title="Onboarding Guide",
    file_paths={"guide": "/path/to/onboarding.pdf"},
)
```

Raises `ResourceAlreadyExistsError` if the slug already exists.

#### CLI

```bash
nuclia memory create_resource --title="Vacation Policy" --slug=vacation-policy
```

---

### Get a resource

```python
from nuclia.sdk.memory import NucliaMemory, ResourceNotFoundError

memory = NucliaMemory()
try:
    resource = memory.get_resource(resource="vacation-policy")
    print(resource.id, resource.title, resource.status)
except ResourceNotFoundError:
    print("Resource not found")
```

**`Resource` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID of the resource. |
| `slug` | `str` | URL-friendly identifier. |
| `title` | `str` | Human-readable title. |
| `summary` | `str \| None` | Short description. |
| `status` | `str` | Processing status (`"processed"`, `"pending"`, `"error"`, …). |

#### CLI

```bash
nuclia memory get_resource --resource=vacation-policy
```

---

### List resources

```python
page = memory.list_resources(query="policy", page=0, size=10)

print(f"Total resources: {page.total}")
for resource in page.items:
    print(f"  {resource.slug}: {resource.title}")
```

**`ResourcePage` fields:** `items`, `total`, `has_more`.

#### CLI

```bash
nuclia memory list_resources
nuclia memory list_resources --query=policy --page=0 --size=10
```

---

### Update a resource

```python
memory.update_resource(
    "vacation-policy",
    title="PTO & Vacation Policy",
    texts={"policy": "...updated text..."},
)
```

#### CLI

```bash
nuclia memory update_resource vacation-policy --title="PTO & Vacation Policy"
```

---

### Delete a resource

```python
memory.delete_resource("vacation-policy", confirm=True)
```

> ⚠️ `confirm=True` is required. This permanently deletes the resource and all its entries.

#### CLI

```bash
nuclia memory delete_resource vacation-policy --confirm=true
```

---

### List sessions per resource

Returns the list of session IDs that have at least one entry in a given resource. This is useful for serverless or stateless workloads where you don't keep a local registry of which sessions exist.

```python
sessions = memory.list_sessions(resource="vacation-policy")
print(sessions)
# ["alice-hr", "bob-hr"]
```

#### List all sessions with global entries

Omit `resource` to get every session that has created at least one global (cross-resource) entry:

```python
sessions = memory.list_sessions()
print(sessions)
# ["agent-session-abc123", "agent-session-xyz789", ...]
```

This call paginates through the KB catalog automatically, so it works correctly even when there are a large number of sessions.

> **Note:** A session ID will only appear in the result if the corresponding field or resource still exists. Users whose entries were fully deleted via `forget_entries()` will not be listed.

#### Error handling

`ResourceNotFoundError` is raised if the given resource does not exist:

```python
from nuclia.sdk.memory import NucliaMemory, ResourceNotFoundError

memory = NucliaMemory()

try:
    sessions = memory.list_sessions(resource="non-existent-resource")
except ResourceNotFoundError:
    print("Resource does not exist.")
```

#### Async

```python
sessions = await memory.list_sessions(resource="vacation-policy")
sessions = await memory.list_sessions()  # global entries
```

#### CLI

```bash
nuclia memory list_sessions --resource=vacation-policy
nuclia memory list_sessions
```

---

## Writing Entries

`remember()` writes a timestamped entry for a session on a resource. The background task automatically distils a fact and updates the knowledge graph.

### Resource-scoped entry

```python
from nuclia.sdk.memory import EntryContextMessage, NucliaMemory

memory = NucliaMemory()

memory.remember(
    text="Approved carry-over exception for Maria (EMP-1042). "
         "She could not use 8 vacation days due to a Q4 product launch.",
    resource="vacation-policy",
    session_id="alice-hr",
    entry_id="alice-entry-001",          # optional; random ID used if omitted
    reasoning="Business-critical event justified the exception.",
    context=[
        EntryContextMessage(
            author="Maria (employee)",
            text="I had 8 days remaining but the Q4 launch prevented me from taking them.",
        ),
        EntryContextMessage(
            author="Maria's manager",
            text="Confirmed — Maria's presence was essential during the entire Q4 period.",
        ),
    ],
    metadata={
        "employee_id": "EMP-1042",
        "department": "Engineering",
        "decision": "approved",
        "days_requested": 8,
    },
)
```

Raises `EntryAlreadyExistsError` if an entry with the same `entry_id` already exists for this session and resource.

### Global entry (not tied to a resource)

Omit `resource` to write a cross-resource or agent-level entry. Each session gets their own dedicated resource for global entries.

```python
memory.remember(
    text="User prefers concise, bullet-point answers.",
    session_id="agent-session-abc123",
)
```

### CLI

```bash
nuclia memory remember \
  --text="Approved carry-over for Maria (EMP-1042)" \
  --resource=vacation-policy \
  --session_id=alice-hr \
  --entry_id=alice-entry-001
```

### `EntryContextMessage` fields

| Field | Type | Description |
|-------|------|-------------|
| `author` | `str` | Name or role of the message author. |
| `text` | `str` | Message content. |

---

## Reading Entries and Facts

### List entries

Iterate over all entries written in a session for a resource:

```python
for entry in memory.entries(resource="vacation-policy", session_id="alice-hr"):
    print(f"[{entry.id}] {entry.timestamp}: {entry.content.text}")
```

List **global** entries (omit `resource`):

```python
for entry in memory.entries(session_id="agent-session-abc123"):
    print(entry.content.text)
```

Pass `recent_first=False` to get oldest entries first.

**`Entry` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Entry identifier. |
| `timestamp` | `datetime` | UTC creation time. |
| `content` | `EntryContent` | Structured content: `text`, `reasoning`, `context`, `metadata`. |

#### CLI

```bash
nuclia memory entries --resource=vacation-policy --session_id=alice-hr
nuclia memory entries --session_id=agent-session-abc123
```

---

### List extracted facts

After the background task runs, each entry is distilled into one or more short facts:

```python
for fact in memory.facts(resource="vacation-policy", session_id="alice-hr"):
    ts = fact.timestamp.strftime("%Y-%m-%d %H:%M")
    print(f"[{ts}] {fact.content.text}")
    if fact.content.related_entry_ids:
        print(f"  ← from entries: {fact.content.related_entry_ids}")
```

**`Fact` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Fact identifier. |
| `timestamp` | `datetime` | UTC extraction time. |
| `content` | `FactContent` | `text`, `reasoning`, `related_entry_ids`. |

#### CLI

```bash
nuclia memory facts --resource=vacation-policy --session_id=alice-hr
```

---

### Query the knowledge graph

Retrieve entity–relation paths extracted from the resource content and a session's entries:

```python
edges = memory.graph(resource="vacation-policy", session_id="alice-hr")
for edge in edges:
    print(
        f"{edge.source.value!r} --{edge.relation.label}--> {edge.destination.value!r}"
    )
```

#### CLI

```bash
nuclia memory graph --resource=vacation-policy --session_id=alice-hr
```

---

## Querying Memory

### Semantic retrieval (`recall`)

Returns a ranked list of relevant context blocks without generating an answer. Useful when you want to feed context into your own LLM pipeline.

```python
blocks = memory.recall(
    question="Has anyone ever approved a carry-over exception?",
    resource="vacation-policy",
    session_id="alice-hr",
    top_k=10,
)

for block in blocks:
    print(f"[score={block.score:.3f}] {block.text[:120]}")
```

**Returns:** `list[RelevantContextBlock]`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Paragraph identifier. |
| `text` | `str` | Text of the retrieved block. |
| `score` | `float` | Relevance score. |

#### CLI

```bash
nuclia memory recall \
  --question="Has anyone approved a carry-over exception?" \
  --resource=vacation-policy \
  --session_id=alice-hr
```

---

### Generative answer (`ask`)

Returns a grounded, personalised answer generated by an LLM over the resource and session's facts. This is the primary entry point for building memory-powered assistants.

Internally it builds a request to the `/ask` endpoint with a filter to only retrieve memories relevant to the provided session and resource

```python
from nuclia.sdk.memory import NucliaMemory

memory = NucliaMemory()

result = memory.ask(
    query="Have I ever approved a carry-over exception?",
    resource="vacation-policy",
    session_id="alice-hr",
)

print(result.answer)

for key, block in result.citations.items():
    print(f"  [{key}] (score={block.score:.3f}) {block.text[:80]}")
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | — | Natural-language question. |
| `resource` | `str` | — | Resource ID or slug to scope the answer to. |
| `session_id` | `str \| None` | `None` | User whose entries and facts are used for personalisation. |
| `context` | `list[ChatContextMessage] \| None` | `None` | Prior conversation messages (oldest first) to include as extra context. |
| `include_global_facts` | `bool` | `False` | Also include this sessions's global (cross-resource) facts in the context. |
| `extra_context` | `list[str] \| None` | `None` | Additional free-text snippets to inject into the prompt. |
| `custom_prompt` | `CustomPrompt \| None` | `None` | Override system, user, and/or rephrase prompt templates. |
| `ask_request_overrides` | `dict \| None` | `None` | Low-level overrides for the underlying `AskRequest`. |

**Returns:** `AskResult`

| Field | Type | Description |
|-------|------|-------------|
| `answer` | `str` | Generated answer text. |
| `citations` | `dict[str, RelevantContextBlock]` | Footnote-keyed map of source paragraphs used in the answer. |

#### Using a custom prompt

```python
from nucliadb_models.search import CustomPrompt

result = memory.ask(
    query="Have I approved any carry-over exceptions this year?",
    resource="vacation-policy",
    session_id="alice-hr",
    custom_prompt=CustomPrompt(
        system=(
            "You are an HR assistant helping {user_name} recall their own past decisions. "
            "All entries in the context were made BY {user_name}. "
            "Answer in the second person ('You approved…')."
        ),
        user=(
            "Context:\n\n{context}\n\n"
            "Answer this question on behalf of {user_name}: {question}"
        ),
    ),
)
```

#### Maintaining conversation history

Pass previous exchanges to maintain dialogue context across turns:

```python
from nucliadb_models.search import ChatContextMessage

history = [
    ChatContextMessage(author="user", text="Tell me about Maria's vacation exception."),
    ChatContextMessage(author="assistant", text="Alice approved 8 days for Maria in Q4."),
]

result = memory.ask(
    query="What was the reasoning behind that decision?",
    resource="vacation-policy",
    session_id="alice-hr",
    context=history,
)
```

#### CLI

```bash
nuclia memory ask \
  --query="Have I approved a carry-over exception?" \
  --resource=vacation-policy \
  --session_id=alice-hr
```

---

## Forgetting

### Delete a single entry

Deletes one entry and any facts derived solely from it.

```python
memory.forget_entry(session_id="alice-hr", entry_id="alice-entry-001", resource="vacation-policy")
```

Omit `resource` to delete from global entries.

#### CLI

```bash
nuclia memory forget_entry --session_id=alice-hr --entry_id=alice-entry-001 --resource=vacation-policy
```

---

### Delete all entries for a session on a resource

Deletes all entries in scope and also deletes the corresponding facts for that same scope.

```python
memory.forget_entries(session_id="alice-hr", resource="vacation-policy")
```

#### CLI

```bash
nuclia memory forget_entries --session_id=alice-hr --resource=vacation-policy
```

---

### Delete a single fact

```python
memory.forget_fact(session_id="alice-hr", fact_id="fact-xyz", resource="vacation-policy")
```

#### CLI

```bash
nuclia memory forget_fact --session_id=alice-hr --fact_id=fact-xyz --resource=vacation-policy
```

---

### Delete all facts for a session on a resource

```python
memory.forget_facts(session_id="alice-hr", resource="vacation-policy")
```

#### CLI

```bash
nuclia memory forget_facts --session_id=alice-hr --resource=vacation-policy
```

---

## Exceptions

| Exception | Raised when |
|-----------|-------------|
| `ResourceAlreadyExistsError` | `create_resource()` is called with a slug that already exists. |
| `ResourceNotFoundError` | `get_resource()`, `update_resource()`, or `delete_resource()` targets a non-existent resource. |
| `EntryAlreadyExistsError` | `remember()` is called with an `entry_id` that already exists for the session/resource. |

---

## Complete Example: Personalised HR Assistant

In the following example, two HR operators (Alice and Bob) handle different employee requests on the same policy resources, and `ask()` produces personalised answers for each of them.

```python
from nuclia.sdk.memory import (
    EntryAlreadyExistsError,
    EntryContextMessage,
    NucliaMemory,
    ResourceAlreadyExistsError,
)

# ── 1. Initialise ─────────────────────────────────────────────────────────────

memory = NucliaMemory()
memory.initialize(
    rules=[
        "Facts must be informative, objective, and verifiable statements.",
        "If an employee ID is provided, it must appear in all related facts.",
    ]
)

# ── 2. Create a resource with reference content ──────────────────────────────────

import textwrap

try:
    memory.create_resource(
        slug="vacation-policy",
        title="Vacation Policy",
        summary="Rules governing employee paid time off.",
        texts={
            "policy": textwrap.dedent("""\
                # Vacation Policy
                Employees may carry over a maximum of 5 unused vacation days.
                Any excess days are forfeited on January 1st unless an exception is approved.
            """)
        },
    )
except ResourceAlreadyExistsError:
    pass  # already created in a previous run

# ── 3. Alice records a decision ───────────────────────────────────────────────

try:
    memory.remember(
        text=(
            "Approved carry-over exception for Maria (EMP-1042). "
            "She was unable to take her 8 remaining days due to the Q4 product launch."
        ),
        resource="vacation-policy",
        session_id="alice-hr",
        entry_id="alice-entry-001",
        reasoning="Business-critical event; denying would penalise her for serving company needs.",
        context=[
            EntryContextMessage(author="Maria", text="Can I carry over 8 days from the Q4 launch period?"),
            EntryContextMessage(author="Maria's manager", text="Confirmed her presence was essential."),
        ],
        metadata={"employee_id": "EMP-1042", "decision": "approved", "days": 8},
    )
except EntryAlreadyExistsError:
    pass

# ── 4. Bob records a different decision ───────────────────────────────────────

try:
    memory.remember(
        text=(
            "Denied carry-over exception for Leo (EMP-5512). "
            "Leo had adequate opportunity to schedule vacation. 6 days will be forfeited."
        ),
        resource="vacation-policy",
        session_id="bob-hr",
        entry_id="bob-entry-001",
        reasoning="No business-critical event; policy should be applied as written.",
        context=[
            EntryContextMessage(author="Leo", text="I forgot to use 6 vacation days. Can I carry them over?"),
        ],
        metadata={"employee_id": "EMP-5512", "decision": "denied", "days": 6},
    )
except EntryAlreadyExistsError:
    pass

# ── 5. Ask the same question for Alice and Bob ────────────────────────────────

question = "Have you ever approved a carry-over exception, and if so, under what conditions?"

for session_id, name in [("alice-hr", "Alice"), ("bob-hr", "Bob")]:
    result = memory.ask(query=question, resource="vacation-policy", session_id=session_id)
    print(f"\n[{name}] {result.answer}")
```

Expected output (paraphrased):
- **Alice**: *"Yes, you approved an 8-day carry-over exception for Maria (EMP-1042) because she could not take leave during the Q4 product launch."*
- **Bob**: *"No, you denied a carry-over exception for Leo (EMP-5512) as he had adequate time to schedule vacation during the year."*

---

## Complete Example: Conversational Memory

`NucliaMemory` maps naturally onto multi-exchange conversations: a **resource** represents an ongoing conversation thread, and each **entry** holds one full exchange as formatted turns. The background data-augmentation task extracts facts from every entry, so `ask()` can answer questions that reach back across many exchanges.

```python
from nuclia.sdk.memory import EntryAlreadyExistsError, NucliaMemory, ResourceAlreadyExistsError

EXCHANGE_ID = "caroline-melanie-42"

memory = NucliaMemory()
memory.initialize()


def format_exchange(n: int, date: str, turns: list[dict]) -> str:
    """Format an exchange into a timestamped header followed by speaker turns."""
    header = f"[Exchange {n} — {date}]"
    body = "\n".join(f"{t['speaker']}: {t['text']}" for t in turns)
    return f"{header}\n\n{body}"


# ── Create the resource once ─────────────────────────────────────────────────────

try:
    memory.create_resource(
        slug="caroline-melanie",
        title="Caroline & Melanie",
    )
except ResourceAlreadyExistsError:
    pass


def remember_exchange(n: int, date: str, turns: list[dict]) -> None:
    """Persist one exchange as a single memory entry."""
    try:
        memory.remember(
            text=format_exchange(n, date, turns),
            resource="caroline-melanie",
            session_id=EXCHANGE_ID,
            entry_id=f"caroline-melanie-e{n}",
            metadata={"exchange": n, "date": date},
        )
    except EntryAlreadyExistsError:
        pass


# ── Ingest exchanges ───────────────────────────────────────────────────────────

remember_exchange(1, "8 May 2023", [
    {"speaker": "Caroline", "text": "Hey Mel! I went to an LGBTQ support group yesterday — it was so powerful."},
    {"speaker": "Melanie",  "text": "Wow, that's cool! Did you hear any inspiring stories?"},
    {"speaker": "Caroline", "text": "The transgender stories were so inspiring. The group has made me feel accepted and given me courage to embrace myself."},
    {"speaker": "Melanie",  "text": "You've got guts. What now?"},
    {"speaker": "Caroline", "text": "Going to continue my education and explore career options. I'm keen on counseling or mental health — I'd love to support people facing similar challenges."},
    {"speaker": "Melanie",  "text": "You'd be a great counselor! By the way, here's a lake sunrise I painted last year."},
    {"speaker": "Caroline", "text": "The colors blend so nicely. Painting looks like a wonderful outlet for expressing yourself."},
    {"speaker": "Melanie",  "text": "It really is. I'm off to go swimming with the kids. Talk soon!"},
])

remember_exchange(2, "25 May 2023", [
    {"speaker": "Melanie",  "text": "Hey Caroline! I ran a charity race for mental health last Saturday — it was really rewarding."},
    {"speaker": "Caroline", "text": "That's amazing, Mel. So proud of you for taking part!"},
    {"speaker": "Melanie",  "text": "I'm carving out me-time each day — running, reading, playing violin. My kids are excited about summer; we're thinking about camping next month."},
    {"speaker": "Caroline", "text": "I've been researching adoption agencies. It's been a dream of mine to give a loving home to kids who need it."},
    {"speaker": "Melanie",  "text": "Wow, Caroline! Your future family is going to be so lucky to have you."},
    {"speaker": "Caroline", "text": "I chose an agency that helps LGBTQ+ families. Their inclusivity spoke to me. It'll be tough as a single parent, but I'm ready for the challenge."},
])

remember_exchange(3, "9 June 2023", [
    {"speaker": "Caroline", "text": "I gave a talk at a school last week about my transgender journey. It was incredible to see the students' reactions."},
    {"speaker": "Melanie",  "text": "I'm so proud of you! You've come such a long way. Keep inspiring people!"},
    {"speaker": "Caroline", "text": "Thanks! My friends and mentors have been my rocks. I've known this group for four years, since I moved from Sweden."},
    {"speaker": "Melanie",  "text": "That support system sounds wonderful. What motivates you most?"},
    {"speaker": "Caroline", "text": "Definitely the people around me. I'm still single, but this community gives me everything I need to keep going."},
])

# ── Ask questions that span exchanges ──────────────────────────────────────────

result = memory.ask(
    query="What career path has Caroline been considering?",
    resource="caroline-melanie",
    session_id=EXCHANGE_ID,
)
print(result.answer)
# → "Caroline has consistently leaned toward counseling or mental health work,
#    particularly to support people facing challenges similar to her own transgender journey."

result = memory.ask(
    query="When did Melanie run a charity race, and what was it for?",
    resource="caroline-melanie",
    session_id=EXCHANGE_ID,
)
print(result.answer)
# → "Melanie ran a charity race for mental health on the Saturday before 25 May 2023."

result = memory.ask(
    query="Where did Caroline move from before settling in her current city?",
    resource="caroline-melanie",
    session_id=EXCHANGE_ID,
)
print(result.answer)
# → "Caroline moved from Sweden four years before the June 2023 conversation."
```