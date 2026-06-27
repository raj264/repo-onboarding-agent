from unittest.mock import patch

from onboarding_agent.retriever import DocResult, IndexNotFoundError
from onboarding_agent.tools.docs_tools import search_docs_tool


def test_search_docs_tool_formats_results_with_source_and_score(tmp_path):
    fake_results = [
        DocResult(
            text="retry logic uses exponential backoff", source_path="docs/architecture.md", score=0.12
        ),
        DocResult(text="timeout defaults to 30s", source_path="docs/faq.md", score=0.34),
    ]
    with patch("onboarding_agent.tools.docs_tools.search_docs", return_value=fake_results) as mock_search:
        output = search_docs_tool(tmp_path, "how does retry work?", k=2)

    mock_search.assert_called_once_with(tmp_path, "how does retry work?", k=2)
    assert "[1] docs/architecture.md (score=0.1200)" in output
    assert "retry logic uses exponential backoff" in output
    assert "[2] docs/faq.md (score=0.3400)" in output


def test_search_docs_tool_reports_no_results(tmp_path):
    with patch("onboarding_agent.tools.docs_tools.search_docs", return_value=[]):
        output = search_docs_tool(tmp_path, "anything")

    assert output == "No relevant documentation found."


def test_search_docs_tool_converts_index_not_found_to_message_instead_of_raising(tmp_path):
    with patch(
        "onboarding_agent.tools.docs_tools.search_docs",
        side_effect=IndexNotFoundError(
            "No index found at /tmp/x. Run 'onboarding-agent index /tmp/x' first."
        ),
    ):
        output = search_docs_tool(tmp_path, "anything")

    assert "No index found" in output
