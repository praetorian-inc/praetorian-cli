"""
Add-Finding Script

This script provides an interactive workflow for adding security findings/risks
to assets in Chariot. It guides the user through:
1. Selecting or entering a risk ID
2. Checking/adding definition files with fuzzy search
3. Associating assets with the risk

Usage:
  praetorian chariot script add-finding
"""

import os
import re
from difflib import SequenceMatcher

import click

from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.sdk.model.globals import Risk, AddRisk, Asset, Kind

try:
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import Completer, Completion
    from fuzzyfinder import fuzzyfinder
    HAS_FUZZY_PROMPT = True
except ImportError:
    HAS_FUZZY_PROMPT = False


def fuzzy_search(query, options, limit=5):
    """
    Perform fuzzy matching on a list of options.
    
    :param query: The search query string
    :param options: List of strings to search through
    :param limit: Maximum number of results to return
    :return: List of tuples (option, similarity_score) sorted by score
    """
    if not query.strip():
        return options[:limit]
    
    matches = []
    query_lower = query.lower()
    
    for option in options:
        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, query_lower, option.lower()).ratio()
        
        # Also check for substring matches which should score higher
        if query_lower in option.lower():
            similarity += 0.3
        
        matches.append((option, similarity))
    
    # Sort by similarity score (descending) and return top matches
    matches.sort(key=lambda x: x[1], reverse=True)
    return [match[0] for match in matches[:limit]]


class AssetCompleter(Completer):
    """Custom completer for asset fuzzy search using fuzzyfinder."""
    
    def __init__(self, assets):
        self.assets = assets
        self.asset_map = {}
        self.display_strings = []
        
        # Create searchable display strings
        for asset in assets:
            key = asset.get('key', 'N/A')
            dns = asset.get('dns', 'N/A')
            name = asset.get('name', 'N/A')
            status = asset.get('status', 'N/A')
            surface = asset.get('surface', 'N/A')
            
            # Create a readable display string
            display_str = f"{key} | DNS: {dns} | Name: {name} | Status: {status} | Surface: {surface}"
            self.display_strings.append(display_str)
            self.asset_map[display_str] = asset
    
    def get_completions(self, document, complete_event):
        word = document.text
        try:
            for match in fuzzyfinder(word, self.display_strings):
                yield Completion(match, start_position=-len(word))
        except:
            # Fallback if fuzzyfinder has issues
            for display_str in self.display_strings:
                if word.lower() in display_str.lower():
                    yield Completion(display_str, start_position=-len(word))


class DefinitionCompleter(Completer):
    """Custom completer for definition file fuzzy search using fuzzyfinder."""
    
    def __init__(self, definitions):
        self.definitions = definitions
    
    def get_completions(self, document, complete_event):
        word = document.text
        try:
            for match in fuzzyfinder(word, self.definitions):
                yield Completion(match, start_position=-len(word))
        except:
            # Fallback if fuzzyfinder has issues
            for definition in self.definitions:
                if word.lower() in definition.lower():
                    yield Completion(definition, start_position=-len(word))


def select_asset_with_fuzzy_prompt(assets):
    """
    Use prompt_toolkit with fuzzyfinder for interactive asset selection.
    
    :param assets: List of asset dictionaries
    :return: Selected asset dict or None if cancelled
    """
    if not HAS_FUZZY_PROMPT:
        return None
    
    try:
        completer = AssetCompleter(assets)
        click.echo(f"\n🔍 Fuzzy search through {len(assets)} assets (type to filter, Tab to complete, Enter to select):")
        
        selected_display = prompt('Select Asset: ', completer=completer)
        
        # Find the corresponding asset
        if selected_display in completer.asset_map:
            return completer.asset_map[selected_display]
        else:
            return None
            
    except (KeyboardInterrupt, EOFError):
        # User cancelled with Ctrl+C or Ctrl+D
        return None
    except Exception as e:
        click.echo(f"Error with fuzzy asset selection: {e}")
        return None


