"""guard module — Metasploit-style module management commands."""

import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error, print_json


def _catalog(sdk):
    from praetorian_cli.catalog import CapabilityCatalog
    return CapabilityCatalog(sdk)


def _join(v):
    """Render a list-or-string catalog field as a comma-joined string."""
    if isinstance(v, (list, tuple)):
        return ", ".join(v)
    return v or ""


def _render_module_table(rows):
    """Plain-text table for module search/list output."""
    if not rows:
        click.echo("No modules match the query.")
        return

    click.echo(f'\n{"Name":<18} {"Category":<14} {"Installed":<12} {"Description"}')
    click.echo(f'{"─" * 18} {"─" * 14} {"─" * 12} {"─" * 48}')

    for r in rows:
        name = r["name"]
        cat = _join(r.get("category", ""))
        if len(cat) > 14:
            cat = cat[:13] + "…"
        desc = r.get("description", "") or ""
        if r.get("local_only"):
            desc = f"[local-only] {desc}"
        if len(desc) > 48:
            desc = desc[:47] + "…"
        if r.get("installed"):
            status = r.get("installed_version") or "yes"
        else:
            status = "—"
        click.echo(f"{name:<18} {cat:<14} {status:<12} {desc}")

    click.echo(f"\n{len(rows)} modules")


def _search_rows(sdk, query="", *, category="", surface="", target="", tag="", installed_only=False):
    """Shared catalog query: returns (rows, catalog) for search/list."""
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import list_installed

    cat = _catalog(sdk)
    reg = get_registry()
    results = cat.search(query, category=category, surface=surface, target=target, tag=tag)
    inst = list_installed()
    rows = []
    for c in results:
        ver = reg.get_version(c.name)
        is_inst = c.name in inst
        if installed_only and not is_inst:
            continue
        rows.append({
            "name": c.name, "title": c.title, "category": c.category,
            "surface": c.surface, "target": c.target, "description": c.description,
            "version": c.version, "executor": c.executor,
            "installed": is_inst, "local_only": reg.is_local_only(c.name),
            "installed_version": ver["version"] if ver else None,
        })
    return rows, cat


@chariot.group()
def module():
    """Manage security tool modules

    \b
    Metasploit-style module management: search, inspect, install, and
    update security tools from the Guard module registry.
    """
    pass


@module.command("search")
@cli_handler
@click.argument("query", default="")
@click.option("--category", "-c", default="", help="Filter by category")
@click.option("--surface", default="", help="Filter by surface")
@click.option("--target", default="", help="Filter by target type")
@click.option("--tag", default="", help="Filter by tag")
@click.option("--installed", "installed_only", is_flag=True, default=False, help="Only installed modules")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def search(sdk, query, category, surface, target, tag, installed_only, as_json):
    """Search available modules (fuzzy, ranked)

    \b
    Example usages:
        guard module search
        guard module search credential
        guard module search --category scanner
        guard module search llm --json
    """
    rows, cat = _search_rows(
        sdk, query, category=category, surface=surface, target=target,
        tag=tag, installed_only=installed_only,
    )

    if as_json:
        print_json(rows)
        return

    if cat.source and cat.source != 'live':
        click.echo(f"(catalog: {cat.source})", err=True)
    _render_module_table(rows)


@module.command("list")
@cli_handler
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def list_modules(sdk, as_json):
    """List all available modules (alias for search with no query)"""
    rows, cat = _search_rows(sdk)

    if as_json:
        print_json(rows)
        return

    if cat.source and cat.source != 'live':
        click.echo(f"(catalog: {cat.source})", err=True)
    _render_module_table(rows)


def _params_json(c):
    return [
        {"name": p.name, "type": p.type, "required": p.required,
         "default": p.default, "options": p.options, "description": p.description}
        for p in c.parameters
    ]


def _render_params(parameters):
    if not parameters:
        click.echo("  (no configurable parameters)")
        return
    click.echo(f'\n  {"Option":<18} {"Type":<10} {"Required":<10} {"Default":<12} {"Description"}')
    click.echo(f'  {"─" * 18} {"─" * 10} {"─" * 10} {"─" * 12} {"─" * 30}')
    for p in parameters:
        desc = p.description or ""
        if p.options:
            desc = f"{desc} [{', '.join(p.options)}]".strip()
        click.echo(
            f"  --{p.name:<16} {p.type:<10} "
            f"{'yes' if p.required else 'no':<10} {(p.default or '—'):<12} {desc}"
        )


