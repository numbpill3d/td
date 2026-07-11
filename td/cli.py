"""td — task daemon. minimal, text-first, daily driver."""
from __future__ import annotations

import datetime
import random
import time
from pathlib import Path
from typing import Optional

import typer
import yaml
from dateutil import parser as dtparser
from dateutil.rrule import DAILY, FR, MO, MONTHLY, SA, SU, TH, TU, WE, WEEKLY, YEARLY, rrule
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

app = typer.Typer(
    name="td",
    help="task daemon — minimal, text-first, daily driver",
    rich_markup_mode="rich",
    add_completion=False,
    invoke_without_command=True,
)

console = Console(highlight=False)

# ── brand palette ──────────────────────────────────────────────────────────────
C_ACCENT = "magenta"
C_DIM = "bright_black"
C_SUCCESS = "green"
C_WARN = "yellow"
C_ERROR = "red"
C_MUTED = "dim"

# ── data paths ─────────────────────────────────────────────────────────────────
TD_DIR = Path.home() / ".td"
TASKS_FILE = TD_DIR / "tasks.yaml"
DONE_FILE = TD_DIR / "done.yaml"

# ── task model ─────────────────────────────────────────────────────────────────
class Task:
    __slots__ = ("id", "text", "recur", "next_due", "created", "done_at")

    def __init__(
        self,
        id: int,
        text: str,
        recur: str | None = None,
        next_due: str | None = None,
        created: str | None = None,
        done_at: str | None = None,
    ):
        self.id = id
        self.text = text
        self.recur = recur
        self.next_due = next_due
        self.created = created or datetime.datetime.now().isoformat()
        self.done_at = done_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "recur": self.recur,
            "next_due": self.next_due,
            "created": self.created,
            "done_at": self.done_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(**d)

    def is_due(self, date: datetime.date | None = None) -> bool:
        if self.done_at:
            return False
        if not self.next_due:
            return True
        due = dtparser.isoparse(self.next_due).date()
        target = date or datetime.datetime.now().date()
        return due <= target

    def advance_recurrence(self) -> bool:
        """Advance to next occurrence. Returns True if advanced, False if no recurrence."""
        if not self.recur or self.done_at:
            return False
        try:
            rule = parse_recurrence(self.recur)
            if rule:
                now = datetime.datetime.now()
                next_occ = rule.after(now, inc=True)
                if next_occ:
                    self.next_due = next_occ.date().isoformat()
                    return True
        except Exception:
            pass
        return False


def parse_recurrence(spec: str):
    """Parse human recurrence: 'every mon 9am', 'every fri', 'every 1st', 'daily'."""
    spec = spec.lower().strip().removeprefix("every ").strip()
    now = datetime.datetime.now()

    # daily
    if spec in ("daily", "day"):
        return rrule(DAILY, dtstart=now)

    # weekly by weekday
    weekdays = {"mon": MO, "tue": TU, "wed": WE, "thu": TH, "fri": FR, "sat": SA, "sun": SU}
    for name, wday in weekdays.items():
        if spec.startswith(name):
            byhour = 9
            if " " in spec:
                try:
                    time_part = spec.split(" ", 1)[1]
                    byhour = datetime.datetime.fromisoformat(f"2000-01-01T{time_part}").hour
                except Exception:
                    pass
            return rrule(WEEKLY, byweekday=wday, byhour=byhour, dtstart=now)

    # monthly by day number (1st, 15th, last)
    if spec.endswith(("st", "nd", "rd", "th")):
        try:
            day = int("".join(c for c in spec if c.isdigit()))
            return rrule(MONTHLY, bymonthday=day, dtstart=now)
        except Exception:
            pass

    # yearly
    if spec in ("yearly", "annual"):
        return rrule(YEARLY, dtstart=now)

    return None


# ── storage ────────────────────────────────────────────────────────────────────
def load_tasks() -> list[Task]:
    TD_DIR.mkdir(exist_ok=True)
    if not TASKS_FILE.exists():
        return []
    data = yaml.safe_load(TASKS_FILE.read_text()) or []
    return [Task.from_dict(d) for d in data]


def save_tasks(tasks: list[Task]) -> None:
    TD_DIR.mkdir(exist_ok=True)
    TASKS_FILE.write_text(yaml.dump([t.to_dict() for t in tasks], sort_keys=False))


