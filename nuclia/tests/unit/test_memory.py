from unittest.mock import MagicMock, patch

from nucliadb_models.metadata import UserClassification, UserMetadata

from nuclia.sdk.memory.utils import (
    _has_memory_conversation_fields,
    _memory_resource_usermetadata,
    _parse_ask_result,
    _slugify,
    _update_memory_resource_label,
)

# ─── _slugify ─────────────────────────────────────────────────────────────────


class Test_slugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_characters_removed(self):
        assert _slugify("Hello, World!") == "hello--world"

    def test_multiple_spaces(self):
        assert _slugify("hello   world") == "hello---world"

    def test_numbers_preserved(self):
        assert _slugify("Version 2 Release") == "version-2-release"

    def test_already_lowercase(self):
        assert _slugify("already lowercase") == "already-lowercase"

    def test_uppercase(self):
        assert _slugify("ALL CAPS") == "all-caps"

    def test_empty_string(self):
        assert _slugify("") == "untitled"

    def test_only_special_characters(self):
        assert _slugify("!@#$%^&*()") == "untitled"

    def test_unicode_stripped(self):
        assert _slugify("café résumé") == "cafe-resume"

    def test_hyphens_stripped(self):
        # Hyphens not in allowed_characters
        assert _slugify("my-slug") == "my-slug"


class TestMemoryResourceClassification:
    def test_adds_classification_once_and_preserves_metadata(self):
        metadata = UserMetadata(
            classifications=[UserClassification(labelset="department", label="legal")]
        )

        updated = _memory_resource_usermetadata(metadata)
        updated = _memory_resource_usermetadata(updated)

        assert updated == UserMetadata(
            classifications=[
                UserClassification(labelset="department", label="legal"),
                UserClassification(labelset="memory", label="resource"),
            ]
        )

    def test_removes_only_memory_classification(self):
        metadata = UserMetadata(
            classifications=[
                UserClassification(labelset="memory", label="resource"),
                UserClassification(labelset="department", label="legal"),
            ]
        )

        assert _memory_resource_usermetadata(metadata, remove=True) == UserMetadata(
            classifications=[
                UserClassification(labelset="department", label="legal"),
            ]
        )

    def test_detects_entry_and_fact_fields(self):
        entry_resource = MagicMock()
        entry_resource.data.conversations = {"__memory__user": MagicMock()}
        fact_resource = MagicMock()
        fact_resource.data.conversations = {
            "da-facts-memory-c-__memory__user": MagicMock()
        }
        plain_resource = MagicMock()
        plain_resource.data.conversations = {"chat": MagicMock()}

        assert _has_memory_conversation_fields(entry_resource)
        assert _has_memory_conversation_fields(fact_resource)
        assert not _has_memory_conversation_fields(plain_resource)

    def test_cleanup_keeps_classification_while_memory_fields_remain(self):
        ndb = MagicMock(kbid="kb")
        resource = MagicMock()
        resource.data.conversations = {"__memory__user": MagicMock()}

        with patch(
            "nuclia.sdk.memory.utils._get_resource_basic", return_value=resource
        ):
            _update_memory_resource_label(ndb, rid=None, slug="topic", cleanup=True)

        ndb.ndb.update_resource_by_slug.assert_not_called()

    def test_cleanup_removes_classification_after_last_memory_field(self):
        ndb = MagicMock(kbid="kb")
        resource = MagicMock()
        resource.data.conversations = {"chat": MagicMock()}
        resource.usermetadata = UserMetadata(
            classifications=[
                UserClassification(labelset="memory", label="resource"),
                UserClassification(labelset="department", label="legal"),
            ]
        )

        with patch(
            "nuclia.sdk.memory.utils._get_resource_basic", return_value=resource
        ):
            _update_memory_resource_label(ndb, rid=None, slug="topic", cleanup=True)

        ndb.ndb.update_resource_by_slug.assert_called_once_with(
            kbid="kb",
            rslug="topic",
            usermetadata=UserMetadata(
                classifications=[
                    UserClassification(labelset="department", label="legal"),
                ]
            ),
        )


# ─── _parse_ask_result ─────────────────────────────────────────────────────


