from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from .config import AppConfig, load_config, save_config, redact_key, config_path, default_model_for_provider
from .generator import generate_repos, validate_repos
from .fs import write_text_file

app = typer.Typer(add_completion=False, no_args_is_help=False)
console = Console()


def _read_multiline_input() -> str:
    """Read multiline input.

    If stdin is piped, read all.
    Else prompt user to type multiple lines, end with EOF.
    Windows: Ctrl+Z then Enter
    macOS/Linux: Ctrl+D
    """
    if not sys.stdin.isatty():
        return sys.stdin.read()

    console.print("[bold]content:[/bold] (输入多行，结束请 EOF：Windows Ctrl+Z 回车；mac/linux Ctrl+D)")
    lines: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _prompt_secret(label: str, current: str) -> str:
    console.print(f"current {label}: {redact_key(current) or '(empty)'}")
    v = typer.prompt(
        f"{label} (leave blank to keep, '-' to clear)",
        default="",
        hide_input=True,
        show_default=False,
    ).strip()
    if v == "":
        return current
    if v == "-":
        return ""
    return v


@app.command("config")
def config_cmd():
    """Configure mkrepo globally (provider, model, base_url, api_key)."""
    cfg = load_config()
    console.print(Panel.fit(f"Config file: {config_path()}", title="mkrepo"))

    provider = typer.prompt(
        "provider [openrouter/openai/anthropic/google/openai_compat]",
        default=cfg.provider,
    ).strip().lower()
    if provider not in ("openrouter", "openai", "anthropic", "google", "openai_compat"):
        raise typer.BadParameter("provider must be one of: openrouter/openai/anthropic/google/openai_compat")

    # Base URLs
    base_url = cfg.base_url
    anthropic_base_url = cfg.anthropic_base_url
    google_base_url = cfg.google_base_url

    if provider in ("openrouter", "openai", "openai_compat"):
        default_base_url = base_url
        if provider == "openai" and (not default_base_url or "openrouter.ai" in default_base_url):
            default_base_url = "https://api.openai.com/v1"
        if provider == "openrouter" and (not default_base_url or "api.openai.com" in default_base_url):
            default_base_url = "https://openrouter.ai/api/v1"
        base_url = typer.prompt("base_url (OpenAI-compatible)", default=default_base_url).strip()
    elif provider == "anthropic":
        anthropic_base_url = typer.prompt("anthropic_base_url", default=anthropic_base_url).strip()
    elif provider == "google":
        google_base_url = typer.prompt("google_base_url", default=google_base_url).strip()

    # Model (default should follow provider when switching)
    model_default = cfg.model
    if provider != cfg.provider:
        # When user changes provider, suggest that provider's default model instead
        # of carrying over a potentially incompatible previous model string.
        model_default = default_model_for_provider(provider)  # type: ignore[arg-type]
    model = typer.prompt("model", default=model_default).strip()

    # Keys
    api_key = cfg.api_key
    openai_api_key = cfg.openai_api_key
    anthropic_api_key = cfg.anthropic_api_key
    google_api_key = cfg.google_api_key

    if provider in ("openrouter", "openai_compat"):
        api_key = _prompt_secret("api_key", api_key)
    elif provider == "openai":
        openai_api_key = _prompt_secret("openai_api_key", openai_api_key)
    elif provider == "anthropic":
        anthropic_api_key = _prompt_secret("anthropic_api_key", anthropic_api_key)
    elif provider == "google":
        google_api_key = _prompt_secret("google_api_key", google_api_key)

    http_referer = typer.prompt("http_referer (optional)", default=cfg.http_referer).strip()
    x_title = typer.prompt("x_title (optional)", default=cfg.x_title).strip()

    new_cfg = AppConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        google_api_key=google_api_key,
        anthropic_base_url=anthropic_base_url,
        google_base_url=google_base_url,
        http_referer=http_referer,
        x_title=x_title,
    )
    save_config(new_cfg)

    # Print summary without leaking keys
    key_show = {
        "openrouter": redact_key(new_cfg.api_key),
        "openai_compat": redact_key(new_cfg.api_key),
        "openai": redact_key(new_cfg.openai_api_key),
        "anthropic": redact_key(new_cfg.anthropic_api_key),
        "google": redact_key(new_cfg.google_api_key),
    }[new_cfg.provider]

    console.print(
        Panel.fit(
            "Saved.\n"
            f"provider: {new_cfg.provider}\n"
            f"model: {new_cfg.model}\n"
            f"base_url: {new_cfg.base_url}\n"
            f"api_key: {key_show or '(empty)'}",
            title="mkrepo",
        )
    )


def _build_tree(repo: Dict[str, Any], *, root_label: str | None = None) -> Tree:
    name = str(repo.get("name", "repo"))
    out_dir = str(repo.get("dir", name))
    root = root_label or f"[bold]{name}[/bold]  →  {out_dir}"

    tree = Tree(root)
    nodes: Dict[str, Any] = {"": tree}

    files = repo.get("files", []) or []
    paths = []
    for f in files:
        p = str((f or {}).get("path", "")).strip()
        if p:
            paths.append(p.replace("\\\\", "/"))

    for path in sorted(set(paths)):
        parts = [p for p in path.split("/") if p]
        cur = ""
        for i, part in enumerate(parts):
            is_file = i == len(parts) - 1
            nxt = f"{cur}/{part}" if cur else part

            if is_file:
                nodes[cur].add(part)
            else:
                if nxt not in nodes:
                    nodes[nxt] = nodes[cur].add(part)
                cur = nxt

    return tree