def select_definition_with_fuzzy_prompt(definitions):
    """
    Use prompt_toolkit with fuzzyfinder for interactive definition selection.
    
    :param definitions: List of definition filenames
    :return: Selected definition filename or None if cancelled
    """
    if not HAS_FUZZY_PROMPT:
        return None
    
    try:
        completer = DefinitionCompleter(definitions)
        click.echo(f"\n🔍 Fuzzy search through {len(definitions)} definitions (type to filter, Tab to complete, Enter to select):")
        
        selected = prompt('Select Definition: ', completer=completer)
        
        # Validate selection
        if selected in definitions:
            return selected
        else:
            return None
            
    except (KeyboardInterrupt, EOFError):
        # User cancelled with Ctrl+C or Ctrl+D
        return None
    except Exception as e:
        click.echo(f"Error with fuzzy definition selection: {e}")
        return None


class ManualAssetParser:
    """
    Parser class for handling different types of manual asset creation.
    Provides specific logic for different asset types.
    """
    
    ASSET_TYPES = {
        'dns-ip': 'DNS + IP Address',
        'aws': 'AWS Resource (ARN)'
    }
    
    def __init__(self):
        pass
    
    def get_asset_type(self):
        """
        Prompt user to select the type of asset they want to create.
        
        :return: Selected asset type key or None if cancelled
        """
        click.echo("\nSelect the type of asset you want to create:")
        for key, description in self.ASSET_TYPES.items():
            click.echo(f"  {key}: {description}")
        
        while True:
            asset_type = click.prompt("Enter asset type", type=click.Choice(list(self.ASSET_TYPES.keys())))
            if asset_type in self.ASSET_TYPES:
                return asset_type
            click.echo("Invalid asset type. Please try again.")
    
    def parse_dns_ip_asset(self):
        """
        Handle DNS + IP asset creation.
        Asks for DNS record as asset name, then IP.
        
        :return: Dict with asset creation parameters
        """
        click.echo(f"\n📡 Creating DNS + IP asset:")
        
        dns_record = click.prompt("Enter DNS record (asset name)", type=str).strip()
        if not dns_record:
            click.echo("DNS record cannot be empty.")
            return None
        
        ip_address = click.prompt("Enter IP address", type=str).strip()
        if not ip_address:
            click.echo("IP address cannot be empty.")
            return None
        
        # Basic IP validation (simple regex)
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, ip_address):
            click.echo("⚠ Warning: IP address format may be invalid")
        
        surface = click.prompt("Enter surface classification", 
                             type=click.Choice(['external', 'internal', 'web', 'api', 'cloud']),
                             default='external')
        
        return {
            'name': dns_record,
            'identifier': ip_address,  # IP as the identifier
            'surface': surface,
            'status': Asset.ACTIVE.value,
            'type': Kind.ASSET.value,
            'expected_key': f"#asset#{dns_record}#{ip_address}"
        }
    
    def parse_aws_asset(self):
        """
        Handle AWS asset creation.
        Asks for ARN, parses last colon field as asset name and full ARN as identifier.
        
        :return: Dict with asset creation parameters
        """
        click.echo(f"\n☁️ Creating AWS asset:")
        
        arn = click.prompt("Enter AWS ARN", type=str).strip()
        if not arn:
            click.echo("ARN cannot be empty.")
            return None
        
        # Basic ARN validation
        if not arn.startswith('arn:aws:'):
            click.echo("⚠ Warning: ARN should start with 'arn:aws:'")
        
        # Parse ARN to extract asset name (last colon field)
        arn_parts = arn.split(':')
        if len(arn_parts) < 6:
            click.echo("❌ Invalid ARN format. Expected format: arn:aws:service:region:account:resource")
            return None
        
        # Last colon field becomes the asset name
        asset_name = ':'.join(arn_parts[5:])
        if not asset_name:
            click.echo("❌ Could not extract asset name from ARN (last colon field is empty)")
            return None
        
        surface = click.prompt("Enter surface classification", 
                             type=click.Choice(['external', 'internal', 'web', 'api', 'cloud']),
                             default='cloud')
        
        click.echo(f"💡 Parsed ARN:")
        click.echo(f"   Asset Name: {asset_name}")
        click.echo(f"   Full ARN: {arn}")
        
        return {
            'name': asset_name,
            'identifier': arn,  # Full ARN as identifier
            'surface': surface,
            'status': Asset.ACTIVE.value,
            'type': Kind.ASSET.value,
            'expected_key': f"#asset#{asset_name}#{arn}"
        }
    
    def create_manual_asset(self):
        """
        Main method to create a manual asset by determining type and calling appropriate parser.
        
        :return: Dict with asset creation parameters or None if cancelled
        """
        asset_type = self.get_asset_type()
        if not asset_type:
            return None
        
        if asset_type == 'dns-ip':
            return self.parse_dns_ip_asset()
        elif asset_type == 'aws':
            return self.parse_aws_asset()
        else:
            click.echo(f"❌ Unsupported asset type: {asset_type}")
            return None


