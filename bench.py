#!/usr/bin/env python3
"""Cell-2 analytics & benchmark tool — measures quality and cost of DeepSeek vs. published baselines."""

import time
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from core import proxy

console = Console()

# DeepSeek-V3 prices (USD / token, as of 2025)
PRICE_INPUT  = 0.27  / 1_000_000
PRICE_OUTPUT = 1.10  / 1_000_000

SYSTEM = "You are Cell-2, a helpful AI assistant. Answer concisely and correctly."

TASKS = [
    {
        "id": "code_fn",
        "label": "Fibonacci function",
        "category": "Code",
        "prompt": "Write a Python function fibonacci(n) that returns the n-th Fibonacci number (iteratively).",
        "check": lambda r: "def fibonacci" in r and "return" in r,
    },
    {
        "id": "code_class",
        "label": "Stack class",
        "category": "Code",
        "prompt": "Write a Python class Stack with push, pop and peek methods. No imports.",
        "check": lambda r: "class Stack" in r and "def push" in r and "def pop" in r,
    },
    {
        "id": "math",
        "label": "Math",
        "category": "Logic",
        "prompt": "I have 17 apples. I give 1/3 to Peter (round down) and half the remainder to Mary. How many do I have left?",
        "check": lambda r: any(x in r for x in ["6", "six"]),
    },
    {
        "id": "logic",
        "label": "Logic puzzle",
        "category": "Logic",
        "prompt": "All Blumbas are Flumbi. Some Flumbi are Glurps. Is it possible that no Blumba is a Glurp? Answer with one word (yes/no) and explain.",
        "check": lambda r: "yes" in r.lower()[:20],
    },
    {
        "id": "tool_fn",
        "label": "Brain funkce (BTC)",
        "category": "Agent",
        "prompt": (
            "Write a complete Python file for a Cell-2 brain function that fetches the current BTC price "
            "from the CoinGecko API. Must include a SPEC dict and def run(**kwargs)."
        ),
        "check": lambda r: "def run" in r and "SPEC" in r and "btc" in r.lower(),
    },
    {
        "id": "planning",
        "label": "Multi-step plan",
        "category": "Agent",
        "prompt": "Design a concrete 3-step implementation plan for a web scraper that tracks product prices.",
        "check": lambda r: any(x in r for x in ["1.", "1)", "Step 1"]) and len(r.split("\n")) >= 3,
    },
    {
        "id": "czech",
        "label": "Language — tech",
        "category": "Language",
        "prompt": "Explain the difference between synchronous and asynchronous programming in 2-3 sentences.",
        "check": lambda r: len(r) > 80 and "async" in r.lower(),
    },
]

# Published benchmark scores (SWE-bench Verified 2025, prices April 2025)
LEADERBOARD = [
    ("Claude 4.5 Sonnet", "77.2 %", "$3.00",  "$15.00", "Best SWE-bench"),
    ("Claude 4.5 Opus",   "74.4 %", "$15.00", "$75.00", "Best complex reasoning"),
    ("Gemini 2.5 Pro",    "~63 %",  "$1.25",  "$10.00", "#1 LMArena Elo (1501)"),
    ("GPT-4o",            "~38 %",  "$2.50",  "$10.00", "Most widespread"),
    ("DeepSeek-V3",       "~42 %",  "$0.27",  "$1.10",  "Best price/performance"),
]


@dataclass
class Result:
    task_id: str
    label: str
    category: str
    passed: bool
    latency: float
    prompt_tok: int
    completion_tok: int
    cost: float
    snippet: str


def run_task(task: dict) -> Result:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": task["prompt"]},
    ]
    t0 = time.perf_counter()
    msg = proxy.chat(messages)
    latency = time.perf_counter() - t0

    usage = proxy.get_last_usage()
    response = msg.get("content", "") or ""
    ptok = usage.get("prompt_tokens", 0)
    ctok = usage.get("completion_tokens", 0)
    cost = ptok * PRICE_INPUT + ctok * PRICE_OUTPUT

    try:
        passed = bool(task["check"](response))
    except Exception:
        passed = False

    return Result(
        task_id=task["id"], label=task["label"], category=task["category"],
        passed=passed, latency=latency,
        prompt_tok=ptok, completion_tok=ctok, cost=cost,
        snippet=response.replace("\n", " ").strip()[:72],
    )


def print_report(results: list[Result]) -> None:
    # --- task table ---
    t = Table(title="Cell-2 — benchmark results", box=box.ROUNDED, show_lines=True)
    t.add_column("Task",       style="cyan",  min_width=18)
    t.add_column("Cat.",       style="dim",   min_width=7)
    t.add_column("✓/✗",       justify="center")
    t.add_column("Latency",    justify="right", style="yellow")
    t.add_column("Tok. in+out",justify="right")
    t.add_column("Cost USD",   justify="right", style="green")
    t.add_column("Preview",    max_width=38, style="dim")

    for r in results:
        mark = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
        t.add_row(
            r.label, r.category, mark,
            f"{r.latency:.2f}s",
            f"{r.prompt_tok}+{r.completion_tok}",
            f"${r.cost:.5f}",
            r.snippet,
        )
    console.print(t)

    # --- summary ---
    n_pass     = sum(1 for r in results if r.passed)
    score_pct  = n_pass / len(results) * 100
    total_cost = sum(r.cost for r in results)
    avg_lat    = sum(r.latency for r in results) / len(results)

    console.print(Panel(
        f"[bold]Score:[/bold] {n_pass}/{len(results)} ({score_pct:.0f} %)  │  "
        f"[bold]Avg latency:[/bold] {avg_lat:.2f} s  │  "
        f"[bold]Total cost:[/bold] ${total_cost:.4f}",
        title="Summary", border_style="green",
    ))

    # --- leaderboard ---
    lb = Table(
        title="Comparison with published benchmarks (SWE-bench Verified 2025)",
        box=box.SIMPLE_HEAVY,
    )
    lb.add_column("Model / Agent",    style="cyan")
    lb.add_column("SWE-bench",        justify="center")
    lb.add_column("Input $/M tok",    justify="right")
    lb.add_column("Output $/M tok",   justify="right")
    lb.add_column("Note",             style="dim")

    for row in LEADERBOARD:
        lb.add_row(*row)

    lb.add_row(
        "[bold green]Cell-2 (tento benchmark)[/bold green]",
        f"[bold green]{score_pct:.0f} %[/bold green]",
        "[bold green]$0.27[/bold green]",
        "[bold green]$1.10[/bold green]",
        f"[bold green]avg latency {avg_lat:.1f} s · ${total_cost:.4f} total[/bold green]",
    )
    console.print()
    console.print(lb)
    console.print("\n[dim]Sources: swebench.com · tech-insider.org · getpassionfruit.com (2025)[/dim]\n")


def main() -> None:
    console.print(Panel(
        "[bold cyan]Cell-2 Analytics & Benchmark[/bold cyan]",
        subtitle="model: deepseek-chat · custom set of 7 tasks",
    ))

    results: list[Result] = []
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), TimeElapsedColumn(),
        console=console,
    ) as progress:
        bar = progress.add_task("Running...", total=len(TASKS))
        for task in TASKS:
            progress.update(bar, description=f"[cyan]{task['label']}[/cyan]")
            try:
                results.append(run_task(task))
            except Exception as e:
                results.append(Result(
                    task_id=task["id"], label=task["label"], category=task["category"],
                    passed=False, latency=0, prompt_tok=0, completion_tok=0,
                    cost=0, snippet=f"[ERROR] {e}",
                ))
            progress.advance(bar)

    print_report(results)


if __name__ == "__main__":
    main()
