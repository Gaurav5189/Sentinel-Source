"""Tests for llm_evaluator.py — LLM query enhancement and batch evaluation."""

import json
import pytest
from unittest.mock import patch, MagicMock
from llm_evaluator import (
    enhance_query_llm,
    evaluate_tools_batch,
    _safe_parse_score,
    _safe_parse_legit,
)


class TestSafeParseScore:
    """Tests for defensive score parsing (CQ-04)."""

    def test_valid_int(self):
        assert _safe_parse_score(7) == 7

    def test_valid_float(self):
        assert _safe_parse_score(8.5) == 8

    def test_string_digit(self):
        assert _safe_parse_score("9") == 9

    def test_string_fraction(self):
        """Handles LLM returning '7/10' format."""
        assert _safe_parse_score("7/10") == 7

    def test_string_non_numeric(self):
        assert _safe_parse_score("high") == 0

    def test_clamps_to_max_10(self):
        assert _safe_parse_score(15) == 10

    def test_clamps_to_min_0(self):
        assert _safe_parse_score(-3) == 0

    def test_none(self):
        assert _safe_parse_score(None) == 0

    def test_empty_string(self):
        assert _safe_parse_score("") == 0


class TestSafeParseLegit:
    """Tests for defensive boolean parsing (CQ-04)."""

    def test_true_bool(self):
        assert _safe_parse_legit(True) is True

    def test_false_bool(self):
        assert _safe_parse_legit(False) is False

    def test_string_true(self):
        assert _safe_parse_legit("true") is True

    def test_string_false(self):
        """Critical: Python's bool('false') returns True, our function fixes this."""
        assert _safe_parse_legit("false") is False

    def test_string_True_capitalized(self):
        assert _safe_parse_legit("True") is True

    def test_integer_1(self):
        assert _safe_parse_legit(1) is True

    def test_integer_0(self):
        assert _safe_parse_legit(0) is False


class TestEnhanceQueryLLM:
    """Tests for the query enhancement function."""

    @patch("llm_evaluator.OPENROUTER_API_KEY", None)
    def test_missing_api_key_returns_original(self):
        """Graceful fallback when API key is missing."""
        result = enhance_query_llm("sql ingestion")
        assert result == "sql ingestion"

    @patch("llm_evaluator.OPENROUTER_MODEL", None)
    def test_missing_model_returns_original(self):
        """Graceful fallback when model is missing."""
        result = enhance_query_llm("sql ingestion")
        assert result == "sql ingestion"

    @patch("llm_evaluator.requests.post")
    @patch("llm_evaluator.OPENROUTER_API_KEY", "test-key")
    @patch("llm_evaluator.OPENROUTER_MODEL", "test-model")
    def test_successful_enhancement(self, mock_post):
        """Verifies query is enhanced from LLM response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "sql injection tool"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = enhance_query_llm("sql ingestion")
        assert result == "sql injection tool"

    @patch("llm_evaluator.requests.post")
    @patch("llm_evaluator.OPENROUTER_API_KEY", "test-key")
    @patch("llm_evaluator.OPENROUTER_MODEL", "test-model")
    def test_strips_quotes_from_response(self, mock_post):
        """Verifies hallucinated quotes are stripped."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '"sql injection scanner"'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = enhance_query_llm("sql scan")
        assert result == "sql injection scanner"

    @patch("llm_evaluator.requests.post")
    @patch("llm_evaluator.OPENROUTER_API_KEY", "test-key")
    @patch("llm_evaluator.OPENROUTER_MODEL", "test-model")
    def test_api_error_returns_original(self, mock_post):
        """Graceful fallback on API errors."""
        mock_post.side_effect = Exception("Connection refused")

        result = enhance_query_llm("test query")
        assert result == "test query"