def prompt_for_risk_id():
    """
    Prompt user for risk ID with validation.
    
    :return: Valid risk ID string
    """
    click.echo("\n💡 Note: If a definition document exists upstream, the risk ID should match the filename of that document.")
    while True:
        risk_id = click.prompt("Enter risk ID", type=str).strip()
        if risk_id:
            # Basic validation - risk IDs should be non-empty strings
            # Could add more specific validation based on your risk ID format
            return risk_id
        click.echo("Risk ID cannot be empty. Please try again.")


def prompt_for_definition_file(sdk, risk_id):
    """
    Handle definition file workflow - check if exists or needs to be added.
    
    :param sdk: Chariot SDK instance
    :param risk_id: The risk ID to use as the definition filename
    :return: Definition filename if one is selected/added, None otherwise
    """
    # Check if user wants to use a definition file
    click.echo("\n💡 Note: Definition files are local files that will only apply to the target account.")
    click.echo("   (If you have an upstream definition you don't want this.)")
    use_definition = click.confirm("Do you want to associate a definition file with this risk?")
    
    if not use_definition:
        return None
    
    # Ask if definition already exists
    exists = click.confirm("Does the definition file already exist in your account?")
    
    if exists:
        # Get list of existing definitions for fuzzy search
        try:
            definitions, _ = sdk.definitions.list()
            if not definitions:
                click.echo("No existing definition files found.")
                return None
            
            if HAS_FUZZY_PROMPT:
                # Use prompt_toolkit with fuzzyfinder for better definition selection experience
                selected = select_definition_with_fuzzy_prompt(definitions)
                
                if selected:
                    return selected
                else:
                    return None
            else:
                # Fallback to original search method
                click.echo("💡 Tip: Install prompt_toolkit and fuzzyfinder for better definition search experience")
                while True:
                    query = click.prompt("Enter definition filename (or part of it for fuzzy search)", type=str)
                    matches = fuzzy_search(query, definitions)
                    
                    if not matches:
                        click.echo("No matching definitions found.")
                        continue
                    
                    click.echo("\nMatching definitions:")
                    for i, definition in enumerate(matches, 1):
                        click.echo(f"  {i}. {definition}")
                    
                    choice = click.prompt("Select definition (number)", type=int)
                    if 1 <= choice <= len(matches):
                        return matches[choice - 1]
                    else:
                        click.echo("Invalid selection. Please try again.")
                    
        except Exception as e:
            click.echo(f"Error retrieving definitions: {e}")
            return None
    else:
        # User needs to add a new definition file
        click.echo(f"\nUploading new definition file (will be named '{risk_id}' in Chariot):")
        click.echo("💡 Path can be:")
        click.echo("   • Absolute path: /full/path/to/file.md")
        click.echo("   • Relative to current directory: ./docs/risk-def.md")
        click.echo("   • Relative to home directory: ~/Documents/definition.md")
        
        # Show current working directory to help user
        current_dir = os.getcwd()
        click.echo(f"📁 Current directory: {current_dir}")
        
        while True:
            local_path = click.prompt("Enter path to local definition file", type=str)
            
            # Expand user path (~) and resolve relative paths
            expanded_path = os.path.expanduser(local_path)
            if not os.path.isabs(expanded_path):
                expanded_path = os.path.join(current_dir, expanded_path)
            
            # Check if file exists
            if not os.path.exists(expanded_path):
                click.echo(f"❌ File not found: {expanded_path}")
                if click.confirm("Try a different path?"):
                    continue
                else:
                    return None
            
            # Check if it's a file (not directory)
            if not os.path.isfile(expanded_path):
                click.echo(f"❌ Path is not a file: {expanded_path}")
                if click.confirm("Try a different path?"):
                    continue
                else:
                    return None
            
            # Use risk_id as the definition name (no extension needed as Chariot handles this)
            definition_name = risk_id
            try:
                result = sdk.definitions.add(expanded_path, definition_name)
                click.echo(f"✓ Successfully uploaded definition file as: {definition_name}")
                return definition_name
            except Exception as e:
                click.echo(f"❌ Error uploading definition file: {e}")
                if click.confirm("Try a different file?"):
                    continue
                else:
                    return None


