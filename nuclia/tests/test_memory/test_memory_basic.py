import asyncio
import tempfile
from typing import Type, Union

import pytest

from nuclia.sdk.memory import (
    AsyncNucliaMemory,
    EntryAlreadyExistsError,
    EntryContextMessage,
    NucliaMemory,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
)
from nuclia.tests.utils import maybe_async_iterate, maybe_await

RESOURCE_VACATION_POLICY = "vacation-policy"
RESOURCE_VACATION_POLICY_LINK = "vacation-policy-link"
RESOURCE_VACATION_POLICY_FILE = "vacation-policy-file"


async def _wait_until_resource_ready_for_search(
    memory: Union[NucliaMemory, AsyncNucliaMemory],
    *,
    resource: str,
    session_id: str,
    max_seconds: int = 120,
    min_resource_facts: int = 1,
    min_global_facts: int = 0,
) -> bool:
    """Wait until a resource is processed and has stable extracted facts."""
    successful_rounds = 0
    for _ in range(max_seconds):
        resource_data = await maybe_await(memory.get_resource(resource=resource))
        if resource_data.status == "processed":
            facts = [
                f
                async for f in maybe_async_iterate(
                    memory.facts(resource=resource, session_id=session_id)
                )
            ]
            has_resource_facts = len(facts) >= min_resource_facts
            has_global_facts = True
            if min_global_facts > 0:
                global_facts = [
                    f
                    async for f in maybe_async_iterate(
                        memory.facts(session_id=session_id)
                    )
                ]
                has_global_facts = len(global_facts) >= min_global_facts

            if has_resource_facts and has_global_facts:
                successful_rounds += 1
                if successful_rounds >= 3:
                    return True
            else:
                successful_rounds = 0
                print(
                    "Resource is processed but facts are not yet available, waiting..."
                )
        else:
            successful_rounds = 0
            print(
                f"Resource status: {resource_data.status}, waiting for 'processed'..."
            )
        await asyncio.sleep(1)
    return False


