import json
from rich.table import Table
from rich.box import MINIMAL
from rich.prompt import Prompt, Confirm
from ..utils import format_timestamp, format_job_status
from ..constants import DEFAULT_COLORS


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
        menu.console.print(f"[red]Error listing jobs: {e}[/red]")
        menu.pause()


def run_job(menu, args):
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
        colors = getattr(menu, 'colors', DEFAULT_COLORS)
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
        target_key = f"#addomain#{domain}#{domain}"
        target_display = f"domain {domain}"
    else:
        target_key = f"#asset#{hostname}#{hostname}"
        target_display = f"asset {hostname}"
    
    # Handle credentials for capabilities that need them
    credentials = None
    if any(keyword in capability.lower() for keyword in ['ad-', 'smb-', 'domain-', 'ldap', 'winrm']):
        if Confirm.ask("  This capability may require credentials. Add them?"):
            username = Prompt.ask("  Username")
            password = Prompt.ask("  Password", password=True)
            credentials = {"Username": username, "Password": password}
    
    # Create job configuration using SDK
    config = menu.sdk.aegis.create_job_config(menu.selected_agent, credentials)
    
    # Confirm job execution
    if not Confirm.ask(f"\n  Run '{capability}' on {target_display}?"):
        menu.console.print("  Cancelled\n")
        menu.pause()
        return

    try:
        config_json = json.dumps(config)
        
        # Add job using SDK
        jobs = menu.sdk.jobs.add(target_key, [capability], config_json)
        
        if jobs:
            job = jobs[0] if isinstance(jobs, list) else jobs
            job_key = job.get('key', '')
            status = job.get('status', 'unknown')
            job_id = job_key.split('#')[-1][:12] if job_key else 'unknown'
            
            menu.console.print(f"\n[green]✓ Job {job_id} queued successfully[/green]")
            menu.console.print(f"  Capability: {capability}")
            menu.console.print(f"  Target: {target_display}")
            menu.console.print(f"  Status: {status}")
        else:
            menu.console.print("\n[red]Error: No job returned from API[/red]")
            
    except Exception as e:
        menu.console.print(f"\n[red]Job execution error: {e}[/red]")
    
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
            menu.console.print(f"[yellow]  No capabilities available for this agent[/yellow]")

        menu.console.print()
        menu.pause()
    except Exception as e:
        menu.console.print(f"[red]Error listing capabilities: {e}[/red]")
        menu.pause()


def _interactive_capability_picker(menu, suggested=None):
    """Interactive capability picker with numbered options"""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    
    if suggested:
        # Validate the suggested capability first
        capability_info = menu.sdk.aegis.validate_capability(suggested)
        if capability_info:
            # Show the suggested capability and ask for confirmation
            desc = (capability_info.get('description', '') or '')[:60]
            menu.console.print(f"\n  Suggested capability:")
            menu.console.print(f"    {suggested}")
            menu.console.print(f"    [{colors['dim']}]{desc}[/{colors['dim']}]")
            
            if Confirm.ask("  Use this capability?", default=True):
                return suggested
            # If they decline, continue to show the full picker below
    
    try:
        # Determine agent OS for filtering
        agent_os = _detect_agent_os(menu)
        
        # Get capabilities filtered by OS
        caps = menu.sdk.aegis.get_capabilities(surface_filter='internal', agent_os=agent_os)
        
        if not caps:
            # Fallback to all capabilities
            caps = menu.sdk.aegis.get_capabilities(surface_filter='internal')
        
        if not caps:
            menu.console.print("  No capabilities available.")
            return None
        
        if agent_os:
            menu.console.print(f"  [{colors['dim']}]Showing {agent_os.title()} capabilities[/{colors['dim']}]")
        
        # Sort and display with numbers
        caps.sort(key=lambda x: x.get('name', ''))
        
        menu.console.print(f"\n  Select capability:")
        for i, cap in enumerate(caps[:20], 1):  # Limit to 20 for usability
            name = cap.get('name', 'unknown')
            desc = (cap.get('description', '') or '')[:40]
            menu.console.print(f"    {i:2d}. {name:<25} {desc}")
        
        if len(caps) > 20:
            menu.console.print(f"    [{colors['dim']}]... and {len(caps) - 20} more capabilities[/{colors['dim']}]")
        
        menu.console.print(f"     0. Enter capability name manually")
        
        while True:
            try:
                choice = Prompt.ask("  Choice", default="1")
                choice_num = int(choice.strip())
                
                if choice_num == 0:
                    return Prompt.ask("  Enter capability name")
                elif 1 <= choice_num <= min(len(caps), 20):
                    return caps[choice_num - 1].get('name', '')
                else:
                    menu.console.print(f"  Please enter a number between 0 and {min(len(caps), 20)}")
                    
            except ValueError:
                menu.console.print("  Please enter a valid number")
            except KeyboardInterrupt:
                menu.console.print("  Cancelled")
                return None
                
    except Exception as e:
        menu.console.print(f"  Error loading capabilities: {e}")
        return Prompt.ask("  Enter capability name manually")


def _detect_agent_os(menu):
    """Detect the operating system of the selected agent"""
    if not menu.selected_agent:
        return None
        
    os_field = (menu.selected_agent.os or '').lower()
    
    if os_field:
        if 'linux' in os_field or os_field in ['ubuntu', 'centos', 'debian', 'rhel', 'fedora', 'suse']:
            return 'linux'
        elif 'windows' in os_field or os_field in ['win32', 'win64', 'nt']:
            return 'windows'
    
    return None


def _select_domain(menu):
    """Interactive domain selection"""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    
    try:
        menu.console.print(f"  [{colors['dim']}]Looking for available domains...[/{colors['dim']}]")
        
        # Use SDK to get available AD domains
        domains = menu.sdk.aegis.get_available_ad_domains()
        
        menu.console.print(f"  [{colors['dim']}]Found {len(domains)} domains[/{colors['dim']}]")
        
        if domains:
            menu.console.print(f"\n  Available domains:")
            for i, domain in enumerate(domains[:10], 1):  # Limit to 10
                menu.console.print(f"    {i:2d}. {domain}")
            
            if len(domains) > 10:
                menu.console.print(f"    [{colors['dim']}]... and {len(domains) - 10} more[/{colors['dim']}]")
            
            menu.console.print(f"     0. Enter domain manually")
            
            while True:
                try:
                    choice = Prompt.ask("  Choose domain", default="1")
                    choice_num = int(choice.strip())
                    
                    if choice_num == 0:
                        return Prompt.ask("  Enter domain name")
                    elif 1 <= choice_num <= min(len(domains), 10):
                        return domains[choice_num - 1]
                    else:
                        menu.console.print(f"  Please enter a number between 0 and {min(len(domains), 10)}")
                        
                except ValueError:
                    menu.console.print("  Please enter a valid number")
                except KeyboardInterrupt:
                    return None
        else:
            menu.console.print(f"  [{colors['dim']}]No domains found in assets. You can still enter one manually.[/{colors['dim']}]")
            return Prompt.ask("  Enter domain name (e.g., contoso.com, example.local)")
            
    except Exception as e:
        menu.console.print(f"  [{colors['dim']}]Error during domain selection: {e}[/{colors['dim']}]")
        return Prompt.ask("  Enter domain name (e.g., contoso.com, example.local)")


def complete(menu, text, tokens):
    sub = ['list', 'run', 'capabilities', 'caps']
    if len(tokens) <= 2:
        return [s for s in sub if s.startswith(text)]
    # Could extend to capability names later
    return []