def _review_and_edit_plan(cfg: AppConfig, repos: List[Dict[str, Any]], content: str) -> List[Dict[str, Any]]:
    """Preview/edit plan before writing files."""
    while True:
        console.print(
            Panel.fit(
                f"provider: {cfg.provider}\nmodel: {cfg.model}",
                title="mkrepo plan preview",
            )
        )

        for i, repo in enumerate(repos, start=1):
            tree = _build_tree(repo)
            console.print(Panel(tree, title=f"Repo {i}", expand=False))

        action = typer.prompt(
            "plan action [a=accept, e=edit json, r=regenerate, q=quit]",
            default="a",
        ).strip().lower()

        if action in ("a", "y", "yes"):
            return repos
        if action in ("q", "quit", "exit"):
            raise typer.Exit(0)

        if action in ("e", "edit"):
            text = json.dumps({"repos": repos}, ensure_ascii=False, indent=2)
            edited = typer.edit(text, extension=".json")
            if edited is None:
                # closed without saving
                continue
            try:
                data = json.loads(edited)
                new_repos = data.get("repos", [])
                validate_repos(new_repos)
                repos = new_repos
            except Exception as e:
                console.print(f"[red]Invalid JSON/plan:[/red] {e}")
            continue

        if action in ("r", "regen", "regenerate"):
            console.print(Panel.fit("Regenerating plan...", title="mkrepo"))
            result = generate_repos(
                provider=cfg.provider,
                model=cfg.model,
                content=content,
                base_url=cfg.base_url,
                api_key=cfg.api_key,
                openai_api_key=cfg.openai_api_key,
                anthropic_api_key=cfg.anthropic_api_key,
                google_api_key=cfg.google_api_key,
                anthropic_base_url=cfg.anthropic_base_url,
                google_base_url=cfg.google_base_url,
                http_referer=cfg.http_referer,
                x_title=cfg.x_title,
            )
            repos = result.repos
            continue

        console.print("[yellow]Unknown action. Use a/e/r/q.[/yellow]")


def _run_default(dry_run: bool) -> None:
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
            provider=cfg.provider,
            model=cfg.model,
            content=content,
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            openai_api_key=cfg.openai_api_key,
            anthropic_api_key=cfg.anthropic_api_key,
            google_api_key=cfg.google_api_key,
            anthropic_base_url=cfg.anthropic_base_url,
            google_base_url=cfg.google_base_url,
            http_referer=cfg.http_referer,
            x_title=cfg.x_title,
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Tip: run `mkrepo -c` or `mkrepo config` to configure provider/model/keys.")
        raise typer.Exit(1)

    repos = result.repos
    console.print(f"[bold]analysis:[/bold] repo num: ({len(repos)})")

    # 3) preview + edit
    repos = _review_and_edit_plan(cfg, repos, content)

    # 4) interactive per repo
    for i, repo in enumerate(repos, start=1):
        default_name = str(repo.get("name", f"repo-{i}"))
        planned_dir = str(repo.get("dir", "") or "").strip()

        console.print(Panel.fit(f"Repo {i}", title="mkrepo"))

        name = typer.prompt(f"repo {i} name", default=default_name).strip()

        # If the plan used the default dir (= repo name) or left it empty,
        # follow the user's (possibly edited) repo name.
        auto_dir = (not planned_dir) or (planned_dir == default_name)
        default_dir = name if auto_dir else planned_dir

        out_dir = typer.prompt(f"repo {i} dir", default=default_dir).strip()
        repo["name"] = name
        repo["dir"] = out_dir

        files = repo.get("files", [])

        # show final tree for this repo
        console.print(Panel(_build_tree(repo), title=f"Repo {i} final plan", expand=False))

        if dry_run:
            console.print("[yellow]dry-run: skip writing files[/yellow]")
            continue

        if not typer.confirm(f"Write files for repo {i} into '{out_dir}'?", default=True):
            console.print("[yellow]skip[/yellow]")
            continue

        base = Path(out_dir)
        base.mkdir(parents=True, exist_ok=True)

        wrote = 0
        for f in files:
            path = str((f or {}).get("path", "")).strip()
            file_content = str((f or {}).get("content", ""))
            if not path:
                continue
            try:
                write_text_file(base, path, file_content)
                wrote += 1
            except Exception as e:
                console.print(f"[red]Failed:[/red] {path} -> {e}")

        console.print(f"[green]repo {i} done:[/green] wrote {wrote} files into {base.resolve()}")

    console.print(Panel.fit("done", title="mkrepo"))


@app.callback(invoke_without_command=True)
def entry(
    ctx: typer.Context,
    config_only: bool = typer.Option(False, "-c", "--config", help="Run config wizard"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview plan only, do not write files"),
):
    """Default entrypoint: `mkrepo` runs generation flow.

    Subcommands still work: `mkrepo config`.
    """
    # If user invoked a subcommand (e.g. mkrepo config), do nothing here
    if ctx.invoked_subcommand is not None:
        return

    if config_only:
        config_cmd()
        raise typer.Exit(0)

    _run_default(dry_run=dry_run)