@pytest.mark.parametrize(
    "memory_klass",
    [NucliaMemory, AsyncNucliaMemory],
)
async def test_basic(
    testing_config,
    memory_klass: Union[Type[NucliaMemory], Type[AsyncNucliaMemory]],
) -> None:

    USER_A = "user-a"

    memory = memory_klass()
    await maybe_await(
        memory.initialize(
            rules=[
                "Facts are to be indexed into an HR pipeline, they must be informative, objective, verifiable statements that can be used to inform future decisions.",
                "If an employee ID is provided, it must appear in all the facts related to that employee, to ensure they can be linked together in the HR system.",
            ],
            graph_extraction=True,
            overwrite=True,
        )
    )
    # Make sure re-initializing with different rules raises an error
    with pytest.raises(ValueError):
        await maybe_await(
            memory.initialize(rules=["foobar"], graph_extraction=False, overwrite=False)
        )

    async def _cleanup():
        for slug in [
            RESOURCE_VACATION_POLICY,
            RESOURCE_VACATION_POLICY_LINK,
            RESOURCE_VACATION_POLICY_FILE,
        ]:
            try:
                await maybe_await(memory.delete_resource(resource=slug, confirm=True))
            except ResourceNotFoundError:
                continue

    # Make sure resource doesn't exist at test start
    await _cleanup()

    # Test creating resource with a text content
    await maybe_await(
        memory.create_resource(
            texts={
                "text": "Our vacation policy allows employees to take 20 days of paid leave per year."
                "Employees can also carry over up to 5 unused days to the next year."
                "To request vacation, employees must submit a request form at least 2 weeks in advance."
                "In case of emergencies, employees can request last-minute leave, which will be evaluated on a case by case basis."
            },
            slug=RESOURCE_VACATION_POLICY,
            title="Company Vacation Policy",
            summary="Company's vacation policy including leave days, carry over, and request process.",
        )
    )

    # Test getting the created resource
    resource = await maybe_await(memory.get_resource(resource=RESOURCE_VACATION_POLICY))
    assert resource.slug == RESOURCE_VACATION_POLICY
    assert resource.title == "Company Vacation Policy"
    assert (
        resource.summary
        == "Company's vacation policy including leave days, carry over, and request process."
    )

    # Test listing resources after creation
    resource_page = await maybe_await(
        memory.list_resources(query="Company Vacation Policy", size=1)
    )
    assert len(resource_page.items) == 1
    assert resource_page.items[0].slug == RESOURCE_VACATION_POLICY
    assert resource_page.items[0].title == "Company Vacation Policy"
    assert (
        resource_page.items[0].summary
        == "Company's vacation policy including leave days, carry over, and request process."
    )

    # Try creating a resource with the same slug, should raise error
    with pytest.raises(ResourceAlreadyExistsError):
        await maybe_await(
            memory.create_resource(
                texts={"text": "Duplicate resource content"},
                slug=RESOURCE_VACATION_POLICY,
                title="Duplicate Vacation Policy",
                summary="This should not be created.",
            )
        )

    # Test creating a resource with a link content
    await maybe_await(
        memory.create_resource(
            urls={"link": "https://www.example.com/vacation-policy"},
            slug=RESOURCE_VACATION_POLICY_LINK,
            title="Vacation Policy Link",
            summary="Link to the company's vacation policy page.",
        )
    )

    # Test creating a resource with a file content
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        tmp_file.write(b"File content")
        tmp_file.seek(0)
        await maybe_await(
            memory.create_resource(
                file_paths={"file": tmp_file.name},
                slug=RESOURCE_VACATION_POLICY_FILE,
                title="Vacation Policy File",
                summary="File containing the company's vacation policy.",
            )
        )

    # Test adding another content to an existing resource
    await maybe_await(
        memory.update_resource(
            texts={"text2": "Additional information about the vacation policy."},
            resource=RESOURCE_VACATION_POLICY,
        )
    )
    await maybe_await(
        memory.update_resource(
            urls={"link2": "https://www.example.com/vacation-policy-faq"},
            resource=RESOURCE_VACATION_POLICY,
        )
    )
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        tmp_file.write(b"Additional file content")
        tmp_file.seek(0)
        await maybe_await(
            memory.update_resource(
                file_paths={"file2": tmp_file.name},
                resource=RESOURCE_VACATION_POLICY,
            )
        )

    # Remember an entry attached to the resource
    await maybe_await(
        memory.remember(
            "Approved carry-over exception for Maria (employee ID: EMP-1042). "
            "She was unable to take her remaining 8 vacation days due to a critical product launch in Q4. "
            "Exception approved for the full 8 days as a one-time allowance.",
            session_id=USER_A,
            resource=RESOURCE_VACATION_POLICY,
            reasoning="The product launch was a company-wide priority that required Maria's presence. "
            "Denying the exception would penalise her for meeting business needs.",
            context=[
                EntryContextMessage(
                    author="Maria (employee)",
                    text="I had 8 vacation days remaining but couldn't take them because of the Q4 launch. Can I carry them over?",
                ),
                EntryContextMessage(
                    author="Maria's manager",
                    text="Confirmed — Maria's presence was essential during the entire Q4 period.",
                ),
            ],
            metadata={
                "employee_id": "EMP-1042",
                "employee_name": "Maria Santos",
                "department": "Engineering",
                "decision": "approved",
                "days_requested": 8,
                "exception_type": "carry-over",
                "supporting_evidence": [
                    "manager_confirmation",
                    "business_critical_event",
                ],
            },
        )
    )
    await maybe_await(
        memory.remember(
            "Denied carry-over exception for Leo (EMP-5512). "
            "Leo had adequate opportunity to schedule vacation during the year and did not do so. "
            "The 6 days will be forfeited per standard policy.",
            resource=RESOURCE_VACATION_POLICY,
            session_id=USER_A,
            reasoning="Unlike cases involving company-mandated business needs, Leo's unused days reflect "
            "personal planning choices. Policy should be applied as written.",
            context=[
                EntryContextMessage(
                    author="Leo (employee)",
                    text="I forgot to use 6 vacation days. Can I carry them over to next year?",
                ),
            ],
            metadata={
                "employee_id": "EMP-5512",
                "employee_name": "Leo Fernandez",
                "department": "Sales",
                "decision": "denied",
                "days_requested": 6,
                "exception_type": "carry-over",
                "supporting_evidence": [],
            },
        )
    )

    # Make sure entries are retrievable
    entries = [
        e
        async for e in maybe_async_iterate(
            memory.entries(session_id=USER_A, resource=RESOURCE_VACATION_POLICY)
        )
    ]
    assert len(entries) >= 1, "Expected at least one resource entry."

    # Check that querying a non-existent resource or session returns no entries
    entries_non_existent_resource = [
        e
        async for e in maybe_async_iterate(
            memory.entries(session_id=USER_A, resource="non-existent-resource")
        )
    ]
    assert len(entries_non_existent_resource) == 0, (
        "Expected no entries for a non-existent resource."
    )
    entries_non_existent_session = [
        e
        async for e in maybe_async_iterate(
            memory.entries(
                session_id="non-existent-session", resource=RESOURCE_VACATION_POLICY
            )
        )
    ]
    assert len(entries_non_existent_session) == 0, (
        "Expected no entries for a non-existent session."
    )

    # Wait until the resource is ready for search before recall tests
    processed = await _wait_until_resource_ready_for_search(
        memory,
        resource=RESOURCE_VACATION_POLICY,
        session_id=USER_A,
        min_resource_facts=2,
    )

    assert processed, "Resource was not processed within the expected time."

    result = await maybe_await(
        memory.ask(
            query="Can employees carry over unused vacation days?",
            resource=RESOURCE_VACATION_POLICY,
        )
    )
    assert "5" in result.answer, (
        "Recall did not return expected information about carry over days."
    )
    assert len(result.citations) >= 1, "Recall did not return any citations."

    # Facts tests
    facts = [
        f
        async for f in maybe_async_iterate(
            memory.facts(resource=RESOURCE_VACATION_POLICY, session_id=USER_A)
        )
    ]
    assert len(facts) >= 2, "Expected at least two fact for the resource."
    oldest_first = [
        f
        async for f in maybe_async_iterate(
            memory.facts(
                resource=RESOURCE_VACATION_POLICY, session_id=USER_A, recent_first=False
            )
        )
    ]
    assert oldest_first[0].id == facts[-1].id
    assert oldest_first[-1].id == facts[0].id

    # Check that facts for non-existent resource or session return no facts
    assert [
        f
        async for f in maybe_async_iterate(
            memory.facts(resource="non-existent-resource", session_id=USER_A)
        )
    ] == [], "Expected no facts for a non-existent resource."
    assert [
        f
        async for f in maybe_async_iterate(
            memory.facts(
                resource=RESOURCE_VACATION_POLICY, session_id="non-existent-session"
            )
        )
    ] == [], "Expected no facts for a non-existent session."

    # List sessions tests
    sessions_in_resource = await maybe_await(
        memory.list_sessions(resource=RESOURCE_VACATION_POLICY)
    )
    assert sessions_in_resource == [USER_A], (
        f"{USER_A} should be listed as a session in 'vacation-policy' resource."
    )

    # Make sure that entries and facts are searchable
    assert (
        await find_message(
            memory, message_text=entries[0].content.text, message_id=entries[0].id
        )
        is True
    )

    assert (
        await find_message(
            memory, message_text=facts[0].content.text, message_id=facts[0].id
        )
        is True
    )

    # Recall tests
    recall_blocks = await maybe_await(
        memory.recall(
            question=facts[0].content.text,
            resource=RESOURCE_VACATION_POLICY,
            session_id=USER_A,
            top_k=20,
            find_request_overrides={"min_score": 0},
        )
    )
    assert len(recall_blocks) >= 1, "Recall did not return any context blocks."
    assert any(block.text for block in recall_blocks), (
        "Recall returned empty context blocks."
    )

    # Listing sessions for a non-existent resource should raise ResourceNotFoundError
    with pytest.raises(ResourceNotFoundError):
        await maybe_await(memory.list_sessions(resource="non-existent-resource"))

    # Pagination tests
    page = 0
    while True:
        resource_page = await maybe_await(memory.list_resources(size=1, page=page))
        if len(resource_page.items) == 0 or resource_page.has_more is False:
            break
        page += 1

    assert page >= 2

    # Graph tests, they are created after facts are processed, so we need to wait a bit
    graph_ready = False
    for _ in range(60):
        graph_result = await maybe_await(
            memory.graph(resource=RESOURCE_VACATION_POLICY, session_id=USER_A)
        )
        if len(graph_result) >= 1:
            graph_ready = True
            break
        else:
            print("Graph not ready yet, waiting...")
            await asyncio.sleep(1)
    graph_result = await maybe_await(
        memory.graph(resource=RESOURCE_VACATION_POLICY, session_id=USER_A)
    )
    assert graph_ready, "Graph did not become ready in time."
    assert len(graph_result) >= 1, "Graph should contain at least one path."

    # Test forgetting entries cascades to corresponding facts
    entries_before_forget = [
        e
        async for e in maybe_async_iterate(
            memory.entries(session_id=USER_A, resource=RESOURCE_VACATION_POLICY)
        )
    ]

    facts_before_forget = [
        f
        async for f in maybe_async_iterate(
            memory.facts(resource=RESOURCE_VACATION_POLICY, session_id=USER_A)
        )
    ]
    assert len(entries_before_forget) >= 1, "Expected at least one resource entry."
    assert len(facts_before_forget) >= 1, "Expected at least one resource fact."

    for entry in entries_before_forget:
        await maybe_await(
            memory.forget_entry(
                session_id=USER_A, resource=RESOURCE_VACATION_POLICY, entry_id=entry.id
            )
        )

    assert [
        f
        async for f in maybe_async_iterate(
            memory.facts(resource=RESOURCE_VACATION_POLICY, session_id=USER_A)
        )
    ] == [], (
        "Forgetting resource entries should also delete corresponding resource facts."
    )

    await maybe_await(
        memory.forget_entries(session_id=USER_A, resource=RESOURCE_VACATION_POLICY)
    )

    assert [
        e
        async for e in maybe_async_iterate(
            memory.entries(session_id=USER_A, resource=RESOURCE_VACATION_POLICY)
        )
    ] == [], "All resource entries for user-a session should have been deleted."

    assert [
        f
        async for f in maybe_async_iterate(
            memory.facts(resource=RESOURCE_VACATION_POLICY, session_id=USER_A)
        )
    ] == [], (
        "Forgetting resource entries should also delete corresponding resource facts."
    )

    # No-op cleanup calls should still be safe
    await maybe_await(
        memory.forget_facts(session_id=USER_A, resource=RESOURCE_VACATION_POLICY)
    )
    await maybe_await(
        memory.forget_fact(
            session_id=USER_A,
            resource=RESOURCE_VACATION_POLICY,
            fact_id=facts_before_forget[0].id,
        )
    )

    # Test delete resources
    with pytest.raises(ValueError):
        # Deleting without confirm should raise error
        await maybe_await(memory.delete_resource(resource=RESOURCE_VACATION_POLICY))

    await _cleanup()


