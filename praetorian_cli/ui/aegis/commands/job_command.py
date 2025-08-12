"""
Job command for managing Aegis jobs
"""

from typing import List
from datetime import datetime
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.box import MINIMAL
from rich.prompt import Prompt, Confirm
from .base_command import BaseCommand


class JobCommand(BaseCommand):
    """Handle Aegis job management"""
    
    def execute(self, args: List[str] = None):
        """Execute job command with subcommands"""
        args = args or []
        
        if not args:
            # No subcommand - show job help
            self.show_job_help()
            return
        
        subcommand = args[0].lower()
        
        if subcommand == 'list':
            self.list_jobs(args[1:])
        elif subcommand == 'run':
            self.run_job(args[1:])
        elif subcommand == 'status':
            self.show_job_status(args[1:])
        elif subcommand == 'capabilities' or subcommand == 'caps':
            self.list_capabilities(args[1:])
        elif subcommand == 'smb':
            self.run_job(['windows-smb-snaffler'])
        elif subcommand == 'domain':
            self.run_job(['windows-domain-collection'])
        elif subcommand == 'latest' or subcommand == 'last':
            self.show_latest_job()
        else:
            self.console.print(f"\n  Unknown job subcommand: {subcommand}")
            self.show_job_help()
    
    def show_job_help(self):
        """Show job command help"""
        help_text = f"""
  Job Commands
  
  job run               Interactive capability picker
  job run <capability>  Run specific capability
  job list              Show recent jobs
  job latest            Show latest job status
  job caps              List available capabilities
  
  Quick shortcuts:
  job smb               Run SMB Snaffler
  job domain            Run domain collection
  
  Examples:
    job run               # Pick from menu
    job smb               # Quick SMB scan
    job list              # Recent jobs
    job latest            # Check last job
"""
        self.console.print(help_text)
    
    def list_jobs(self, args: List[str]):
        """List jobs for the selected agent"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return
        
        hostname = self.selected_agent.get('hostname', 'Unknown')
        client_id = self.selected_agent.get('client_id', '')
        
        self.console.print(f"\n  Jobs for {hostname}")
        
        try:
            # Get jobs filtered by agent (using client_id or hostname in the key)
            jobs, _ = self.sdk.jobs.list(prefix_filter=hostname)
            
            if not jobs:
                self.console.print(f"  [{self.colors['dim']}]No jobs found for this agent[/{self.colors['dim']}]\n")
                return
            
            # Create minimal table
            table = Table(
                show_header=True,
                header_style=f"{self.colors['dim']}",
                border_style=self.colors['dim'],
                box=MINIMAL,
                show_lines=False,
                padding=(0, 2),
                pad_edge=False
            )
            
            table.add_column("TIME", width=16, no_wrap=True)
            table.add_column("CAPABILITY", min_width=20)
            table.add_column("STATUS", width=10)
            table.add_column("ID", style=f"{self.colors['dim']}", width=20)
            
            # Sort jobs by creation time (newest first)
            jobs.sort(key=lambda j: j.get('created', 0), reverse=True)
            
            # Show only recent jobs (last 10)
            for job in jobs[:10]:
                # Parse job info
                capability = job.get('capabilities', ['unknown'])[0] if job.get('capabilities') else 'unknown'
                status = self._format_job_status(job.get('status', 'unknown'))
                job_id = job.get('key', '').split('#')[-1][:20]  # Last part of key, truncated
                
                # Format timestamp
                created = job.get('created', 0)
                if created:
                    time_str = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M")
                else:
                    time_str = "unknown"
                
                table.add_row(time_str, capability, status, job_id)
            
            self.console.print()
            self.console.print(table)
            self.console.print()
            
        except Exception as e:
            self.console.print(f"  [{self.colors['dim']}]Error listing jobs: {e}[/{self.colors['dim']}]")
    
    def run_job(self, args: List[str]):
        """Run a job on the selected agent"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return
        
        hostname = self.selected_agent.get('hostname', 'Unknown')
        
        # Get capability name from args or prompt
        if args:
            capability = args[0]
        else:
            # Show quick picker for common capabilities
            capability = self._quick_capability_picker()
            if not capability:
                return  # User cancelled
        
        # Validate capability exists for Aegis internal surface
        try:
            # Handle different response formats from API
            capabilities_response = self.sdk.capabilities.list(executor='aegis')
            
            if isinstance(capabilities_response, tuple):
                all_capabilities, _ = capabilities_response
            elif isinstance(capabilities_response, list):
                all_capabilities = capabilities_response
            elif isinstance(capabilities_response, dict):
                # API might return {'capabilities': [...]} or similar structure
                all_capabilities = capabilities_response.get('capabilities', 
                                                           capabilities_response.get('data', 
                                                                                   capabilities_response.get('items', [])))
            else:
                all_capabilities = []
            
            # Check if the capability exists and is valid for Aegis
            valid_capabilities = []
            for cap in all_capabilities:
                if isinstance(cap, dict) and cap.get('name'):
                    valid_capabilities.append(cap.get('name', '').lower())
            
            if capability.lower() not in valid_capabilities:
                self.console.print(f"\n  [{self.colors['error']}]Invalid capability: '{capability}'[/{self.colors['error']}]")
                self.console.print(f"  [{self.colors['dim']}]Use 'job capabilities' to see available options[/{self.colors['dim']}]\n")
                return
                
        except Exception as e:
            # If capability validation fails, show warning but continue
            self.console.print(f"  [{self.colors['warning']}]Warning: Could not validate capability '{capability}': {e}[/{self.colors['warning']}]")
        
        # Confirm job execution
        if not Confirm.ask(f"\n  Run '{capability}' on {hostname}?"):
            self.console.print("  Cancelled\n")
            return
        
        try:
            agent = self.selected_agent
            client_id = agent.get('client_id', '')
            
            # Quick capability lookup for target type
            target_type = 'asset'  # default
            try:
                caps_resp = self.sdk.capabilities.list(executor='aegis')
                caps = caps_resp[0] if isinstance(caps_resp, tuple) else caps_resp
                if isinstance(caps, dict):
                    caps = caps.get('capabilities', caps.get('data', caps.get('items', [])))
                
                for cap in caps:
                    if isinstance(cap, dict) and cap.get('name', '').lower() == capability.lower():
                        target_type = cap.get('target', 'asset').lower()
                        break
            except:
                pass
            
            # Create target key
            if target_type == 'addomain':
                # For AD targets, show available domains and let user pick
                domain = self._select_domain()
                if not domain:
                    return  # User cancelled
                # Use the full addomain key format: #addomain#domain#domain
                target_key = f"#addomain#{domain}#{domain}"
                self.console.print(f"  [{self.colors['dim']}]Target domain: {domain}[/{self.colors['dim']}]")
            else:
                target_key = f"#asset#{hostname}#{hostname}"
                self.console.print(f"  [{self.colors['dim']}]Target asset: {hostname}[/{self.colors['dim']}]")
            
            # Check if we have cached credentials for this session
            if not hasattr(self.menu, '_cached_creds'):
                self.menu._cached_creds = {}
            
            config = {
                "aegis": "true", 
                "client_id": client_id,
                "manual": "true"
            }
            
            # Smart credential handling
            cred_keywords = ['smb', 'domain', 'ad', 'ldap', 'winrm', 'wmi']
            needs_creds = any(kw in capability.lower() for kw in cred_keywords)
            
            if needs_creds:
                cache_key = f"{hostname}_{target_type}"
                use_cached = False
                
                if cache_key in self.menu._cached_creds:
                    # Ask if user wants to use cached credentials
                    use_cached = Confirm.ask("  Use cached credentials?")
                    
                if use_cached:
                    config.update(self.menu._cached_creds[cache_key])
                    self.console.print(f"  Using cached credentials for {hostname}")
                else:
                    # Prompt for new credentials
                    from rich.prompt import Prompt
                    
                    # Just ask for plain username - no domain format needed
                    username = Prompt.ask("  Username")
                    
                    password = Prompt.ask("  Password", password=True)
                    
                    # Use capitalized field names to match UI format
                    creds = {"Username": username, "Password": password}
                    config.update(creds)
                    self.menu._cached_creds[cache_key] = creds
            
            # Execute job properly 
            import json
            config_json = json.dumps(config)
            
            try:
                jobs = self.sdk.jobs.add(target_key, [capability], config_json)
                
                if jobs:
                    job = jobs[0] if isinstance(jobs, list) else jobs
                    job_key = job.get('key', '')
                    status = job.get('status', 'unknown')
                    job_id = job_key.split('#')[-1][:12] if job_key else 'unknown'
                    
                    self.console.print(f"  ✓ Job {job_id} queued successfully")
                    self.console.print(f"  [{self.colors['dim']}]Status: {status}[/{self.colors['dim']}]")
                    
                    if job_key:
                        short_id = job_key.split('#')[-1]
                        self.console.print(f"  [{self.colors['dim']}]Use 'job status {short_id[:8]}' to check progress[/{self.colors['dim']}]")
                else:
                    self.console.print(f"  ✗ No job returned from API")
                    
            except Exception as e:
                self.console.print(f"  ✗ Error: {e}")
                
        except Exception as e:
            self.console.print(f"  ✗ Unexpected error: {str(e)}")
    
    def show_job_status(self, args: List[str]):
        """Show status of a specific job"""
        if not args:
            self.console.print("\n  Usage: job status <job-id>\n")
            return
        
        job_id = args[0]
        
        try:
            # Try to find the job
            jobs, _ = self.sdk.jobs.list()
            
            matching_job = None
            for job in jobs:
                if job_id in job.get('key', ''):
                    matching_job = job
                    break
            
            if not matching_job:
                self.console.print(f"\n  Job not found: {job_id}\n")
                return
            
            # Display job details
            self.console.print(f"\n  Job Details\n")
            
            capability = matching_job.get('capabilities', ['unknown'])[0] if matching_job.get('capabilities') else 'unknown'
            status = self._format_job_status(matching_job.get('status', 'unknown'))
            created = matching_job.get('created', 0)
            
            if created:
                time_str = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = "unknown"
            
            self.console.print(f"    Capability:   {capability}")
            self.console.print(f"    Status:       {status}")
            self.console.print(f"    Started:      {time_str}")
            self.console.print(f"    Target:       {matching_job.get('dns', 'unknown')}")
            
            # Show config if present
            if matching_job.get('config'):
                self.console.print(f"    Config:       {matching_job.get('config')}")
            
            self.console.print()
            
        except Exception as e:
            self.console.print(f"\n  [{self.colors['dim']}]Error getting job status: {e}[/{self.colors['dim']}]\n")
    
    def show_latest_job(self):
        """Show status of the most recent job for the selected agent"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return
        
        hostname = self.selected_agent.get('hostname', 'Unknown')
        
        try:
            # Get recent jobs for this agent
            jobs, _ = self.sdk.jobs.list(prefix_filter=hostname)
            
            if not jobs:
                self.console.print(f"\n  No jobs found for {hostname}\n")
                return
            
            # Sort by creation time and get the latest
            jobs.sort(key=lambda j: j.get('created', 0), reverse=True)
            latest_job = jobs[0]
            
            # Display latest job info
            capability = latest_job.get('capabilities', ['unknown'])[0] if latest_job.get('capabilities') else 'unknown'
            status = self._format_job_status(latest_job.get('status', 'unknown'))
            job_id = latest_job.get('key', '').split('#')[-1][:12]
            created = latest_job.get('created', 0)
            
            if created:
                from datetime import datetime
                time_str = datetime.fromtimestamp(created).strftime("%H:%M:%S")
                date_str = datetime.fromtimestamp(created).strftime("%m/%d")
            else:
                time_str = date_str = "unknown"
            
            self.console.print(f"\n  Latest job: {capability}")
            self.console.print(f"  Status: {status}")
            self.console.print(f"  Started: {date_str} at {time_str}")
            self.console.print(f"  Job ID: {job_id}\n")
            
        except Exception as e:
            self.console.print(f"\n  Error getting latest job: {e}\n")
    
    def list_capabilities(self, args: List[str]):
        """List available Aegis capabilities for internal attack surface"""
        try:
            # Get all Aegis capabilities first
            # Note: Handle different response formats from API
            capabilities_response = self.sdk.capabilities.list(executor='aegis')
            
            if isinstance(capabilities_response, tuple):
                all_capabilities, _ = capabilities_response
            elif isinstance(capabilities_response, list):
                all_capabilities = capabilities_response
            elif isinstance(capabilities_response, dict):
                # API might return {'capabilities': [...]} or similar structure
                all_capabilities = capabilities_response.get('capabilities', 
                                                           capabilities_response.get('data', 
                                                                                   capabilities_response.get('items', [])))
            else:
                all_capabilities = []
            
            if not all_capabilities:
                self.console.print(f"  [{self.colors['dim']}]No Aegis capabilities found[/{self.colors['dim']}]\n")
                return
            
            # Filter for internal attack surface capabilities
            internal_capabilities = [
                cap for cap in all_capabilities 
                if isinstance(cap, dict) and cap.get('surface', '').lower() == 'internal'
            ]
            
            # Filter by agent OS if we have a selected agent
            if self.selected_agent:
                agent_os = self._detect_agent_os()
                if agent_os:
                    original_count = len(internal_capabilities)
                    internal_capabilities = [
                        cap for cap in internal_capabilities
                        if cap.get('name', '').lower().startswith(f'{agent_os}-')
                    ]
                    filtered_count = len(internal_capabilities)
                    self.console.print(f"  [{self.colors['dim']}]Filtered for {agent_os.title()}: {filtered_count}/{original_count} capabilities[/{self.colors['dim']}]")
            
            # If no internal-specific capabilities, show all Aegis capabilities
            capabilities = internal_capabilities if internal_capabilities else all_capabilities
            
            # Show counts
            total_aegis = len(all_capabilities)
            internal_count = len(internal_capabilities)
            
            self.console.print(f"  [{self.colors['dim']}]Aegis capabilities: {total_aegis} total, {internal_count} internal surface[/{self.colors['dim']}]\n")
            
            # Group capabilities by target type
            by_target = {}
            for cap in capabilities:
                if isinstance(cap, dict):
                    target = cap.get('target', 'other')
                    if target not in by_target:
                        by_target[target] = []
                    by_target[target].append(cap)
            
            # Display capabilities
            for target, caps in sorted(by_target.items()):
                self.console.print(f"  [{self.colors['dim']}]{target.title()} capabilities:[/{self.colors['dim']}]")
                
                # Sort capabilities by name
                caps.sort(key=lambda x: x.get('Name', ''))
                
                for cap in caps:
                    name = cap.get('name', 'unknown')
                    desc = cap.get('description', '')
                    surface = cap.get('surface', 'N/A')
                    
                    # Truncate description for display
                    if desc and len(desc) > 50:
                        desc = desc[:47] + "..."
                    
                    # Show surface type for context
                    surface_indicator = f"[{surface}]" if surface != 'N/A' else ""
                    
                    self.console.print(f"    {name:<20} {desc} {surface_indicator}")
                
                self.console.print()
                
        except Exception as e:
            self.console.print(f"  [{self.colors['error']}]Error retrieving capabilities: {e}[/{self.colors['error']}]")
            self.console.print(f"  [{self.colors['dim']}]Unable to fetch current capability list from API[/{self.colors['dim']}]\n")
    
    def _detect_agent_os(self):
        """Detect the operating system of the selected agent"""
        if not self.selected_agent:
            return None
            
        agent = self.selected_agent
        
        # Check the direct 'os' field 
        os_field = agent.get('os', '').lower()
        
        if os_field:
            if 'linux' in os_field or os_field in ['ubuntu', 'centos', 'debian', 'rhel', 'fedora', 'suse']:
                return 'linux'
            elif 'windows' in os_field or os_field in ['win32', 'win64', 'nt']:
                return 'windows'
        
        # Default: return None to show all capabilities
        return None
    
    def _select_domain(self):
        """Let user select from available AD domains"""
        try:
            # Get addomain assets
            domains = []
            try:
                assets_resp = self.sdk.assets.list(asset_type='addomain')
                assets = assets_resp[0] if isinstance(assets_resp, tuple) else assets_resp
                if isinstance(assets, dict):
                    assets = assets.get('assets', assets.get('data', assets.get('items', [])))
                
                if assets:
                    for asset in assets:
                        if isinstance(asset, dict):
                            dns = asset.get('dns', '')
                            key = asset.get('key', '')
                            
                            # Extract domain from key field if dns is empty
                            if dns:
                                domains.append(dns)
                            elif key and '#addomain#' in key:
                                # Extract domain from key format: #addomain#domain.com#domain.com
                                parts = key.split('#')
                                if len(parts) >= 3 and parts[1] == 'addomain':
                                    domain = parts[2]
                                    domains.append(domain)
            except Exception:
                pass
            domains = sorted(list(set(domains)))  # Remove duplicates and sort
            
            if not domains:
                self.console.print(f"\n  [{self.colors['dim']}]No AD domains found in the system[/{self.colors['dim']}]")
                from rich.prompt import Prompt
                return Prompt.ask("  Enter domain name manually")
            
            # Show numbered list
            self.console.print(f"\n  Available domains:")
            for i, domain in enumerate(domains[:15], 1):  # Limit to 15
                self.console.print(f"    {i:2d}. {domain}")
            
            if len(domains) > 15:
                self.console.print(f"    ... and {len(domains) - 15} more")
            
            self.console.print(f"     0. Enter domain manually")
            
            from rich.prompt import Prompt
            max_choice = min(len(domains), 15)
            
            while True:
                try:
                    choice_str = Prompt.ask("  Choice", default="1")
                    choice = int(choice_str.strip())
                    
                    if choice == 0:
                        return Prompt.ask("  Domain name")
                    elif 1 <= choice <= max_choice:
                        return domains[choice - 1]
                    else:
                        self.console.print(f"  Please enter a number between 0 and {max_choice}")
                        
                except ValueError:
                    self.console.print(f"  Please enter a number between 0 and {max_choice}")
                except KeyboardInterrupt:
                    self.console.print("  Cancelled")
                    return None
                
        except Exception:
            from rich.prompt import Prompt
            return Prompt.ask("  Enter domain name manually")
    
    def _quick_capability_picker(self):
        """Quick capability picker with numbered options"""
        try:
            # Get internal surface capabilities
            caps_resp = self.sdk.capabilities.list(executor='aegis')
            caps = caps_resp[0] if isinstance(caps_resp, tuple) else caps_resp
            if isinstance(caps, dict):
                caps = caps.get('capabilities', caps.get('data', caps.get('items', [])))
            
            # Filter and sort internal capabilities
            internal_caps = [
                cap for cap in caps 
                if isinstance(cap, dict) and cap.get('surface', '').lower() == 'internal'
            ]
            
            # Filter by agent OS if we have a selected agent
            if self.selected_agent:
                agent_os = self._detect_agent_os()
                
                if agent_os:
                    internal_caps = [
                        cap for cap in internal_caps
                        if cap.get('name', '').lower().startswith(f'{agent_os}-')
                    ]
                    self.console.print(f"  [{self.colors['dim']}]Filtered for {agent_os.title()} capabilities[/{self.colors['dim']}]")
            
            internal_caps.sort(key=lambda x: x.get('name', ''))
            
            if not internal_caps:
                # Fallback to all aegis capabilities
                internal_caps = [cap for cap in caps if isinstance(cap, dict)]
                internal_caps.sort(key=lambda x: x.get('name', ''))
            
            # Group capabilities by target type for better organization
            by_target = {}
            for cap in internal_caps:
                if isinstance(cap, dict):
                    target = cap.get('target', 'other')
                    if target not in by_target:
                        by_target[target] = []
                    by_target[target].append(cap)
            
            # Show grouped capabilities with numbering
            self.console.print(f"\n  Select capability:")
            cap_index = 1
            cap_list = []  # Track capabilities for selection
            
            for target, caps in sorted(by_target.items()):
                self.console.print(f"\n  [{self.colors['dim']}]{target.title()}:[/{self.colors['dim']}]")
                
                for cap in caps[:10]:  # Limit per group for usability
                    name = cap.get('name', 'unknown')
                    desc = cap.get('description', '')[:40]
                    self.console.print(f"    {cap_index:2d}. {name:<25} {desc}")
                    cap_list.append(cap)
                    cap_index += 1
                
                if len(caps) > 10:
                    self.console.print(f"    [{self.colors['dim']}]... and {len(caps) - 10} more {target} capabilities[/{self.colors['dim']}]")
            
            self.console.print(f"\n     0. Show all capabilities")
            
            # Store the capability list for selection
            internal_caps = cap_list
            
            # Use regular Prompt and parse the number ourselves for better reliability
            from rich.prompt import Prompt
            max_choice = len(internal_caps)
            
            while True:
                try:
                    choice_str = Prompt.ask("  Choice", default="1")
                    choice = int(choice_str.strip())
                    
                    if choice == 0:
                        # Show full list
                        self.list_capabilities([])
                        return Prompt.ask("\n  Enter capability name")
                    elif 1 <= choice <= max_choice:
                        return internal_caps[choice - 1].get('name', '')
                    else:
                        self.console.print(f"  Please enter a number between 0 and {max_choice}")
                        
                except ValueError:
                    self.console.print(f"  Please enter a number between 0 and {max_choice}")
                except KeyboardInterrupt:
                    self.console.print("  Cancelled")
                    return None
                
        except Exception:
            # Fallback to text input
            from rich.prompt import Prompt
            self.console.print("\n  Enter capability name (or 'list' to see all):")
            cap = Prompt.ask("  Capability")
            if cap.lower() == 'list':
                self.list_capabilities([])
                cap = Prompt.ask("\n  Enter capability name")
            return cap
    
    def _format_job_status(self, status: str) -> Text:
        """Format job status with color"""
        status_upper = status.upper()
        
        if status_upper.startswith('JQ'):
            return Text("queued", style=f"{self.colors['dim']}")
        elif status_upper.startswith('JR'):
            return Text("running", style=f"{self.colors['warning']}")
        elif status_upper.startswith('JP'):
            return Text("passed", style=f"{self.colors['success']}")
        elif status_upper.startswith('JF'):
            return Text("failed", style=f"{self.colors['error']}")
        else:
            return Text(status.lower(), style=f"{self.colors['dim']}")