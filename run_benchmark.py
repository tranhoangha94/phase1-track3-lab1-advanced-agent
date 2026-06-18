from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import typer
from rich import print

from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.llm import use_mock
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.schemas import QAExample, RunRecord
from src.reflexion_lab.utils import load_dataset, save_jsonl

app = typer.Typer(add_completion=False)


def _append_jsonl(path: Path, record: RunRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")


def _log_progress(log_path: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(f"[cyan]{line}[/cyan]")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run_agent_with_progress(
    agent: ReActAgent | ReflexionAgent,
    examples: list[QAExample],
    agent_label: str,
    jsonl_path: Path,
    log_path: Path,
    verbose: bool,
) -> list[RunRecord]:
    total = len(examples)
    records: list[RunRecord] = []
    jsonl_path.write_text("", encoding="utf-8")

    for index, example in enumerate(examples, start=1):
        preview = example.question[:70].replace("\n", " ")
        if verbose:
            os.environ["BENCHMARK_VERBOSE"] = "1"
            _log_progress(
                log_path,
                f"{agent_label} {index}/{total} | qid={example.qid} | START | {preview}...",
            )
        else:
            _log_progress(
                log_path,
                f"{agent_label} {index}/{total} | qid={example.qid} | {preview}...",
            )

        record = agent.run(example)
        records.append(record)
        _append_jsonl(jsonl_path, record)

        status = "OK" if record.is_correct else "FAIL"
        _log_progress(
            log_path,
            (
                f"{agent_label} {index}/{total} | qid={example.qid} | {status} "
                f"| attempts={record.attempts} | pred={record.predicted_answer[:60]!r}"
            ),
        )

    if verbose:
        os.environ.pop("BENCHMARK_VERBOSE", None)

    return records


@app.command()
def main(
    dataset: str = "data/hotpot_mini.json",
    out_dir: str = "outputs/sample_run",
    reflexion_attempts: int = 3,
    mock: bool = typer.Option(None, "--mock/--llm", help="Force mock runtime or real LLM calls."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log từng attempt bên trong agent."),
    report_only: bool = typer.Option(
        False,
        "--report-only",
        help="Chỉ tạo lại Report.md từ react_runs.jsonl / reflexion_runs.jsonl đã có.",
    ),
    report_mode: str = typer.Option("llm", "--report-mode", help="Mode ghi vào report khi dùng --report-only."),
) -> None:
    out_path = Path(out_dir)
    if report_only:
        react_records = _load_jsonl_records(out_path / "react_runs.jsonl")
        reflexion_records = _load_jsonl_records(out_path / "reflexion_runs.jsonl")
        all_records = react_records + reflexion_records
        if not all_records:
            raise typer.BadParameter(f"Không tìm thấy run records trong {out_dir}")
        report = build_report(all_records, dataset_name=Path(dataset).name, mode=report_mode)
        json_path, md_path = save_report(report, out_path, root_report="Report.md")
        print(f"[green]Saved[/green] {json_path}")
        print(f"[green]Saved[/green] {md_path}")
        print(f"[green]Saved[/green] Report.md")
        return

    if mock is not None:
        os.environ["USE_MOCK"] = "1" if mock else "0"
    mode = "mock" if use_mock() else "llm"
    examples = load_dataset(dataset)
    log_path = out_path / "progress.log"
    log_path.write_text("", encoding="utf-8")

    _log_progress(log_path, f"Benchmark start | mode={mode} | total_questions={len(examples)}")

    react = ReActAgent()
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts)
    react_records = _run_agent_with_progress(
        react,
        examples,
        "ReAct",
        out_path / "react_runs.jsonl",
        log_path,
        verbose,
    )
    reflexion_records = _run_agent_with_progress(
        reflexion,
        examples,
        "Reflexion",
        out_path / "reflexion_runs.jsonl",
        log_path,
        verbose,
    )
    all_records = react_records + reflexion_records
    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)
    report = build_report(all_records, dataset_name=Path(dataset).name, mode=mode)
    json_path, md_path = save_report(report, out_path, root_report="Report.md")
    _log_progress(log_path, "Benchmark done")
    print(f"[green]Saved[/green] {json_path}")
    print(f"[green]Saved[/green] {md_path}")
    print(f"[green]Saved[/green] Report.md")
    print(f"[green]Saved[/green] {log_path}")
    print(json.dumps(report.summary, indent=2))


def _load_jsonl_records(path: Path) -> list[RunRecord]:
    if not path.exists():
        return []
    return [
        RunRecord.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    app()