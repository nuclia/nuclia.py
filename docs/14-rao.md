# Retrieval Agents Orchestrator

Interact with Nuclia's Retrieval Agents Orchestrator to have intelligent conversations over several knowledge sources with persistent session management and real-time streaming responses.

## Prerequisites

Install the Nuclia SDK:

```sh
pip install nuclia
```

Ensure you have:
- A valid Nuclia authentication token (see [Authentication](02-auth.md))
- Access to a configured Retrieval Agent

## Overview

The nuclia.py library provides several ways to interact with your Retrieval Agents Orchestrators:

- **Interactive CLI**: A rich, user-friendly terminal interface (recommended)
- **Standard CLI**: Direct access to raw websocket messages for debugging
- **Session Management**: Create and manage persistent conversation sessions
- **Programmatic API**: Python SDK for building custom applications


## Listing Available Agents

Discover what Retrieval Agents Orchestrators you have access to.

- CLI:

  ```sh
  nuclia agents list
  ```

- SDK:

  ```python
  from nuclia.sdk.agents import NucliaAgents

  agents = NucliaAgents()
  all_agents = agents.list()

  for agent in all_agents:
      print(f"Agent: {agent.title} ({agent.id})")
      print(f"  Slug: {agent.slug}")
      print(f"  Zone: {agent.zone}")
  ```

### Getting a Specific Agent

- CLI:

  ```sh
  nuclia agents get --account="my-account" --id="agent-uuid" --zone="europe-1"
  ```

- SDK:

  ```python
  from nuclia.sdk.agents import NucliaAgents

  agents = NucliaAgents()
  agent_details = agents.get(
      account="my-account",
      id="agent-uuid",
      zone="europe-1"
  )
  print(agent_details)
  ```

### Setting a Default Agent

- CLI:

  ```sh
  nuclia agents default [AGENT_SLUG or AGENT_UUID]
  ```

- SDK:

  ```python
  from nuclia.sdk.agents import NucliaAgents

  agents = NucliaAgents()
  agents.default("my-agent")
  ```

This sets the default agent for all subsequent operations.

## Interactive CLI (Recommended)

The interactive CLI provides a beautiful, real-time interface for conversing with your Retrieval Agents Orchestrator.

### Starting the Interactive CLI

- CLI:

  ```sh
  nuclia agent cli interact
  ```

- SDK:

  ```python
  from nuclia.sdk.agent import NucliaAgent

  agent = NucliaAgent()
  agent.cli.interact()
  ```

This launches an interactive terminal session where you can:
- Ask questions and see streaming responses
- View processing steps in real-time
- Manage conversation sessions
- See retrieved context and citations

### Interactive CLI Commands

The CLI supports several commands (prefix with `/`):

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/new_session` | Create a new persistent session (only for a Retrieval Agent Orchestrator with memory)|
| `/list_sessions` | List all your sessions |
| `/change_session` | Switch to a different session, use 'ephemeral' for a temporary session |
| `/clear` | Clear the screen |
| `/exit` | Exit the CLI |

Please note that all commands related to sessions require a Retrieval Agent Orchestrator with the option **Agent with memory** enabled during creation.

## Session Management

Sessions allow you to maintain conversation context across multiple interactions.

> This feature will only be available if you checked **Agent with memory** during the creation of your Retrieval Agents Orchestrator.

### Creating a Session

- CLI:

  ```sh
  nuclia agent session new --name="My Research Session"
  ```

- SDK:

  ```python
  from nuclia.sdk.agent import NucliaAgent

  agent = NucliaAgent()
  session_uuid = agent.session.new("My Research Session")
  print(f"Created session: {session_uuid}")
  ```

### Listing Sessions

- CLI:

  ```sh
  nuclia agent session list
  ```

- SDK:

  ```python
  from nuclia.sdk.agent import NucliaAgent

  agent = NucliaAgent()
  sessions = agent.session.list()
  for session in sessions.resources:
      print(f"{session.title}: {session.id}")
  ```

### Getting a Session

- CLI:

  ```sh
  nuclia agent session get --session_uuid=[SESSION_UUID]
  ```

- SDK:

  ```python
  from nuclia.sdk.agent import NucliaAgent

  agent = NucliaAgent()
  session = agent.session.get(session_uuid)
  print(f"Session: {session.title}")
  print(f"Created: {session.created}")
  ```

### Deleting a Session

- CLI:

  ```sh
  nuclia agent session delete --session_uuid=[SESSION_UUID]
  ```

- SDK:

  ```python
  from nuclia.sdk.agent import NucliaAgent

  agent = NucliaAgent()
  agent.session.delete(session_uuid)
  ```

## Interaction

Aside from the interactive CLI, you can interact with your Retrieval Agents Orchestrator with the simple CLI or programmatically using the SDK.

### Basic Interaction


**CLI:**
```bash
nuclia agent interact "What is Eric known for?"
```

**SDK:**
```python
from nuclia.sdk.agent import NucliaAgent

agent = NucliaAgent()

# Iterate over streaming responses
for response in agent.interact(
    question="What is Eric known for?"
):
    if response.operation == "ANSWER" and response.answer:
        print(response.answer)
    elif response.step:
        print(f"Processing: {response.step.module}")