@module.command("info")
@cli_handler
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def info(sdk, name, as_json):
    """Show full details for a module

    \b
    Example usages:
        guard module info brutus
        guard module info nuclei --json
    """
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import is_installed, get_binary_path

    cat = _catalog(sdk)
    c = cat.get(name)
    if c is None:
        error(f"Unknown module: {name}. Use 'guard module search' to find modules.")

    reg = get_registry()
    ver_info = reg.get_version(c.name)

    if as_json:
        out = {
            "name": c.name, "title": c.title, "category": c.category,
            "surface": c.surface, "target": c.target, "description": c.description,
            "version": c.version, "executor": c.executor, "runs_on": c.runs_on,
            "integration": c.integration, "parameters": _params_json(c),
        }
        out["installed"] = is_installed(c.name)
        out["local_only"] = reg.is_local_only(c.name)
        out["installed_version"] = ver_info["version"] if ver_info else None
        out["binary_path"] = get_binary_path(c.name)
        print_json(out)
        return

    installed_str = "not installed"
    if is_installed(c.name):
        path = get_binary_path(c.name)
        ver = ver_info["version"] if ver_info else "unknown"
        installed_str = f"{ver} ({path})"

    click.echo(f"\n  Name:        {c.name}")
    click.echo(f"  Title:       {c.title}")
    click.echo(f"  Category:    {_join(c.category)}")
    click.echo(f"  Surface:     {c.surface}")
    click.echo(f"  Target:      {_join(c.target)}")
    click.echo(f"  Version:     {c.version or '—'}")
    click.echo(f"  Executor:    {c.executor}")
    click.echo(f"  Installed:   {installed_str}")
    if reg.is_local_only(c.name):
        click.echo(f"  Local-only:  yes")
    click.echo(f"  Description: {c.description}")

    if c.parameters:
        click.echo(f"\n  Options:")
        _render_params(c.parameters)

    click.echo(f"\n  Usage:")
    click.echo(f"    guard run tool {c.name} <target>")
    click.echo()


@module.command("options")
@cli_handler
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def options(sdk, name, as_json):
    """Show configurable options for a module

    \b
    Example: guard module options brutus
    """
    cat = _catalog(sdk)
    c = cat.get(name)
    if c is None:
        error(f"Unknown module: {name}")

    if as_json:
        print_json(_params_json(c))
        return

    if not c.parameters:
        click.echo(f"{c.name}: no configurable options.")
        return

    _render_params(c.parameters)
    click.echo()


@module.command("install")
@cli_handler
@click.argument("name")
@click.option("--force", is_flag=True, default=False, help="Reinstall even if present")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def install(sdk, name, force, as_json):
    """Install a module binary from GitHub releases

    \b
    Example usages:
        guard module install brutus
        guard module install all
        guard module install brutus --force
    """
    from praetorian_cli.runners.local import install_tool, INSTALLABLE_TOOLS, is_installed

    if name == "all":
        from concurrent.futures import ThreadPoolExecutor, as_completed
        targets = [t for t in sorted(INSTALLABLE_TOOLS) if force or not is_installed(t)]

        def _do(t):
            return install_tool(t, force=force)

        if as_json:
            results = []
            with ThreadPoolExecutor(max_workers=4) as pool:
                futs = {pool.submit(_do, t): t for t in targets}
                for fut in as_completed(futs):
                    t = futs[fut]
                    try:
                        results.append({"name": t, "status": "installed", "path": fut.result()})
                    except Exception as e:
                        results.append({"name": t, "status": "error", "error": str(e)})
            print_json(results)
        else:
            from rich.progress import Progress, SpinnerColumn, TextColumn
            from rich.console import Console
            console = Console()
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
                tasks = {t: prog.add_task(f"{t}: queued", total=None) for t in targets}
                with ThreadPoolExecutor(max_workers=4) as pool:
                    futs = {pool.submit(_do, t): t for t in targets}
                    for fut in as_completed(futs):
                        t = futs[fut]
                        try:
                            fut.result()
                            prog.update(tasks[t], description=f"{t}: installed")
                        except Exception as e:
                            prog.update(tasks[t], description=f"{t}: FAILED {e}")
        return

    try:
        if not as_json:
            click.echo(f"Installing {name}...")
        path = install_tool(name, force=force)
        if as_json:
            print_json({"name": name, "status": "installed", "path": path})
        else:
            click.echo(f"Installed: {path}")
    except Exception as e:
        if as_json:
            print_json({"name": name, "status": "error", "error": str(e)})
        else:
            error(str(e))