def load_done() -> list[Task]:
    if not DONE_FILE.exists():
        return []
    data = yaml.safe_load(DONE_FILE.read_text()) or []
    return [Task.from_dict(d) for d in data]


def save_done(done: list[Task]) -> None:
    TD_DIR.mkdir(exist_ok=True)
    DONE_FILE.write_text(yaml.dump([t.to_dict() for t in done], sort_keys=False))


def next_id(tasks: list[Task], done: list[Task]) -> int:
    all_ids = [t.id for t in tasks] + [t.id for t in done]
    return max(all_ids, default=0) + 1


# ── banner ─────────────────────────────────────────────────────────────────────
_BANNER_LINES = [
    ("  ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ", "bold bright_white"),
    ("  █       █       █       █       █       █       █       ", "white"),
    ("  █  ▄▄▄▄▄█  ▄▄▄▄▄█  ▄▄▄▄▄█  ▄▄▄▄▄█  ▄▄▄▄▄█  ▄▄▄▄▄█  ▄▄▄▄▄█ ", "bold magenta"),
    ("  █ █▄▄▄▄▄ █ █▄▄▄▄▄ █ █▄▄▄▄▄ █ █▄▄▄▄▄ █ █▄▄▄▄▄ █ █▄▄▄▄▄ █ █▄▄▄▄▄ ", "magenta"),
    ("  █▄▄▄▄▄█ █▄▄▄▄▄█ █▄▄▄▄▄█ █▄▄▄▄▄█ █▄▄▄▄▄█ █▄▄▄▄▄█ █▄▄▄▄▄█ █▄▄▄▄▄█ ", "bold magenta"),
]

_NOISE = "═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬"


def _static(n: int) -> str:
    return "".join(random.choice(_NOISE) for _ in range(n))


def _build(revealed: int, beam: int = -1, glitch: set[int] | None = None) -> Text:
    t = Text()
    g = glitch or set()
    for i, (line, style) in enumerate(_BANNER_LINES):
        if i in g:
            t.append(_static(len(line)) + "\n", style="dim magenta")
        elif i < revealed:
            t.append(line + "\n", style=style)
        elif i == beam:
            t.append(line + "\n", style="bold bright_magenta")
        else:
            t.append(_static(len(line)) + "\n", style="dim magenta")
    return t


def print_banner() -> None:
    with Live(Align.center(_build(0, 0)), console=console, refresh_per_second=20, transient=False) as live:
        for beam in range(len(_BANNER_LINES) + 1):
            live.update(Align.center(_build(max(0, beam - 1), beam)))
            time.sleep(0.035)
        for lit in range(len(_BANNER_LINES) + 1):
            up_beam = (len(_BANNER_LINES) - 1) - lit
            live.update(Align.center(_build(len(_BANNER_LINES), beam=up_beam if lit < len(_BANNER_LINES) else -1)))
            time.sleep(0.045)
        for _ in range(4):
            bad = {i for i in range(len(_BANNER_LINES)) if random.random() < 0.12}
            live.update(Align.center(_build(len(_BANNER_LINES), -1, glitch=bad)))
            time.sleep(0.025)
        final = _build(len(_BANNER_LINES), len(_BANNER_LINES))
        final.append("\n  task daemon  ·  minimal  ·  text-first\n", style="dim magenta")
        live.update(Align.center(final))


# ── helpers ────────────────────────────────────────────────────────────────────
def rule(title: str = "", style: str = C_DIM) -> None:
    console.print(Rule(title, style=style))


def success(msg: str) -> None:
    console.print(f"[bold {C_SUCCESS}]✓[/]  {msg}")


def error(msg: str) -> None:
    console.print(f"[bold {C_ERROR}]✗[/]  [bold {C_ERROR}]error:[/] {msg}")


def warn(msg: str) -> None:
    console.print(f"[{C_WARN}]⚠[/]  {msg}")


def info(msg: str) -> None:
    console.print(f"[{C_MUTED}]·[/]  [dim]{msg}[/]")


def bullet(msg: str) -> None:
    console.print(f"  [dim {C_ACCENT}]•[/] {msg}")


