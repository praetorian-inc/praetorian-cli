from rich.table import Table
from rich.box import MINIMAL
from ..utils import format_timestamp, format_job_status


def handle_job(menu, args):
    """Handle job command with subcommands: list, run, capabilities."""
    if not args:
        show_job_help(menu)
        return

    subcommand = args[0].lower()
    if subcommand == 'list':
        list_jobs(menu)
    elif subcommand == 'run':
        run_job(menu, args[1:])
    elif subcommand in ['capabilities', 'caps']:
        list_capabilities(menu, args[1:])
    else:
        menu.console.print(f"\n  Unknown job subcommand: {subcommand}")
        show_job_help(menu)


def show_job_help(menu):
    help_text = f"""
  Job Commands

  job list                  List recent jobs for selected agent
  job run <capability>      Run a capability on selected agent
                           [--config <json>] Optional configuration  
  job capabilities          List available capabilities (alias: caps)
                           [--details] Show full descriptions
  
  Examples:
    job list                 # List recent jobs
    job capabilities         # List capabilities with brief descriptions
    job caps --details       # List capabilities with full descriptions  
    job run windows-enum     # Run capability on selected agent
    job run smb-enum --config '{{"target":"192.168.1.1"}}'
"""
    menu.console.print(help_text)
    menu.pause()


def list_jobs(menu):
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    hostname = menu.selected_agent.hostname

    try:
        jobs, _ = menu.sdk.jobs.list(prefix_filter=hostname)

        if not jobs:
            menu.console.print(f"\n  No jobs found for {hostname}\n")
            menu.pause()
            return

        jobs.sort(key=lambda j: j.get('created', 0), reverse=True)

        colors = menu.colors
        jobs_table = Table(
            show_header=True,
            header_style=f"bold {colors['primary']}",
            border_style=colors['dim'],
            box=MINIMAL,
            show_lines=False,
            padding=(0, 2),
            pad_edge=False
        )

        jobs_table.add_column("JOB ID", style=f"bold {colors['accent']}", width=12, no_wrap=True)
        jobs_table.add_column("CAPABILITY", style="white", min_width=20, no_wrap=True)
        jobs_table.add_column("STATUS", width=10, justify="center", no_wrap=True)
        jobs_table.add_column("CREATED", style=f"{colors['dim']}", width=12, justify="right", no_wrap=True)

        menu.console.print()
        menu.console.print(f"  Recent Jobs for {hostname}")
        menu.console.print()

        for job in jobs[:10]:
            capability = job.get('capabilities', ['unknown'])[0] if job.get('capabilities') else 'unknown'
            status = job.get('status', 'unknown')
            job_id = job.get('key', '').split('#')[-1][:10]
            created = job.get('created', 0)

            created_str = format_timestamp(created)
            status_display = format_job_status(status, colors)

            jobs_table.add_row(job_id, capability, status_display, created_str)

        menu.console.print(jobs_table)
        menu.console.print()
        menu.pause()

    except Exception as e:
        menu.console.print(f"[red]Error listing jobs: {e}[/red]")
        menu.pause()


def run_job(menu, args):
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    if not args:
        menu.console.print("\n[red]  Usage: job run <capability> [--config <json>][/red]")
        menu.console.print("  Use 'job capabilities' to see available capabilities\n")
        menu.pause()
        return

    capability = args[0]
    config = None

    i = 1
    while i < len(args):
        if args[i] == '--config' and i + 1 < len(args):
            config = args[i + 1]
            i += 2
        else:
            i += 1

    try:
        result = menu.sdk.aegis.run_job(
            agent=menu.selected_agent,
            capabilities=[capability],
            config=config
        )

        if result.get('success'):
            menu.console.print(f"\n[green]✓ Job queued successfully[/green]")
            menu.console.print(f"  Capability: {capability}")
            if 'job_id' in result:
                menu.console.print(f"  Job ID: {result['job_id']}")
            if 'status' in result:
                menu.console.print(f"  Status: {result['status']}")
        else:
            error_msg = result.get('message', 'Unknown error')
            menu.console.print(f"\n[red]Error running job: {error_msg}[/red]")

        menu.console.print()
        menu.pause()
    except Exception as e:
        menu.console.print(f"[red]Job execution error: {e}[/red]")
        menu.pause()


def list_capabilities(menu, args):
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    show_details = '--details' in args or '-d' in args

    try:
        result = menu.sdk.aegis.run_job(
            agent=menu.selected_agent,
            capabilities=None,
            config=None
        )

        colors = menu.colors
        if 'capabilities' in result:
            capabilities_table = Table(
                show_header=True,
                header_style=f"bold {colors['primary']}",
                border_style=colors['dim'],
                box=MINIMAL,
                show_lines=False,
                padding=(0, 2),
                pad_edge=False
            )

            capabilities_table.add_column("CAPABILITY", style=f"bold {colors['success']}", min_width=25, no_wrap=True)
            capabilities_table.add_column("DESCRIPTION", style="white", no_wrap=False)

            for cap in result['capabilities']:
                name = cap.get('name', 'unknown')
                full_desc = cap.get('description', '') or 'No description available'
                if show_details:
                    desc = full_desc
                else:
                    desc = full_desc[:80] + '...' if len(full_desc) > 80 else full_desc
                capabilities_table.add_row(name, desc)

            menu.console.print()
            title = "  Available Capabilities"
            title += " (Detailed)" if show_details else " (use --details for full descriptions)"
            menu.console.print(title)
            menu.console.print()
            menu.console.print(capabilities_table)
        else:
            menu.console.print(f"[yellow]  No capabilities available for this agent[/yellow]")

        menu.console.print()
        menu.pause()
    except Exception as e:
        menu.console.print(f"[red]Error listing capabilities: {e}[/red]")
        menu.pause()


def complete(menu, text, tokens):
    sub = ['list', 'run', 'capabilities', 'caps']
    if len(tokens) <= 2:
        return [s for s in sub if s.startswith(text)]
    # Could extend to capability names later
    return []
