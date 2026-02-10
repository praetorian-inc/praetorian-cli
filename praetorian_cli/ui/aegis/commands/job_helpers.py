"""Shared helpers for job and schedule commands - capability picker, domain/credential
selectors, parameter configuration."""

import json
from rich.prompt import Prompt, Confirm
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, FuzzyCompleter
from ..constants import DEFAULT_COLORS


# ---------------------------------------------------------------------------
# Capability helpers
# ---------------------------------------------------------------------------

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


def capability_needs_credentials(capability_info):
    """Check if a capability requires credentials based on its parameters."""
    credential_params = {'username', 'password', 'domain'}
    parameters = capability_info.get('parameters', [])
    if isinstance(parameters, dict):
        param_names = {k.lower() for k in parameters.keys()}
    elif isinstance(parameters, list):
        param_names = {p.get('name', '').lower() for p in parameters}
    else:
        return False
    return bool(credential_params & param_names)


# ---------------------------------------------------------------------------
# Interactive pickers
# ---------------------------------------------------------------------------

def interactive_capability_picker(menu, suggested=None):
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
        agent_os = detect_agent_os(menu)

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


def detect_agent_os(menu):
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


def select_domain(menu):
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


def select_credentials(menu):
    """Interactive credential selection with numbered list.

    Returns:
        tuple: (credential_key, credential_display_name) or (None, None) if skipped
    """
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    try:
        menu.console.print(f"  [{colors['dim']}]Fetching available credentials...[/{colors['dim']}]")

        all_credentials, _ = menu.sdk.credentials.list()
        credentials = [c for c in all_credentials if c.get('type') == 'active-directory']

        if not credentials:
            menu.console.print(f"  [{colors['dim']}]No active-directory credentials found.[/{colors['dim']}]")
            return None, None

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
                    return None, None
                elif 1 <= choice_num <= min(len(credentials), 10):
                    selected = credentials[choice_num - 1]
                    name = selected.get('name', 'Unknown')
                    username = selected.get('username', '')
                    display_name = f"{name} ({username})" if username else name
                    menu.console.print(f"  [{colors['success']}]Credential selected: {display_name}[/{colors['success']}]")
                    return selected.get('key', ''), display_name
                else:
                    menu.console.print(f"  Please enter a number between 0 and {min(len(credentials), 10)}")

            except ValueError:
                menu.console.print("  Please enter a valid number")
            except KeyboardInterrupt:
                menu.console.print("  Skipped")
                return None, None

    except Exception as e:
        menu.console.print(f"  [{colors['dim']}]Error fetching credentials: {e}[/{colors['dim']}]")
        return None, None


def configure_parameters(menu, capability_info, has_credential=False):
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


def resolve_addomain_target_key(menu, domain):
    """Query the assets API to resolve an AD domain to its actual asset key (with SID).

    Returns:
        str: The actual asset key, or None if the domain asset was not found.
    """
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    try:
        assets, _ = menu.sdk.assets.list(key_prefix=f"#addomain#{domain}")
        if assets and len(assets) > 0:
            return assets[0].get('key')
    except Exception as e:
        menu.console.print(f"  [{colors['error']}]Error querying domain asset: {e}[/{colors['error']}]")

    return None