def collect_assets_for_risk(sdk):
    """
    Collect all assets to be associated with the risk before proceeding.
    Cache new asset creation operations for later execution.
    
    :param sdk: Chariot SDK instance
    :return: Tuple of (existing_asset_keys, new_assets_to_create)
    """
    click.echo(f"\nCollecting assets to associate with this risk...")
    existing_assets = []
    new_assets_to_create = []
    
    while True:
        # Ask if asset exists or should be created
        asset_exists = click.confirm("Does this asset already exist in Chariot?")
        
        if asset_exists:
            # Perform asset search with fuzzy matching
            try:
                # Ask if user wants to filter assets by DNS prefix to reduce search space
                dns_filter = ""
                use_dns_filter = click.confirm("Would you like to filter assets by DNS hostname before searching? (Recommended for accounts with many assets)")
                if use_dns_filter:
                    dns_filter = click.prompt("Enter DNS hostname prefix to filter by (e.g., 'example.com' or 'api.')", type=str, default="").strip()
                    if dns_filter:
                        click.echo(f"💡 Filtering assets by DNS prefix: '{dns_filter}'")
                
                # Get assets with optional DNS filtering (load more pages for better selection)
                all_assets, _ = sdk.assets.list(prefix_filter=dns_filter, pages=5)  # Get more assets for better fzf experience
                if not all_assets:
                    if dns_filter:
                        click.echo(f"No assets found matching DNS filter: '{dns_filter}'")
                    else:
                        click.echo("No assets found in your account.")
                    
                    if click.confirm("Would you like to create a new asset instead?"):
                        asset_exists = False
                    else:
                        continue
                
                if asset_exists:  # Still true after the check above
                    if HAS_FUZZY_PROMPT:
                        # Use prompt_toolkit with fuzzyfinder for better search experience
                        selected_asset = select_asset_with_fuzzy_prompt(all_assets)
                        
                        if selected_asset:
                            asset_key = selected_asset.get('key')
                            if asset_key:
                                existing_assets.append(asset_key)
                                click.echo(f"✓ Added existing asset {asset_key} to association list")
                            else:
                                click.echo("Error: Selected asset has no key")
                        else:
                            if click.confirm("Asset selection cancelled. Create a new asset instead?"):
                                asset_exists = False
                            else:
                                continue
                    else:
                        # Fallback to original search method if fuzzy prompt not available
                        click.echo("💡 Tip: Install prompt_toolkit and fuzzyfinder (pip install prompt_toolkit fuzzyfinder) for better search experience")
                        while True:
                            search_query = click.prompt("Enter asset name or DNS to search", type=str)
                            
                            # Create searchable strings from assets (combine key, dns, name)
                            asset_search_strings = []
                            asset_map = {}
                            for asset in all_assets:
                                search_str = f"{asset.get('key', '')} {asset.get('dns', '')} {asset.get('name', '')}"
                                asset_search_strings.append(search_str)
                                asset_map[search_str] = asset
                            
                            matches = fuzzy_search(search_query, asset_search_strings)
                            
                            if not matches:
                                click.echo("No matching assets found.")
                                if click.confirm("Try another search?"):
                                    continue
                                elif click.confirm("Create a new asset instead?"):
                                    asset_exists = False
                                    break
                                else:
                                    continue
                            
                            click.echo("\nMatching assets:")
                            for i, match in enumerate(matches, 1):
                                asset = asset_map[match]
                                click.echo(f"  {i}. {asset.get('key', 'N/A')} (DNS: {asset.get('dns', 'N/A')}, Name: {asset.get('name', 'N/A')})")
                            
                            choice = click.prompt("Select asset (number)", type=int)
                            if 1 <= choice <= len(matches):
                                selected_asset = asset_map[matches[choice - 1]]
                                asset_key = selected_asset.get('key')
                                if asset_key:
                                    existing_assets.append(asset_key)
                                    click.echo(f"✓ Added existing asset {asset_key} to association list")
                                    break
                            else:
                                click.echo("Invalid selection. Please try again.")
            
            except Exception as e:
                click.echo(f"Error searching assets: {e}")
                if click.confirm("Would you like to create a new asset instead?"):
                    asset_exists = False
        
        if not asset_exists:
            # Use ManualAssetParser to handle different asset types
            parser = ManualAssetParser()
            new_asset_data = parser.create_manual_asset()
            
            if new_asset_data:
                new_assets_to_create.append(new_asset_data)
                click.echo(f"✓ Cached new asset creation: {new_asset_data['expected_key']}")
            else:
                click.echo("❌ Asset creation cancelled or failed")
        
        # Ask if user wants to add more assets
        if not click.confirm("Add another asset to this risk?"):
            break
    
    return existing_assets, new_assets_to_create


