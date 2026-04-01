"""Rich terminal display for :class:`~measurediff.comparator.MeasureComparison`.

Renders a structured, coloured report highlighting where two measures are the
same or different across expression, window specs, and lineage leaf sources.
"""

from __future__ import annotations

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .comparator import (
    LineageComparison,
    LeafSource,
    MeasureComparison,
    WindowComparison,
)


# Shared console — auto-detects whether the terminal supports colour.
_console = Console()


def render_diff(comparison: MeasureComparison, console: Console | None = None) -> None:
    """Render a rich diff of *comparison* to the terminal.

    Args:
        comparison: Result of :func:`~measurediff.comparator.compare_measures`.
        console:    Optional :class:`~rich.console.Console` for testing/capture.
                    Defaults to a shared auto-detecting console.
    """
    c = console or _console
    c.print()

    # ------------------------------------------------------------------
    # Header — measure identity (names always differ, shown prominently)
    # ------------------------------------------------------------------
    header = _make_header_table(comparison)
    c.print(Panel(header, title="Measure Diff", border_style="bright_blue"))

    # ------------------------------------------------------------------
    # Similarity score
    # ------------------------------------------------------------------
    c.print(_make_score_panel(comparison))

    # ------------------------------------------------------------------
    # Expression
    # ------------------------------------------------------------------
    c.print(_make_expr_panel(comparison))

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------
    c.print(_make_window_panel(comparison))

    # ------------------------------------------------------------------
    # Lineage
    # ------------------------------------------------------------------
    c.print(_make_lineage_panel(comparison))

    c.print()


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _make_header_table(cmp: MeasureComparison) -> Table:
    t = Table.grid(expand=True, padding=(0, 2))
    t.add_column(justify="left")
    t.add_column(justify="left")

    t.add_row(
        Text("A", style="bold cyan"),
        Text("B", style="bold cyan"),
    )
    t.add_row(
        Text(cmp.view_a, style="dim"),
        Text(cmp.view_b, style="dim"),
    )
    t.add_row(
        Text(cmp.measure_a.name, style="bold white"),
        Text(cmp.measure_b.name, style="bold white"),
    )
    return t


def _make_score_panel(cmp: MeasureComparison) -> Panel:
    pct = cmp.score * 100
    label = cmp.label

    if label == "Identical":
        style = "bold green"
        border = "green"
    elif label == "Similar":
        style = "bold yellow"
        border = "yellow"
    else:
        style = "bold red"
        border = "red"

    content = Text(f"{label}  {pct:.1f}%", style=style, justify="center")
    return Panel(content, title="Similarity", border_style=border, expand=False)


def _make_expr_panel(cmp: MeasureComparison) -> Panel:
    ec = cmp.expr

    if ec.same:
        # If raw expressions are identical, one line is enough
        if ec.raw_a == ec.raw_b:
            content = Text(ec.raw_a, style="green")
        else:
            # Different raw but same normalized — show both raw + note
            t = Table.grid(expand=True, padding=(0, 2))
            t.add_column(header="A", style="dim")
            t.add_column(header="B", style="dim")
            t.add_row(
                Text(ec.raw_a, style="yellow"),
                Text(ec.raw_b, style="yellow"),
            )
            t.add_row(
                Text(f"→ {ec.normalized_a}", style="green"),
                Text(f"→ {ec.normalized_b}", style="green"),
            )
            note = Text("\n✓ Normalized expressions match", style="green")
            content = Columns([t, note])  # type: ignore[arg-type]
            # Fall through with a Panel directly
            return Panel(content, title="Expression", border_style="green")
        border = "green"
        title = "Expression  ✓"
    else:
        t = Table.grid(expand=True, padding=(0, 2))
        t.add_column(ratio=1)
        t.add_column(ratio=1)
        t.add_row(
            Text("A — raw", style="bold dim"),
            Text("B — raw", style="bold dim"),
        )
        t.add_row(Text(ec.raw_a, style="yellow"),
                  Text(ec.raw_b, style="yellow"))
        t.add_row(
            Text("A — normalized", style="bold dim"),
            Text("B — normalized", style="bold dim"),
        )
        t.add_row(Text(ec.normalized_a, style="red"),
                  Text(ec.normalized_b, style="red"))
        content = t  # type: ignore[assignment]
        border = "red"
        title = "Expression  ✗"

    # type: ignore[arg-type]
    return Panel(content, title=title, border_style=border)


