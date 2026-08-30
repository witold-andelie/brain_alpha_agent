from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .evaluator import MockBrainEvaluator
from .formula import FormulaValidationError, validate_formula
from .generator import STRATEGY_PROFILES, candidate_strategy, generate_candidates
from .knowledge import import_revenue_knowledge
from .moltbook import MoltbookClient, search_as_knowledge
from .quality import QualityThresholds, assess_quality
from .research import bind_payload_to_candidate, load_json_object, run_research
from .reference import load_reference_project
from .course_reference import load_course_alpha_templates
from .brain_api import (
    BrainClient,
    BrainConfig,
    BrainSimulationAdapter,
    OfflineSimulationSession,
)
from .storage import AlphaStore


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None or args.command == "repl":
        return _repl(args)
    store = AlphaStore(args.db)
    try:
        if args.command == "generate":
            knowledge = store.knowledge_items()
            candidates = generate_candidates(
                region=args.region,
                universe=args.universe,
                delay=args.delay,
                neutralization=args.neutralization,
                knowledge=knowledge,
                profile=args.profile,
            )
            for candidate in candidates:
                store.save_candidate(candidate)
            print(
                {
                    "generated": len(candidates),
                    "profile": args.profile,
                    "candidates": [
                        {"id": candidate.id, **candidate_strategy(candidate)}
                        for candidate in candidates
                    ],
                }
            )
        elif args.command == "validate":
            print({"fields": validate_formula(args.formula), "valid": True})
        elif args.command == "evaluate":
            candidate = store.candidate(args.alpha_id)
            if candidate is None:
                raise ValueError("alpha not found in database; run generate first")
            result = MockBrainEvaluator().evaluate(candidate)
            store.save_candidate(candidate)
            store.save_evaluation(result)
            print(
                {
                    "alpha_id": result.alpha_id,
                    "evaluator": "mock",
                    "quality_score": round(result.quality_score, 4),
                    "fitness": round(result.fitness, 4),
                    "sharpe": round(result.sharpe, 4),
                    "turnover": round(result.turnover, 4),
                }
            )
        elif args.command == "rank":
            print(store.ranked())
        elif args.command == "import-revenue":
            items = import_revenue_knowledge(args.revenue_db)
            for item in items:
                store.save_knowledge(item)
            print({"imported": len(items)})
        elif args.command == "import-reference":
            expressions = load_reference_project(args.reference_path)
            for expression in expressions:
                store.save_reference(expression)
            print(
                {
                    "imported_reference_expressions": len(expressions),
                    "source": args.reference_path,
                }
            )
        elif args.command == "import-course":
            expressions = load_course_alpha_templates(args.course_path)
            for expression in expressions:
                store.save_reference(expression)
            print(
                {
                    "imported_course_templates": len(expressions),
                    "source": args.course_path,
                }
            )
        elif args.command == "import-moltbook":
            items = search_as_knowledge(MoltbookClient(), args.query, limit=args.limit)
            for item in items:
                store.save_knowledge(item)
            print({"imported_moltbook_items": len(items), "query": args.query})
        elif args.command == "fields":
            client = BrainClient()
            client.authenticate()
            fields = client.get_data_fields(search=args.search, limit=args.limit)
            print(
                [
                    {
                        "id": item.get("id"),
                        "description": item.get("description"),
                        "dataset": item.get("dataset", {}).get("id"),
                    }
                    for item in fields
                ]
            )
        elif args.command == "simulate":
            candidate = store.candidate(args.alpha_id)
            if candidate is None:
                raise ValueError("alpha not found in database; run generate first")
            payload = bind_payload_to_candidate(
                json.loads(Path(args.payload).read_text(encoding="utf-8")), candidate
            )
            if args.offline:
                client = BrainClient(
                    BrainConfig(username="offline", password="offline"),
                    session=OfflineSimulationSession(),
                )
            else:
                client = BrainClient()
                client.authenticate()
            adapter = BrainSimulationAdapter(
                client, sleep=(lambda _: None) if args.offline else time.sleep
            )
            result = adapter.simulate(
                payload, timeout=args.timeout, poll_interval=args.poll_interval
            )
            request_settings = payload.get("settings", {})
            scenario = {
                "regime": args.regime,
                "candidate_region": candidate.region,
                "candidate_universe": candidate.universe,
                "candidate_delay": candidate.delay,
                "candidate_neutralization": candidate.neutralization,
                "request_settings": request_settings
                if isinstance(request_settings, dict)
                else {},
            }
            evaluator = "offline" if args.offline else "brain"
            run_id = store.save_simulation_run(
                candidate, payload, result, scenario, evaluator
            )
            saved = store.simulation_result(
                str(
                    result.get("id")
                    or result.get("simulation_id")
                    or result.get("simulationId")
                )
            )
            print(
                {
                    "run_id": run_id,
                    "simulation_id": result.get("id")
                    or result.get("simulation_id")
                    or result.get("simulationId"),
                    "alpha_id": candidate.id,
                    "status": result.get("status", result.get("state")),
                    "evaluator": evaluator,
                    "metrics": saved["metrics"] if saved else {},
                }
            )
        elif args.command == "research":
            candidates = []
            for alpha_id in args.alpha_id:
                candidate = store.candidate(alpha_id)
                if candidate is None:
                    raise ValueError(f"alpha not found in database: {alpha_id}")
                candidates.append(candidate)
            scenarios = load_json_object(args.scenarios)
            if (
                not isinstance(scenarios, list)
                or not scenarios
                or not all(isinstance(item, dict) for item in scenarios)
            ):
                raise ValueError("scenarios must be a non-empty JSON array of objects")
            payload_template = load_json_object(args.payload_template)
            if args.offline:
                client = BrainClient(
                    BrainConfig(username="offline", password="offline"),
                    session=OfflineSimulationSession(),
                )
            else:
                client = BrainClient()
                client.authenticate()
            adapter = BrainSimulationAdapter(
                client, sleep=(lambda _: None) if args.offline else time.sleep
            )
            completed = run_research(
                candidates,
                scenarios,
                payload_template,
                adapter,
                save_run=store.save_simulation_run,
                evaluator="offline" if args.offline else "brain",
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                max_runs=args.max_runs,
            )
            print({"completed": len(completed), "runs": completed})
        elif args.command == "assess":
            if store.candidate(args.alpha_id) is None:
                raise ValueError("alpha not found in database; run generate first")
            required_regimes = (
                tuple(args.require_regime)
                if args.require_regime
                else QualityThresholds().required_regimes
            )
            thresholds = QualityThresholds(
                min_scenarios=args.min_scenarios,
                min_distinct_scenarios=args.min_distinct_scenarios,
                max_whipsaw_turnover=args.max_whipsaw_turnover,
                required_regimes=required_regimes,
            )
            assessment = assess_quality(
                store.simulation_results_for_alpha(args.alpha_id),
                thresholds=thresholds,
            )
            assessment_id = store.save_quality_assessment(
                args.alpha_id, thresholds, assessment
            )
            print(
                {
                    "assessment_id": assessment_id,
                    "alpha_id": args.alpha_id,
                    "passed": assessment.passed,
                    "score": assessment.score,
                    "scenarios": assessment.scenarios,
                    "distinct_scenarios": assessment.distinct_scenarios,
                    "regimes": assessment.regimes,
                    "reasons": assessment.reasons,
                }
            )
        elif args.command == "status":
            print(
                {
                    "db": str(Path(args.db)),
                    "alphas": store.connection.execute(
                        "SELECT COUNT(*) FROM alphas"
                    ).fetchone()[0],
                    "mock_evaluations": store.connection.execute(
                        "SELECT COUNT(*) FROM evaluations"
                    ).fetchone()[0],
                    "simulation_runs": store.connection.execute(
                        "SELECT COUNT(*) FROM simulation_runs"
                    ).fetchone()[0],
                    "quality_assessments": store.connection.execute(
                        "SELECT COUNT(*) FROM quality_assessments"
                    ).fetchone()[0],
                    "knowledge": store.connection.execute(
                        "SELECT COUNT(*) FROM knowledge"
                    ).fetchone()[0],
                    "reference_expressions": store.reference_count(),
                }
            )
    finally:
        store.close()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brain-alpha")
    parser.add_argument("--db", default="data/brain_alpha.db")
    commands = parser.add_subparsers(dest="command")
    generate = commands.add_parser("generate")
    generate.add_argument("--region", default="USA")
    generate.add_argument("--universe", default="TOP3000")
    generate.add_argument("--delay", type=int, default=1)
    generate.add_argument("--neutralization", default="SUBINDUSTRY")
    generate.add_argument(
        "--profile", choices=sorted(STRATEGY_PROFILES), default="robust"
    )
    validate = commands.add_parser("validate")
    validate.add_argument("formula")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("alpha_id")
    commands.add_parser("rank")
    revenue = commands.add_parser("import-revenue")
    revenue.add_argument("--revenue-db", default="../revenue_agent/data/paper.db")
    reference = commands.add_parser("import-reference")
    reference.add_argument(
        "--reference-path", default=r"D:\CS_materials\量化\101_Alphas_项目"
    )
    course = commands.add_parser("import-course")
    course.add_argument(
        "--course-path",
        default=r"D:\CS_materials\量化\Course2_作业答案\src\必做4_批量生成Alpha.py",
    )
    moltbook = commands.add_parser("import-moltbook")
    moltbook.add_argument("--query", required=True)
    moltbook.add_argument("--limit", type=int, default=20)
    fields = commands.add_parser("fields")
    fields.add_argument("--search")
    fields.add_argument("--limit", type=int, default=50)
    simulate = commands.add_parser("simulate")
    simulate.add_argument("alpha_id")
    simulate.add_argument(
        "--payload",
        required=True,
        help="path to the exact BRAIN simulation request JSON",
    )
    simulate.add_argument("--timeout", type=float, default=300)
    simulate.add_argument("--poll-interval", type=float, default=2)
    simulate.add_argument(
        "--regime", required=True, help="research regime label for this run"
    )
    simulate.add_argument(
        "--offline", action="store_true", help="use a deterministic local fake session"
    )
    research = commands.add_parser("research")
    research.add_argument("--alpha-id", action="append", required=True)
    research.add_argument("--payload-template", required=True)
    research.add_argument("--scenarios", required=True)
    research.add_argument("--timeout", type=float, default=300)
    research.add_argument("--poll-interval", type=float, default=2)
    research.add_argument("--max-runs", type=_positive_int, default=50)
    research.add_argument(
        "--offline", action="store_true", help="use deterministic local fake sessions"
    )
    assess = commands.add_parser("assess")
    assess.add_argument("alpha_id")
    assess.add_argument("--min-scenarios", type=_at_least_three_int, default=3)
    assess.add_argument("--min-distinct-scenarios", type=_at_least_three_int, default=3)
    assess.add_argument("--max-whipsaw-turnover", type=float, default=0.6)
    assess.add_argument("--require-regime", action="append")
    commands.add_parser("status")
    commands.add_parser("repl")
    return parser


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _at_least_three_int(value: str) -> int:
    parsed = int(value)
    if parsed < 3:
        raise argparse.ArgumentTypeError("high-quality assessment requires at least 3")
    return parsed


