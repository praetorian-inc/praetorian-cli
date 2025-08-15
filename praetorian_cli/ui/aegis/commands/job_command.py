"""
Simplified job command for managing Aegis jobs
"""

import json
from typing import List
from rich.prompt import Prompt, Confirm
from .base_command import BaseCommand


class JobCommand(BaseCommand):
    """Handle Aegis job management - simplified version"""
    
    def execute(self, args: List[str] = None):
        """Execute job command with subcommands"""
        args = args or []
        
        if not args:
            self.show_job_help()
            return
        
        subcommand = args[0].lower()
        
        if subcommand == 'list':
            self.list_jobs()
        elif subcommand == 'run':
            self.run_job(args[1:])
        elif subcommand == 'capabilities' or subcommand == 'caps':
            self.list_capabilities()
        else:
            self.console.print(f"\n  Unknown job subcommand: {subcommand}")
            self.show_job_help()
    
    def show_job_help(self):
        """Show job command help"""
        help_text = """
  Job Commands
  
  job run               Run a capability on selected agent
  job list              Show recent jobs  
  job caps              List available capabilities
  
  Examples:
    job run               # Interactive capability picker
    job list              # Recent jobs
    job caps              # Available capabilities
"""
        self.console.print(help_text)
    
    def list_jobs(self):
        """List recent jobs for the selected agent"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return
        
        hostname = self.selected_agent.hostname or 'Unknown'
        
        try:
            # Get recent jobs for this agent
            jobs, _ = self.sdk.jobs.list(prefix_filter=hostname)
            
            if not jobs:
                self.console.print(f"\n  No jobs found for {hostname}\n")
                return
            
            # Sort by creation time and show recent ones
            jobs.sort(key=lambda j: j.get('created', 0), reverse=True)
            
            self.console.print(f"\n  Recent jobs for {hostname}:")
            for job in jobs[:5]:  # Show last 5 jobs
                capability = job.get('capabilities', ['unknown'])[0] if job.get('capabilities') else 'unknown'
                status = job.get('status', 'unknown')
                job_id = job.get('key', '').split('#')[-1][:8]
                
                # Simple status indicator
                status_color = {
                    'JQ': 'dim', 'JR': 'yellow', 'JP': 'green', 'JF': 'red'
                }.get(status[:2], 'dim')
                
                self.console.print(f"    [{status_color}]{capability:<25} {status:<8}[/{status_color}] {job_id}")
            
            self.console.print()
            
        except Exception as e:
            self.console.print(f"  Error listing jobs: {e}")
    
    def list_capabilities(self):
        """List available capabilities"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return
        
        try:
            # Get capabilities using SDK
            caps = self.sdk.aegis.get_capabilities(surface_filter='internal')
            
            if not caps:
                self.console.print("  No capabilities found.")
                return
            
            self.console.print("\n  Available capabilities:")
            for cap in sorted(caps, key=lambda x: x.get('name', '')):
                name = cap.get('name', 'unknown')
                desc = (cap.get('description', '') or '')[:50]
                self.console.print(f"    {name:<25} {desc}")
            
            self.console.print()
            
        except Exception as e:
            self.console.print(f"  Error listing capabilities: {e}")
    
    def run_job(self, args: List[str]):
        """Run a job on the selected agent"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return
        
        hostname = self.selected_agent.hostname or 'Unknown'
        
        # Always use interactive picker for better UX, but pre-select if capability provided
        suggested_capability = args[0] if args else None
        capability = self._interactive_capability_picker(suggested_capability)
        if not capability:
            return  # User cancelled
        
        # Validate capability using SDK
        capability_info = self.sdk.aegis.validate_capability(capability)
        if not capability_info:
            self.console.print(f"  [{self.colors['error']}]Invalid capability: '{capability}'[/{self.colors['error']}]")
            self.console.print("  Use 'job capabilities' to see available options")
            return
        
        target_type = capability_info.get('target', 'asset').lower()
        
        # Create appropriate target key
        if target_type == 'addomain':
            # For AD capabilities, use interactive domain selection
            domain = self._select_domain()
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
        config = self.sdk.aegis.create_job_config(self.selected_agent, credentials)
        
        # Confirm job execution
        if not Confirm.ask(f"\n  Run '{capability}' on {target_display}?"):
            self.console.print("  Cancelled\n")
            return
        
        try:
            config_json = json.dumps(config)
            
            # Add job using SDK
            jobs = self.sdk.jobs.add(target_key, [capability], config_json)
            
            if jobs:
                job = jobs[0] if isinstance(jobs, list) else jobs
                job_key = job.get('key', '')
                status = job.get('status', 'unknown')
                job_id = job_key.split('#')[-1][:12] if job_key else 'unknown'
                
                self.console.print(f"  ✓ Job {job_id} queued successfully")
                self.console.print(f"  Target: {target_display}")
                self.console.print(f"  Status: {status}")
            else:
                self.console.print("  Error: No job returned from API")
                
        except Exception as e:
            self.console.print(f"  Error: {e}")
    
    def _interactive_capability_picker(self, suggested=None):
        """Interactive capability picker with numbered options"""
        if suggested:
            # Validate the suggested capability first
            capability_info = self.sdk.aegis.validate_capability(suggested)
            if capability_info:
                # Show the suggested capability and ask for confirmation
                desc = (capability_info.get('description', '') or '')[:60]
                self.console.print(f"\n  Suggested capability:")
                self.console.print(f"    {suggested}")
                self.console.print(f"    [{self.colors['dim']}]{desc}[/{self.colors['dim']}]")
                
                if Confirm.ask("  Use this capability?", default=True):
                    return suggested
                # If they decline, continue to show the full picker below
        try:
            # Determine agent OS for filtering
            agent_os = self._detect_agent_os()
            
            # Get capabilities filtered by OS
            caps = self.sdk.aegis.get_capabilities(surface_filter='internal', agent_os=agent_os)
            
            if not caps:
                # Fallback to all capabilities
                caps = self.sdk.aegis.get_capabilities(surface_filter='internal')
            
            if not caps:
                self.console.print("  No capabilities available.")
                return None
            
            if agent_os:
                self.console.print(f"  [{self.colors['dim']}]Showing {agent_os.title()} capabilities[/{self.colors['dim']}]")
            
            # Sort and display with numbers
            caps.sort(key=lambda x: x.get('name', ''))
            
            self.console.print(f"\n  Select capability:")
            for i, cap in enumerate(caps[:20], 1):  # Limit to 20 for usability
                name = cap.get('name', 'unknown')
                desc = (cap.get('description', '') or '')[:40]
                self.console.print(f"    {i:2d}. {name:<25} {desc}")
            
            if len(caps) > 20:
                self.console.print(f"    [{self.colors['dim']}]... and {len(caps) - 20} more capabilities[/{self.colors['dim']}]")
            
            self.console.print(f"     0. Enter capability name manually")
            
            while True:
                try:
                    choice = Prompt.ask("  Choice", default="1")
                    choice_num = int(choice.strip())
                    
                    if choice_num == 0:
                        return Prompt.ask("  Enter capability name")
                    elif 1 <= choice_num <= min(len(caps), 20):
                        return caps[choice_num - 1].get('name', '')
                    else:
                        self.console.print(f"  Please enter a number between 0 and {min(len(caps), 20)}")
                        
                except ValueError:
                    self.console.print("  Please enter a valid number")
                except KeyboardInterrupt:
                    self.console.print("  Cancelled")
                    return None
                    
        except Exception as e:
            self.console.print(f"  Error loading capabilities: {e}")
            return Prompt.ask("  Enter capability name manually")
    
    def _detect_agent_os(self):
        """Detect the operating system of the selected agent"""
        if not self.selected_agent:
            return None
            
        os_field = (self.selected_agent.os or '').lower()
        
        if os_field:
            if 'linux' in os_field or os_field in ['ubuntu', 'centos', 'debian', 'rhel', 'fedora', 'suse']:
                return 'linux'
            elif 'windows' in os_field or os_field in ['win32', 'win64', 'nt']:
                return 'windows'
        
        return None
    
    def _select_domain(self):
        """Interactive domain selection"""
        try:
            self.console.print(f"  [{self.colors['dim']}]Looking for available domains...[/{self.colors['dim']}]")
            
            # Use SDK to get available AD domains
            domains = self.sdk.aegis.get_available_ad_domains()
            
            self.console.print(f"  [{self.colors['dim']}]Found {len(domains)} domains[/{self.colors['dim']}]")
            
            if domains:
                self.console.print(f"\n  Available domains:")
                for i, domain in enumerate(domains[:10], 1):  # Limit to 10
                    self.console.print(f"    {i:2d}. {domain}")
                
                if len(domains) > 10:
                    self.console.print(f"    [{self.colors['dim']}]... and {len(domains) - 10} more[/{self.colors['dim']}]")
                
                self.console.print(f"     0. Enter domain manually")
                
                while True:
                    try:
                        choice = Prompt.ask("  Choose domain", default="1")
                        choice_num = int(choice.strip())
                        
                        if choice_num == 0:
                            return Prompt.ask("  Enter domain name")
                        elif 1 <= choice_num <= min(len(domains), 10):
                            return domains[choice_num - 1]
                        else:
                            self.console.print(f"  Please enter a number between 0 and {min(len(domains), 10)}")
                            
                    except ValueError:
                        self.console.print("  Please enter a valid number")
                    except KeyboardInterrupt:
                        return None
            else:
                self.console.print(f"  [{self.colors['dim']}]No domains found in assets. You can still enter one manually.[/{self.colors['dim']}]")
                return Prompt.ask("  Enter domain name (e.g., contoso.com, example.local)")
                
        except Exception as e:
            self.console.print(f"  [{self.colors['dim']}]Error during domain selection: {e}[/{self.colors['dim']}]")
            return Prompt.ask("  Enter domain name (e.g., contoso.com, example.local)")