def _make_window_panel(cmp: MeasureComparison) -> Panel:
    wc: WindowComparison = cmp.window

    if not wc.specs_a and not wc.specs_b:
        content = Text("No window specs on either measure", style="dim")
        return Panel(content, title="Window", border_style="dim")

    if wc.same:
        content = Text("Window specs match", style="green")
        return Panel(content, title="Window  ✓", border_style="green")

    t = Table(show_header=True, header_style="bold")
    t.add_column("Spec", justify="right", style="dim", no_wrap=True)
    t.add_column("Field")
    t.add_column("A")
    t.add_column("B")
    t.add_column("", justify="center", no_wrap=True)

    # Collect matching fields to show as context
    total_specs = max(len(wc.specs_a), len(wc.specs_b))
    diff_keys = {(d.spec_index, d.field) for d in wc.field_diffs}

    for i in range(total_specs):
        wa = wc.specs_a[i] if i < len(wc.specs_a) else None
        wb = wc.specs_b[i] if i < len(wc.specs_b) else None
        for fname in ("order", "range", "semiadditive"):
            va = getattr(wa, fname, None) if wa else None
            vb = getattr(wb, fname, None) if wb else None
            if va is None and vb is None:
                continue
            if (i, fname) in diff_keys:
                mark = Text("✗", style="red")
                style_a = "red"
                style_b = "red"
            else:
                mark = Text("✓", style="green")
                style_a = "green"
                style_b = "green"
            t.add_row(
                f"[{i}]",
                fname,
                Text(str(va) if va is not None else "—", style=style_a),
                Text(str(vb) if vb is not None else "—", style=style_b),
                mark,
            )

    return Panel(t, title="Window  ✗", border_style="yellow")


def _make_lineage_panel(cmp: MeasureComparison) -> Panel:
    lc: LineageComparison = cmp.lineage

    if not lc.leaf_sources_a and not lc.leaf_sources_b:
        content = Text("No lineage on either measure", style="dim")
        return Panel(content, title="Lineage", border_style="dim")

    t = Table(show_header=True, header_style="bold")
    t.add_column("Source")
    t.add_column("Column")
    t.add_column("In A", justify="center")
    t.add_column("In B", justify="center")

    def _leaf_row(leaf: LeafSource, in_a: bool, in_b: bool) -> None:
        if in_a and in_b:
            style = "green"
            mark_a = Text("✓", style="green")
            mark_b = Text("✓", style="green")
        elif in_a:
            style = "red"
            mark_a = Text("✓", style="red")
            mark_b = Text("—", style="dim")
        else:
            style = "red"
            mark_a = Text("—", style="dim")
            mark_b = Text("✓", style="red")
        t.add_row(Text(leaf.table, style=style), Text(
            leaf.column, style=style), mark_a, mark_b)

    # Shared first, then exclusive
    for leaf in sorted(lc.shared_leaves, key=lambda l: (l.table, l.column)):
        _leaf_row(leaf, in_a=True, in_b=True)
    for leaf in sorted(lc.only_in_a, key=lambda l: (l.table, l.column)):
        _leaf_row(leaf, in_a=True, in_b=False)
    for leaf in sorted(lc.only_in_b, key=lambda l: (l.table, l.column)):
        _leaf_row(leaf, in_a=False, in_b=True)

    border = "green" if lc.leaves_same else "yellow"
    title_mark = "✓" if lc.leaves_same else "~"
    title = f"Lineage (leaf sources)  {title_mark}"

    extras: list[str] = []
    if lc.has_extra_hops_a:
        extras.append(f"  [yellow]⚠ A has extra intermediate hops[/yellow]")
    if lc.has_extra_hops_b:
        extras.append(f"  [yellow]⚠ B has extra intermediate hops[/yellow]")

    if extras:
        from rich.console import Group  # local import to avoid top-level dep confusion
        content = Group(t, *[Text.from_markup(e) for e in extras])
        return Panel(content, title=title, border_style=border)

    return Panel(t, title=title, border_style=border)