def associate_assets_with_risk(sdk, risk_id, definition_name, existing_assets, new_assets_to_create):
    """
    Associate collected assets with the risk using a single risk status.
    Creates new assets first, then associates all assets with the risk.
    
    :param sdk: Chariot SDK instance
    :param risk_id: The risk identifier
    :param definition_name: Optional definition filename
    :param existing_assets: List of existing asset keys
    :param new_assets_to_create: List of asset creation data dicts
    """
    total_assets = len(existing_assets) + len(new_assets_to_create)
    if total_assets == 0:
        click.echo("No assets to associate with the risk.")
        return
    
    click.echo(f"\nPreparing to associate {total_assets} asset(s) with risk: {risk_id}")
    if definition_name:
        click.echo(f"Using definition file: {definition_name}")
    
    # Get risk status once for all assets
    risk_status = click.prompt("Enter risk status for all associated assets", 
                             default=AddRisk.TRIAGE_HIGH.value,
                             type=click.Choice([
                                 AddRisk.TRIAGE_INFO.value,
                                 AddRisk.TRIAGE_LOW.value,
                                 AddRisk.TRIAGE_MEDIUM.value,
                                 AddRisk.TRIAGE_HIGH.value,
                                 AddRisk.TRIAGE_CRITICAL.value
                             ]))
    
    # Get final approval before making changes
    click.echo("\n📋 Summary of changes to be applied:")
    click.echo(f"  Risk ID: {risk_id}")
    click.echo(f"  Risk Status: {risk_status}")
    if definition_name:
        click.echo(f"  Definition File: {definition_name}")
    
    if existing_assets:
        click.echo(f"  Existing assets to associate ({len(existing_assets)}):")
        for asset_key in existing_assets:
            click.echo(f"    - {asset_key}")
    
    if new_assets_to_create:
        click.echo(f"  New assets to create and associate ({len(new_assets_to_create)}):")
        for asset_data in new_assets_to_create:
            click.echo(f"    - {asset_data['expected_key']} (DNS: {asset_data['name']}, ID: {asset_data['identifier']}, Surface: {asset_data['surface']})")
    
    if not click.confirm("\nProceed with applying these changes?"):
        click.echo("Operation cancelled by user.")
        return
    
    # Now execute all operations
    all_asset_keys = []
    successful_associations = []
    
    # First, create new assets
    if new_assets_to_create:
        click.echo(f"\nCreating {len(new_assets_to_create)} new asset(s)...")
        for asset_data in new_assets_to_create:
            try:
                asset = sdk.assets.add(
                    asset_data['name'],
                    asset_data['identifier'], 
                    surface=asset_data['surface'], 
                    status=asset_data['status']
                )
                asset_key = asset.get('key')
                if asset_key:
                    all_asset_keys.append(asset_key)
                    click.echo(f"✓ Created asset: {asset_key}")
                    
                    # Explicitly add surface as an attribute to ensure proper UI display
                    try:
                        sdk.attributes.add(asset_key, 'surface', asset_data['surface'])
                        click.echo(f"  ✓ Set surface attribute: {asset_data['surface']}")
                    except Exception as e:
                        click.echo(f"  ⚠ Warning: Could not set surface attribute: {e}")
                        
                else:
                    click.echo(f"❌ Error: Asset created but no key returned for {asset_data['expected_key']}")
            except Exception as e:
                click.echo(f"❌ Error creating asset {asset_data['expected_key']}: {e}")
    
    # Add existing assets to the list
    all_asset_keys.extend(existing_assets)
    
    # Now associate risks with all assets
    if all_asset_keys:
        click.echo(f"\nAssociating risk '{risk_id}' with {len(all_asset_keys)} asset(s)...")
        for asset_key in all_asset_keys:
            try:
                # Add the risk to the asset with capability source for better tracking
                risk = sdk.risks.add(asset_key, risk_id, risk_status, 
                                   None,  # No comment as requested
                                   capability='manual-add-finding')
                click.echo(f"✓ Associated risk '{risk_id}' with asset {asset_key}")
                successful_associations.append(asset_key)
                
                # Add definition as an attribute if specified
                if definition_name:
                    try:
                        sdk.attributes.add(risk['key'], 'definition', definition_name)
                        click.echo(f"  ✓ Associated definition file '{definition_name}' with the risk")
                    except Exception as e:
                        click.echo(f"  ⚠ Warning: Could not associate definition file: {e}")
                        
            except Exception as e:
                click.echo(f"❌ Error adding risk to asset {asset_key}: {e}")
    
    # Summary
    if successful_associations:
        click.echo(f"\n✅ Successfully associated risk '{risk_id}' with {len(successful_associations)} asset(s):")
        for asset in successful_associations:
            click.echo(f"  - {asset}")
        if definition_name:
            click.echo(f"✅ Used definition file: {definition_name}")
    else:
        click.echo("\n❌ No assets were successfully associated with the risk.")


