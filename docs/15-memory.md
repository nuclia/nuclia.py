# NucliaMemory

`NucliaMemory` is a high-level SDK component that turns any Nuclia Knowledge Box into a **personalised, multi-user memory store**. It lets you:

- Organise knowledge into **topics** (discrete memory domains backed by KB resources).
- Attach **entries** (annotated observations, decisions, or notes) to topics on behalf of specific users.
- Automatically extract distilled **facts** and a **knowledge graph** from each entry via a background data-augmentation task.
- **Recall** grounded, personalised answers for any user without mixing up other users' context.

All examples assume you have [authenticated](02-auth.md) and set a [default Knowledge Box](03-kb.md).

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Topic** | A named memory domain stored as a KB resource. It can contain reference documents (policy text, guidelines, etc.) and collects the entries of all users. |
| **Entry** | A timestamped text entry belonging to a topic. It records any content to be remembered. For example, decisions, observations, or conversation transcripts. It may also contain optional `reasoning`, `context` messages, and structured `metadata`. |
| **Fact** | A short, distilled statement automatically extracted from an entry by the Memory data augmentation task. Facts act as a compressed, searchable index of entries. |
| **Graph** | An entity–relation graph extracted from both the topic's reference content and a user's entries, giving a personalised knowledge graph view. |
| **Global entry** | An entry not tied to any specific topic. Stored under a per-user resource. Useful for cross-topic or agent-level memory. |

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

## Managing Topics

### Create a topic

Topics are the named memory domains. Create one before writing entries to it.

```python
topic_id = memory.create_topic(
    title="Vacation Policy",
    slug="vacation-policy",          # optional; auto-generated from title if omitted
    summary="Rules governing PTO.",  # optional
    texts={"policy": "...full policy text..."},  # optional reference documents
)
```

You can also attach remote URLs or local files as reference content:

```python
memory.create_topic(
    title="Employee Handbook",
    urls={"handbook": "https://example.com/handbook.pdf"},
)

memory.create_topic(
    title="Onboarding Guide",
    file_paths={"guide": "/path/to/onboarding.pdf"},
)
```

Raises `TopicAlreadyExistsError` if the slug already exists.

#### CLI

```bash
nuclia memory create_topic --title="Vacation Policy" --slug=vacation-policy
```

---

### Get a topic

```python
from nuclia.sdk.memory import NucliaMemory, TopicNotFoundError

memory = NucliaMemory()
try:
    topic = memory.get_topic(topic="vacation-policy")
    print(topic.id, topic.title, topic.status)
except TopicNotFoundError:
    print("Topic not found")
```

**`Topic` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID of the topic resource. |
| `slug` | `str` | URL-friendly identifier. |
| `title` | `str` | Human-readable title. |
| `summary` | `str \| None` | Short description. |
| `status` | `str` | Processing status (`"processed"`, `"pending"`, `"error"`, …). |

#### CLI

```bash
nuclia memory get_topic --topic=vacation-policy
```

---

### List topics

```python
page = memory.list_topics(query="policy", page=0, size=10)

print(f"Total topics: {page.total}")
for topic in page.items:
    print(f"  {topic.slug}: {topic.title}")
```

**`TopicPage` fields:** `items`, `total`, `has_more`.

#### CLI

```bash
nuclia memory list_topics
nuclia memory list_topics --query=policy --page=0 --size=10
```

---

### Update a topic

```python
memory.update_topic(
    "vacation-policy",
    title="PTO & Vacation Policy",
    texts={"policy": "...updated text..."},
)
```

#### CLI

```bash
nuclia memory update_topic vacation-policy --title="PTO & Vacation Policy"
```

---

### Delete a topic

```python
memory.delete_topic("vacation-policy", confirm=True)
```

> ⚠️ `confirm=True` is required. This permanently deletes the topic and all its entries.

#### CLI

```bash
nuclia memory delete_topic vacation-policy --confirm=true
```

---

## Writing Entries

`remember()` writes a timestamped entry for a user on a topic. The background task automatically distils a fact and updates the knowledge graph.

