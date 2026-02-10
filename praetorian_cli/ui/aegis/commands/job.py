import json
from rich.table import Table
from rich.box import MINIMAL
from rich.prompt import Prompt, Confirm
from ..utils import format_timestamp, format_job_status
from ..constants import DEFAULT_COLORS
from .job_helpers import (
    interactive_capability_picker as _interactive_capability_picker,
    select_domain as _select_domain,
    select_credentials as _select_credentials,
    configure_parameters as _configure_parameters,
    capability_needs_credentials as _capability_needs_credentials,
    resolve_addomain_target_key,
)


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
  job run [capability]      Run a capability on selected agent (interactive picker)
  job capabilities          List available capabilities (alias: caps)
                           [--details] Show full descriptions
  
  Examples:
    job list                 # List recent jobs
    job capabilities         # List capabilities with brief descriptions
    job caps --details       # List capabilities with full descriptions  
    job run                  # Interactive capability picker
    job run windows-enum     # Run specific capability with confirmation
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

        colors = getattr(menu, 'colors', DEFAULT_COLORS)
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
        menu.console.print(f"[{colors['error']}]Error listing jobs: {e}[/{colors['error']}]")
        menu.pause()


def run_job(menu, args):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    hostname = menu.selected_agent.hostname or 'Unknown'

    # Use interactive capability picker if no capability provided, otherwise validate the provided one
    suggested_capability = args[0] if args else None
    capability = _interactive_capability_picker(menu, suggested_capability)
    if not capability:
        return  # User cancelled

    # Validate capability using SDK
    capability_info = menu.sdk.aegis.validate_capability(capability)
    if not capability_info:
        menu.console.print(f"  [{colors['error']}]Invalid capability: '{capability}'[/{colors['error']}]")
        menu.console.print("  Use 'job capabilities' to see available options")
        menu.pause()
        return

    target_type = capability_info.get('target', 'asset').lower()

    # Create appropriate target key
    if target_type == 'addomain':
        # For AD capabilities, use interactive domain selection
        domain = _select_domain(menu)
        if not domain:
            return  # User cancelled

        # Query assets to get the actual domain asset key (with SID)
        target_key = resolve_addomain_target_key(menu, domain)
        if not target_key:
            menu.console.print(f"  [{colors['error']}]No asset found for domain '{domain}'.[/{colors['error']}]")
            menu.console.print(f"  [{colors['dim']}]The domain must exist as an asset before running jobs against it.[/{colors['dim']}]")
            menu.console.print(f"  [{colors['dim']}]Add it first with: praetorian chariot add asset --dns {domain} --type addomain[/{colors['dim']}]")
            menu.pause()
            return

        target_display = f"domain {domain}"
    else:
        target_key = f"#asset#{hostname}#{hostname}"
        target_display = f"asset {hostname}"
    
    # Handle credentials for capabilities that need them
    credentials = []
    credential_display_name = None
    if _capability_needs_credentials(capability_info):
        if Confirm.ask("  This capability may require credentials. Add them?"):
            credential_key, credential_display_name = _select_credentials(menu)
            if credential_key:
                # Parse credential key to extract UUID
                # Format: #credential#<category>#<type>#<credential_id>
                parts = credential_key.split('#')
                if len(parts) >= 5:
                    credential_id = parts[-1]  # Last part is the UUID
                    # Pass UUID to jobs.add() - API will retrieve values server-side
                    credentials.append(credential_id)

    # Create job configuration using SDK
    config = menu.sdk.aegis.create_job_config(menu.selected_agent, None)

    # Handle large artifact storage - always offer the option
    # Default to True if capability metadata says it supports it, or if capability name suggests large output
    capability_suggests_large = capability_info.get('largeArtifact', False) or any(
        keyword in capability.lower() for keyword in ['snaffler', 'bloodhound', 'sharphound', 'umber', 'dump', 'collect', 'extract']
    )
    if Confirm.ask("  Enable large artifact storage? (Results will be uploaded to S3)", default=capability_suggests_large):
        config['largeArtifact'] = 'true'

    # Configure optional parameters if capability has them
    # Skip credential params if credentials are attached
    has_credential = len(credentials) > 0
    custom_params = _configure_parameters(menu, capability_info, has_credential=has_credential)
    if custom_params:
        config.update(custom_params)

    # Confirm job execution
    if not Confirm.ask(f"\n  Run '{capability}' on {target_display}?"):
        menu.console.print("  Cancelled\n")
        menu.pause()
        return

    try:
        config_json = json.dumps(config)

        # Add job using SDK with credential UUIDs (API retrieves values server-side)
        jobs = menu.sdk.jobs.add(target_key, [capability], config_json, credentials=credentials)
        
        if jobs:
            job = jobs[0] if isinstance(jobs, list) else jobs
            job_key = job.get('key', '')
            status = job.get('status', 'unknown')
            job_id = job_key.split('#')[-1] if job_key else 'unknown'

            menu.console.print(f"\n[{colors['success']}]✓ Job queued successfully[/{colors['success']}]")
            menu.console.print(f"  Job ID: {job_id}")
            menu.console.print(f"  Job Key: {job_key}")
            menu.console.print(f"  Capability: {capability}")
            menu.console.print(f"  Target: {target_display}")
            menu.console.print(f"  Status: {status}")
            if credentials and credential_display_name:
                menu.console.print(f"  Credential: {credential_display_name}")
        else:
            menu.console.print(f"\n[{colors['error']}]Error: No job returned from API[/{colors['error']}]")
            
    except Exception as e:
        menu.console.print(f"\n[{colors['error']}]Job execution error: {e}[/{colors['error']}]")
    
    menu.console.print()
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

        colors = getattr(menu, 'colors', DEFAULT_COLORS)
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
            menu.console.print(f"[{colors['warning']}]  No capabilities available for this agent[/{colors['warning']}]")

        menu.console.print()
        menu.pause()
    except Exception as e:
        menu.console.print(f"[{colors['error']}]Error listing capabilities: {e}[/{colors['error']}]")
        menu.pause()


def complete(menu, text, tokens):
    sub = ['list', 'run', 'capabilities', 'caps']
    if len(tokens) <= 2:
        return [s for s in sub if s.startswith(text)]
    # Could extend to capability names later
    return []
