from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .config import AppConfig, load_config, save_config, redact_key, config_path
from .generator import generate_repos
from .fs import write_text_file

app = typer.Typer(add_completion=False)
console = Console()


def _read_multiline_input() -> str:
    """
    If stdin piped, read all. Else prompt user to type multiple lines, end with EOF (Ctrl+Z on Windows, Ctrl+D on Unix).
    """
    if not sys.stdin.isatty():
        return sys.stdin.read()

    console.print("[bold]content:[/bold] (输入多行，结束请 EOF：Windows Ctrl+Z 回车；mac/linux Ctrl+D)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        lines.append(line)
    return "\n".join(lines).strip()


@app.command()
def config():
    """
    Configure mkrepo globally (model, base_url, api_key).
    """
    cfg = load_config()
    console.print(Panel.fit(f"Config file: {config_path()}", title="mkrepo"))

    base_url = typer.prompt("base_url", default=cfg.base_url)
    model = typer.prompt("model", default=cfg.model)
    api_key = typer.prompt("api_key", default=cfg.api_key, hide_input=True)

    http_referer = typer.prompt("http_referer (optional)", default=cfg.http_referer)
    x_title = typer.prompt("x_title (optional)", default=cfg.x_title)

    new_cfg = AppConfig(
        base_url=base_url.strip(),
        model=model.strip(),
        api_key=api_key.strip(),
        http_referer=http_referer.strip(),
        x_title=x_title.strip(),
    )
    save_config(new_cfg)
    console.print(
        Panel.fit(
            f"Saved.\nbase_url: {new_cfg.base_url}\nmodel: {new_cfg.model}\napi_key: {redact_key(new_cfg.api_key)}",
            title="mkrepo",
        )
    )


@app.command()
def main(
        config_only: bool = typer.Option(False, "-c", "--config", help="Run config wizard"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Print plan only, do not write files"),
):
    """
    Generate a repo (multi-file project) from natural language.
    """
    if config_only:
        config()
        raise typer.Exit(0)

    cfg = load_config()

    # 1) input
    content = _read_multiline_input()
    if not content:
        console.print("[red]No content provided.[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit("Calling LLM to generate repo plan...", title="mkrepo"))

    # 2) generate
    try:
        result = generate_repos(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            model=cfg.model,
            content=content,
            http_referer=cfg.http_referer,
            x_title=cfg.x_title,
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Tip: run `mkrepo -c` to configure api_key/model/base_url.")
        raise typer.Exit(1)

    repos = result.repos
    console.print(f"[bold]analysis:[/bold] repo num: ({len(repos)})")

    # 3) interactive per repo
    for i, repo in enumerate(repos, start=1):
        default_name = str(repo.get("name", f"repo-{i}"))
        default_dir = str(repo.get("dir", default_name))

        console.print(Panel.fit(f"Repo {i}", title="mkrepo"))

        name = typer.prompt(f"repo {i} name", default=default_name)
        out_dir = typer.prompt(f"repo {i} dir", default=default_dir)

        files = repo.get("files", [])
        console.print("[bold]making files:[/bold]")
        for f in files:
            path = str(f.get("path", "")).strip()
            if not path:
                continue
            console.print(f"  > {path}")

        if dry_run:
            console.print("[yellow]dry-run: skip writing files[/yellow]")
            continue

        base = Path(out_dir)
        base.mkdir(parents=True, exist_ok=True)

        wrote = 0
        for f in files:
            path = str(f.get("path", "")).strip()
            content = str(f.get("content", ""))
            if not path:
                continue
            try:
                write_text_file(base, path, content)
                wrote += 1
            except Exception as e:
                console.print(f"[red]Failed:[/red] {path} -> {e}")

        console.print(f"[green]repo {i} done:[/green] wrote {wrote} files into {base.resolve()}")

    console.print(Panel.fit("done", title="mkrepo"))