### Topic-scoped entry

```python
from nuclia.sdk.memory import EntryContextMessage, NucliaMemory

memory = NucliaMemory()

memory.remember(
    text="Approved carry-over exception for Maria (EMP-1042). "
         "She could not use 8 vacation days due to a Q4 product launch.",
    topic="vacation-policy",
    user_id="alice-hr",
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

Raises `EntryAlreadyExistsError` if an entry with the same `entry_id` already exists for this user and topic.

### Global entry (not tied to a topic)

Omit `topic` to write a cross-topic or agent-level entry. Each user gets their own dedicated resource for global entries.

```python
memory.remember(
    text="User prefers concise, bullet-point answers.",
    user_id="agent-session-abc123",
)
```

### CLI

```bash
nuclia memory remember \
  --text="Approved carry-over for Maria (EMP-1042)" \
  --topic=vacation-policy \
  --user_id=alice-hr \
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

Iterate over all entries written by a user for a topic:

```python
for entry in memory.entries(topic="vacation-policy", user_id="alice-hr"):
    print(f"[{entry.id}] {entry.timestamp}: {entry.content.text}")
```

List **global** entries (omit `topic`):

```python
for entry in memory.entries(user_id="agent-session-abc123"):
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
nuclia memory entries --topic=vacation-policy --user_id=alice-hr
nuclia memory entries --user_id=agent-session-abc123
```

---

### List extracted facts

After the background task runs, each entry is distilled into one or more short facts:

```python
for fact in memory.facts(topic="vacation-policy", user_id="alice-hr"):
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
nuclia memory facts --topic=vacation-policy --user_id=alice-hr
```

---

### Query the knowledge graph

Retrieve entity–relation paths extracted from the topic content and a user's entries:

```python
edges = memory.graph(topic="vacation-policy", user_id="alice-hr")
for edge in edges:
    print(
        f"{edge.source.value!r} --{edge.relation.label}--> {edge.destination.value!r}"
    )
```

#### CLI

```bash
nuclia memory graph --topic=vacation-policy --user_id=alice-hr
```

---

## Querying Memory

### Semantic retrieval (`recall`)

Returns a ranked list of relevant context blocks without generating an answer. Useful when you want to feed context into your own LLM pipeline.

```python
blocks = memory.recall(
    question="Has anyone ever approved a carry-over exception?",
    topic="vacation-policy",
    user_id="alice-hr",
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
  --topic=vacation-policy \
  --user_id=alice-hr
```

---

### Generative answer (`ask`)

Returns a grounded, personalised answer generated by an LLM over the topic and user's facts. This is the primary entry point for building memory-powered assistants.

Internally it builds a request to the `/ask` endpoint with a filter to only retrieve memories relevant to the provided user and topic

```python
from nuclia.sdk.memory import NucliaMemory

memory = NucliaMemory()

result = memory.ask(
    query="Have I ever approved a carry-over exception?",
    topic="vacation-policy",
    user_id="alice-hr",
)

print(result.answer)

for key, block in result.citations.items():
    print(f"  [{key}] (score={block.score:.3f}) {block.text[:80]}")
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | — | Natural-language question. |
| `topic` | `str` | — | Topic ID or slug to scope the answer to. |
| `user_id` | `str \| None` | `None` | User whose entries and facts are used for personalisation. |
| `context` | `list[ChatContextMessage] \| None` | `None` | Prior conversation messages (oldest first) to include as extra context. |
| `include_global_facts` | `bool` | `False` | Also include this user's global (cross-topic) facts in the context. |
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
    topic="vacation-policy",
    user_id="alice-hr",
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
    topic="vacation-policy",
    user_id="alice-hr",
    context=history,
)
```

#### CLI

```bash
nuclia memory ask \
  --query="Have I approved a carry-over exception?" \
  --topic=vacation-policy \
  --user_id=alice-hr
```

---

## Forgetting

### Delete a single entry

Deletes one entry and any facts derived solely from it.

```python
memory.forget_entry(user_id="alice-hr", entry_id="alice-entry-001", topic="vacation-policy")
```