class TestEvaluateToolsBatch:
    """Tests for the batch LLM evaluation function."""

    def test_empty_list_returns_empty(self):
        result = evaluate_tools_batch([])
        assert result == []

    @patch("llm_evaluator.OPENROUTER_API_KEY", None)
    def test_missing_api_key_skips_evaluation(self, sample_repo_list):
        """All repos get score=0 when API key is missing."""
        results = evaluate_tools_batch(sample_repo_list)

        assert len(results) == 2
        for repo in results:
            assert repo["score"] == 0
            assert repo["is_legit"] is False
            assert "missing API key" in repo["analysis"]

    @patch("llm_evaluator.OPENROUTER_MODEL", None)
    @patch("llm_evaluator.OPENROUTER_API_KEY", "test-key")
    def test_missing_model_skips_evaluation(self, sample_repo_list):
        """All repos get skipped when model is not configured."""
        results = evaluate_tools_batch(sample_repo_list)

        for repo in results:
            assert repo["score"] == 0
            assert "not configured" in repo["analysis"]

    @patch("llm_evaluator.requests.post")
    @patch("llm_evaluator.OPENROUTER_API_KEY", "test-key")
    @patch("llm_evaluator.OPENROUTER_MODEL", "test-model")
    def test_successful_evaluation(self, mock_post, sample_repo_list, sample_llm_response_json):
        """Verifies correct parsing of a valid LLM evaluation response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(sample_llm_response_json)}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = evaluate_tools_batch(sample_repo_list)

        sqlmap = next(r for r in results if r["name"] == "sqlmap")
        assert sqlmap["score"] == 9
        assert sqlmap["is_legit"] is True
        assert "SQL injection" in sqlmap["analysis"]

    @patch("llm_evaluator.requests.post")
    @patch("llm_evaluator.OPENROUTER_API_KEY", "test-key")
    @patch("llm_evaluator.OPENROUTER_MODEL", "test-model")
    def test_markdown_wrapped_json_handled(self, mock_post, sample_repo_list, sample_llm_response_json):
        """Verifies that ```json ... ``` wrapping is stripped."""
        wrapped = f"```json\n{json.dumps(sample_llm_response_json)}\n```"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": wrapped}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = evaluate_tools_batch(sample_repo_list)
        sqlmap = next(r for r in results if r["name"] == "sqlmap")
        assert sqlmap["score"] == 9

    @patch("llm_evaluator.requests.post")
    @patch("llm_evaluator.OPENROUTER_API_KEY", "test-key")
    @patch("llm_evaluator.OPENROUTER_MODEL", "test-model")
    def test_invalid_json_graceful_failure(self, mock_post, sample_repo_list):
        """Verifies graceful handling of malformed LLM JSON output (CQ-01)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "This is not valid JSON {{"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = evaluate_tools_batch(sample_repo_list)

        for repo in results:
            assert repo["score"] == 0
            assert "invalid response format" in repo["analysis"]

    @patch("llm_evaluator.requests.post")
    @patch("llm_evaluator.OPENROUTER_API_KEY", "test-key")
    @patch("llm_evaluator.OPENROUTER_MODEL", "test-model")
    def test_error_details_not_leaked_to_user(self, mock_post, sample_repo_list):
        """SEC-05: Internal error details must NOT appear in user-facing analysis."""
        mock_post.side_effect = Exception("Internal server error with secret details")

        results = evaluate_tools_batch(sample_repo_list)

        for repo in results:
            assert "secret details" not in repo["analysis"]
            assert "temporarily unavailable" in repo["analysis"]

    def test_does_not_mutate_input(self, sample_repo_list):
        """Verifies the original list/dicts are not modified."""
        original_names = [r["name"] for r in sample_repo_list]
        original_key_counts = [len(r.keys()) for r in sample_repo_list]

        evaluate_tools_batch(sample_repo_list)

        for i, repo in enumerate(sample_repo_list):
            assert repo["name"] == original_names[i]
            assert len(repo.keys()) == original_key_counts[i]
