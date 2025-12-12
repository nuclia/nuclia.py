from enum import Enum
from typing import TYPE_CHECKING

from nuclia_models.agent.interaction import AnswerOperation, AragAnswer
from nuclia_models.agent.memory import Answer, Context, Step
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

from nuclia.data import get_auth
from nuclia.decorators import agent
from nuclia.lib.agent import AgentClient

if TYPE_CHECKING:
    from nuclia.lib.agent import AgentClient
    from nuclia.sdk.agent_sessions import NucliaAgentSessions
    from nuclia.sdk.auth import NucliaAuth


class AgentCommand(Enum):
    EXIT = "exit"
    HELP = "help"
    NEW_SESSION = "new_session"
    LIST_SESSIONS = "list_sessions"
    CHANGE_SESSION = "change_session"
    CLEAR = "clear"


HELP = {
    AgentCommand.EXIT: "Exit the interactive CLI.",
    AgentCommand.HELP: "Show this help message.",
    AgentCommand.NEW_SESSION: "Create a new persistent session.",
    AgentCommand.LIST_SESSIONS: "List all created sessions.",
    AgentCommand.CHANGE_SESSION: "Change to a different session.",
    AgentCommand.CLEAR: "Clear the screen.",
}

MAX_RESULT_DISPLAY_LENGTH = 500
MAX_CONTEXT_DISPLAY_LENGTH = 300


