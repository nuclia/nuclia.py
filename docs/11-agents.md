# Agents: Automate Tasks for Better Search Performance

Enhance your Knowledge Box's performance and precision by running automated agents.

---

## **Available Task Names**
Below is a list of task names you can use:

- **DEMO_DATASET**: Upload a demo dataset.
- **LABELER**: Apply labels to text blocks or resources based on descriptions and examples.
- **LLM_GRAPH**: Use an LLM to generate a Knowledge Graph by extracting relationships and entities.
- **SYNTHETIC_QUESTIONS**: Generate questions and answers from documents
- **ASK**: Ask questions directly from your documents.
- **SEMANTIC_MODEL_MIGRATOR**: Compute the vectors of a new semantic model for the fields of a knowledge box and send them back to NucliaDB for ingestion.
- **LLAMA_GUARD**: Label text blocks or resources as unsafe if they have been flagged as inappropriate.
- **PROMPT_GUARD**: Detect and label jailbreak-related content.

---

## **How to Use Tasks**

### Create a task

#### SDK Example

```python
from nuclia import sdk
from nuclia_models.worker.tasks import TaskName, ApplyOptions, DataAugmentation
from nuclia_models.worker.proto import ApplyTo, Filter, LLMConfig, Operation

kb = sdk.NucliaKB()
kb.task.start(
    task_name=TaskName.LABELER,
    apply=ApplyOptions.EXISTING,
    parameters=DataAugmentation(
        name="test",
        on=ApplyTo.FIELD,
        filter=Filter(),
        operations=[Operation()],
        llm=LLMConfig(),
    ),
)
```

#### CLI Example
```bash
nuclia kb task start --task_name=labeler --apply=existing --parameters='{
    "name": "test",
    "on": 1,
    "filter": {},
    "operations": [
        {}
    ],
    "llm": {}
}'
```

### List all tasks

#### SDK Example

```python
from nuclia import sdk

kb = sdk.NucliaKB()
kb.task.list()
```

#### CLI Example
```bash
nuclia kb task list
```

### Get a task

#### SDK Example

```python
from nuclia import sdk

kb = sdk.NucliaKB()
kb.task.get(task_id="71018fb9-053e-4ca0-9d89-226ada9598e6")
```

#### CLI Example
```bash
nuclia kb task get --task_id=71018fb9-053e-4ca0-9d89-226ada9598e6
```

### Stop a task

#### SDK Example

```python
from nuclia import sdk

kb = sdk.NucliaKB()
kb.task.stop(task_id="71018fb9-053e-4ca0-9d89-226ada9598e6")
```

#### CLI Example
```bash
nuclia kb task stop --task_id=71018fb9-053e-4ca0-9d89-226ada9598e6
```

### Restart a task

#### SDK Example

```python
from nuclia import sdk

kb = sdk.NucliaKB()
kb.task.restart(task_id="71018fb9-053e-4ca0-9d89-226ada9598e6")
```

#### CLI Example
```bash
nuclia kb task restart --task_id=71018fb9-053e-4ca0-9d89-226ada9598e6
```

### Delete a task

#### SDK Example

```python
from nuclia import sdk

kb = sdk.NucliaKB()
kb.task.delete(task_id="71018fb9-053e-4ca0-9d89-226ada9598e6")
```

#### CLI Example
```bash
nuclia kb task delete --task_id=71018fb9-053e-4ca0-9d89-226ada9598e6
```

---

### Notes
- Replace `71018fb9-053e-4ca0-9d89-226ada9598e6` with your actual `task_id`.
- Use `nuclia kb task <command>` to perform operations via the CLI.