```

Not supplying a `session_uuid` when calling `interact` will use an ephemeral session by default. To maintain context, provide a persistent session UUID.

### Using Persistent Sessions

**CLI:**
```bash
nuclia agent sessions new "Customer Support Chat"
# Note the session UUID returned
nuclia agent interact "What are your business hours?" --session_uuid="SESSION_UUID"
nuclia agent interact "Are you open on weekends?" --session_uuid="SESSION_UUID"
```

**SDK:**
```python
from nuclia.sdk.agent import NucliaAgent

agent = NucliaAgent()

# Create a session
session_uuid = agent.session.new("Customer Support Chat")

# Have a conversation with context
for response in agent.interact(
    session_uuid=session_uuid,
    question="What are your business hours?"
):
    if response.answer:
        print(response.answer)

# Follow-up question maintains context
for response in agent.interact(
    session_uuid=session_uuid,
    question="Are you open on weekends?"
):
    if response.answer:
        print(response.answer)
```

## Understanding Response Types

When interacting with an agent, you receive a stream of `AragAnswer` objects with different operations:

| Operation | Description |
|-----------|-------------|
| `START` | Interaction has begun |
| `ANSWER` | Processing step or partial answer |
| `DONE` | Interaction complete |
| `ERROR` | An error occurred |
| `AGENT_REQUEST` | Agent needs user feedback |

### Response Attributes

Each response may contain:

- **`step`**: Information about the current processing step
  - `module`: The module being executed (e.g., "rephrase", "basic_ask", "remi")
  - `title`: Display title for the step
  - `value`: Result of the step
  - `reason`: Explanation for the step
  - `timeit`: Time taken in seconds
  - `input_nuclia_tokens`/`output_nuclia_tokens`: Token usage

- **`context`**: Retrieved context from the knowledge base
  - `chunks`: List of retrieved text chunks with sources
  - `summary`: Summary of the context or partial answer

- **`answer`**: The final answer text (Markdown formatted)

- **`generated_text`**: Intermediate generated text

- **`possible_answer`**: Alternative answer being considered

- **`exception`**: Error details if something went wrong

### Processing Responses

```python
from nuclia.sdk.agent import NucliaAgent
from nuclia_models.agent.interaction import AnswerOperation

agent = NucliaAgent()

for response in agent.interact(question="Tell me about AI"):
    if response.operation == AnswerOperation.START:
        print("Starting...")
    
    elif response.step:
        print(f"Step: {response.step.module} ({response.step.timeit:.2f}s)")
    
    elif response.context:
        print(f"Retrieved {len(response.context.chunks)} chunks")
        for chunk in response.context.chunks:
            print(f"  - {chunk.title}: {chunk.text[:100]}...")
    
    elif response.answer:
        print(f"\nFinal Answer:\n{response.answer}")
    
    elif response.operation == AnswerOperation.DONE:
        print("Complete!")
    
    elif response.operation == AnswerOperation.ERROR:
        print(f"Error: {response.exception.detail if response.exception else 'Unknown'}")
```

## Standard CLI for Raw Messages

For debugging or advanced use cases, you can access raw websocket messages programmatically:

```python
from nuclia.sdk.agent import NucliaAgent

agent = NucliaAgent()

# Iterate over all messages
for message in agent.interact(
    question="What is RAO?"
):
    # message is an AragAnswer object with all raw data
    print(f"Operation: {message.operation}")
    print(f"Raw message: {message.model_dump_json(indent=2)}")
```

This gives you direct access to all websocket message data for debugging or custom processing.

## Advanced Features

### Agent Feedback Requests

Agents can request additional input from users during processing:

```python
from nuclia.sdk.agent import NucliaAgent
from nuclia_models.agent.interaction import AnswerOperation

agent = NucliaAgent()
generator = agent.interact(question="Help me with X")

for response in generator:
    if response.operation == AnswerOperation.AGENT_REQUEST:
        # Agent is requesting user input
        user_input = input(f"Agent asks: {response.feedback.question}\n> ")
        # Send response back
        generator.send(user_input)
    elif response.answer:
        print(response.answer)
```

### Error Handling

```python
from nuclia.sdk.agent import NucliaAgent
from nuclia.exceptions import RaoAPIException

agent = NucliaAgent()

try:
    for response in agent.interact(question="Hello?"):
        if response.exception:
            print(f"Agent error: {response.exception.detail}")
        elif response.answer:
            print(response.answer)
except RaoAPIException as e:
    print(f"API error: {e.detail}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Passing Custom Headers to MCP

If your Retrieval Agents Orchestrator requires custom headers for MCP Agents, you can pass them as follows:

**CLI:**
```bash
nuclia agent interact "What is AI?" --headers '{"X-Custom-Header": "value"}'
```

**SDK:**
```python
from nuclia.sdk.agent import NucliaAgent

agent = NucliaAgent()
for response in agent.interact(
    question="What is AI?",
    headers={"X-Custom-Header": "value"}
):
    if response.answer:
        print(response.answer)
```

Please ensure that the 'Allowed Headers' configuration in your MCP agent includes any custom headers you wish to use.

## Best Practices

1. **Use Sessions for Context**: Create sessions when you need multi-turn conversations with context retention
2. **Use Ephemeral Sessions for One-offs**: Don't supply a session UUID for using agents in a stateless manner.
3. **Stream for UX**: Process responses as they arrive for better user experience
4. **Handle All Operations**: Check for different operation types (START, ANSWER, DONE, ERROR) when processing responses
5. **Clean Up Sessions**: Delete sessions when done to avoid clutter
6. **Use Interactive CLI**: For manual testing and exploration, the interactive CLI provides the best experience
