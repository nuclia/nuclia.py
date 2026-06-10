import tempfile
import time

import pytest

from nuclia.sdk.memory import (
    AnnotationAlreadyExistsError,
    AnnotationContextMessage,
    NucliaMemory,
    TopicAlreadyExistsError,
    TopicNotFoundError,
)


def test_basic(testing_config):
    memory = NucliaMemory()

    def _delete_topics(slugs):
        for slug in slugs:
            try:
                memory.forget(topic=slug, confirm=True)
            except TopicNotFoundError:
                pass

    # Make sure topic doesn't exist at test start
    _delete_topics(["vacation-policy", "vacation-policy-link", "vacation-policy-file"])

    # Test creating topic with a text content
    memory.store(
        "Our vacation policy allows employees to take 20 days of paid leave per year."
        "Employees can also carry over up to 5 unused days to the next year."
        "To request vacation, employees must submit a request form at least 2 weeks in advance."
        "In case of emergencies, employees can request last-minute leave, which will be evaluated on a case by case basis.",
        slug="vacation-policy",
        title="Company Vacation Policy",
        summary="Company's vacation policy including leave days, carry over, and request process.",
    )

    # Test getting the created topic
    topic = memory.get(topic="vacation-policy")
    assert topic.slug == "vacation-policy"
    assert topic.title == "Company Vacation Policy"
    assert (
        topic.summary
        == "Company's vacation policy including leave days, carry over, and request process."
    )

    # Test listing topics after creation
    topic_page = memory.list(query="Company Vacation Policy", size=1)
    assert len(topic_page.items) == 1
    assert topic_page.items[0].slug == "vacation-policy"
    assert topic_page.items[0].title == "Company Vacation Policy"
    assert (
        topic_page.items[0].summary
        == "Company's vacation policy including leave days, carry over, and request process."
    )

    # Try creating a topic with the same slug, should raise error
    with pytest.raises(TopicAlreadyExistsError):
        memory.store(
            "Duplicate topic content",
            slug="vacation-policy",
            title="Duplicate Vacation Policy",
            summary="This should not be created.",
        )

    # Test creating a topic with a link content
    memory.store(
        "https://www.example.com/vacation-policy",
        slug="vacation-policy-link",
        title="Vacation Policy Link",
        summary="Link to the company's vacation policy page.",
    )

    # Test creating a topic with a file content
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        tmp_file.write(b"File content")
        tmp_file.seek(0)
        memory.store(
            path=tmp_file.name,
            slug="vacation-policy-file",
            title="Vacation Policy File",
            summary="File containing the company's vacation policy.",
        )

    # Test adding another content to an existing topic
    memory.store(
        text="Additional information about the vacation policy.",
        topic="vacation-policy",
    )
    memory.store(
        url="https://www.example.com/vacation-policy-faq",
        topic="vacation-policy",
    )
    with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
        tmp_file.write(b"Additional file content")
        tmp_file.seek(0)
        memory.store(
            path=tmp_file.name,
            topic="vacation-policy",
        )

    # Wait until the topic status is processed before the recall tests
    processed = False
    for _ in range(60):
        topic = memory.get(topic="vacation-policy")
        if topic.status == "processed":
            processed = True
            break
        else:
            print(f"Topic status: {topic.status}, waiting for 'processed'...")
            time.sleep(1)

    assert processed, "Topic was not processed within the expected time."

    result = memory.recall(
        query="Can employees carry over unused vacation days?",
        topic="vacation-policy",
    )
    assert "5" in result.answer, (
        "Recall did not return expected information about carry over days."
    )
    assert len(result.citations) >= 1, "Recall did not return any citations."

    # Pagination tests
    page = 0
    while True:
        topic_page = memory.list(size=1, page=page)
        if len(topic_page.items) == 0 or topic_page.has_more is False:
            break
        page += 1

    assert page >= 2

    # Test delete topics
    with pytest.raises(ValueError):
        # Deleting without confirm should raise error
        memory.forget(topic="vacation-policy")

    _delete_topics(["vacation-policy", "vacation-policy-link", "vacation-policy-file"])


def test_basic_nontopic(testing_config):
    """Test the memory API without attaching any content to a topic.

    Covers global annotations: annotating, listing, deduplication, and deletion.
    """
    memory = NucliaMemory()
    USER_A = "user-a"
    USER_B = "user-b"

    def _cleanup():
        # Remove all global annotations for both test users
        for uid in (USER_A, USER_B):
            memory.forget(user_id=uid)

    _cleanup()

    # ── annotate globally ───────────────────────────────────────────────────

    annotation_id_1 = memory.annotate(
        "I prefer concise bullet-point summaries.",
        user_id=USER_A,
    )
    assert annotation_id_1, "annotate() should return a non-empty annotation ID."

    annotation_id_2 = memory.annotate(
        "Always respond in Spanish.",
        user_id=USER_A,
        reasoning="User's preferred language is Spanish.",
        context=[
            AnnotationContextMessage(author=USER_A, text="Hola, ¿cómo estás?"),
        ],
    )

    # A different user can annotate independently
    annotation_id_3 = memory.annotate(
        "Prefers detailed explanations.",
        user_id=USER_B,
    )

    # ── duplicate annotation ID is rejected ────────────────────────────────

    with pytest.raises(AnnotationAlreadyExistsError):
        memory.annotate(
            "Duplicate.",
            user_id=USER_A,
            annotation_id=annotation_id_1,
        )

    # ── list global annotations ─────────────────────────────────────────────

    user_a_annotations = list(memory.annotations(user_id=USER_A))
    assert len(user_a_annotations) == 2, (
        f"Expected 2 global annotations for {USER_A}, got {len(user_a_annotations)}."
    )
    # Most-recent-first: annotation_id_2 should come before annotation_id_1
    assert user_a_annotations[0].id == annotation_id_2
    assert user_a_annotations[1].id == annotation_id_1

    user_b_annotations = list(memory.annotations(user_id=USER_B))
    assert len(user_b_annotations) == 1
    assert user_b_annotations[0].id == annotation_id_3

    # oldest-first ordering
    user_a_oldest_first = list(memory.annotations(user_id=USER_A, recent_first=False))
    assert user_a_oldest_first[0].id == annotation_id_1
    assert user_a_oldest_first[1].id == annotation_id_2

    # ── annotation content is preserved ────────────────────────────────────

    annotation = user_a_annotations[0]  # annotation_id_2
    assert annotation.content.text == "Always respond in Spanish."
    assert annotation.content.reasoning == "User's preferred language is Spanish."
    assert annotation.content.context is not None
    assert annotation.content.context[0].author == USER_A

    # ── delete a single global annotation ──────────────────────────────────

    memory.forget(user_id=USER_A, annotation_id=annotation_id_1)
    user_a_annotations = list(memory.annotations(user_id=USER_A))
    assert len(user_a_annotations) == 1
    assert user_a_annotations[0].id == annotation_id_2

    # Forgetting a non-existent annotation should be a no-op
    memory.forget(user_id=USER_A, annotation_id="nonexistent-id")

    # ── delete all global annotations for a user ────────────────────────────

    memory.forget(user_id=USER_A)
    user_a_annotations = list(memory.annotations(user_id=USER_A))
    assert len(user_a_annotations) == 0, (
        "All global annotations for user A should have been deleted."
    )

    # User B's annotations are unaffected
    user_b_annotations = list(memory.annotations(user_id=USER_B))
    assert len(user_b_annotations) == 1

    _cleanup()
