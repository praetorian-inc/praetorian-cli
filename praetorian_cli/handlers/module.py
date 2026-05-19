"""guard module — Metasploit-style module management commands."""

import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error, print_json


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
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def search(sdk, query, category, as_json):
    """Search available modules by name, category, or keyword

    \b
    Example usages:
        guard module search
        guard module search credential
        guard module search --category scanner
        guard module search llm --json
    """
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import list_installed

    reg = get_registry()
    results = reg.search_modules(query, category=category)
    installed = list_installed()

    if as_json:
        for r in results:
            r["installed"] = r["name"] in installed
            ver = reg.get_version(r["name"])
            r["version"] = ver["version"] if ver else None
        print_json(results)
        return

    if not results:
        click.echo("No modules match the query.")
        return

    click.echo(f'\n{"Name":<18} {"Category":<14} {"Installed":<12} {"Description"}')
    click.echo(f'{"─" * 18} {"─" * 14} {"─" * 12} {"─" * 48}')

    for r in results:
        name = r["name"]
        cat = r.get("category", "")
        desc = r.get("description", "")
        if len(desc) > 48:
            desc = desc[:47] + "…"
        ver = reg.get_version(name)
        if name in installed:
            status = ver["version"] if ver else "yes"
        else:
            status = "—"
        click.echo(f"{name:<18} {cat:<14} {status:<12} {desc}")

    click.echo(f"\n{len(results)} modules")


@module.command("list")
@cli_handler
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
def list_modules(sdk, as_json):
    """List all available modules (alias for search with no query)"""
    from praetorian_cli.registry import get_registry
    from praetorian_cli.runners.local import list_installed

    reg = get_registry()
    results = reg.search_modules()
    installed = list_installed()

    if as_json:
        for r in results:
            r["installed"] = r["name"] in installed
            ver = reg.get_version(r["name"])
            r["version"] = ver["version"] if ver else None
        print_json(results)
        return

    click.echo(f'\n{"Name":<18} {"Category":<14} {"Installed":<12} {"Description"}')
    click.echo(f'{"─" * 18} {"─" * 14} {"─" * 12} {"─" * 48}')
    for r in results:
        name = r["name"]
        cat = r.get("category", "")
        desc = r.get("description", "")
        if len(desc) > 48:
            desc = desc[:47] + "…"
        ver = reg.get_version(name)
        if name in installed:
            status = ver["version"] if ver else "yes"
        else:
            status = "—"
        click.echo(f"{name:<18} {cat:<14} {status:<12} {desc}")
    click.echo(f"\n{len(results)} modules")


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

    reg = get_registry()
    mod = reg.get_module(name)
    if not mod:
        error(f"Unknown module: {name}. Use 'guard module search' to find modules.")

    ver_info = reg.get_version(name.lower())

    if as_json:
        out = {"name": name.lower(), **mod}
        out["installed"] = is_installed(name.lower())
        out["version"] = ver_info["version"] if ver_info else None
        out["binary_path"] = get_binary_path(name.lower())
        print_json(out)
        return

    installed_str = "not installed"
    if is_installed(name.lower()):
        path = get_binary_path(name.lower())
        ver = ver_info["version"] if ver_info else "unknown"
        installed_str = f"{ver} ({path})"

    click.echo(f"\n  Name:        {name.lower()}")
    click.echo(f"  Category:    {mod.get('category', '')}")
    click.echo(f"  Author:      {mod.get('author', '')}")
    click.echo(f"  Repository:  {mod.get('repo', '')}")
    click.echo(f"  Installed:   {installed_str}")
    click.echo(f"  Target:      {mod.get('target_type', 'asset')}")
    click.echo(f"  Description: {mod.get('description', '')}")

    tags = mod.get("tags", [])
    if tags:
        click.echo(f"  Tags:        {', '.join(tags)}")

    options = mod.get("options", {})
    if options:
        click.echo(f"\n  Options:")
        for opt_name, opt_info in options.items():
            opt_type = opt_info.get("type", "string")
            opt_desc = opt_info.get("description", "")
            click.echo(f"    --{opt_name:<14} {opt_type:<8} {opt_desc}")

    click.echo(f"\n  Usage:")
    click.echo(f"    guard run tool {name.lower()} <target>")
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
    from praetorian_cli.registry import get_registry

    reg = get_registry()
    mod = reg.get_module(name)
    if not mod:
        error(f"Unknown module: {name}")

    opts = mod.get("options", {})

    if as_json:
        print_json(opts)
        return

    if not opts:
        click.echo(f"{name}: no configurable options.")
        return

    click.echo(f'\n{"Option":<18} {"Type":<10} {"Required":<10} {"Description"}')
    click.echo(f'{"─" * 18} {"─" * 10} {"─" * 10} {"─" * 40}')
    for opt_name, opt_info in opts.items():
        click.echo(
            f"--{opt_name:<16} {opt_info.get('type', 'string'):<10} "
            f"{'yes' if opt_info.get('required') else 'no':<10} "
            f"{opt_info.get('description', '')}"
        )
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
        results = []
        for tool_name in sorted(INSTALLABLE_TOOLS):
            try:
                if not force and is_installed(tool_name):
                    if as_json:
                        results.append({"name": tool_name, "status": "already_installed"})
                    else:
                        click.echo(f"{tool_name}: already installed")
                else:
                    if not as_json:
                        click.echo(f"{tool_name}: installing...", nl=False)
                    path = install_tool(tool_name, force=force)
                    if as_json:
                        results.append({"name": tool_name, "status": "installed", "path": path})
                    else:
                        click.echo(f" {path}")
            except Exception as e:
                if as_json:
                    results.append({"name": tool_name, "status": "error", "error": str(e)})
                else:
                    click.echo(f" FAILED: {e}", err=True)
        if as_json:
            print_json(results)
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
    import os
    from praetorian_cli.runners.local import get_binary_path, INSTALL_DIR
    from praetorian_cli.registry import get_registry

    path = get_binary_path(name)
    if not path:
        if as_json:
            print_json({"name": name, "status": "not_installed"})
        else:
            error(f"{name} is not installed.")
        return

    if not path.startswith(INSTALL_DIR):
        if as_json:
            print_json({"name": name, "status": "error", "error": "System binary, not managed by guard"})
        else:
            error(f"{name} at {path} is a system binary, not managed by guard module install.")
        return

    os.remove(path)
    get_registry().remove_version(name)

    if as_json:
        print_json({"name": name, "status": "uninstalled"})
    else:
        click.echo(f"Uninstalled: {name}")


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