async def find_message(
    memory: NucliaMemory | AsyncNucliaMemory, message_text: str, message_id: str
) -> bool:
    find_results = await maybe_await(
        memory.kb.search.find(
            query=message_text,
            top_k=1,
        )
    )
    return any(best_match.startswith(message_id) for best_match in find_results)


@pytest.mark.parametrize(
    "memory_klass",
    [NucliaMemory, AsyncNucliaMemory],
)
async def test_basic_nonresource(
    testing_config,
    memory_klass: Union[Type[NucliaMemory], Type[AsyncNucliaMemory]],
) -> None:
    """Test the memory API without attaching any content to a resource.

    Covers global entries: remember, listing, deduplication, and deletion.
    """
    USER_A = "user-axx"
    USER_B = "user-bxx"

    memory = memory_klass()

    async def _cleanup():
        # Remove all global entries for both test sessions
        for session_id in (USER_A, USER_B):
            await maybe_await(memory.forget_entries(session_id=session_id))

    await _cleanup()

    # ── remember globally ───────────────────────────────────────────────────

    entry_id_1 = await maybe_await(
        memory.remember(
            "I prefer concise bullet-point summaries.",
            session_id=USER_A,
        )
    )
    assert entry_id_1, "remember() should return a non-empty entry ID."

    entry_id_2 = await maybe_await(
        memory.remember(
            "Always respond in Spanish.",
            session_id=USER_A,
            reasoning="User's preferred language is Spanish.",
            context=[
                EntryContextMessage(author=USER_A, text="Hola, ¿cómo estás?"),
            ],
        )
    )

    # A different session can annotate independently
    entry_id_3 = await maybe_await(
        memory.remember(
            "Prefers detailed explanations.",
            session_id=USER_B,
        )
    )

    # ── duplicate entry ID is rejected ────────────────────────────────

    with pytest.raises(EntryAlreadyExistsError):
        await maybe_await(
            memory.remember(
                "Duplicate.",
                session_id=USER_A,
                entry_id=entry_id_1,
            )
        )

    # ── list global entries ─────────────────────────────────────────────

    session_a_entries = [
        e async for e in maybe_async_iterate(memory.entries(session_id=USER_A))
    ]
    assert len(session_a_entries) == 2, (
        f"Expected 2 global entries for {USER_A}, got {len(session_a_entries)}."
    )
    # Most-recent-first: entry_id_2 should come before entry_id_1
    assert session_a_entries[0].id == entry_id_2
    assert session_a_entries[1].id == entry_id_1

    session_b_entries = [
        e async for e in maybe_async_iterate(memory.entries(session_id=USER_B))
    ]
    assert len(session_b_entries) == 1
    assert session_b_entries[0].id == entry_id_3

    # oldest-first ordering
    session_a_oldest_first = [
        e
        async for e in maybe_async_iterate(
            memory.entries(session_id=USER_A, recent_first=False)
        )
    ]
    assert session_a_oldest_first[0].id == entry_id_1
    assert session_a_oldest_first[1].id == entry_id_2

    # ── entry content is preserved ────────────────────────────────────

    entry = session_a_entries[0]  # entry_id_2
    assert entry.content.text == "Always respond in Spanish."
    assert entry.content.reasoning == "User's preferred language is Spanish."
    assert entry.content.context is not None
    assert entry.content.context[0].author == USER_A

    # ── delete a single global entry ──────────────────────────────────
    await maybe_await(memory.forget_entry(session_id=USER_A, entry_id=entry_id_1))
    session_a_entries = [
        e async for e in maybe_async_iterate(memory.entries(session_id=USER_A))
    ]
    assert len(session_a_entries) == 1
    assert session_a_entries[0].id == entry_id_2

    # Forgetting a non-existent entry should be a no-op
    await maybe_await(memory.forget_entry(session_id=USER_A, entry_id="nonexistent-id"))

    # ── delete all global entries for a session ────────────────────────────

    await maybe_await(memory.forget_entries(session_id=USER_A))
    session_a_entries = [
        e async for e in maybe_async_iterate(memory.entries(session_id=USER_A))
    ]
    assert len(session_a_entries) == 0, (
        "All global entries for session A should have been deleted."
    )

    # User B's entries are unaffected
    session_b_entries = [
        e async for e in maybe_async_iterate(memory.entries(session_id=USER_B))
    ]
    assert len(session_b_entries) == 1

    # ── list sessions (global, no resource) ──────────────────────────────────

    all_sessions = await maybe_await(memory.list_sessions())
    assert USER_B in all_sessions, (
        f"{USER_B} should appear in global session list (still has an entry)."
    )
    # USER_A's global entries were all deleted, so they should not appear
    assert USER_A not in all_sessions, (
        f"{USER_A} should not appear in global session list after all entries were deleted."
    )

    await _cleanup()
