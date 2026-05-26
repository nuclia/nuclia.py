from unittest.mock import MagicMock

from nuclia.sdk.memory import (
    infer_title,
    parse_recall_answer,
    slugify,
)

# ─── slugify ─────────────────────────────────────────────────────────────────


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_characters_removed(self):
        assert slugify("Hello, World!") == "hello-world"

    def test_multiple_spaces(self):
        assert slugify("hello   world") == "hello---world"

    def test_numbers_preserved(self):
        assert slugify("Version 2 Release") == "version-2-release"

    def test_already_lowercase(self):
        assert slugify("already lowercase") == "already-lowercase"

    def test_uppercase(self):
        assert slugify("ALL CAPS") == "all-caps"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_only_special_characters(self):
        assert slugify("!@#$%^&*()") == ""

    def test_unicode_stripped(self):
        assert slugify("café résumé") == "caf-rsum"

    def test_hyphens_stripped(self):
        # Hyphens not in allowed_characters
        assert slugify("my-slug") == "my-slug"


# ─── infer_title ─────────────────────────────────────────────────────────────


class TestInferTitle:
    def test_from_slug(self):
        assert infer_title(slug="vacation-policy") == "Vacation Policy"

    def test_from_text_short(self):
        assert infer_title(text="Hello world") == "Hello World"

    def test_from_text_long_truncated(self):
        long_text = "a" * 100
        result = infer_title(text=long_text)
        # Should only use first 50 chars
        assert len(result) <= 50

    def test_from_path(self):
        assert infer_title(path="/home/user/documents/report.pdf") == "Report.Pdf"

    def test_from_url(self):
        assert infer_title(url="https://example.com/my-document") == "My Document"

    def test_no_arguments(self):
        assert infer_title() == "Untitled topic"

    def test_priority_slug_over_text(self):
        result = infer_title(slug="my-slug", text="some text")
        assert result == "My Slug"

    def test_priority_text_over_path(self):
        result = infer_title(text="some text", path="/file.txt")
        assert result == "Some Text"

    def test_priority_path_over_url(self):
        result = infer_title(path="/file.txt", url="https://example.com/doc")
        assert result == "File.Txt"


# ─── parse_recall_answer ─────────────────────────────────────────────────────


class TestParseRecallAnswer:
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

    def test_no_citations(self):
        response = self._make_ask_response("Just a plain answer with no citations.")
        answer, citations = parse_recall_answer(response)
        assert answer == "Just a plain answer with no citations."
        assert citations == {}

    def test_single_citation(self):
        raw = "The policy allows 10 days [1].\n\n[1]: block-AA"
        para = MagicMock()
        para.id = "chunk-123"
        para.text = "A maximum of 10 consecutive days."

        response = self._make_ask_response(
            answer=raw,
            paragraphs={"chunk-123": para},
            footnote_map={"block-AA": "chunk-123"},
        )
        answer, citations = parse_recall_answer(response)
        assert answer == "The policy allows 10 days [1]."
        assert "1" in citations
        assert citations["1"].id == "chunk-123"
        assert citations["1"].text == "A maximum of 10 consecutive days."

    def test_multiple_citations(self):
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
        answer, citations = parse_recall_answer(response)
        assert answer == "Answer text [1] and more [2]."
        assert len(citations) == 2
        assert citations["1"].id == "chunk-1"
        assert citations["2"].id == "chunk-2"

    def test_citation_with_missing_chunk(self):
        """Citation references a block that doesn't map to a retrieved paragraph."""
        raw = "Answer [1].\n\n[1]: block-MISSING"
        response = self._make_ask_response(
            answer=raw,
            paragraphs={},
            footnote_map={"block-MISSING": "nonexistent-chunk"},
        )
        answer, citations = parse_recall_answer(response)
        assert answer == "Answer [1]."
        assert citations == {}

    def test_citation_block_not_in_footnote_map(self):
        """Citation block ID not found in citation_footnote_to_context."""
        raw = "Answer [1].\n\n[1]: block-UNKNOWN"
        response = self._make_ask_response(
            answer=raw,
            paragraphs={},
            footnote_map={},
        )
        answer, citations = parse_recall_answer(response)
        assert answer == "Answer [1]."
        assert citations == {}

    def test_multiline_answer(self):
        raw = "Line one.\n\nLine two.\n\nLine three.\n\n[1]: block-AA"
        para = MagicMock()
        para.id = "chunk-1"
        para.text = "Source text"
        response = self._make_ask_response(
            answer=raw,
            paragraphs={"chunk-1": para},
            footnote_map={"block-AA": "chunk-1"},
        )
        answer, citations = parse_recall_answer(response)
        # rsplit with maxsplit=1 should keep only the last \n\n as the split point
        assert answer == "Line one.\n\nLine two.\n\nLine three."
        assert "1" in citations

    def test_real_world_example(self):
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
        answer, citations = parse_recall_answer(response)
        assert "15 consecutive vacation days" in answer
        assert "\n\n[1]:" not in answer
        assert (
            citations["1"].text
            == "A maximum of 10 consecutive days can be taken without director approval."
        )