def _repl(args: argparse.Namespace) -> int:
    print("Brain Alpha Agent | offline evaluator | 不会自动提交 BRAIN")
    print("输入 /help 查看命令。")
    while True:
        try:
            line = input("alpha> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            return 0
        if not line:
            continue
        if line.startswith("/"):
            line = line[1:].strip()
        parts = line.split()
        command = parts[0].lower()
        if command in {"quit", "exit", "q"}:
            print("已退出。")
            return 0
        if command in {"help", "?"}:
            print(
                "命令: /generate | /validate FORMULA | /evaluate ALPHA_ID | /rank | /import-reference | /import-course | /fields | /import-revenue | /status | /quit"
            )
            continue
        try:
            if command == "generate":
                main(["--db", args.db, "generate"])
            elif command == "validate" and len(parts) > 1:
                main(["--db", args.db, "validate", line[len("validate ") :]])
            elif command == "evaluate" and len(parts) == 2:
                main(["--db", args.db, "evaluate", parts[1]])
            elif command in {"rank", "status"}:
                main(["--db", args.db, command])
            elif command == "import-revenue":
                main(["--db", args.db, "import-revenue"])
            elif command == "import-reference":
                main(["--db", args.db, "import-reference"])
            elif command == "import-course":
                main(["--db", args.db, "import-course"])
            elif command == "fields":
                main(["--db", args.db, "fields"])
            elif "因子" in line or "alpha" in line.casefold():
                print("我可以生成、校验、评估和排序因子。输入 /generate 开始。")
            else:
                print("无法识别命令。输入 /help。")
        except FormulaValidationError as error:
            print(f"公式不合法: {error}")
        except Exception as error:
            print(f"操作未执行: {error}")
