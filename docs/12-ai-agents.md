# AI Agents

Build AI agent teams that work together to tackle complex tasks using Nuclia-hosted LLMs.

With the `crewAI` Python library and the `NucliaNuaChat` class, you can integrate crewAI agents with Nuclia’s LLMs.

## Prerequisites

1. Install the required libraries:
   ```bash
   pip install crewai nuclia[litellm]
   ```

2. Obtain your Nuclia [NUA key](https://docs.nuclia.dev/docs/management/authentication#generate-nua-key)

## How to Integrate crewAI Agents with Nuclia LLMs

Here’s a step-by-step guide to integrate a crewAI agent with a Nuclia-hosted LLM:

```python
from crewai import Agent
import litellm
from nuclia.lib.nua_chat import NucliaNuaChat

# Replace with your Nuclia Key
NUA_KEY = "<your-nua-key>"

# Initialize the Nuclia LLM handler
custom_llm = NucliaNuaChat(
    token=NUA_KEY,
)

# Define the LLM provider and model
PROVIDER = "nuclia"
MODEL = "claude-3"

# Map the custom LLM handler to the provider
litellm.custom_provider_map = [{"provider": PROVIDER, "custom_handler": custom_llm}]

# Define the LLM identifier
LLM = f"{PROVIDER}/{MODEL}"

# Configure and initialize the agent
Agent(
    role="Senior Software Engineer",
    goal="Create software as needed",
    backstory=(
        "You are a Senior Software Engineer at a leading tech think tank."
        "Your expertise in programming in python. and do your best to produce perfect code"
    ),
    llm=LLM,
)
```

## A complete example

### Markdown validator

This example demonstrates how to use crewAI and Nuclia-hosted LLMs to validate Markdown files. It is retrieved from the crewAI repository [Markdown Validator Example](https://github.com/crewAIInc/crewAI-examples/tree/main/markdown_validator).

Only modified files are shown here. For the complete code and instructions on how to run it, check the link above.

#### crew.py

```python
import litellm
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from nuclia.lib.nua_chat import NucliaNuaChat

from markdown_validator.tools.markdownTools import markdown_validation_tool

NUA_KEY = "<your-nua-key>"

custom_llm = NucliaNuaChat(
    token=NUA_KEY,
)

PROVIDER = "nuclia"
litellm.custom_provider_map = [{"provider": PROVIDER, "custom_handler": custom_llm}]

LLM = f"{PROVIDER}/claude-3"

@CrewBase
class MarkDownValidatorCrew():
    """MarkDownValidatorCrew crew"""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def RequirementsManager(self) -> Agent:
        return Agent(
            config=self.agents_config['Requirements_Manager'],
            tools=[markdown_validation_tool],
            allow_delegation=False,
            verbose=False,
            llm=LLM
        )

    @task
    def syntax_review_task(self) -> Task:
        return Task(
            config=self.tasks_config['syntax_review_task'],
            agent=self.RequirementsManager()
        )

    @crew
    def crew(self) -> Crew:
        """Creates the MarkDownValidatorCrew crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=False,
        )
```

#### main.py

```python
import sys

from markdown_validator.crew import MarkDownValidatorCrew


def run():
    """
    Run the markdown validation crew to analyze the markdown file.
    """
    # Get the input markdown file from command line arguments
    inputs = {
        'query': 'Please provide the markdown file to analyze:',
        'filename': sys.argv[1] if len(sys.argv) > 1 else None,  # Expect 'filename' key
    }

    # Check if the markdown file path is provided
    if inputs['filename']:
        print(f"Starting markdown validation for file: {inputs['filename']}")
        crewResult = MarkDownValidatorCrew().crew().kickoff(inputs=inputs)
        print("Markdown validation completed")
        return crewResult
    else:
        raise ValueError("Error: No markdown file provided. Please provide a file path as a command-line argument.")


def train():
    """
    Train the markdown validator crew for a given number of iterations.
    """
    # Get the number of iterations and markdown file path from command line arguments
    inputs = {
        'query': 'Training the markdown validation model.',
        'filename': sys.argv[2] if len(sys.argv) > 2 else None,  # Expect 'filename' key
    }

    # Check if the markdown file path is provided
    if inputs['filename']:
        try:
            print(f"Starting training for file: {inputs['filename']}")
            MarkDownValidatorCrew().crew().train(n_iterations=int(sys.argv[1]), filename=inputs['filename'])
            print("Training completed successfully.")
        except Exception as e1:
            raise Exception(f"An error occurred while training the crew: {e1}")
    else:
        raise ValueError(
            "Error: No markdown file provided for training. Please provide the number of iterations and a file path.")


if __name__ == "__main__":
    print("## Welcome to Markdown Validator Crew")
    print('-------------------------------------')

    try:
        result = run()
        print("\n\n########################")
        print("## Validation Report")
        print("########################\n")
        print(f"Final Recommendations: {result}")
    except Exception as e:
        print(f"An error occurred: {e}")
```

:::note
For more examples, check out the [crewAI examples repository](https://github.com/crewAIInc/crewAI-examples). Remember you will need to adapt them to use a custom Nuclia LLM.
:::