class TestParseAskAnswer:
    def _make_ask_response(self, answer: str, paragraphs=None, footnote_map=None):
        """Helper to build a mock SyncAskResponse."""
        response = MagicMock()
        response.answer = answer
        response.citation_footnote_to_context = footnote_map or {}

        if paragraphs is None:
            paragraphs = {}

        # Build nested structure: resources -> fields -> paragraphs
        mock_resource = MagicMock()
        mock_field = MagicMock()
        mock_field.paragraphs = paragraphs
        mock_resource.fields = {"field1": mock_field}
        response.retrieval_results.resources = {"res1": mock_resource}

        return response

    def test_no_citations(self) -> None:
        response = self._make_ask_response("Just a plain answer with no citations.")
        result = _parse_ask_result(response)
        assert result.answer == "Just a plain answer with no citations."
        assert result.citations == {}

    def test_single_citation(self) -> None:
        raw = "The policy allows 10 days [1].\n\n[1]: block-AA"
        para = MagicMock()
        para.id = "chunk-123"
        para.text = "A maximum of 10 consecutive days."

        response = self._make_ask_response(
            answer=raw,
            paragraphs={"chunk-123": para},
            footnote_map={"block-AA": "chunk-123"},
        )
        result = _parse_ask_result(response)
        assert result.answer == "The policy allows 10 days [1]."
        assert "1" in result.citations
        assert result.citations["1"].id == "chunk-123"
        assert result.citations["1"].text == "A maximum of 10 consecutive days."

    def test_multiple_citations(self) -> None:
        raw = "Answer text [1] and more [2].\n\n[1]: block-AA\n[2]: block-BB"
        para1 = MagicMock()
        para1.id = "chunk-1"
        para1.text = "First paragraph"
        para2 = MagicMock()
        para2.id = "chunk-2"
        para2.text = "Second paragraph"

        response = self._make_ask_response(
            answer=raw,
            paragraphs={"chunk-1": para1, "chunk-2": para2},
            footnote_map={"block-AA": "chunk-1", "block-BB": "chunk-2"},
        )
        result = _parse_ask_result(response)
        assert result.answer == "Answer text [1] and more [2]."
        assert len(result.citations) == 2
        assert result.citations["1"].id == "chunk-1"
        assert result.citations["1"].text == "First paragraph"
        assert result.citations["2"].id == "chunk-2"
        assert result.citations["2"].text == "Second paragraph"

    def test_citation_with_missing_chunk(self) -> None:
        """Citation references a block that doesn't map to a retrieved paragraph."""
        raw = "Answer [1].\n\n[1]: block-MISSING"
        response = self._make_ask_response(
            answer=raw,
            paragraphs={},
            footnote_map={"block-MISSING": "nonexistent-chunk"},
        )
        result = _parse_ask_result(response)
        assert result.answer == "Answer [1]."
        assert result.citations == {}

    def test_citation_block_not_in_footnote_map(self) -> None:
        """Citation block ID not found in citation_footnote_to_context."""
        raw = "Answer [1].\n\n[1]: block-UNKNOWN"
        response = self._make_ask_response(
            answer=raw,
            paragraphs={},
            footnote_map={},
        )
        result = _parse_ask_result(response)
        assert result.answer == "Answer [1]."
        assert result.citations == {}

    def test_multiline_answer(self) -> None:
        raw = "Line one.\n\nLine two.\n\nLine three.\n\n[1]: block-AA"
        para = MagicMock()
        para.id = "chunk-1"
        para.text = "Source text"
        response = self._make_ask_response(
            answer=raw,
            paragraphs={"chunk-1": para},
            footnote_map={"block-AA": "chunk-1"},
        )
        result = _parse_ask_result(response)
        # rsplit with maxsplit=1 should keep only the last \n\n as the split point
        assert result.answer == "Line one.\n\nLine two.\n\nLine three."
        assert "1" in result.citations

    def test_real_world_example(self) -> None:
        raw = (
            "An employee cannot take 15 consecutive vacation days without director "
            "approval, as the policy allows a maximum of 10 consecutive days without "
            "such approval [1].\n\n[1]: block-AA"
        )
        para = MagicMock()
        para.id = "chunk-vacation"
        para.text = (
            "A maximum of 10 consecutive days can be taken without director approval."
        )
        response = self._make_ask_response(
            answer=raw,
            paragraphs={"chunk-vacation": para},
            footnote_map={"block-AA": "chunk-vacation"},
        )
        result = _parse_ask_result(response)
        assert "15 consecutive vacation days" in result.answer
        assert "\n\n[1]:" not in result.answer
        assert (
            result.citations["1"].text
            == "A maximum of 10 consecutive days can be taken without director approval."
        )
