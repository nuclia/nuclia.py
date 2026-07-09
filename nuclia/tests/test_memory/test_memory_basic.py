import asyncio
import tempfile
from typing import Type, Union

import pytest

from nuclia.sdk.memory import (
    AsyncNucliaMemory,
    EntryAlreadyExistsError,
    EntryContextMessage,
    NucliaMemory,
    TopicAlreadyExistsError,
    TopicNotFoundError,
)
from nuclia.tests.utils import maybe_async_iterate, maybe_await


@pytest.mark.parametrize(
    "memory_klass",
    [NucliaMemory, AsyncNucliaMemory],
)
async def test_basic(
    testing_config,
    memory_klass: Union[Type[NucliaMemory], Type[AsyncNucliaMemory]],
) -> None:
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

    async def _cleanup(slugs):
        for slug in slugs:
            try:
                await maybe_await(memory.delete_topic(topic=slug, confirm=True))
            except TopicNotFoundError:
                pass
            await maybe_await(memory.forget_entries(user_id="user-a", topic=slug))
            await maybe_await(memory.forget_facts(user_id="user-a", topic=slug))
        await maybe_await(memory.forget_entries(user_id="user-a"))
        await maybe_await(memory.forget_facts(user_id="user-a"))

    # Make sure topic doesn't exist at test start
    await _cleanup(["vacation-policy", "vacation-policy-link", "vacation-policy-file"])

    # Test creating topic with a text content
    await maybe_await(
        memory.create_topic(
            texts={
                "text": "Our vacation policy allows employees to take 20 days of paid leave per year."
                "Employees can also carry over up to 5 unused days to the next year."
                "To request vacation, employees must submit a request form at least 2 weeks in advance."
                "In case of emergencies, employees can request last-minute leave, which will be evaluated on a case by case basis."
            },
            slug="vacation-policy",
            title="Company Vacation Policy",
            summary="Company's vacation policy including leave days, carry over, and request process.",
        )
    )

    # Test getting the created topic
    topic = await maybe_await(memory.get_topic(topic="vacation-policy"))
    assert topic.slug == "vacation-policy"
    assert topic.title == "Company Vacation Policy"
    assert (
        topic.summary
        == "Company's vacation policy including leave days, carry over, and request process."
    )

    # Test listing topics after creation
    topic_page = await maybe_await(
        memory.list_topics(query="Company Vacation Policy", size=1)
    )
    assert len(topic_page.items) == 1
    assert topic_page.items[0].slug == "vacation-policy"
    assert topic_page.items[0].title == "Company Vacation Policy"
    assert (
        topic_page.items[0].summary
        == "Company's vacation policy including leave days, carry over, and request process."
    )

    # Try creating a topic with the same slug, should raise error
    with pytest.raises(TopicAlreadyExistsError):
        await maybe_await(
            memory.create_topic(
                texts={"text": "Duplicate topic content"},
                slug="vacation-policy",
                title="Duplicate Vacation Policy",
                summary="This should not be created.",
            )
        )

    # Test creating a topic with a link content
    await maybe_await(
        memory.create_topic(
            urls={"link": "https://www.example.com/vacation-policy"},
            slug="vacation-policy-link",
            title="Vacation Policy Link",
            summary="Link to the company's vacation policy page.",
        )
    )

    # Test creating a topic with a file content
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        tmp_file.write(b"File content")
        tmp_file.seek(0)
        await maybe_await(
            memory.create_topic(
                file_paths={"file": tmp_file.name},
                slug="vacation-policy-file",
                title="Vacation Policy File",
                summary="File containing the company's vacation policy.",
            )
        )

    # Test adding another content to an existing topic
    await maybe_await(
        memory.update_topic(
            texts={"text2": "Additional information about the vacation policy."},
            topic="vacation-policy",
        )
    )
    await maybe_await(
        memory.update_topic(
            urls={"link2": "https://www.example.com/vacation-policy-faq"},
            topic="vacation-policy",
        )
    )
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        tmp_file.write(b"Additional file content")
        tmp_file.seek(0)
        await maybe_await(
            memory.update_topic(
                file_paths={"file2": tmp_file.name},
                topic="vacation-policy",
            )
        )

    # Remember an entry globally (not attached to any topic)
    await maybe_await(
        memory.remember(
            "Charles can always request vacation days. He is entitled to 20 days of paid leave per year.",
            user_id="user-a",
            entry_id="foobar",
        )
    )

    # Remember an entry attached to the topic
    await maybe_await(
        memory.remember(
            "Approved carry-over exception for Maria (employee ID: EMP-1042). "
            "She was unable to take her remaining 8 vacation days due to a critical product launch in Q4. "
            "Exception approved for the full 8 days as a one-time allowance.",
            user_id="user-a",
            topic="vacation-policy",
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
            topic="vacation-policy",
            user_id="user-a",
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
    global_entries = [
        e async for e in maybe_async_iterate(memory.entries(user_id="user-a"))
    ]
    assert len(global_entries) >= 1, "Expected at least one global entry."

    topic_entries = [
        e
        async for e in maybe_async_iterate(
            memory.entries(user_id="user-a", topic="vacation-policy")
        )
    ]
    assert len(topic_entries) >= 1, "Expected at least one topic entry."

    # Wait until the topic status is processed before the recall tests
    processed = False
    for _ in range(60):
        topic = await maybe_await(memory.get_topic(topic="vacation-policy"))
        if topic.status == "processed":
            has_facts = (
                len(
                    [
                        f
                        async for f in maybe_async_iterate(
                            memory.facts(topic="vacation-policy", user_id="user-a")
                        )
                    ]
                )
                >= 2
            )
            if not has_facts:
                print("Topic is processed but facts are not yet available, waiting...")
                await asyncio.sleep(1)
                continue
            processed = True
            break
        else:
            print(f"Topic status: {topic.status}, waiting for 'processed'...")
            await asyncio.sleep(1)

    assert processed, "Topic was not processed within the expected time."

    result = await maybe_await(
        memory.ask(
            query="Can employees carry over unused vacation days?",
            topic="vacation-policy",
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
            memory.facts(topic="vacation-policy", user_id="user-a")
        )
    ]
    assert len(facts) >= 2, "Expected at least two fact for the topic."
    oldest_first = [
        f
        async for f in maybe_async_iterate(
            memory.facts(topic="vacation-policy", user_id="user-a", recent_first=False)
        )
    ]
    assert oldest_first[0].id == facts[-1].id
    assert oldest_first[-1].id == facts[0].id

    global_facts = [
        f async for f in maybe_async_iterate(memory.facts(user_id="user-a"))
    ]
    assert len(global_facts) >= 1, "Expected at least one global fact."

    # Pagination tests
    page = 0
    while True:
        topic_page = await maybe_await(memory.list_topics(size=1, page=page))
        if len(topic_page.items) == 0 or topic_page.has_more is False:
            break
        page += 1

    assert page >= 2

    # Graph tests
    graph_result = await maybe_await(
        memory.graph(topic="vacation-policy", user_id="user-a")
    )
    assert len(graph_result) >= 1, "Graph should contain at least one path."

    # Test forgetting facts and entries
    await maybe_await(memory.forget_fact(user_id="user-a", fact_id=global_facts[0].id))
    await maybe_await(
        memory.forget_fact(
            user_id="user-a", topic="vacation-policy", fact_id=facts[1].id
        )
    )
    await maybe_await(memory.forget_facts(user_id="user-a", topic="vacation-policy"))
    await maybe_await(memory.forget_facts(user_id="user-a"))
    await maybe_await(
        memory.forget_entry(user_id="user-a", entry_id=global_entries[0].id)
    )
    await maybe_await(
        memory.forget_entries(
            user_id="user-a", topic="vacation-policy", entry_id=topic_entries[0].id
        )
    )
    await maybe_await(memory.forget_entries(user_id="user-a", topic="vacation-policy"))
    await maybe_await(memory.forget_entries(user_id="user-a"))

    # Test delete topics
    with pytest.raises(ValueError):
        # Deleting without confirm should raise error
        await maybe_await(memory.delete_topic(topic="vacation-policy"))

    await _cleanup(["vacation-policy", "vacation-policy-link", "vacation-policy-file"])


@pytest.mark.parametrize(
    "memory_klass",
    [NucliaMemory, AsyncNucliaMemory],
)
async def test_basic_nontopic(
    testing_config,
    memory_klass: Union[Type[NucliaMemory], Type[AsyncNucliaMemory]],
) -> None:
    """Test the memory API without attaching any content to a topic.

    Covers global entries: remember, listing, deduplication, and deletion.
    """
    memory = memory_klass()
    USER_A = "user-a"
    USER_B = "user-b"

    async def _cleanup():
        # Remove all global entries for both test users
        for uid in (USER_A, USER_B):
            await maybe_await(memory.forget_entries(user_id=uid))

    await _cleanup()

    # ── remember globally ───────────────────────────────────────────────────

    entry_id_1 = await maybe_await(
        memory.remember(
            "I prefer concise bullet-point summaries.",
            user_id=USER_A,
        )
    )
    assert entry_id_1, "remember() should return a non-empty entry ID."

    entry_id_2 = await maybe_await(
        memory.remember(
            "Always respond in Spanish.",
            user_id=USER_A,
            reasoning="User's preferred language is Spanish.",
            context=[
                EntryContextMessage(author=USER_A, text="Hola, ¿cómo estás?"),
            ],
        )
    )

    # A different user can annotate independently
    entry_id_3 = await maybe_await(
        memory.remember(
            "Prefers detailed explanations.",
            user_id=USER_B,
        )
    )

    # ── duplicate entry ID is rejected ────────────────────────────────

    with pytest.raises(EntryAlreadyExistsError):
        await maybe_await(
            memory.remember(
                "Duplicate.",
                user_id=USER_A,
                entry_id=entry_id_1,
            )
        )

    # ── list global entries ─────────────────────────────────────────────

    user_a_entries = [
        e async for e in maybe_async_iterate(memory.entries(user_id=USER_A))
    ]
    assert len(user_a_entries) == 2, (
        f"Expected 2 global entries for {USER_A}, got {len(user_a_entries)}."
    )
    # Most-recent-first: entry_id_2 should come before entry_id_1
    assert user_a_entries[0].id == entry_id_2
    assert user_a_entries[1].id == entry_id_1

    user_b_entries = [
        e async for e in maybe_async_iterate(memory.entries(user_id=USER_B))
    ]
    assert len(user_b_entries) == 1
    assert user_b_entries[0].id == entry_id_3

    # oldest-first ordering
    user_a_oldest_first = [
        e
        async for e in maybe_async_iterate(
            memory.entries(user_id=USER_A, recent_first=False)
        )
    ]
    assert user_a_oldest_first[0].id == entry_id_1
    assert user_a_oldest_first[1].id == entry_id_2

    # ── entry content is preserved ────────────────────────────────────

    entry = user_a_entries[0]  # entry_id_2
    assert entry.content.text == "Always respond in Spanish."
    assert entry.content.reasoning == "User's preferred language is Spanish."
    assert entry.content.context is not None
    assert entry.content.context[0].author == USER_A

    # ── delete a single global entry ──────────────────────────────────
    await maybe_await(memory.forget_entry(user_id=USER_A, entry_id=entry_id_1))
    user_a_entries = [
        e async for e in maybe_async_iterate(memory.entries(user_id=USER_A))
    ]
    assert len(user_a_entries) == 1
    assert user_a_entries[0].id == entry_id_2

    # Forgetting a non-existent entry should be a no-op
    await maybe_await(memory.forget_entry(user_id=USER_A, entry_id="nonexistent-id"))

    # ── delete all global entries for a user ────────────────────────────

    await maybe_await(memory.forget_entries(user_id=USER_A))
    user_a_entries = [
        e async for e in maybe_async_iterate(memory.entries(user_id=USER_A))
    ]
    assert len(user_a_entries) == 0, (
        "All global entries for user A should have been deleted."
    )

    # User B's entries are unaffected
    user_b_entries = [
        e async for e in maybe_async_iterate(memory.entries(user_id=USER_B))
    ]
    assert len(user_b_entries) == 1

    await _cleanup()
