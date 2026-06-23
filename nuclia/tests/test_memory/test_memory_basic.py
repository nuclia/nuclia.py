import tempfile
import time

import pytest

from nuclia.sdk.memory import (
    EntryAlreadyExistsError,
    EntryContextMessage,
    NucliaMemory,
    TopicAlreadyExistsError,
    TopicNotFoundError,
)


def test_basic(testing_config) -> None:
    memory = NucliaMemory()
    memory.initialize(
        rules=[
            "Extract HR relevant information from the text like vacation policy, sick leave, and benefits.",
        ],
        graph_extraction=True,
    )
    # Make sure re-initializing with different rules raises an error
    with pytest.raises(ValueError):
        memory.initialize(rules=["foobar"], graph_extraction=False, overwrite=False)

    def _delete_topics(slugs):
        for slug in slugs:
            try:
                memory.delete_topic(topic=slug, confirm=True)
            except TopicNotFoundError:
                pass

    # Make sure topic doesn't exist at test start
    _delete_topics(["vacation-policy", "vacation-policy-link", "vacation-policy-file"])

    # Test creating topic with a text content
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

    # Test getting the created topic
    topic = memory.get_topic(topic="vacation-policy")
    assert topic.slug == "vacation-policy"
    assert topic.title == "Company Vacation Policy"
    assert (
        topic.summary
        == "Company's vacation policy including leave days, carry over, and request process."
    )

    # Test listing topics after creation
    topic_page = memory.list_topics(query="Company Vacation Policy", size=1)
    assert len(topic_page.items) == 1
    assert topic_page.items[0].slug == "vacation-policy"
    assert topic_page.items[0].title == "Company Vacation Policy"
    assert (
        topic_page.items[0].summary
        == "Company's vacation policy including leave days, carry over, and request process."
    )

    # Try creating a topic with the same slug, should raise error
    with pytest.raises(TopicAlreadyExistsError):
        memory.create_topic(
            texts={"text": "Duplicate topic content"},
            slug="vacation-policy",
            title="Duplicate Vacation Policy",
            summary="This should not be created.",
        )

    # Test creating a topic with a link content
    memory.create_topic(
        urls={"link": "https://www.example.com/vacation-policy"},
        slug="vacation-policy-link",
        title="Vacation Policy Link",
        summary="Link to the company's vacation policy page.",
    )

    # Test creating a topic with a file content
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        tmp_file.write(b"File content")
        tmp_file.seek(0)
        memory.create_topic(
            file_paths={"file": tmp_file.name},
            slug="vacation-policy-file",
            title="Vacation Policy File",
            summary="File containing the company's vacation policy.",
        )

    # Test adding another content to an existing topic
    memory.update_topic(
        texts={"text2": "Additional information about the vacation policy."},
        topic="vacation-policy",
    )
    memory.update_topic(
        urls={"link2": "https://www.example.com/vacation-policy-faq"},
        topic="vacation-policy",
    )
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        tmp_file.write(b"Additional file content")
        tmp_file.seek(0)
        memory.update_topic(
            file_paths={"file2": tmp_file.name},
            topic="vacation-policy",
        )

    # Remember an entry globally (not attached to any topic)
    memory.remember(
        "Employees should submit vacation requests at least 2 weeks in advance.",
        user_id="user-a",
        entry_id="foobar",
    )
    # Remember an entry attached to the topic
    memory.remember(
        "Employees can carry over up to 5 unused vacation days to the next year.",
        user_id="user-a",
        topic="vacation-policy",
    )

    # Make sure entries are retrievable
    global_entries = list(memory.entries(user_id="user-a"))
    assert len(global_entries) >= 1, "Expected at least one global entry."

    topic_entries = list(memory.entries(user_id="user-a", topic="vacation-policy"))
    assert len(topic_entries) >= 1, "Expected at least one topic entry."

    # Wait until the topic status is processed before the recall tests
    processed = False
    for _ in range(60):
        topic = memory.get_topic(topic="vacation-policy")
        if topic.status == "processed":
            processed = True
            break
        else:
            print(f"Topic status: {topic.status}, waiting for 'processed'...")
            time.sleep(1)

    assert processed, "Topic was not processed within the expected time."

    result = memory.ask(
        query="Can employees carry over unused vacation days?",
        topic="vacation-policy",
    )
    assert "5" in result.answer, (
        "Recall did not return expected information about carry over days."
    )
    assert len(result.citations) >= 1, "Recall did not return any citations."

    # Facts tests
    facts = list(memory.facts(topic="vacation-policy", user_id="user-a"))
    assert len(facts) >= 1, "Expected at least one fact for the topic."
    oldest_first = list(
        memory.facts(topic="vacation-policy", user_id="user-a", recent_first=False)
    )
    assert oldest_first[0].id == facts[-1].id
    assert oldest_first[1].id == facts[0].id

    global_facts = list(memory.facts(user_id="user-a"))
    assert len(global_facts) >= 1, "Expected at least one global fact."

    # Pagination tests
    page = 0
    while True:
        topic_page = memory.list_topics(size=1, page=page)
        if len(topic_page.items) == 0 or topic_page.has_more is False:
            break
        page += 1

    assert page >= 2

    # Graph tests
    graph = memory.graph(topic="vacation-policy", user_id="user-a")
    assert len(graph) >= 1, "Graph should contain at least one path."

    # Test forgetting facts and entries
    memory.forget_fact(user_id="user-a", fact_id=global_facts[0].id)
    memory.forget_fact(user_id="user-a", topic="vacation-policy", fact_id=facts[1].id)
    memory.forget_facts(user_id="user-a", topic="vacation-policy")
    memory.forget_facts(user_id="user-a")
    memory.forget_entry(user_id="user-a", entry_id=global_entries[0].id)
    memory.forget_entries(
        user_id="user-a", topic="vacation-policy", entry_id=topic_entries[0].id
    )
    memory.forget_entries(user_id="user-a", topic="vacation-policy")
    memory.forget_entries(user_id="user-a")

    # Test delete topics
    with pytest.raises(ValueError):
        # Deleting without confirm should raise error
        memory.delete_topic(topic="vacation-policy")

    _delete_topics(["vacation-policy", "vacation-policy-link", "vacation-policy-file"])