Omit `topic` to delete from global entries.

#### CLI

```bash
nuclia memory forget_entry --user_id=alice-hr --entry_id=alice-entry-001 --topic=vacation-policy
```

---

### Delete all entries for a user on a topic

```python
memory.forget_entries(user_id="alice-hr", topic="vacation-policy")
```

#### CLI

```bash
nuclia memory forget_entries --user_id=alice-hr --topic=vacation-policy
```

---

### Delete a single fact

```python
memory.forget_fact(user_id="alice-hr", fact_id="fact-xyz", topic="vacation-policy")
```

#### CLI

```bash
nuclia memory forget_fact --user_id=alice-hr --fact_id=fact-xyz --topic=vacation-policy
```

---

### Delete all facts for a user on a topic

```python
memory.forget_facts(user_id="alice-hr", topic="vacation-policy")
```

#### CLI

```bash
nuclia memory forget_facts --user_id=alice-hr --topic=vacation-policy
```

---

## Exceptions

| Exception | Raised when |
|-----------|-------------|
| `TopicAlreadyExistsError` | `create_topic()` is called with a slug that already exists. |
| `TopicNotFoundError` | `get_topic()`, `update_topic()`, or `delete_topic()` targets a non-existent topic. |
| `EntryAlreadyExistsError` | `remember()` is called with an `entry_id` that already exists for the user/topic. |

---

## Complete Example: Personalised HR Assistant

The following example mirrors the [hr_buddy_demo.py](../examples/hr_buddy_demo.py) script. Two HR operators (Alice and Bob) handle different employee requests on the same policy topics, and `ask()` produces personalised answers for each of them.

```python
from nuclia.sdk.memory import (
    EntryAlreadyExistsError,
    EntryContextMessage,
    NucliaMemory,
    TopicAlreadyExistsError,
)

# ── 1. Initialise ─────────────────────────────────────────────────────────────

memory = NucliaMemory()
memory.initialize(
    rules=[
        "Facts must be informative, objective, and verifiable statements.",
        "If an employee ID is provided, it must appear in all related facts.",
    ]
)

# ── 2. Create a topic with reference content ──────────────────────────────────

import textwrap

try:
    memory.create_topic(
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
except TopicAlreadyExistsError:
    pass  # already created in a previous run

# ── 3. Alice records a decision ───────────────────────────────────────────────

try:
    memory.remember(
        text=(
            "Approved carry-over exception for Maria (EMP-1042). "
            "She was unable to take her 8 remaining days due to the Q4 product launch."
        ),
        topic="vacation-policy",
        user_id="alice-hr",
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
        topic="vacation-policy",
        user_id="bob-hr",
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

for user_id, name in [("alice-hr", "Alice"), ("bob-hr", "Bob")]:
    result = memory.ask(query=question, topic="vacation-policy", user_id=user_id)
    print(f"\n[{name}] {result.answer}")
```

Expected output (paraphrased):
- **Alice**: *"Yes, you approved an 8-day carry-over exception for Maria (EMP-1042) because she could not take leave during the Q4 product launch."*
- **Bob**: *"No, you denied a carry-over exception for Leo (EMP-5512) as he had adequate time to schedule vacation during the year."*

---

## Complete Example: Conversational Memory

`NucliaMemory` maps naturally onto multi-session conversations: a **topic** represents an ongoing conversation thread, and each **entry** holds one full session as formatted turns. The background data-augmentation task extracts facts from every entry, so `ask()` can answer questions that reach back across many sessions.

