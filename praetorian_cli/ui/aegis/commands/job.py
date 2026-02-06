import json
from rich.table import Table
from rich.box import MINIMAL
from rich.prompt import Prompt, Confirm
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, FuzzyCompleter
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

        # Query assets to get the actual domain asset key (with SID)
        try:
            assets, _ = menu.sdk.assets.list(key_prefix=f"#addomain#{domain}")
            if assets and len(assets) > 0:
                # Use the actual asset key from the database (includes SID)
                target_key = assets[0].get('key', f"#addomain#{domain}#{domain}")
            else:
                # Fallback if no asset found (shouldn't happen for existing domains)
                menu.console.print(f"  [yellow]Warning: No asset found for domain {domain}, using constructed key[/yellow]")
                target_key = f"#addomain#{domain}#{domain}"
        except Exception as e:
            menu.console.print(f"  [yellow]Warning: Error querying domain asset: {e}[/yellow]")
            target_key = f"#addomain#{domain}#{domain}"

        target_display = f"domain {domain}"
    else:
        target_key = f"#asset#{hostname}#{hostname}"
        target_display = f"asset {hostname}"
    
    # Handle credentials for capabilities that need them
    credentials = []
    if any(keyword in capability.lower() for keyword in ['ad-', 'smb-', 'domain-', 'ldap', 'winrm']):
        if Confirm.ask("  This capability may require credentials. Add them?"):
            credential_key = _select_credentials(menu)
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

            menu.console.print(f"\n[green]✓ Job queued successfully[/green]")
            menu.console.print(f"  Job ID: {job_id}")
            menu.console.print(f"  Job Key: {job_key}")
            menu.console.print(f"  Capability: {capability}")
            menu.console.print(f"  Target: {target_display}")
            menu.console.print(f"  Status: {status}")
            if credentials:
                menu.console.print(f"  Credentials: {len(credentials)} attached")
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


def _parse_capability_name(name):
    """Extract OS, category, and tool from capability name.

    Pattern: {os}-{category}-{tool}[-{action}]
    Examples:
        windows-ad-umber-collect -> os=windows, category=ad, tool=umber
        windows-smb-snaffler -> os=windows, category=smb, tool=snaffler
        linux-enum-linpeas -> os=linux, category=enum, tool=linpeas
    """
    parts = name.split('-')
    if len(parts) >= 3:
        return {'os': parts[0], 'category': parts[1], 'tool': parts[2]}
    elif len(parts) == 2:
        return {'os': parts[0], 'category': parts[1], 'tool': ''}
    else:
        return {'os': '', 'category': '', 'tool': name}


class CapabilityCompleter(Completer):
    """Custom completer for capabilities with metadata display."""

    def __init__(self, capabilities):
        """Initialize with list of capability dicts from API."""
        self.capabilities = capabilities

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lower()

        for cap in self.capabilities:
            name = cap.get('name', '')
            name_lower = name.lower()
            target = cap.get('target', 'asset').lower()
            description = cap.get('description', '') or ''
            parsed = _parse_capability_name(name)
            category = parsed.get('category', '')

            # Build searchable text (name + category + target)
            searchable = f"{name_lower} {category} {target}"

            # Check if input matches any part
            if not text or text in searchable:
                # Format: name    [target]  category  description
                desc_truncated = description[:35] + '...' if len(description) > 35 else description
                display_meta = f"[{target}] {category:<6} {desc_truncated}"

                yield Completion(
                    name,
                    start_position=-len(document.text_before_cursor),
                    display=name,
                    display_meta=display_meta,
                )


def _interactive_capability_picker(menu, suggested=None):
    """Interactive capability picker with fuzzy search."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    if suggested:
        # Validate the suggested capability first
        capability_info = menu.sdk.aegis.validate_capability(suggested)
        if capability_info:
            # Show the suggested capability and ask for confirmation
            desc = (capability_info.get('description', '') or '')[:60]
            target = capability_info.get('target', 'asset')
            menu.console.print(f"\n  Suggested capability:")
            menu.console.print(f"    {suggested} [{target}]")
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

        # Sort capabilities by name
        caps.sort(key=lambda x: x.get('name', ''))

        if agent_os:
            menu.console.print(f"\n  [{colors['dim']}]Showing {agent_os.title()} capabilities ({len(caps)} available)[/{colors['dim']}]")
        else:
            menu.console.print(f"\n  [{colors['dim']}]{len(caps)} capabilities available[/{colors['dim']}]")

        menu.console.print(f"  [{colors['dim']}]Type to filter, Tab to complete, Enter to select, Ctrl+C to cancel[/{colors['dim']}]")

        # Create fuzzy completer with capability metadata
        base_completer = CapabilityCompleter(caps)
        fuzzy_completer = FuzzyCompleter(base_completer)

        try:
            # Use prompt_toolkit for fuzzy search
            result = pt_prompt(
                "  Select capability: ",
                completer=fuzzy_completer,
                complete_while_typing=True,
            )

            if result and result.strip():
                return result.strip()
            else:
                menu.console.print("  No capability selected.")
                return None

        except KeyboardInterrupt:
            menu.console.print("\n  Cancelled")
            return None
        except EOFError:
            menu.console.print("\n  Cancelled")
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
    """Interactive domain selection with numbered list."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    try:
        menu.console.print(f"  [{colors['dim']}]Looking for available domains...[/{colors['dim']}]")

        domains = menu.sdk.aegis.get_available_ad_domains()

        menu.console.print(f"  [{colors['dim']}]Found {len(domains)} domains[/{colors['dim']}]")

        if domains:
            menu.console.print(f"\n  Available domains:")
            for i, domain in enumerate(domains[:10], 1):
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


