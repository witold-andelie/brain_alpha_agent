from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class BrainConfig:
    base_url: str = "https://api.worldquantbrain.com"
    username: str = ""
    password: str = ""

    @classmethod
    def from_env(cls) -> "BrainConfig":
        return cls(os.getenv("BRAIN_BASE_URL", cls.base_url), os.getenv("BRAIN_USERNAME", ""), os.getenv("BRAIN_PASSWORD", ""))


class BrainClient:
    """Official API boundary. Network writes are intentionally not exposed in MVP."""

    def __init__(self, config: BrainConfig | None = None, session: Any | None = None) -> None:
        self.config = config or BrainConfig.from_env()
        if not self.config.username or not self.config.password:
            raise RuntimeError("BRAIN_USERNAME and BRAIN_PASSWORD are required")
        try:
            import requests
        except ImportError as error:
            raise RuntimeError("install the optional brain dependency: pip install -e '.[brain]'") from error
        self.session = session or requests.Session()
        self.session.auth = (self.config.username, self.config.password)

    def authenticate(self) -> None:
        response = self.session.post(f"{self.config.base_url.rstrip('/')}/authentication", timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"BRAIN authentication failed: HTTP {response.status_code}")

    def get_data_fields(self, *, search: str | None = None, dataset_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        if dataset_id:
            params["dataset.id"] = dataset_id
        response = self.session.get(f"{self.config.base_url.rstrip('/')}/data-fields", params=params, timeout=30)
        response.raise_for_status()
        return response.json().get("results", [])


class BrainSimulationError(RuntimeError):
    pass


class _OfflineResponse:
    def __init__(self, payload: dict[str, Any], *, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self.payload


class OfflineSimulationSession:
    """Deterministic HTTP-like session used by the CLI offline mode."""

    def __init__(self) -> None:
        self.auth = None
        self._polls = 0
        self._submissions = 0
        self._active_id = ""

    def post(self, url: str, **kwargs: Any) -> _OfflineResponse:
        self._submissions += 1
        self._polls = 0
        self._active_id = f"offline-simulation-{self._submissions}"
        return _OfflineResponse({}, status_code=202, headers={"Location": f"{url}/{self._active_id}"})

    def get(self, url: str, **kwargs: Any) -> _OfflineResponse:
        self._polls += 1
        if self._polls == 1:
            return _OfflineResponse({"id": self._active_id, "status": "RUNNING"})
        return _OfflineResponse({
            "id": self._active_id,
            "status": "COMPLETE",
            "evaluator": "offline",
            "Sharpe": 1.1,
            "Fitness": 0.75,
            "Returns": 0.08,
            "Turnover": 0.25,
            "Drawdown": 0.12,
            "Long-Count": 450,
            "Short-Count": 450,
            "Universe-Count": 1000,
        })


class BrainSimulationAdapter:
    """Submit and poll one BRAIN simulation through an authenticated client."""

    _SUCCESS_STATES = frozenset({"COMPLETE", "COMPLETED", "DONE", "SUCCESS"})
    _FAILURE_STATES = frozenset({"CANCELLED", "CANCELED", "ERROR", "FAILED", "FAILURE"})

    def __init__(
        self,
        client: BrainClient,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.clock = clock
        self.sleep = sleep

    def simulate(self, payload: dict[str, Any], *, timeout: float = 300, poll_interval: float = 2) -> dict[str, Any]:
        if timeout <= 0 or poll_interval < 0:
            raise ValueError("timeout must be positive and poll_interval cannot be negative")
        location = self._submit(payload)
        deadline = self.clock() + timeout
        while True:
            result = self._get_result(location)
            state = str(result.get("status", result.get("state", ""))).upper()
            if state in self._SUCCESS_STATES:
                if not (result.get("id") or result.get("simulation_id") or result.get("simulationId")):
                    result = {**result, "simulation_id": location.rstrip("/").rsplit("/", 1)[-1]}
                return result
            if state in self._FAILURE_STATES:
                raise BrainSimulationError(f"BRAIN simulation failed: {state}")
            if self.clock() >= deadline:
                raise TimeoutError(f"BRAIN simulation timed out: {location}")
            self.sleep(poll_interval)

    def _submit(self, payload: dict[str, Any]) -> str:
        url = f"{self.client.config.base_url.rstrip('/')}/simulations"
        response = self.client.session.post(url, json=payload, timeout=30)
        try:
            response.raise_for_status()
        except Exception as error:
            raise BrainSimulationError(f"BRAIN simulation submission failed: HTTP {response.status_code}") from error
        headers = getattr(response, "headers", {})
        location = headers.get("Location") or headers.get("location")
        if location:
            return location
        body = response.json()
        simulation_id = body.get("id") or body.get("simulation_id") or body.get("simulationId")
        if not simulation_id:
            raise BrainSimulationError("BRAIN simulation response did not include a location or simulation id")
        return f"{self.client.config.base_url.rstrip('/')}/simulations/{simulation_id}"

    def _get_result(self, location: str) -> dict[str, Any]:
        response = self.client.session.get(location, timeout=30)
        try:
            response.raise_for_status()
        except Exception as error:
            raise BrainSimulationError(f"BRAIN simulation polling failed: HTTP {response.status_code}") from error
        result = response.json()
        if not isinstance(result, dict):
            raise BrainSimulationError("BRAIN simulation response must be a JSON object")
        return result