```python
from nuclia.sdk.memory import EntryAlreadyExistsError, NucliaMemory, TopicAlreadyExistsError

USER_ID = "user-42"

memory = NucliaMemory()
memory.initialize()


def format_session(n: int, date: str, turns: list[dict]) -> str:
    """Format a session into a timestamped header followed by speaker turns."""
    header = f"[Session {n} — {date}]"
    body = "\n".join(f"{t['speaker']}: {t['text']}" for t in turns)
    return f"{header}\n\n{body}"


# ── Create the topic once ─────────────────────────────────────────────────────

try:
    memory.create_topic(
        slug="caroline-melanie",
        title="Caroline & Melanie",
    )
except TopicAlreadyExistsError:
    pass


def remember_session(n: int, date: str, turns: list[dict]) -> None:
    """Persist one session as a single memory entry."""
    try:
        memory.remember(
            text=format_session(n, date, turns),
            topic="caroline-melanie",
            user_id=USER_ID,
            entry_id=f"caroline-melanie-s{n}",
            metadata={"session": n, "date": date},
        )
    except EntryAlreadyExistsError:
        pass


# ── Ingest sessions ───────────────────────────────────────────────────────────

remember_session(1, "8 May 2023", [
    {"speaker": "Caroline", "text": "Hey Mel! I went to an LGBTQ support group yesterday — it was so powerful."},
    {"speaker": "Melanie",  "text": "Wow, that's cool! Did you hear any inspiring stories?"},
    {"speaker": "Caroline", "text": "The transgender stories were so inspiring. The group has made me feel accepted and given me courage to embrace myself."},
    {"speaker": "Melanie",  "text": "You've got guts. What now?"},
    {"speaker": "Caroline", "text": "Going to continue my education and explore career options. I'm keen on counseling or mental health — I'd love to support people facing similar challenges."},
    {"speaker": "Melanie",  "text": "You'd be a great counselor! By the way, here's a lake sunrise I painted last year."},
    {"speaker": "Caroline", "text": "The colors blend so nicely. Painting looks like a wonderful outlet for expressing yourself."},
    {"speaker": "Melanie",  "text": "It really is. I'm off to go swimming with the kids. Talk soon!"},
])

remember_session(2, "25 May 2023", [
    {"speaker": "Melanie",  "text": "Hey Caroline! I ran a charity race for mental health last Saturday — it was really rewarding."},
    {"speaker": "Caroline", "text": "That's amazing, Mel. So proud of you for taking part!"},
    {"speaker": "Melanie",  "text": "I'm carving out me-time each day — running, reading, playing violin. My kids are excited about summer; we're thinking about camping next month."},
    {"speaker": "Caroline", "text": "I've been researching adoption agencies. It's been a dream of mine to give a loving home to kids who need it."},
    {"speaker": "Melanie",  "text": "Wow, Caroline! Your future family is going to be so lucky to have you."},
    {"speaker": "Caroline", "text": "I chose an agency that helps LGBTQ+ families. Their inclusivity spoke to me. It'll be tough as a single parent, but I'm ready for the challenge."},
])

remember_session(3, "9 June 2023", [
    {"speaker": "Caroline", "text": "I gave a talk at a school last week about my transgender journey. It was incredible to see the students' reactions."},
    {"speaker": "Melanie",  "text": "I'm so proud of you! You've come such a long way. Keep inspiring people!"},
    {"speaker": "Caroline", "text": "Thanks! My friends and mentors have been my rocks. I've known this group for four years, since I moved from Sweden."},
    {"speaker": "Melanie",  "text": "That support system sounds wonderful. What motivates you most?"},
    {"speaker": "Caroline", "text": "Definitely the people around me. I'm still single, but this community gives me everything I need to keep going."},
])

# ── Ask questions that span sessions ──────────────────────────────────────────

result = memory.ask(
    query="What career path has Caroline been considering?",
    topic="caroline-melanie",
    user_id=USER_ID,
)
print(result.answer)
# → "Caroline has consistently leaned toward counseling or mental health work,
#    particularly to support people facing challenges similar to her own transgender journey."

result = memory.ask(
    query="When did Melanie run a charity race, and what was it for?",
    topic="caroline-melanie",
    user_id=USER_ID,
)
print(result.answer)
# → "Melanie ran a charity race for mental health on the Saturday before 25 May 2023."

result = memory.ask(
    query="Where did Caroline move from before settling in her current city?",
    topic="caroline-melanie",
    user_id=USER_ID,
)
print(result.answer)
# → "Caroline moved from Sweden four years before the June 2023 conversation."
```