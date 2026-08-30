from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .deduplication import formula_signature
from .domain import AlphaCandidate, EvaluationResult, KnowledgeItem
from .metrics import extract_simulation_metrics
from .research import request_fingerprint, scenario_fingerprint


class AlphaStore:
    def __init__(self, path: str | Path = "data/brain_alpha.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS alphas (
                id TEXT PRIMARY KEY, formula TEXT NOT NULL, hypothesis TEXT NOT NULL,
                fields_json TEXT NOT NULL, operators_json TEXT NOT NULL, region TEXT NOT NULL,
                universe TEXT NOT NULL, delay INTEGER NOT NULL, neutralization TEXT NOT NULL,
                source TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evaluations (
                alpha_id TEXT PRIMARY KEY, result_json TEXT NOT NULL, quality_score REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY, domain TEXT NOT NULL, topic TEXT NOT NULL,
                hypothesis TEXT NOT NULL, confidence REAL NOT NULL, source_agent TEXT NOT NULL,
                observed_at TEXT NOT NULL, evidence TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reference_expressions (
                id TEXT PRIMARY KEY, expression TEXT NOT NULL,
                source_path TEXT NOT NULL, notes TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS simulation_results (
                simulation_id TEXT PRIMARY KEY, alpha_id TEXT NOT NULL,
                status TEXT NOT NULL, raw_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS simulation_runs (
                run_id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                alpha_id TEXT NOT NULL,
                status TEXT NOT NULL,
                evaluator TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                scenario_hash TEXT NOT NULL,
                formula_hash TEXT NOT NULL,
                candidate_json TEXT NOT NULL,
                request_json TEXT NOT NULL,
                scenario_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (alpha_id) REFERENCES alphas(id)
            );
            CREATE INDEX IF NOT EXISTS simulation_runs_alpha_created
                ON simulation_runs(alpha_id, created_at);
            CREATE INDEX IF NOT EXISTS simulation_runs_request
                ON simulation_runs(evaluator, request_hash, scenario_hash);
            CREATE TABLE IF NOT EXISTS quality_assessments (
                assessment_id TEXT PRIMARY KEY,
                alpha_id TEXT NOT NULL,
                passed INTEGER NOT NULL,
                score REAL,
                thresholds_json TEXT NOT NULL,
                assessment_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (alpha_id) REFERENCES alphas(id)
            );
            CREATE INDEX IF NOT EXISTS quality_assessments_alpha_created
                ON quality_assessments(alpha_id, created_at);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def save_candidate(self, candidate: AlphaCandidate) -> None:
        with self.connection:
            existing = self.connection.execute(
                """
                SELECT formula, region, universe, delay, neutralization
                FROM alphas WHERE id = ?
                """,
                (candidate.id,),
            ).fetchone()
            identity = (
                candidate.formula,
                candidate.region,
                candidate.universe,
                candidate.delay,
                candidate.neutralization,
            )
            if existing is not None:
                if tuple(existing) != identity:
                    raise ValueError(
                        "candidate id collision with different configuration"
                    )
                self.connection.execute(
                    """
                    UPDATE alphas
                    SET hypothesis = ?, fields_json = ?, operators_json = ?, source = ?
                    WHERE id = ?
                    """,
                    (
                        candidate.hypothesis,
                        _json_dumps(candidate.fields),
                        _json_dumps(candidate.operators),
                        candidate.source,
                        candidate.id,
                    ),
                )
            else:
                self.connection.execute(
                    """
                    INSERT INTO alphas (
                        id, formula, hypothesis, fields_json, operators_json, region,
                        universe, delay, neutralization, source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate.id,
                        candidate.formula,
                        candidate.hypothesis,
                        _json_dumps(candidate.fields),
                        _json_dumps(candidate.operators),
                        candidate.region,
                        candidate.universe,
                        candidate.delay,
                        candidate.neutralization,
                        candidate.source,
                        _now(),
                    ),
                )

    def candidate(self, alpha_id: str) -> AlphaCandidate | None:
        row = self.connection.execute(
            "SELECT * FROM alphas WHERE id = ?", (alpha_id,)
        ).fetchone()
        if row is None:
            return None
        return AlphaCandidate(
            id=row["id"],
            formula=row["formula"],
            hypothesis=row["hypothesis"],
            fields=tuple(json.loads(row["fields_json"])),
            operators=tuple(json.loads(row["operators_json"])),
            region=row["region"],
            universe=row["universe"],
            delay=row["delay"],
            neutralization=row["neutralization"],
            source=row["source"],
        )

    def save_evaluation(self, result: EvaluationResult) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO evaluations VALUES (?, ?, ?)",
                (
                    result.alpha_id,
                    _json_dumps(asdict(result)),
                    result.quality_score,
                ),
            )

    def save_simulation_result(self, alpha_id: str, payload: dict[str, Any]) -> None:
        """Legacy response-only storage. New real runs should use save_simulation_run."""
        simulation_id, status, metrics = _simulation_parts(payload)
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO simulation_results VALUES (?, ?, ?, ?, ?, ?)",
                (
                    simulation_id,
                    alpha_id,
                    status,
                    _json_dumps(payload),
                    _json_dumps(metrics),
                    _now(),
                ),
            )

    def save_simulation_run(
        self,
        candidate: AlphaCandidate,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        scenario: dict[str, Any],
        evaluator: str,
    ) -> str:
        if evaluator not in {"brain", "offline"}:
            raise ValueError("evaluator must be brain or offline")
        simulation_id, status, metrics = _simulation_parts(response_payload)
        run_id = uuid.uuid4().hex
        created_at = _now()
        request_hash = request_fingerprint(request_payload)
        scenario_hash = scenario_fingerprint(scenario)
        formula_hash = hashlib.sha256(
            formula_signature(candidate.formula).encode()
        ).hexdigest()
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO simulation_results VALUES (?, ?, ?, ?, ?, ?)",
                (
                    simulation_id,
                    candidate.id,
                    status,
                    _json_dumps(response_payload),
                    _json_dumps(metrics),
                    created_at,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO simulation_runs VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    run_id,
                    simulation_id,
                    candidate.id,
                    status,
                    evaluator,
                    request_hash,
                    scenario_hash,
                    formula_hash,
                    _json_dumps(asdict(candidate)),
                    _json_dumps(request_payload),
                    _json_dumps(scenario),
                    _json_dumps(response_payload),
                    _json_dumps(metrics),
                    created_at,
                ),
            )
        return run_id

    def simulation_result(self, simulation_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM simulation_results WHERE simulation_id = ?", (simulation_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["raw"] = json.loads(result.pop("raw_json"))
        result["metrics"] = json.loads(result.pop("metrics_json"))
        return result

    def simulation_results_for_alpha(self, alpha_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM simulation_runs WHERE alpha_id = ? ORDER BY created_at, run_id",
            (alpha_id,),
        ).fetchall()
        if rows:
            results: list[dict[str, Any]] = []
            for row in rows:
                result = dict(row)
                for column, key in (
                    ("candidate_json", "candidate"),
                    ("request_json", "request"),
                    ("scenario_json", "scenario"),
                    ("raw_json", "raw"),
                    ("metrics_json", "metrics"),
                ):
                    result[key] = json.loads(result.pop(column))
                results.append(result)
            return results

        legacy_rows = self.connection.execute(
            "SELECT * FROM simulation_results WHERE alpha_id = ? ORDER BY created_at",
            (alpha_id,),
        ).fetchall()
        legacy_results = []
        for row in legacy_rows:
            result = dict(row)
            result["raw"] = json.loads(result.pop("raw_json"))
            result["metrics"] = json.loads(result.pop("metrics_json"))
            result["evaluator"] = str(result["raw"].get("evaluator") or "unknown")
            result["scenario"] = {}
            result["scenario_hash"] = ""
            legacy_results.append(result)
        return legacy_results

    def save_quality_assessment(
        self, alpha_id: str, thresholds: object, assessment: object
    ) -> str:
        if self.candidate(alpha_id) is None:
            raise ValueError("cannot assess an unknown alpha")
        assessment_id = uuid.uuid4().hex
        assessment_data = asdict(assessment)
        with self.connection:
            self.connection.execute(
                "INSERT INTO quality_assessments VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    assessment_id,
                    alpha_id,
                    int(bool(assessment_data["passed"])),
                    assessment_data["score"],
                    _json_dumps(asdict(thresholds)),
                    _json_dumps(assessment_data),
                    _now(),
                ),
            )
        return assessment_id

    def save_knowledge(self, item: KnowledgeItem) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO knowledge VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    item.domain,
                    item.topic,
                    item.hypothesis,
                    item.confidence,
                    item.source_agent,
                    item.observed_at.isoformat(),
                    item.evidence,
                ),
            )

    def knowledge_items(self) -> tuple[KnowledgeItem, ...]:
        rows = self.connection.execute(
            "SELECT * FROM knowledge ORDER BY observed_at DESC"
        ).fetchall()
        return tuple(
            KnowledgeItem(
                row["id"],
                row["domain"],
                row["topic"],
                row["hypothesis"],
                row["confidence"],
                row["source_agent"],
                datetime.fromisoformat(row["observed_at"]),
                row["evidence"],
            )
            for row in rows
        )

    def ranked(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id, formula, hypothesis, source, created_at FROM alphas"
        ).fetchall()
        ranked: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            assessment = self.connection.execute(
                """
                SELECT passed, score, assessment_id
                FROM quality_assessments
                WHERE alpha_id = ?
                ORDER BY created_at DESC, assessment_id DESC
                LIMIT 1
                """,
                (row["id"],),
            ).fetchone()
            if assessment is not None:
                item.update(
                    {
                        "quality_score": assessment["score"],
                        "passed": bool(assessment["passed"]),
                        "score_source": "brain_assessment",
                        "assessment_id": assessment["assessment_id"],
                    }
                )
            else:
                mock = self.connection.execute(
                    "SELECT quality_score FROM evaluations WHERE alpha_id = ?",
                    (row["id"],),
                ).fetchone()
                item.update(
                    {
                        "quality_score": mock["quality_score"] if mock else None,
                        "passed": None,
                        "score_source": "mock" if mock else "unassessed",
                    }
                )
            ranked.append(item)

        def sort_key(item: dict[str, Any]) -> tuple[int, int, float, str]:
            source_order = 0 if item["score_source"] == "brain_assessment" else 1
            pass_order = 0 if item["passed"] is True else 1
            score = float(item["quality_score"] or -1.0)
            return (source_order, pass_order, -score, str(item["created_at"]))

        return sorted(ranked, key=sort_key)

    def reference_count(self) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM reference_expressions"
            ).fetchone()[0]
        )

    def save_reference(self, item: object) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO reference_expressions VALUES (?, ?, ?, ?)",
                (item.id, item.expression, item.source_path, item.notes),
            )


def _simulation_parts(payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    simulation_id = str(
        payload.get("id")
        or payload.get("simulation_id")
        or payload.get("simulationId")
        or ""
    )
    if not simulation_id:
        raise ValueError("simulation result must include an id")
    status = str(payload.get("status", payload.get("state", "UNKNOWN"))).upper()
    return simulation_id, status, extract_simulation_metrics(payload)


def _json_dumps(value: Any) -> str:
    return json.dumps(
        value,
        default=str,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
