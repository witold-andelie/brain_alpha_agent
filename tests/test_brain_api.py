import pytest

from brain_alpha_agent.brain_api import BrainClient, BrainConfig


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, authentication=None, fields=None):
        self.auth = None
        self.authentication = authentication or FakeResponse()
        self.fields = fields or FakeResponse(payload={"results": []})
        self.calls = []

    def post(self, url, timeout):
        self.calls.append(("POST", url, timeout))
        return self.authentication

    def get(self, url, params, timeout):
        self.calls.append(("GET", url, params, timeout))
        return self.fields


def test_brain_client_uses_injected_session_for_read_only_requests() -> None:
    session = FakeSession(
        fields=FakeResponse(
            payload={
                "results": [
                    {
                        "id": "roic",
                        "description": "Return on invested capital",
                        "dataset": {"id": "fundamental"},
                    }
                ]
            }
        )
    )
    client = BrainClient(
        BrainConfig(base_url="https://example.test", username="user", password="pass"),
        session=session,
    )

    client.authenticate()
    fields = client.get_data_fields(search="roic", dataset_id="fundamental", limit=1)

    assert fields[0]["id"] == "roic"
    assert session.auth == ("user", "pass")
    assert session.calls == [
        ("POST", "https://example.test/authentication", 30),
        (
            "GET",
            "https://example.test/data-fields",
            {"limit": 1, "search": "roic", "dataset.id": "fundamental"},
            30,
        ),
    ]


def test_brain_client_rejects_failed_authentication() -> None:
    session = FakeSession(authentication=FakeResponse(status_code=401))
    client = BrainClient(BrainConfig(username="user", password="pass"), session=session)

    with pytest.raises(RuntimeError, match="HTTP 401"):
        client.authenticate()


def test_brain_client_requires_credentials() -> None:
    with pytest.raises(RuntimeError, match="BRAIN_USERNAME and BRAIN_PASSWORD"):
        BrainClient(session=FakeSession())


def test_brain_client_requires_https_base_url() -> None:
    with pytest.raises(ValueError, match="absolute HTTPS"):
        BrainClient(
            BrainConfig(
                base_url="http://example.test", username="user", password="pass"
            ),
            session=FakeSession(),
        )
