from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .domain import AlphaCandidate, EvaluationResult, KnowledgeItem
from .metrics import extract_simulation_metrics


class AlphaStore:
    def __init__(self, path: str | Path = "data/brain_alpha.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
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
        """)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def save_candidate(self, candidate: AlphaCandidate) -> None:
        self.connection.execute("INSERT OR REPLACE INTO alphas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (candidate.id, candidate.formula, candidate.hypothesis, json.dumps(candidate.fields), json.dumps(candidate.operators), candidate.region, candidate.universe, candidate.delay, candidate.neutralization, candidate.source, _now()))
        self.connection.commit()

    def candidate(self, alpha_id: str) -> AlphaCandidate | None:
        row = self.connection.execute("SELECT * FROM alphas WHERE id = ?", (alpha_id,)).fetchone()
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
        self.connection.execute("INSERT OR REPLACE INTO evaluations VALUES (?, ?, ?)", (result.alpha_id, json.dumps(asdict(result), default=str), result.quality_score))
        self.connection.commit()

    def save_simulation_result(self, alpha_id: str, payload: dict) -> None:
        simulation_id = str(payload.get("id") or payload.get("simulation_id") or payload.get("simulationId") or "")
        if not simulation_id:
            raise ValueError("simulation result must include an id")
        status = str(payload.get("status", payload.get("state", "UNKNOWN")))
        self.connection.execute(
            "INSERT OR REPLACE INTO simulation_results VALUES (?, ?, ?, ?, ?, ?)",
            (simulation_id, alpha_id, status, json.dumps(payload), json.dumps(extract_simulation_metrics(payload)), _now()),
        )
        self.connection.commit()

    def simulation_result(self, simulation_id: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM simulation_results WHERE simulation_id = ?", (simulation_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["raw"] = json.loads(result.pop("raw_json"))
        result["metrics"] = json.loads(result.pop("metrics_json"))
        return result

    def simulation_results_for_alpha(self, alpha_id: str) -> list[dict]:
        rows = self.connection.execute("SELECT * FROM simulation_results WHERE alpha_id = ? ORDER BY created_at", (alpha_id,)).fetchall()
        results = []
        for row in rows:
            result = dict(row)
            result["raw"] = json.loads(result.pop("raw_json"))
            result["metrics"] = json.loads(result.pop("metrics_json"))
            results.append(result)
        return results

    def save_knowledge(self, item: KnowledgeItem) -> None:
        self.connection.execute("INSERT OR REPLACE INTO knowledge VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (item.id, item.domain, item.topic, item.hypothesis, item.confidence, item.source_agent, item.observed_at.isoformat(), item.evidence))
        self.connection.commit()

    def knowledge_items(self) -> tuple[KnowledgeItem, ...]:
        rows = self.connection.execute("SELECT * FROM knowledge ORDER BY observed_at DESC").fetchall()
        return tuple(KnowledgeItem(row["id"], row["domain"], row["topic"], row["hypothesis"], row["confidence"], row["source_agent"], datetime.fromisoformat(row["observed_at"]), row["evidence"]) for row in rows)

    def ranked(self) -> list[dict]:
        rows = self.connection.execute("SELECT a.id, a.formula, a.hypothesis, e.quality_score FROM alphas a LEFT JOIN evaluations e ON a.id = e.alpha_id ORDER BY e.quality_score DESC NULLS LAST, a.created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def reference_count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM reference_expressions").fetchone()[0])

    def save_reference(self, item: object) -> None:
        self.connection.execute("INSERT OR REPLACE INTO reference_expressions VALUES (?, ?, ?, ?)", (item.id, item.expression, item.source_path, item.notes))
        self.connection.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
