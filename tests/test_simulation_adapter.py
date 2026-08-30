import pytest

from brain_alpha_agent.brain_api import (
    BrainClient,
    BrainConfig,
    BrainSimulationAdapter,
    BrainSimulationError,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self.payload = payload or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    auth = None

    def __init__(self, submitted=None, polled=None):
        self.submitted = submitted or FakeResponse(
            status_code=202,
            headers={"Location": "https://example.test/simulations/sim-1"},
        )
        self.polled = list(polled or [])
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.submitted

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.polled.pop(0)


def make_adapter(session, now=None, sleeps=None):
    current = [0.0] if now is None else [now]
    sleeps = [] if sleeps is None else sleeps

    def clock():
        return current[0]

    def sleep(seconds):
        sleeps.append(seconds)
        current[0] += seconds

    client = BrainClient(
        BrainConfig(base_url="https://example.test", username="user", password="pass"),
        session=session,
    )
    return BrainSimulationAdapter(client, clock=clock, sleep=sleep), current


def test_simulation_adapter_submits_and_polls_until_complete():
    session = FakeSession(
        polled=[
            FakeResponse(payload={"status": "RUNNING"}),
            FakeResponse(payload={"status": "COMPLETE", "sharpe": 1.2}),
        ]
    )
    sleeps = []
    adapter, _ = make_adapter(session, sleeps=sleeps)

    result = adapter.simulate({"alpha": "rank(roic)"}, timeout=10, poll_interval=3)

    assert result == {"status": "COMPLETE", "sharpe": 1.2, "simulation_id": "sim-1"}
    assert sleeps == [3]
    assert session.calls[0][2]["json"] == {"alpha": "rank(roic)"}
    assert session.calls[1][1] == "https://example.test/simulations/sim-1"


def test_simulation_adapter_accepts_id_from_submission_body():
    session = FakeSession(
        submitted=FakeResponse(status_code=201, payload={"simulationId": "sim-2"}),
        polled=[FakeResponse(payload={"state": "DONE", "fitness": 0.8})],
    )
    adapter, _ = make_adapter(session)

    adapter.simulate({}, timeout=10)

    assert session.calls[1][1] == "https://example.test/simulations/sim-2"


def test_simulation_adapter_raises_for_failed_simulation():
    session = FakeSession(polled=[FakeResponse(payload={"status": "FAILED"})])
    adapter, _ = make_adapter(session)

    with pytest.raises(BrainSimulationError, match="simulation failed"):
        adapter.simulate({}, timeout=10)


def test_simulation_adapter_raises_on_timeout():
    session = FakeSession(polled=[FakeResponse(payload={"status": "RUNNING"})] * 3)
    adapter, _ = make_adapter(session)

    with pytest.raises(TimeoutError, match="timed out"):
        adapter.simulate({}, timeout=2, poll_interval=1)


def test_simulation_adapter_raises_on_submission_failure():
    session = FakeSession(submitted=FakeResponse(status_code=403))
    adapter, _ = make_adapter(session)

    with pytest.raises(BrainSimulationError, match="submission failed"):
        adapter.simulate({}, timeout=10)


def test_simulation_adapter_resolves_relative_location_on_same_origin():
    session = FakeSession(
        submitted=FakeResponse(
            status_code=202, headers={"Location": "/simulations/sim-relative"}
        ),
        polled=[FakeResponse(payload={"status": "COMPLETE"})],
    )
    adapter, _ = make_adapter(session)

    adapter.simulate({}, timeout=10)

    assert session.calls[1][1] == "https://example.test/simulations/sim-relative"


def test_simulation_adapter_rejects_cross_origin_location():
    session = FakeSession(
        submitted=FakeResponse(
            status_code=202,
            headers={"Location": "https://attacker.example/simulations/sim-1"},
        )
    )
    adapter, _ = make_adapter(session)

    with pytest.raises(BrainSimulationError, match="changed origin"):
        adapter.simulate({}, timeout=10)
    assert len(session.calls) == 1


def test_simulation_adapter_requires_positive_poll_interval():
    adapter, _ = make_adapter(FakeSession())

    with pytest.raises(ValueError, match="must be positive"):
        adapter.simulate({}, timeout=10, poll_interval=0)


def test_simulation_adapter_backs_off_after_rate_limit():
    session = FakeSession(
        polled=[
            FakeResponse(status_code=429, headers={"Retry-After": "4"}),
            FakeResponse(payload={"status": "COMPLETE"}),
        ]
    )
    sleeps = []
    adapter, _ = make_adapter(session, sleeps=sleeps)

    adapter.simulate({}, timeout=10, poll_interval=1)

    assert sleeps == [4.0]
