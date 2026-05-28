import tempfile
import time

import pytest

from nuclia.sdk.memory import NucliaMemory, TopicAlreadyExistsError, TopicNotFoundError


def test_basic(testing_config):
    memory = NucliaMemory()

    # Make sure topic doesn't exist at test start
    try:
        topic = memory.get(topic="vacation-policy")
    except TopicNotFoundError:
        pass
    else:
        # Delete topic if it exists to ensure clean state
        with pytest.raises(ValueError):
            memory.forget(topic=topic.id)
        memory.forget(topic=topic.id, confirm=True)

    # Test getting non-existent topic raises error
    with pytest.raises(TopicNotFoundError):
        memory.get(topic="vacation-policy")

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
    topics = memory.list()
    assert len(topics) == 1
    assert topics[0].slug == "vacation-policy"
    assert topics[0].title == "Company Vacation Policy"
    assert (
        topics[0].summary
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
        topics = memory.list(size=1, page=page)
        if len(topics) == 0:
            break
        page += 1

    assert page >= 2

    # Test delete topic
    for slug in ["vacation-policy", "vacation-policy-link", "vacation-policy-file"]:
        with pytest.raises(ValueError):
            memory.forget(topic=slug)
        memory.forget(topic=slug, confirm=True)