# ── table rendering ────────────────────────────────────────────────────────────
def render_tasks(tasks: list[Task], title: str, show_id: bool = True, date_filter: datetime.date | None = None) -> Panel:
    table = Table(box=box.SIMPLE_HEAVY, border_style=C_DIM, show_header=True, header_style=f"bold {C_ACCENT}")
    if show_id:
        table.add_column("id", style=f"bold {C_ACCENT}", no_wrap=True, width=4)
    table.add_column("task", style="white", min_width=40)
    if date_filter is None:
        table.add_column("due", style=C_MUTED, no_wrap=True, width=12)
        table.add_column("recur", style=C_MUTED, no_wrap=True, width=18)
    for t in tasks:
        due_str = t.next_due or "—"
        recur_str = t.recur or "—"
        if date_filter:
            row = [str(t.id), t.text] if show_id else [t.text]
        else:
            row = [str(t.id), t.text, due_str, recur_str] if show_id else [t.text, due_str, recur_str]
        table.add_row(*row)
    return Panel(table, title=f"[bold {C_ACCENT}]{title}[/]", border_style=C_DIM, box=box.ROUNDED)


# ── commands ───────────────────────────────────────────────────────────────────
@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print()
        console.print(Columns([_help_commands(), _help_examples()], equal=False, expand=True))
        console.print()


def _help_commands() -> Panel:
    t = Table(box=None, show_header=False, padding=(0, 2), expand=True)
    t.add_column("cmd", style=f"bold {C_ACCENT}", no_wrap=True, min_width=10)
    t.add_column("desc", style="white")
    rows = [
        ("add", "add a task"),
        ("ls", "list today + overdue"),
        ("week", "7-day view"),
        ("all", "everything"),
        ("do", "mark done"),
        ("rm", "remove task"),
        ("defer", "push to tomorrow"),
        ("edit", "edit task text"),
        ("recur", "set/clear recurrence"),
        ("done", "show completed"),
        ("purge", "archive old done"),
    ]
    for cmd, desc in rows:
        t.add_row(cmd, desc)
    return Panel(t, title=f"[bold {C_ACCENT}]commands[/]", border_style=C_DIM, box=box.ROUNDED)


def _help_examples() -> Panel:
    t = Table(box=None, show_header=False, padding=(0, 2), expand=True)
    t.add_column("label", style=C_MUTED, no_wrap=True, min_width=14)
    t.add_column("cmd", style=f"bold {C_SUCCESS}")
    rows = [
        ("basic", 'td add "review PR"'),
        ("recurring", 'td add "standup" --every "mon 9am"'),
        ("monthly", 'td add "pay rent" --every "1st"'),
        ("mark done", "td do 3"),
        ("defer", "td defer 3"),
        ("edit", "td edit 3 \"new text\""),
        ("week view", "td week"),
    ]
    for label, cmd in rows:
        t.add_row(label, cmd)
    return Panel(t, title=f"[bold {C_ACCENT}]examples[/]", border_style=C_DIM, box=box.ROUNDED)


@app.command()
def add(
    text: str = typer.Argument(..., help="Task text"),
    every: Optional[str] = typer.Option(None, "--every", "-e", help="Recurrence: 'mon 9am', 'fri', '1st', 'daily'"),
) -> None:
    """Add a task."""
    tasks = load_tasks()
    done = load_done()
    task = Task(id=next_id(tasks, done), text=text, recur=every)
    if every:
        rule = parse_recurrence(every)
        if rule:
            task.next_due = rule.after(datetime.datetime.now(), inc=True).date().isoformat()
    tasks.append(task)
    save_tasks(tasks)
    success(f"added [{task.id}] {text}" + (f" — every {every}" if every else ""))


@app.command(name="ls")
def ls(
    all: bool = typer.Option(False, "--all", "-a", help="Show all pending (not just due)"),
) -> None:
    """List today + overdue (or all pending with --all)."""
    tasks = load_tasks()
    today = datetime.datetime.now().date()
    if all:
        pending = [t for t in tasks if not t.done_at]
    else:
        pending = [t for t in tasks if not t.done_at and t.is_due(today)]
    pending.sort(key=lambda t: (t.next_due or "~", t.id))
    if not pending:
        info("nothing due" + ("" if all else " — use --all to see all pending"))
        return
    console.print(render_tasks(pending, "due today" if not all else "all pending", date_filter=None if all else today))


@ app.command()
def week() -> None:
    """7-day view."""
    tasks = load_tasks()
    today = datetime.datetime.now().date()
    days = [today + datetime.timedelta(days=i) for i in range(7)]
    panels = []
    for d in days:
        day_tasks = [t for t in tasks if not t.done_at and t.is_due(d)]
        label = d.strftime("%a %m/%d")
        if d == today:
            label += " [bold magenta](today)[/]"
        panels.append(render_tasks(day_tasks, label, show_id=True))
    console.print(Columns(panels, equal=True, expand=True))


