"""Pretty console output for pbi2dbr transpilation events.

Set ``enabled = True`` (done automatically by the ``pbi2dbr convert`` CLI
command) to have every DAX → SQL and Power Query M → SQL conversion printed
to the terminal as it happens.
"""

from __future__ import annotations

from typing import Optional

import click

# Flip to True via the CLI to enable per-conversion console output.
enabled: bool = False


def show_dax(
    table: str,
    name: str,
    dax: str,
    sql: str,
    window: list[dict],
    warnings: list[str],
) -> None:
    """Print a DAX → SQL conversion block."""
    if not enabled:
        return

    lbl = click.style("DAX", fg="yellow")
    tbl = click.style(f"[{table}]", bold=True)
    click.echo(f"  {lbl}  {tbl} {name}")

    for line in dax.strip().splitlines():
        click.echo(f"         {click.style(line.strip(), dim=True)}")

    lbl_sql = click.style("SQL", fg="green")
    click.echo(f"  {lbl_sql}  {click.style(sql, fg='cyan')}")

    for w in window:
        parts = f"order={w.get('order', '')}  range={w.get('range', '')}"
        if w.get("semiadditive"):
            parts += f"  semiadditive={w['semiadditive']}"
        click.echo(f"         {click.style('window: ' + parts, dim=True)}")

    for warn in warnings:
        click.echo(f"         {click.style('▲ ' + warn, fg='yellow')}")

    click.echo()


def show_m_resolution(
    table: str,
    source_ref: Optional[str],
    filter_sql: Optional[str],
    native_sql: Optional[str],
) -> None:
    """Print a Power Query M → UC reference / SQL resolution block."""
    if not enabled:
        return
    if not source_ref and not filter_sql and not native_sql:
        return

    lbl = click.style("  M ", fg="magenta")
    tbl = click.style(f"[{table}]", bold=True)

    if native_sql:
        click.echo(f"{lbl}  {tbl}  →  {click.style('(native SQL)', dim=True)}")
        lines = native_sql.strip().splitlines()
        for line in lines[:6]:
            click.echo(f"         {click.style(line, fg='cyan')}")
        if len(lines) > 6:
            click.echo(
                f"         {click.style(f'… ({len(lines) - 6} more lines)', dim=True)}")
    elif source_ref:
        click.echo(f"{lbl}  {tbl}  →  {click.style(source_ref, fg='cyan')}")
        if filter_sql:
            click.echo(
                f"         {click.style('filter: ' + filter_sql, dim=True)}")

    click.echo()
