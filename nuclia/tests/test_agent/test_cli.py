"""Tests for the Nuclia Agent CLI interact() method."""

from typing import Type, Union
from unittest.mock import patch
from uuid import uuid4

import pytest
from rich.console import Console

from nuclia.sdk.agent import AsyncNucliaAgent, NucliaAgent
from nuclia.sdk.agent_cli import NucliaAgentCLI
from nuclia.tests.utils import maybe_await


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_simple_question(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test CLI interact with a simple question and exit."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    # Simulate user asking a question and then exiting
    with patch.object(
        console, "input", side_effect=["What is Eric known for?", "/exit"]
    ):
        await maybe_await(cli.interact())

    # Check that output was generated
    output = console.export_text()
    assert len(output) > 0
    assert "Nuclia Agent CLI" in output
    assert "What is Eric known for?" in output or "Eric" in output
    assert "Goodbye" in output or "exit" in output.lower()


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_help_command(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test CLI interact with help command."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    with patch.object(console, "input", side_effect=["/help", "/exit"]):
        await maybe_await(cli.interact())

    output = console.export_text()
    assert "Available Commands" in output
    assert "Exit the interactive CLI" in output
    assert "Show this help message" in output
    assert "new_session" in output or "NEW_SESSION" in output
    assert "list_sessions" in output or "LIST_SESSIONS" in output


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_empty_input(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test CLI interact handles empty input gracefully."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    with patch.object(console, "input", side_effect=["", "  ", "/exit"]):
        await maybe_await(cli.interact())

    # Should not crash and should show welcome
    output = console.export_text()
    assert "Nuclia Agent CLI" in output
    assert "Goodbye" in output


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_unknown_command(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test CLI interact handles unknown commands."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    with patch.object(console, "input", side_effect=["/unknown_command", "/exit"]):
        await maybe_await(cli.interact())

    output = console.export_text()
    assert "Unknown command" in output
    assert "/unknown_command" in output or "unknown_command" in output


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_clear_command(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test CLI interact with clear command."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    with patch.object(console, "input", side_effect=["/clear", "/exit"]):
        await maybe_await(cli.interact())

    # Should clear and show welcome again
    output = console.export_text()
    assert "Nuclia Agent CLI" in output
    assert "Goodbye" in output


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_list_sessions(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test CLI interact with list sessions command."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    with patch.object(console, "input", side_effect=["/list_sessions", "/exit"]):
        await maybe_await(cli.interact())

    output = console.export_text()
    # Should show sessions list or message about no sessions
    assert "Nuclia Agent CLI" in output
    assert "Goodbye" in output


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_keyboard_interrupt(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test CLI interact handles keyboard interrupt gracefully."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    with patch.object(console, "input", side_effect=KeyboardInterrupt()):
        await maybe_await(cli.interact())

    output = console.export_text()
    # Should handle interrupt gracefully
    assert "Nuclia Agent CLI" in output
    assert "Interrupted" in output or "Goodbye" in output


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_multiple_questions(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test CLI interact with multiple questions in sequence."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    with patch.object(
        console,
        "input",
        side_effect=[
            "What is Eric known for?",
            "Tell me about Python",
            "/exit",
        ],
    ):
        await maybe_await(cli.interact())

    output = console.export_text()
    assert "Nuclia Agent CLI" in output
    # Should have processed both questions
    assert "Eric" in output or "What is Eric" in output
    assert "Goodbye" in output


@pytest.mark.parametrize(
    "agent_klass",
    [NucliaAgent, AsyncNucliaAgent],
)
async def test_cli_interact_session_workflow(
    testing_config,
    agent_klass: Type[Union[NucliaAgent, AsyncNucliaAgent]],
):
    """Test complete session workflow: create, list, use, switch."""
    console = Console(record=True, force_terminal=False, width=120)
    cli = NucliaAgentCLI(console=console)

    session_name = f"nuclia-py-cli-test-{uuid4().hex}"
    with patch.object(
        console,
        "input",
        side_effect=[
            "/new_session",
            session_name,
            "What is Eric known for?",
            "/list_sessions",
            "/change_session",
            "ephemeral",
            "What does he enjoy?",
            "/exit",
        ],
    ):
        await maybe_await(cli.interact())

    output = console.export_text()
    assert "Nuclia Agent CLI" in output
    # Should show session creation
    assert session_name in output or "created" in output.lower()
    # Should process both questions
    assert "humor" in output
    # Should show session list
    assert "list" in output.lower() or "sessions" in output.lower()