class NucliaAgentCLI:
    # underscore so that it does not show up in the CLI commands
    _session: "NucliaAgentSessions"

    @property
    def _auth(self) -> "NucliaAuth":
        auth = get_auth()
        return auth

    def __init__(self) -> None:
        # Lazy import to avoid circular dependency
        from nuclia.sdk.agent_sessions import NucliaAgentSessions

        self._session = NucliaAgentSessions()

    def _build_step_display(self, step: Step) -> Table:
        """Build a table for displaying a processing step."""
        step_info = Table.grid(padding=(0, 2))
        step_info.add_column(style="cyan", justify="right")
        step_info.add_column(style="white")

        step_info.add_row("Module:", f"[bold]{step.module}[/]")
        if step.value:
            step_info.add_row(
                "Result:",
                Markdown(
                    step.value[:MAX_RESULT_DISPLAY_LENGTH] + "..."
                    if len(step.value) > MAX_RESULT_DISPLAY_LENGTH
                    else step.value
                ),
            )
        if step.reason:
            step_info.add_row(
                "Reason:",
                Markdown(
                    step.reason[:MAX_RESULT_DISPLAY_LENGTH] + "..."
                    if len(step.reason) > MAX_RESULT_DISPLAY_LENGTH
                    else step.reason
                ),
            )
        step_info.add_row("Time:", f"{step.timeit:.2f}s")
        if step.input_nuclia_tokens or step.output_nuclia_tokens:
            step_info.add_row(
                "Tokens:",
                f"in: {step.input_nuclia_tokens:.0f}, out: {step.output_nuclia_tokens:.0f}",
            )
        return step_info

    def _build_context_display(self, ctx: Context) -> Table:
        """Build a table for displaying retrieved context."""
        context_table = Table(
            show_header=True,
            header_style="bold cyan",
            expand=True,
            show_edge=False,
            padding=(0, 1),
            box=box.SIMPLE,
        )
        context_table.add_column("Source", style="cyan", no_wrap=True, ratio=1)
        context_table.add_column("Content", style="white", ratio=7)

        for i, chunk in enumerate(ctx.chunks[:5]):  # Show first 5 chunks
            content = (
                chunk.text[:MAX_CONTEXT_DISPLAY_LENGTH] + "..."
                if len(chunk.text) > MAX_CONTEXT_DISPLAY_LENGTH
                else chunk.text
            )
            context_table.add_row(chunk.title or f"Chunk {i + 1}", content)

        # Add summary row if available
        if ctx.summary:
            context_table.add_row(
                "[bold]Summary[/]",
                ctx.summary,
            )
        return context_table

    def _build_error_display(self, exception) -> Markdown:
        """Build a formatted error message display."""
        error_message = f"**Error Details:**\n\n{exception.detail}"
        return Markdown(error_message)

    def _build_feedback_display(self, feedback) -> Table:
        """Build a table for displaying agent feedback request."""
        feedback_table = Table.grid(padding=(0, 2))
        feedback_table.add_column(style="cyan", justify="right")
        feedback_table.add_column(style="white")

        feedback_table.add_row("Module:", f"[bold]{feedback.module}[/]")
        feedback_table.add_row("Question:", feedback.question)
        if feedback.data:
            import json

            feedback_table.add_row("Data:", json.dumps(feedback.data, indent=2))

        return feedback_table

    def _build_possible_answer_display(self, possible_answer: Answer) -> Table:
        """Build a table for displaying a possible answer."""
        answer_table = Table.grid(padding=(0, 2))
        answer_table.add_column(style="cyan", justify="right")
        answer_table.add_column(style="white")

        if possible_answer.answer:
            answer_table.add_row("Text:", Markdown(possible_answer.answer))

        return answer_table

    def _print_panel(
        self, console: Console, content, title: str, border_style: str = "green"
    ):
        """Helper to print a panel with consistent agent title formatting."""
        console.print(
            Panel(
                content,
                title=title,
                border_style=border_style,
            )
        )

    def _print_welcome(self, console: Console, agent_title: str):
        """Print the welcome panel."""
        self._print_panel(
            console,
            "[bold]Nuclia Agent CLI[/]\n\n"
            "Type your questions to interact with the agent.\n"
            "Type [cyan]/help[/] for available commands.",
            f"[bold green]{agent_title}[/]",
            "green",
        )

    def _handle_new_session(
        self, console: Console, ac: "AgentClient", agent_title: str
    ) -> str | None:
        """Handle creating a new session."""
        session_name = console.input("[bold cyan]Session name:[/] ").strip()
        if session_name:
            try:
                session_uuid = self._session.new(name=session_name, ac=ac)
                self._print_panel(
                    console,
                    f"[green]✓ Created session:[/] {session_name}\n[dim]UUID: {session_uuid}[/]",
                    f"[bold green]{agent_title}[/] · Session Created",
                    "green",
                )
                return session_uuid
            except Exception as e:
                self._print_panel(
                    console,
                    f"[red]✗ Failed to create session:[/] {str(e)}",
                    f"[bold green]{agent_title}[/] · Error",
                    "red",
                )
        return None

    def _handle_list_sessions(
        self, console: Console, ac: "AgentClient", agent_title: str
    ):
        """Handle listing all sessions."""
        try:
            sessions = self._session.list(ac=ac)
            if not sessions.resources:
                self._print_panel(
                    console,
                    "[yellow]No sessions found.[/]",
                    f"[bold green]{agent_title}[/] · Sessions",
                    "green",
                )
                return

            sessions_table = Table(
                show_header=True,
                header_style="bold magenta",
                expand=True,
                box=box.SIMPLE,
            )
            sessions_table.add_column("Title", style="cyan")
            sessions_table.add_column("UUID", style="dim")
            sessions_table.add_column("Created", style="green")

            for session in sessions.resources:
                sessions_table.add_row(
                    session.title or "Untitled",
                    session.id,
                    str(
                        session.created.strftime("%Y-%m-%d %H:%M")
                        if session.created
                        else "N/A"
                    ),
                )

            self._print_panel(
                console,
                sessions_table,
                f"[bold green]{agent_title}[/] · Available Sessions",
                "green",
            )
        except Exception as e:
            self._print_panel(
                console,
                f"[red]✗ Failed to list sessions:[/] {str(e)}",
                f"[bold green]{agent_title}[/] · Error",
                "red",
            )

    def _handle_change_session(
        self, console: Console, ac: "AgentClient", agent_title: str
    ) -> str | None:
        """Handle changing to a different session."""
        new_session_uuid = console.input(
            "[bold cyan]Session UUID (or 'ephemeral'):[/] "
        ).strip()
        if new_session_uuid == "ephemeral":
            self._print_panel(
                console,
                "[green]✓ Switched to ephemeral session[/]",
                f"[bold green]{agent_title}[/] · Session Changed",
                "green",
            )
            return "ephemeral"
        elif new_session_uuid:
            try:
                self._session.get(session_uuid=new_session_uuid, ac=ac)
                self._print_panel(
                    console,
                    f"[green]✓ Switched to session:[/] {new_session_uuid}",
                    f"[bold green]{agent_title}[/] · Session Changed",
                    "green",
                )
                return new_session_uuid
            except Exception as e:
                self._print_panel(
                    console,
                    f"[red]✗ Failed to switch session:[/] {str(e)}",
                    f"[bold green]{agent_title}[/] · Error",
                    "red",
                )
        return None

    def _handle_command(
        self, command: str, console: Console, ac: "AgentClient", agent_title: str
    ) -> tuple[bool, str | None]:
        """
        Handle a CLI command.

        Returns:
            Tuple of (should_exit, new_session_uuid)
        """
        if command == AgentCommand.EXIT.value:
            console.print("\n[yellow]Goodbye![/]")
            return True, None

        if command == AgentCommand.HELP.value:
            help_text = "[bold]Available Commands:[/]\n\n"
            for cmd, desc in HELP.items():
                help_text += f"  [cyan]/{cmd.value}[/] - {desc}\n"
            self._print_panel(
                console,
                help_text,
                f"[bold green]{agent_title}[/] · Help",
                "green",
            )
            return False, None

        if command == AgentCommand.NEW_SESSION.value:
            new_uuid = self._handle_new_session(console, ac, agent_title)
            return False, new_uuid

        if command == AgentCommand.LIST_SESSIONS.value:
            self._handle_list_sessions(console, ac, agent_title)
            return False, None

        if command == AgentCommand.CHANGE_SESSION.value:
            new_uuid = self._handle_change_session(console, ac, agent_title)
            return False, new_uuid

        if command == AgentCommand.CLEAR.value:
            console.clear()
            self._print_welcome(console, agent_title)
            console.print()
            return False, None

        # Unknown command
        self._print_panel(
            console,
            f"[red]Unknown command:[/] /{command}\n\nType [cyan]/help[/] for available commands.",
            f"[bold green]{agent_title}[/] · Error",
            "red",
        )
        return False, None

    def _update_live_display(
        self,
        live: Live,
        response_elements: list,
        agent_title: str,
        spinner: Spinner,
        show_spinner: bool = True,
    ):
        """Update the live display with current response elements."""
        if show_spinner:
            content = Group(*response_elements, spinner)
        else:
            content = Group(*response_elements)

        live.update(
            Panel(
                content,
                title=f"[bold green]{agent_title}[/]",
                border_style="green",
            )
        )

    def _handle_agent_feedback(
        self,
        response: AragAnswer,
        response_elements: list,
        live: Live,
        console: Console,
        agent_title: str,
        spinner: Spinner,
    ) -> str:
        """
        Handle agent request for user feedback.

        Returns the user's response string.
        """
        feedback_display = self._build_feedback_display(response.feedback)
        element = Panel(
            feedback_display,
            title="[bold magenta]🤖 Agent Request[/]",
            border_style="magenta",
        )
        response_elements.append(element)

        # Update display to show request
        live.update(
            Panel(
                Group(*response_elements),
                title=f"[bold magenta]{agent_title}[/] · Requesting Input",
                border_style="magenta",
            )
        )

        # Get user input
        live.stop()
        user_response = console.input("[bold magenta]Your response:[/] ").strip()
        live.start()

        # Add user response to display
        user_element = Panel(
            user_response,
            title="[bold blue]👤 Your Response[/]",
            border_style="blue",
        )
        response_elements.append(user_element)
        self._update_live_display(live, response_elements, agent_title, spinner)

        return user_response

    def _process_response_operation(
        self, response: AragAnswer, spinner: Spinner
    ) -> tuple[Panel | None, bool]:
        """
        Process a single response operation and return the display element and whether to stop.

        Returns:
            Tuple of (element to display or None, should_stop)
        """
        if response.operation == AnswerOperation.START:
            spinner.update(text="[dim]Starting[/]")
            return None, False

        if response.operation == AnswerOperation.DONE:
            spinner.update(text="[dim]Done[/]")
            return None, True

        if response.operation == AnswerOperation.ERROR or response.exception:
            if response.exception:
                error_display = self._build_error_display(response.exception)
                element = Panel(
                    error_display,
                    title="[bold red]❌ Error[/]",
                    border_style="red",
                )
                return element, True
            return None, True

        if response.step:
            step_info = self._build_step_display(response.step)
            element = Panel(
                step_info,
                title=f"[yellow]⚙️ {response.step.title}[/]",
                border_style="yellow",
            )
            spinner.update(text="[dim]Running[/]")
            return element, False

        if response.context:
            context_table = self._build_context_display(response.context)
            element = Panel(
                context_table,
                title="[bold cyan]📚 Context Retrieved[/]",
                border_style="cyan",
            )
            spinner.update(text="[dim]Running[/]")
            return element, False

        if response.possible_answer:
            possible_answer_display = self._build_possible_answer_display(
                response.possible_answer
            )
            element = Panel(
                possible_answer_display,
                title="[bold yellow]💭 Possible Answer[/]",
                border_style="yellow",
            )
            spinner.update(text="[dim]Generating[/]")
            return element, False

        if response.generated_text:
            element = Panel(
                Markdown(response.generated_text),
                title="[bold white]📝 Generated Text[/]",
                border_style="white",
            )
            spinner.update(text="[dim]Generating[/]")
            return element, False

        if response.answer:
            element = Panel(
                Markdown(response.answer),
                title="[bold green]✅ Answer[/]",
                border_style="green",
            )
            return element, True

        return None, False

    def _process_agent_question(
        self,
        ac: "AgentClient",
        session_uuid: str,
        question: str,
        console: Console,
        agent_title: str,
    ):
        """Process a user question through the agent."""
        response_elements: list = []
        spinner = Spinner("dots", text="[dim]Thinking...[/]", style="cyan")

        with Live(
            Panel(
                spinner,
                title=f"[bold green]{agent_title}[/]",
                border_style="green",
            ),
            console=console,
            refresh_per_second=10,
        ) as live:
            generator = ac.interact(session_uuid, question)
            user_feedback = None

            try:
                while True:
                    # Get next response (send user feedback if available)
                    if user_feedback is not None:
                        response = generator.send(user_feedback)
                        user_feedback = None
                    else:
                        response = next(generator)

                    # Handle agent feedback request
                    if (
                        response.operation == AnswerOperation.AGENT_REQUEST
                        and response.feedback
                    ):
                        user_feedback = self._handle_agent_feedback(
                            response,
                            response_elements,
                            live,
                            console,
                            agent_title,
                            spinner,
                        )
                        continue

                    # Process the response
                    element, should_stop = self._process_response_operation(
                        response, spinner
                    )

                    if element:
                        response_elements.append(element)
                        # Special handling for final answer or error
                        if should_stop:
                            self._update_live_display(
                                live,
                                response_elements,
                                agent_title,
                                spinner,
                                show_spinner=False,
                            )
                        else:
                            self._update_live_display(
                                live, response_elements, agent_title, spinner
                            )

                    if should_stop:
                        break

            except StopIteration:
                pass

        console.print()  # Add spacing after response

    def _get_session_display_name(
        self,
        session_uuid: str,
        session_titles: dict[str, str | None],
        ac: "AgentClient",
    ) -> str:
        """Get display name for a session, fetching it if needed."""
        if session_uuid not in session_titles and session_uuid != "ephemeral":
            try:
                session_info = self._session.get(session_uuid=session_uuid, ac=ac)
                session_titles[session_uuid] = session_info.title
            except Exception:
                session_titles[session_uuid] = None

        return session_titles.get(session_uuid) or session_uuid[:8]

    @agent
    def interact(self, **kwargs):
        """Main interactive CLI loop."""
        ac: AgentClient = kwargs["ac"]
        agent_config = self._auth._config.get_agent(ac.agent_id)
        agent_title: str = (
            agent_config.title if agent_config and agent_config.title else "Agent"
        )
        session_uuid = "ephemeral"
        console = Console()
        session_titles: dict[str, str | None] = {"ephemeral": "Ephemeral Session"}

        console.clear()
        self._print_welcome(console, agent_title)
        console.print()

        try:
            while True:
                # Display prompt with session info
                session_display = self._get_session_display_name(
                    session_uuid, session_titles, ac
                )
                prompt_text = f"[bold blue]You[/] [dim]({session_display}):[/] "
                user_input = console.input(prompt_text).strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    command = user_input[1:].lower()
                    should_exit, new_session_uuid = self._handle_command(
                        command, console, ac, agent_title
                    )
                    if should_exit:
                        break
                    if new_session_uuid:
                        session_uuid = new_session_uuid
                    continue

                # Process agent question
                try:
                    self._process_agent_question(
                        ac, session_uuid, user_input, console, agent_title
                    )
                except KeyboardInterrupt:
                    console.print(
                        Panel(
                            "[yellow]Interrupted[/]",
                            title=f"[bold green]{agent_title}[/]",
                            border_style="yellow",
                        )
                    )
                except Exception as e:
                    console.print(
                        Panel(
                            f"[red]✗ Error:[/] {str(e)}",
                            title=f"[bold green]{agent_title}[/]",
                            border_style="red",
                        )
                    )

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Interrupted. Goodbye![/]")
        except Exception as e:
            console.print(f"\n[red]✗ Fatal Error:[/] {str(e)}")