def _select_credentials(menu):
    """Interactive credential selection with numbered list - returns credential key."""
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    try:
        menu.console.print(f"  [{colors['dim']}]Fetching available credentials...[/{colors['dim']}]")

        all_credentials, _ = menu.sdk.credentials.list()
        credentials = [c for c in all_credentials if c.get('type') == 'active-directory']

        if not credentials:
            menu.console.print(f"  [{colors['dim']}]No active-directory credentials found.[/{colors['dim']}]")
            return None

        menu.console.print(f"\n  Available credentials:")
        for i, cred in enumerate(credentials[:10], 1):
            name = cred.get('name', 'Unknown')
            username = cred.get('username', '')
            display = f"{name} ({username})" if username else name
            menu.console.print(f"    {i:2d}. {display}")

        if len(credentials) > 10:
            menu.console.print(f"    [{colors['dim']}]... and {len(credentials) - 10} more[/{colors['dim']}]")

        menu.console.print(f"     0. Skip credential attachment")

        while True:
            try:
                choice = Prompt.ask("  Choose credential", default="1")
                choice_num = int(choice.strip())

                if choice_num == 0:
                    menu.console.print("  Skipped credential attachment.")
                    return None
                elif 1 <= choice_num <= min(len(credentials), 10):
                    selected = credentials[choice_num - 1]
                    menu.console.print(f"  [{colors['success']}]Credential selected: {selected.get('name', 'Unknown')}[/{colors['success']}]")
                    return selected.get('key', '')
                else:
                    menu.console.print(f"  Please enter a number between 0 and {min(len(credentials), 10)}")

            except ValueError:
                menu.console.print("  Please enter a valid number")
            except KeyboardInterrupt:
                menu.console.print("  Skipped")
                return None

    except Exception as e:
        menu.console.print(f"  [{colors['dim']}]Error fetching credentials: {e}[/{colors['dim']}]")
        return None


def _configure_parameters(menu, capability_info, has_credential=False):
    """Interactive parameter configuration - returns dict of parameter values.

    Args:
        menu: Menu instance with console access
        capability_info: Capability information with parameters
        has_credential: If True, skip Username/Password/Domain params (they come from credential)
    """
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    parameters = capability_info.get('parameters', [])
    if not parameters:
        return {}

    # Parameters that come from credentials (skip if credential attached)
    credential_params = {'Username', 'Password', 'Domain'}

    menu.console.print(f"\n  [{colors['dim']}]Configure parameters (press Enter to use default):[/{colors['dim']}]")

    configured = {}

    # Handle both dict format (legacy/tests) and list format (actual API)
    if isinstance(parameters, dict):
        # Dict format: {'timeout': '300', 'threads': '10'}
        for param_name, default_value in parameters.items():
            # Skip credential params if credential is attached
            if has_credential and param_name in credential_params:
                continue
            value = Prompt.ask(f"  {param_name}", default=str(default_value))
            configured[param_name] = value
    elif isinstance(parameters, list):
        # List format: [{'name': 'timeout', 'default': 300}, {'name': 'threads', 'default': 10}]
        for param in parameters:
            param_name = param.get('name', '')
            default_value = param.get('default', '')
            if param_name:
                # Skip credential params if credential is attached
                if has_credential and param_name in credential_params:
                    continue
                value = Prompt.ask(f"  {param_name}", default=str(default_value))
                configured[param_name] = value

    return configured


def complete(menu, text, tokens):
    sub = ['list', 'run', 'capabilities', 'caps']
    if len(tokens) <= 2:
        return [s for s in sub if s.startswith(text)]
    # Could extend to capability names later
    return []