@click.command('add-finding')
@cli_handler
def add_finding_command(sdk):
    """
    Interactive script for adding security findings/risks to assets.
    
    This script guides you through:
    1. Entering a risk ID
    2. Optionally associating a definition file (with fuzzy search)
    3. Associating one or more assets with the risk
    """
    click.echo("🔍 Add Finding - Interactive Risk Association")
    click.echo("=" * 50)
    
    try:
        # Step 1: Get risk ID
        risk_id = prompt_for_risk_id()
        click.echo(f"✓ Risk ID: {risk_id}")
        
        # Step 2: Handle definition file
        definition_name = prompt_for_definition_file(sdk, risk_id)
        if definition_name:
            click.echo(f"✓ Definition file: {definition_name}")
        
        # Step 3: Collect all assets to be associated (cache new asset creations)
        existing_assets, new_assets_to_create = collect_assets_for_risk(sdk)
        
        # Step 4: Associate collected assets with the risk (with final approval)
        associate_assets_with_risk(sdk, risk_id, definition_name, existing_assets, new_assets_to_create)
        
        click.echo("\n🎉 Add Finding workflow completed!")
        
    except KeyboardInterrupt:
        click.echo("\n\nWorkflow cancelled by user.")
    except Exception as e:
        click.echo(f"\n❌ An error occurred: {e}")


def register(script_group: click.MultiCommand):
    """
    Register the add-finding command with the script group.
    
    :param script_group: The Click MultiCommand group to register with
    """
    script_group.add_command(add_finding_command)