@module.command("uninstall")
@cli_handler
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def uninstall(sdk, name, as_json):
    """Remove an installed module binary

    \b
    Example: guard module uninstall brutus
    """
    from praetorian_cli.runners.local import uninstall_tool
    removed = uninstall_tool(name.lower())
    if as_json:
        print_json({"name": name.lower(), "removed": removed})
    else:
        click.echo(f"{name}: {'removed' if removed else 'not installed'}")


@module.command("sync")
@cli_handler
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def sync(sdk, as_json):
    """Force-refresh the capability catalog from the backend."""
    cat = _catalog(sdk)
    ok = cat.refresh(force=True)
    n = len(cat.all())
    if as_json:
        print_json({"refreshed": ok, "count": n, "source": cat.source})
    else:
        click.echo(f"Catalog {'refreshed' if ok else 'unchanged'}: {n} capabilities ({cat.source}).")


@module.command("update")
@cli_handler
@click.argument("name", default="all")
@click.option("--registry", "update_registry", is_flag=True, default=False, help="Force refresh the registry")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def update(sdk, name, update_registry, as_json):
    """Update installed modules to latest release

    \b
    Example usages:
        guard module update
        guard module update brutus
        guard module update --registry
    """
    import subprocess
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import install_tool, is_installed, INSTALLABLE_TOOLS

    reg = get_registry()

    if update_registry:
        refreshed = reg.refresh(force=True)
        if not as_json:
            click.echo("Registry refreshed." if refreshed else "Registry refresh failed (using cached).")

    tools_to_update = sorted(INSTALLABLE_TOOLS) if name == "all" else [name]
    results = []

    for tool_name in tools_to_update:
        if not is_installed(tool_name):
            if name != "all":
                if as_json:
                    results.append({"name": tool_name, "status": "not_installed"})
                else:
                    click.echo(f"{tool_name}: not installed")
            continue

        mod = reg.get_module(tool_name)
        if not mod:
            continue

        current = reg.get_version(tool_name)
        current_ver = current["version"] if current else "unknown"

        try:
            ver_result = subprocess.run(
                ["gh", "release", "view", "--repo", mod["repo"], "--json", "tagName", "-q", ".tagName"],
                capture_output=True, text=True, timeout=15,
            )
            latest_ver = ver_result.stdout.strip() if ver_result.returncode == 0 else None
        except Exception:
            latest_ver = None

        if not latest_ver:
            if as_json:
                results.append({"name": tool_name, "status": "error", "error": "Could not check latest version"})
            else:
                click.echo(f"{tool_name}: could not check latest version")
            continue

        if latest_ver == current_ver:
            if as_json:
                results.append({"name": tool_name, "status": "up_to_date", "version": current_ver})
            elif name != "all":
                click.echo(f"{tool_name}: up to date ({current_ver})")
            continue

        try:
            if not as_json:
                click.echo(f"{tool_name}: {current_ver} -> {latest_ver}...", nl=False)
            path = install_tool(tool_name, force=True)
            if as_json:
                results.append({"name": tool_name, "status": "updated", "from": current_ver, "to": latest_ver, "path": path})
            else:
                click.echo(f" done")
        except Exception as e:
            if as_json:
                results.append({"name": tool_name, "status": "error", "error": str(e)})
            else:
                click.echo(f" FAILED: {e}", err=True)

    if as_json:
        print_json(results)


@module.command("installed")
@cli_handler
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def installed(sdk, as_json):
    """List installed modules with versions"""
    from praetorian_cli.runners.local import list_installed, INSTALLABLE_TOOLS
    from praetorian_cli.registry import get_registry

    reg = get_registry()
    inst = list_installed()
    versions = reg.get_all_versions()

    if as_json:
        result = []
        for tool_name in sorted(INSTALLABLE_TOOLS):
            entry = {"name": tool_name, "installed": tool_name in inst}
            if tool_name in inst:
                entry["path"] = inst[tool_name]
                ver = versions.get(tool_name)
                entry["version"] = ver["version"] if ver else None
            result.append(entry)
        print_json(result)
        return

    click.echo(f'\n{"Tool":<18} {"Status":<12} {"Version":<12} {"Path"}')
    click.echo(f'{"─" * 18} {"─" * 12} {"─" * 12} {"─" * 50}')
    for tool_name in sorted(INSTALLABLE_TOOLS):
        if tool_name in inst:
            ver = versions.get(tool_name, {}).get("version", "—")
            click.echo(f"{tool_name:<18} {'installed':<12} {ver:<12} {inst[tool_name]}")
        else:
            click.echo(f"{tool_name:<18} {'—':<12} {'—':<12}")
    click.echo()