def test_basic_nontopic(testing_config) -> None:
    """Test the memory API without attaching any content to a topic.

    Covers global entries: remember, listing, deduplication, and deletion.
    """
    memory = NucliaMemory()
    USER_A = "user-a"
    USER_B = "user-b"

    def _cleanup():
        # Remove all global entries for both test users
        for uid in (USER_A, USER_B):
            memory.forget_entries(user_id=uid)

    _cleanup()

    # ── remember globally ───────────────────────────────────────────────────

    entry_id_1 = memory.remember(
        "I prefer concise bullet-point summaries.",
        user_id=USER_A,
    )
    assert entry_id_1, "remember() should return a non-empty entry ID."

    entry_id_2 = memory.remember(
        "Always respond in Spanish.",
        user_id=USER_A,
        reasoning="User's preferred language is Spanish.",
        context=[
            EntryContextMessage(author=USER_A, text="Hola, ¿cómo estás?"),
        ],
    )

    # A different user can annotate independently
    entry_id_3 = memory.remember(
        "Prefers detailed explanations.",
        user_id=USER_B,
    )

    # ── duplicate entry ID is rejected ────────────────────────────────

    with pytest.raises(EntryAlreadyExistsError):
        memory.remember(
            "Duplicate.",
            user_id=USER_A,
            entry_id=entry_id_1,
        )

    # ── list global entries ─────────────────────────────────────────────

    user_a_entrys = list(memory.entries(user_id=USER_A))
    assert len(user_a_entrys) == 2, (
        f"Expected 2 global entrys for {USER_A}, got {len(user_a_entrys)}."
    )
    # Most-recent-first: entry_id_2 should come before entry_id_1
    assert user_a_entrys[0].id == entry_id_2
    assert user_a_entrys[1].id == entry_id_1

    user_b_entrys = list(memory.entries(user_id=USER_B))
    assert len(user_b_entrys) == 1
    assert user_b_entrys[0].id == entry_id_3

    # oldest-first ordering
    user_a_oldest_first = list(memory.entries(user_id=USER_A, recent_first=False))
    assert user_a_oldest_first[0].id == entry_id_1
    assert user_a_oldest_first[1].id == entry_id_2

    # ── entry content is preserved ────────────────────────────────────

    entry = user_a_entrys[0]  # entry_id_2
    assert entry.content.text == "Always respond in Spanish."
    assert entry.content.reasoning == "User's preferred language is Spanish."
    assert entry.content.context is not None
    assert entry.content.context[0].author == USER_A

    # ── delete a single global entry ──────────────────────────────────

    memory.forget_entry(user_id=USER_A, entry_id=entry_id_1)
    user_a_entrys = list(memory.entries(user_id=USER_A))
    assert len(user_a_entrys) == 1
    assert user_a_entrys[0].id == entry_id_2

    # Forgetting a non-existent entry should be a no-op
    memory.forget_entry(user_id=USER_A, entry_id="nonexistent-id")

    # ── delete all global entrys for a user ────────────────────────────

    memory.forget_entries(user_id=USER_A)
    user_a_entrys = list(memory.entries(user_id=USER_A))
    assert len(user_a_entrys) == 0, (
        "All global entrys for user A should have been deleted."
    )

    # User B's entrys are unaffected
    user_b_entrys = list(memory.entries(user_id=USER_B))
    assert len(user_b_entrys) == 1

    _cleanup()
