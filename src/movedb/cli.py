#!/usr/bin/env python3
"""
movedb — Movement Database CLI.

Batch-import biomechanics data into Rerun .rrd files, serve them via the
Rerun catalog server, and query across recordings.

Usage:
    movedb import c3d <directory> -o <output>
    movedb import osim <directory> -o <output>
    movedb import b3d <directory> -o <output>
    movedb catalog serve <path>
    movedb catalog query <path> <sql>
    movedb info
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click


def _find_importer(name: str) -> str | None:
    """Check if an importer is available on PATH."""
    return shutil.which(f"rerun-importer-{name}")


def _run(cmd: list[str]) -> None:
    """Run a CLI command, streaming output."""
    click.echo(f"  $ {' '.join(cmd)}", err=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise click.ClickException(f"Command failed with exit code {result.returncode}")


# ---------------------------------------------------------------------------
# movedb import
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """Movement Database — batch-import biomechanics data into Rerun."""


@cli.group()
def import_cmd() -> None:
    """Import biomechanics data into .rrd files."""


@import_cmd.command("c3d")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output-dir", default=".", show_default=True,
              help="Output directory for .rrd files")
@click.option("--min-body-measurements", default=3, show_default=True,
              help="Stop scanning body params after finding this many")
def import_c3d(directory: str, output_dir: str, min_body_measurements: int) -> None:
    """Batch-import C3D files grouped by subject."""
    importer = _find_importer("c3d")
    if not importer:
        raise click.ClickException(
            "rerun-importer-c3d not found. Install: pip install movedb-core[c3d]"
        )
    click.echo(f"Importing C3D files from {directory} → {output_dir}")
    _run([importer, "batch", directory, "-o", output_dir,
          f"--min-body-measurements={min_body_measurements}"])


@import_cmd.command("osim")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output-dir", default=".", show_default=True,
              help="Output directory for .rrd files")
@click.option("--animate", type=click.Path(exists=True),
              help="Path to IK .mot file for animation")
def import_osim(directory: str, output_dir: str, animate: str | None) -> None:
    """Batch-import OpenSim model and results files."""
    importer = _find_importer("osim")
    if not importer:
        raise click.ClickException(
            "rerun-importer-osim not found. Install: pip install movedb-core[osim]"
        )
    click.echo(f"Importing OpenSim files from {directory} → {output_dir}")
    cmd = [importer, "batch", directory, "-o", output_dir]
    if animate:
        cmd.extend(["--animate", animate])
    _run(cmd)


@import_cmd.command("b3d")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output-dir", default=".", show_default=True,
              help="Output directory for .rrd files")
def import_b3d(directory: str, output_dir: str) -> None:
    """Batch-import .b3d files grouped by subject."""
    importer = _find_importer("b3d")
    if not importer:
        raise click.ClickException(
            "rerun-importer-b3d not found. Install: pip install movedb-core[b3d]"
        )
    click.echo(f"Importing B3D files from {directory} → {output_dir}")
    _run([importer, "batch", directory, "-o", output_dir])


# ---------------------------------------------------------------------------
# movedb catalog
# ---------------------------------------------------------------------------

@cli.group()
def catalog() -> None:
    """Manage .rrd catalog for cross-recording queries."""


@catalog.command("serve")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--port", default=51234, show_default=True,
              help="Catalog server port")
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--dataset-name", default="biomechanics", show_default=True,
              help="Dataset name in the catalog")
def catalog_serve(path: str, port: int, host: str, dataset_name: str) -> None:
    """Start a Rerun catalog server serving .rrd files."""
    try:
        import rerun as rr
    except ImportError:
        raise click.ClickException(
            "rerun-sdk required. Install: pip install movedb-core[all]"
        )
    click.echo(f"Starting catalog server: {host}:{port}")
    click.echo(f"  Dataset '{dataset_name}' → {path}")
    server = rr.server.Server(
        host=host,
        port=port,
        datasets={dataset_name: path},
    )
    click.echo(f"  Server running. Connect via: rerun --connect rerun+http://{host}:{port}/proxy")
    click.echo("  Press Ctrl+C to stop.")
    try:
        server.wait()
    except KeyboardInterrupt:
        click.echo("\nShutting down.")


@catalog.command("query")
@click.argument("path", type=click.Path(exists=True))
@click.argument("sql")
@click.option("--format", "-f", "fmt", default="table",
              type=click.Choice(["table", "json", "csv"]),
              help="Output format")
def catalog_query(path: str, sql: str, fmt: str) -> None:
    """Query .rrd files with SQL using the DuckDB extension."""
    try:
        import duckdb
    except ImportError:
        raise click.ClickException(
            "duckdb required. Install: pip install duckdb"
        )
    path = os.path.abspath(path)
    conn = duckdb.connect()
    # Load the rrd extension
    conn.execute("INSTALL rrd FROM community;")
    conn.execute("LOAD rrd;")
    # Register the directory
    if os.path.isdir(path):
        conn.execute(f"CALL rrd_scan_directory('{path}', 'biomechanics');")
    else:
        conn.execute(f"CALL rrd_scan('{path}', 'single_file');")

    result = conn.execute(sql)
    if fmt == "json":
        rows = result.fetchall()
        cols = [d[0] for d in result.description]
        click.echo(json.dumps([dict(zip(cols, row)) for row in rows], indent=2))
    elif fmt == "csv":
        result = conn.execute(sql)
        rows = result.fetchall()
        cols = [d[0] for d in result.description]
        click.echo(",".join(cols))
        for row in rows:
            click.echo(",".join(str(v) for v in row))
    else:
        result = conn.execute(sql)
        rows = result.fetchall()
        cols = [d[0] for d in result.description]
        if not rows:
            click.echo("(no results)")
            return
        # Column widths
        widths = [len(c) for c in cols]
        for row in rows:
            for i, v in enumerate(row):
                widths[i] = max(widths[i], len(str(v)))
        # Header
        header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
        sep = "-+-".join("-" * widths[i] for i in range(len(cols)))
        click.echo(header)
        click.echo(sep)
        for row in rows:
            line = " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row))
            click.echo(line)
        click.echo(f"\n({len(rows)} rows)")


# ---------------------------------------------------------------------------
# movedb info
# ---------------------------------------------------------------------------

@cli.command()
def info() -> None:
    """Show available importers and their status."""
    click.echo("MoveDB — Movement Database")
    click.echo("")
    click.echo("Importers:")
    for name in ("c3d", "osim", "b3d"):
        found = _find_importer(name)
        status = f"✓ {shutil.which(name)}" if found else "✗ not installed"
        click.echo(f"  rerun-importer-{name}: {status}")
    click.echo("")
    click.echo("Dependencies:")
    for pkg in ("rerun-sdk", "duckdb"):
        try:
            __import__(pkg.replace("-", "_"))
            click.echo(f"  {pkg}: ✓ installed")
        except ImportError:
            click.echo(f"  {pkg}: ✗ not installed")
    click.echo("")
    click.echo("Install importers:")
    click.echo("  pip install movedb-core[c3d]   # C3D files")
    click.echo("  pip install movedb-core[osim]   # OpenSim files")
    click.echo("  pip install movedb-core[b3d]    # AddBiomechanics files (x86_64)")
    click.echo("  pip install movedb-core[all]    # everything")


if __name__ == "__main__":
    cli()
