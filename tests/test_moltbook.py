import pytest

from brain_alpha_agent.moltbook import MoltbookClient, MoltbookError, search_as_knowledge


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "results": [
                {
                    "id": "post-1",
                    "type": "post",
                    "title": "A discussion about volatility regimes",
                    "content": "Volatility regime changes may alter the stability of short horizon signals.",
                    "similarity": 0.82,
                    "created_at": "2026-08-09T00:00:00Z",
                }
            ]
        }


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


def test_moltbook_search_is_read_only_and_converts_results_to_knowledge():
    session = FakeSession()
    client = MoltbookClient(api_key="test-key", session=session)

    items = search_as_knowledge(client, "volatility regime", limit=1)

    assert len(items) == 1
    assert items[0].source_agent == "moltbook"
    assert "https://www.moltbook.com/post/post-1" in items[0].evidence
    assert session.calls[0][0].startswith("https://www.moltbook.com/api/v1/search?")
    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer test-key"


def test_moltbook_client_requires_key():
    with pytest.raises(MoltbookError, match="MOLTBOOK_API_KEY"):
        MoltbookClient(api_key="", session=FakeSession())


def test_moltbook_client_rejects_invalid_search_options():
    client = MoltbookClient(api_key="test-key", session=FakeSession())

    with pytest.raises(ValueError):
        client.search("x", result_type="posts-and-comments")