@app.command()
def all() -> None:
    """All pending tasks."""
    tasks = [t for t in load_tasks() if not t.done_at]
    tasks.sort(key=lambda t: (t.next_due or "~", t.id))
    console.print(render_tasks(tasks, "all pending"))


@app.command()
def do(task_id: int) -> None:
    """Mark task done."""
    tasks = load_tasks()
    done = load_done()
    for t in tasks:
        if t.id == task_id:
            t.done_at = datetime.datetime.now().isoformat()
            done.append(t)
            tasks.remove(t)
            # if recurring, create next instance
            if t.recur and t.advance_recurrence():
                t.done_at = None
                t.id = next_id(tasks, done)
                tasks.append(t)
                success(f"done [{task_id}] — next due {t.next_due}")
            else:
                success(f"done [{task_id}]")
            save_tasks(tasks)
            save_done(done)
            return
    error(f"task {task_id} not found")


@app.command()
def rm(task_id: int) -> None:
    """Remove task permanently."""
    tasks = load_tasks()
    for i, t in enumerate(tasks):
        if t.id == task_id:
            tasks.pop(i)
            save_tasks(tasks)
            success(f"removed [{task_id}]")
            return
    error(f"task {task_id} not found")


@app.command()
def defer(task_id: int, days: int = 1) -> None:
    """Push task forward by N days (default 1)."""
    tasks = load_tasks()
    for t in tasks:
        if t.id == task_id:
            base = datetime.date.fromisoformat(t.next_due) if t.next_due else datetime.datetime.now().date()
            t.next_due = (base + datetime.timedelta(days=days)).isoformat()
            save_tasks(tasks)
            success(f"deferred [{task_id}] to {t.next_due}")
            return
    error(f"task {task_id} not found")


@app.command()
def edit(task_id: int, new_text: str) -> None:
    """Edit task text."""
    tasks = load_tasks()
    for t in tasks:
        if t.id == task_id:
            t.text = new_text
            save_tasks(tasks)
            success(f"updated [{task_id}]")
            return
    error(f"task {task_id} not found")


@app.command()
def recur(task_id: int, every: Optional[str] = typer.Argument(None, help="Recurrence spec, or empty to clear")) -> None:
    """Set or clear recurrence."""
    tasks = load_tasks()
    for t in tasks:
        if t.id == task_id:
            t.recur = every
            if every:
                rule = parse_recurrence(every)
                if rule:
                    t.next_due = rule.after(datetime.datetime.now(), inc=True).date().isoformat()
            else:
                t.next_due = None
            save_tasks(tasks)
            success(f"recurrence {'set to ' + every if every else 'cleared'} for [{task_id}]")
            return
    error(f"task {task_id} not found")


@app.command()
def done() -> None:
    """Show completed tasks (last 30 days)."""
    done = load_done()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
    recent = [t for t in done if t.done_at and datetime.datetime.fromisoformat(t.done_at) > cutoff]
    recent.sort(key=lambda t: t.done_at or "", reverse=True)
    if not recent:
        info("no completed tasks in last 30 days")
        return
    table = Table(box=box.SIMPLE_HEAVY, border_style=C_DIM, header_style=f"bold {C_ACCENT}")
    table.add_column("id", style=f"bold {C_ACCENT}", width=4)
    table.add_column("task", style="white", min_width=40)
    table.add_column("completed", style=C_MUTED, width=16)
    for t in recent[:30]:
        dt = datetime.datetime.fromisoformat(t.done_at).strftime("%m/%d %H:%M") if t.done_at else "—"
        table.add_row(str(t.id), t.text, dt)
    console.print(Panel(table, title=f"[bold {C_ACCENT}]done (30d)[/]", border_style=C_DIM, box=box.ROUNDED))


@app.command()
def purge(days: int = 90) -> None:
    """Archive done tasks older than N days."""
    done = load_done()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    kept = [t for t in done if not t.done_at or datetime.datetime.fromisoformat(t.done_at) > cutoff]
    removed = len(done) - len(kept)
    save_done(kept)
    success(f"archived {removed} tasks older than {days}d")


if __name__ == "__main__":
    app()