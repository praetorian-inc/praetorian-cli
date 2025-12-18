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
import csv
import uuid
import tempfile
from pathlib import Path
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
        'aws': 'AWS Resource (ARN)',
        'azure': 'Azure Resource (Resource ID)',
        'dns-dns': 'DNS + DNS'
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
        Asks for DNS record as asset name, then IP or text identifier.
        
        :return: Dict with asset creation parameters
        """
        click.echo(f"\n📡 Creating DNS + IP asset:")
        
        dns_record = click.prompt("Enter DNS record (asset name)", type=str).strip()
        if not dns_record:
            click.echo("DNS record cannot be empty.")
            return None
        
        identifier = click.prompt("Enter IP address or identifier text", type=str).strip()
        if not identifier:
            click.echo("Identifier cannot be empty.")
            return None
        
        # Check if it's a valid IP address
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, identifier):
            click.echo("⚠ Warning: Identifier does not match IP address format. Using as text identifier.")
            click.echo(f"  Identifier: '{identifier}'")
        
        surface = click.prompt("Enter surface classification", 
                             type=click.Choice(['external', 'internal', 'web', 'api', 'cloud']),
                             default='external')
        
        return {
            'name': dns_record,
            'identifier': identifier,  # Can be IP or text
            'surface': surface,
            'status': Asset.ACTIVE.value,
            'type': Kind.ASSET.value,
            'expected_key': f"#asset#{dns_record}#{identifier}"
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

    def parse_azure_asset(self):
        """
        Handle Azure asset creation.
        Asks for Azure Resource ID, parses last slash field as asset name and full Resource ID as identifier.

        :return: Dict with asset creation parameters
        """
        click.echo(f"\n☁️ Creating Azure asset:")

        resource_id = click.prompt("Enter Azure Resource ID", type=str).strip()
        if not resource_id:
            click.echo("Azure Resource ID cannot be empty.")
            return None

        # Validate Azure Resource ID format with relaxed rules
        try:
            self._validate_azure_resource_id(resource_id)
        except ValueError as e:
            click.echo(f"❌ Invalid Azure Resource ID: {e}")
            return None

        # Parse Resource ID to extract asset name (last segment after final slash)
        segments = [s for s in resource_id.split('/') if s]  # Remove empty segments
        asset_name = segments[-1]

        if not asset_name:
            click.echo("❌ Could not extract asset name from Azure Resource ID (final segment is empty)")
            return None

        surface = click.prompt("Enter surface classification",
                             type=click.Choice(['external', 'internal', 'web', 'api', 'cloud']),
                             default='cloud')

        click.echo(f"💡 Parsed Azure Resource ID:")
        click.echo(f"   Asset Name: {asset_name}")
        click.echo(f"   Full Resource ID: {resource_id}")

        return {
            'name': asset_name,
            'identifier': resource_id,  # Full Resource ID as identifier
            'surface': surface,
            'status': Asset.ACTIVE.value,
            'type': Kind.ASSET.value,
            'expected_key': f"#asset#{asset_name}#{resource_id}"
        }

    def _validate_azure_resource_id(self, resource_id):
        """
        Validate Azure Resource ID with relaxed rules to handle various Azure resource types.

        :param resource_id: The Azure Resource ID to validate
        :raises ValueError: If the resource ID format is invalid
        """
        if not (resource_id.startswith('/subscriptions/') or resource_id.startswith('/providers/')):
            raise ValueError("Azure Resource ID must start with '/subscriptions/' or '/providers/'")

        segments = [s for s in resource_id.split('/') if s]  # Remove empty segments
        if len(segments) < 3:
            raise ValueError("Azure Resource ID must have at least 3 segments")

        if not segments[-1]:
            raise ValueError("Resource name (final segment) cannot be empty")

        if '/providers/' not in resource_id:
            raise ValueError("Azure Resource ID must contain '/providers/'")

        # Optional warning for unusual patterns (not an error)
        if len(segments) < 4 or len(segments) > 15:
            click.echo(f"⚠ Warning: Unusual Azure Resource ID format with {len(segments)} segments")

    def parse_dns_dns_asset(self):
        """
        Handle DNS + DNS asset creation.
        Asks for DNS record as asset name, then DNS identifier.

        :return: Dict with asset creation parameters
        """
        click.echo(f"\n📡 Creating DNS + DNS asset:")

        dns_record = click.prompt("Enter DNS record (asset name)", type=str).strip()
        if not dns_record:
            click.echo("DNS record cannot be empty.")
            return None

        dns_identifier = click.prompt("Enter DNS identifier", type=str).strip()
        if not dns_identifier:
            click.echo("DNS identifier cannot be empty.")
            return None

        surface = click.prompt("Enter surface classification",
                             type=click.Choice(['external', 'internal', 'web', 'api', 'cloud']),
                             default='external')

        return {
            'name': dns_record,
            'identifier': dns_identifier,
            'surface': surface,
            'status': Asset.ACTIVE.value,
            'type': Kind.ASSET.value,
            'expected_key': f"#asset#{dns_record}#{dns_identifier}"
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
        elif asset_type == 'azure':
            return self.parse_azure_asset()
        elif asset_type == 'dns-dns':
            return self.parse_dns_dns_asset()
        else:
            click.echo(f"❌ Unsupported asset type: {asset_type}")
            return None
    
    def parse_asset_from_bulk_data(self, asset_type, asset_value, surface):
        """
        Parse asset data from bulk input (non-interactive) for the given asset type.

        :param asset_type: Type of asset (dns-ip, aws, azure, dns-dns)
        :param asset_value: Value to parse based on type
        :param surface: Surface classification
        :return: Asset creation data dict
        """
        if asset_type == 'dns-ip':
            # For DNS-IP, expect format: "dns_record|ip_address_or_identifier"
            if '|' not in asset_value:
                raise ValueError(f"DNS-IP asset_value must be in format 'dns_record|ip_address_or_identifier', got: {asset_value}")
            
            parts = asset_value.split('|', 1)
            dns_record = parts[0].strip()
            identifier = parts[1].strip()
            
            if not dns_record or not identifier:
                raise ValueError("Both DNS record and identifier must be non-empty")
            
            # Check if it's a valid IP address
            ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if not re.match(ip_pattern, identifier):
                # Log warning but allow the text identifier
                click.echo(f"    ⚠ Warning: Identifier '{identifier}' does not match IP format for DNS record '{dns_record}'")
            
            return {
                'name': dns_record,
                'identifier': identifier,
                'surface': surface,
                'status': Asset.ACTIVE.value,
                'type': Kind.ASSET.value,
                'expected_key': f"#asset#{dns_record}#{identifier}"
            }
            
        elif asset_type == 'dns-dns':
            # For DNS-DNS, expect format: "dns_record|dns_identifier"
            if '|' not in asset_value:
                raise ValueError(f"DNS-DNS asset_value must be in format 'dns_record|dns_identifier', got: {asset_value}")
            
            parts = asset_value.split('|', 1)
            dns_record = parts[0].strip()
            dns_identifier = parts[1].strip()
            
            if not dns_record or not dns_identifier:
                raise ValueError("Both DNS record and DNS identifier must be non-empty")
            
            return {
                'name': dns_record,
                'identifier': dns_identifier,
                'surface': surface,
                'status': Asset.ACTIVE.value,
                'type': Kind.ASSET.value,
                'expected_key': f"#asset#{dns_record}#{dns_identifier}"
            }
            
        elif asset_type == 'aws':
            # For AWS, expect full ARN
            arn = asset_value.strip()
            
            if not arn.startswith('arn:aws:'):
                raise ValueError(f"AWS ARN should start with 'arn:aws:', got: {arn}")
            
            # Parse ARN to extract asset name
            arn_parts = arn.split(':')
            if len(arn_parts) < 6:
                raise ValueError(f"Invalid ARN format. Expected format: arn:aws:service:region:account:resource, got: {arn}")
            
            asset_name = ':'.join(arn_parts[5:])
            if not asset_name:
                raise ValueError("Could not extract asset name from ARN (last colon field is empty)")
            
            return {
                'name': asset_name,
                'identifier': arn,
                'surface': surface,
                'status': Asset.ACTIVE.value,
                'type': Kind.ASSET.value,
                'expected_key': f"#asset#{asset_name}#{arn}"
            }

        elif asset_type == 'azure':
            # For Azure, expect full Resource ID
            resource_id = asset_value.strip()

            # Validate Azure Resource ID format with relaxed rules
            if not (resource_id.startswith('/subscriptions/') or resource_id.startswith('/providers/')):
                raise ValueError(f"Azure Resource ID must start with '/subscriptions/' or '/providers/', got: {resource_id}")

            segments = [s for s in resource_id.split('/') if s]  # Remove empty segments
            if len(segments) < 3:
                raise ValueError(f"Azure Resource ID must have at least 3 segments, got {len(segments)} segments: {resource_id}")

            if '/providers/' not in resource_id:
                raise ValueError(f"Azure Resource ID must contain '/providers/': {resource_id}")

            # Extract asset name (last segment after final slash)
            asset_name = segments[-1]
            if not asset_name:
                raise ValueError("Could not extract asset name from Azure Resource ID (final segment is empty)")

            # Optional warning for unusual patterns (not an error)
            if len(segments) < 4 or len(segments) > 15:
                click.echo(f"    ⚠ Warning: Unusual Azure Resource ID format with {len(segments)} segments for resource '{asset_name}'")

            return {
                'name': asset_name,
                'identifier': resource_id,
                'surface': surface,
                'status': Asset.ACTIVE.value,
                'type': Kind.ASSET.value,
                'expected_key': f"#asset#{asset_name}#{resource_id}"
            }
        else:
            raise ValueError(f"Unsupported asset type: {asset_type}")


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


def process_definition_screenshots(sdk, definition_content, definition_file_path):
    """
    Process markdown definition content to find screenshots, upload them to Chariot,
    and replace local paths with Chariot file references.
    
    :param sdk: Chariot SDK instance
    :param definition_content: String content of the markdown definition file
    :param definition_file_path: Path to the original definition file for resolving relative paths
    :return: Tuple of (processed_content, success_flag)
    """
    # Regex pattern to match markdown image syntax: ![caption](filepath)
    image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    
    # Find all image references in the markdown
    image_matches = list(re.finditer(image_pattern, definition_content))
    
    if not image_matches:
        # No images found, return original content
        return definition_content, True
    
    # Track replacements to make
    replacements = []
    definition_dir = os.path.dirname(os.path.abspath(definition_file_path))
    
    click.echo(f"\n📸 Found screenshot references in definition file, processing...")
    
    for match in image_matches:
        caption = match.group(1)
        filepath = match.group(2)
        
        # Skip if this already looks like a Chariot file reference
        if filepath.startswith('#file/'):
            continue
            
        click.echo(f"   Processing: ![{caption}]({filepath})")
        
        # Resolve the actual file path
        if os.path.isabs(filepath):
            actual_filepath = filepath
        else:
            # Relative path - resolve relative to definition file location
            actual_filepath = os.path.join(definition_dir, filepath)
        
        # Normalize the path
        actual_filepath = os.path.normpath(actual_filepath)
        
        # Check if file exists
        if not os.path.exists(actual_filepath):
            click.echo(f"❌ Screenshot file not found: {actual_filepath}")
            return definition_content, False
        
        if not os.path.isfile(actual_filepath):
            click.echo(f"❌ Path is not a file: {actual_filepath}")
            return definition_content, False
        
        # Generate GUID for this screenshot
        screenshot_guid = str(uuid.uuid4())
        chariot_path = f"definitions/files/{screenshot_guid}"
        
        try:
            # Upload screenshot to Chariot
            result = sdk.files.add(actual_filepath, chariot_filepath=chariot_path)
            click.echo(f"   ✓ Uploaded: {os.path.basename(actual_filepath)} -> {chariot_path}")
            
            # Track this replacement
            old_ref = f"![{caption}]({filepath})"
            new_ref = f"![{caption}](#file/{chariot_path})"
            replacements.append((old_ref, new_ref))
            
        except Exception as e:
            click.echo(f"❌ Failed to upload screenshot {actual_filepath}: {e}")
            return definition_content, False
    
    # Apply all replacements to the content
    processed_content = definition_content
    for old_ref, new_ref in replacements:
        processed_content = processed_content.replace(old_ref, new_ref)
    
    click.echo(f"✓ Processed {len(replacements)} screenshot(s) in definition file")
    return processed_content, True


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
                # Read the definition file content
                with open(expanded_path, 'r', encoding='utf-8') as f:
                    definition_content = f.read()
                
                # Process any screenshots in the definition file
                processed_content, screenshot_success = process_definition_screenshots(
                    sdk, definition_content, expanded_path
                )
                
                if not screenshot_success:
                    click.echo("❌ Screenshot processing failed - definition upload cancelled")
                    if click.confirm("Try a different file?"):
                        continue
                    else:
                        return None
                
                # Create temporary file with processed content if screenshots were processed
                if processed_content != definition_content:
                    # Screenshots were processed, upload the modified content
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_file:
                        temp_file.write(processed_content)
                        temp_file.flush()
                        
                        try:
                            result = sdk.definitions.add(temp_file.name, definition_name)
                            click.echo(f"✓ Successfully uploaded definition file as: {definition_name}")
                            return definition_name
                        finally:
                            # Clean up temporary file
                            os.unlink(temp_file.name)
                else:
                    # No screenshots to process, upload original file
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
                # Step 1: Select asset type category
                asset_type_category = click.prompt(
                    "Select asset type",
                    type=click.Choice(['asset', 'ad-object'], case_sensitive=False),
                    default='asset',
                    show_choices=True
                )

                key_prefix = ''
                filter_value = ''
                ad_object_type = None

                if asset_type_category == 'asset':
                    # Step 2: Get DNS filter for regular assets
                    filter_value = click.prompt(
                        "Enter DNS hostname to filter by (leave empty for all assets)",
                        type=str,
                        default=""
                    ).strip()
                    if filter_value:
                        key_prefix = f'#asset#{filter_value}'
                        click.echo(f"💡 Searching assets with DNS prefix: '{filter_value}'")

                elif asset_type_category == 'ad-object':
                    # Step 2: Select specific AD object type
                    ad_object_type = click.prompt(
                        "Select AD object type",
                        type=click.Choice([
                            'addomain',
                            'aduser',
                            'adcomputer',
                            'adgroup',
                            'adgpo',
                            'adou',
                            'adcontainer',
                            'adlocalgroup',
                            'adlocaluser',
                            'adaiaca',
                            'adrootca',
                            'adenterpriseca',
                            'adntauthstore',
                            'adcerttemplate',
                            'adissuancepolicy'
                        ], case_sensitive=False),
                        default='addomain',
                        show_choices=True
                    )

                    # Step 3: Get AD domain filter
                    filter_value = click.prompt(
                        f"Enter AD domain to filter by (leave empty for all {ad_object_type} objects)",
                        type=str,
                        default=""
                    ).strip()
                    if filter_value:
                        key_prefix = f'#{ad_object_type}#{filter_value}'
                        click.echo(f"💡 Searching {ad_object_type} objects with domain prefix: '{filter_value}'")
                    else:
                        key_prefix = f'#{ad_object_type}#'

                # Get assets with optional filtering (load more pages for better selection)
                all_assets, _ = sdk.assets.list(key_prefix=key_prefix, pages=100000)  # Get more assets for better fzf experience
                if not all_assets:
                    asset_type_label = ad_object_type if ad_object_type else asset_type_category
                    if filter_value:
                        click.echo(f"No {asset_type_label} assets found matching filter: '{filter_value}'")
                    else:
                        click.echo(f"No {asset_type_label} assets found in your account.")
                    
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


class BulkFindingParser:
    """
    Parser class for handling bulk finding uploads from CSV files.
    """
    
    REQUIRED_COLUMNS = ['risk_id', 'asset_value', 'asset_type', 'asset_surface', 'risk_status']
    OPTIONAL_COLUMNS = ['definition_name', 'evidence_file']
    
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.asset_parser = ManualAssetParser()
    
    def parse(self):
        """
        Parse the bulk findings CSV file.
        
        :return: List of finding dictionaries
        """
        if self.file_path.suffix.lower() != '.csv':
            raise ValueError(f"Only CSV files are supported. Got: {self.file_path.suffix}")
        
        findings = []
        
        with open(self.file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Validate headers
            headers = set(reader.fieldnames)
            missing_required = set(self.REQUIRED_COLUMNS) - headers
            if missing_required:
                raise ValueError(f"Missing required columns in CSV: {missing_required}")
            
            for row_num, row in enumerate(reader, 2):  # Start at 2 since header is row 1
                try:
                    finding = self._validate_and_normalize_finding(row, row_num)
                    findings.append(finding)
                except ValueError as e:
                    click.echo(f"❌ Row {row_num}: {e}")
                    continue
        
        return findings
    
    def _validate_and_normalize_finding(self, finding, row_id):
        """
        Validate and normalize a single finding record.
        
        :param finding: Raw finding dict from CSV
        :param row_id: Row identifier for error reporting
        :return: Normalized finding dict
        """
        # Check required fields
        for field in self.REQUIRED_COLUMNS:
            field_value = finding.get(field, '') or ''
            if not field_value.strip():
                raise ValueError(f"Missing required field '{field}'")
        
        # Validate asset type
        asset_type = (finding.get('asset_type', '') or '').strip()
        if asset_type not in self.asset_parser.ASSET_TYPES:
            valid_types = list(self.asset_parser.ASSET_TYPES.keys())
            raise ValueError(f"Invalid asset_type '{asset_type}'. Must be one of: {valid_types}")
        
        # Validate risk status
        risk_status = (finding.get('risk_status', '') or '').strip()
        valid_statuses = [
            AddRisk.TRIAGE_INFO.value,
            AddRisk.TRIAGE_LOW.value,
            AddRisk.TRIAGE_MEDIUM.value,
            AddRisk.TRIAGE_HIGH.value,
            AddRisk.TRIAGE_CRITICAL.value
        ]
        if risk_status not in valid_statuses:
            raise ValueError(f"Invalid risk_status '{risk_status}'. Must be one of: {valid_statuses}")
        
        # Validate surface
        asset_surface = (finding.get('asset_surface', '') or '').strip()
        valid_surfaces = ['external', 'internal', 'web', 'api', 'cloud']
        if asset_surface not in valid_surfaces:
            raise ValueError(f"Invalid asset_surface '{asset_surface}'. Must be one of: {valid_surfaces}")
        
        # Parse asset value using ManualAssetParser
        asset_value = (finding.get('asset_value', '') or '').strip()
        try:
            parsed_asset = self.asset_parser.parse_asset_from_bulk_data(asset_type, asset_value, asset_surface)
        except Exception as e:
            raise ValueError(f"Error parsing asset: {e}")
        
        # Validate evidence file if provided
        evidence_file_raw = finding.get('evidence_file', '') or ''
        evidence_file = evidence_file_raw.strip() or None
        if evidence_file:
            # Expand user path (~) and resolve relative paths
            expanded_path = os.path.expanduser(evidence_file)
            if not os.path.isabs(expanded_path):
                # Make relative to current working directory
                expanded_path = os.path.join(os.getcwd(), expanded_path)
            
            # Normalize the path
            expanded_path = os.path.normpath(expanded_path)
            
            # Check if file exists
            if not os.path.exists(expanded_path):
                raise ValueError(f"Evidence file not found: {expanded_path}")
            
            if not os.path.isfile(expanded_path):
                raise ValueError(f"Evidence file path is not a file: {expanded_path}")
            
            evidence_file = expanded_path
        # If no evidence file provided, evidence_file remains None

        # Create normalized finding
        normalized = {
            'risk_id': finding['risk_id'].strip(),
            'asset_type': asset_type,
            'asset_value': asset_value,
            'parsed_asset': parsed_asset,
            'risk_status': risk_status,
            'definition_name': (finding.get('definition_name', '') or '').strip() or None,
            'evidence_file': evidence_file,
            'row_id': row_id
        }
        
        return normalized


def process_bulk_findings(sdk, bulk_file_path):
    """
    Process bulk findings from CSV file.
    
    :param sdk: Chariot SDK instance
    :param bulk_file_path: Path to CSV file
    """
    click.echo("🔍 Bulk Add Finding - CSV Processing Mode")
    click.echo("=" * 50)
    
    try:
        # Parse CSV file
        parser = BulkFindingParser(bulk_file_path)
        findings = parser.parse()
        
        if not findings:
            click.echo("❌ No valid findings found in CSV file.")
            return
        
        click.echo(f"✓ Parsed {len(findings)} finding(s) from CSV")
        
        # Group findings by risk_id for efficient processing
        findings_by_risk = {}
        for finding in findings:
            risk_id = finding['risk_id']
            if risk_id not in findings_by_risk:
                findings_by_risk[risk_id] = []
            findings_by_risk[risk_id].append(finding)
        
        # Display summary
        click.echo(f"\n📋 Processing summary:")
        click.echo(f"  • {len(findings)} total asset-risk associations")
        click.echo(f"  • {len(findings_by_risk)} unique risk IDs")
        
        total_new_assets = len([f for f in findings if f['parsed_asset']])
        click.echo(f"  • {total_new_assets} new assets to create")
        
        total_evidence_files = len([f for f in findings if f['evidence_file']])
        if total_evidence_files > 0:
            click.echo(f"  • {total_evidence_files} evidence files to upload")
        
        if not click.confirm("\nProceed with bulk processing?"):
            click.echo("Operation cancelled by user.")
            return
        
        # Process each risk group
        successful_count = 0
        for risk_id, risk_findings in findings_by_risk.items():
            click.echo(f"\n🔄 Processing risk: {risk_id}")
            
            try:
                # Create assets first
                asset_keys = []
                for finding in risk_findings:
                    asset_data = finding['parsed_asset']
                    try:
                        asset = sdk.assets.add(
                            asset_data['name'],
                            asset_data['identifier'],
                            surface=asset_data['surface'],
                            status=asset_data['status']
                        )
                        asset_key = asset.get('key')
                        if asset_key:
                            asset_keys.append(asset_key)
                            click.echo(f"  ✓ Created asset: {asset_key}")
                            
                            # Set surface attribute
                            try:
                                sdk.attributes.add(asset_key, 'surface', asset_data['surface'])
                            except Exception as e:
                                click.echo(f"    ⚠ Warning: Could not set surface attribute: {e}")
                        else:
                            click.echo(f"  ❌ Error: Asset created but no key returned for {asset_data['expected_key']}")
                    except Exception as e:
                        click.echo(f"  ❌ Error creating asset {asset_data['expected_key']}: {e}")
                
                # Associate risks with created assets
                for idx, finding in enumerate(risk_findings):
                    if idx < len(asset_keys):
                        asset_key = asset_keys[idx]
                        try:
                            risk = sdk.risks.add(
                                asset_key, 
                                risk_id, 
                                finding['risk_status'], 
                                None,
                                capability='manual-bulk-add-finding'
                            )
                            click.echo(f"  ✓ Associated risk '{risk_id}' with asset {asset_key}")
                            
                            # Add definition if specified
                            if finding['definition_name']:
                                try:
                                    sdk.attributes.add(risk['key'], 'definition', finding['definition_name'])
                                    click.echo(f"    ✓ Associated definition: {finding['definition_name']}")
                                except Exception as e:
                                    click.echo(f"    ⚠ Warning: Could not associate definition: {e}")
                            
                            # Upload evidence file if specified
                            if finding['evidence_file']:
                                try:
                                    upload_evidence_to_risk(sdk, risk['key'], finding['evidence_file'])
                                    click.echo(f"    ✓ Uploaded evidence: {os.path.basename(finding['evidence_file'])}")
                                except Exception as e:
                                    click.echo(f"    ⚠ Warning: Could not upload evidence: {e}")
                            
                            successful_count += 1
                            
                        except Exception as e:
                            click.echo(f"  ❌ Error adding risk to asset {asset_key}: {e}")
                
            except Exception as e:
                click.echo(f"❌ Error processing risk {risk_id}: {e}")
        
        # Final summary
        click.echo(f"\n✅ Bulk processing completed!")
        click.echo(f"Successfully processed {successful_count} out of {len(findings)} asset-risk associations")
        
    except Exception as e:
        click.echo(f"❌ Error during bulk processing: {e}")


def collect_evidence_for_risks(sdk, risk_associations):
    """
    Collect evidence files for associated risks after they've been created.
    
    :param sdk: Chariot SDK instance
    :param risk_associations: List of dicts with 'risk_key', 'risk_id', 'asset_key' info
    :return: Dict mapping risk_key to evidence info
    """
    if not risk_associations:
        return {}
    
    click.echo(f"\n📎 Evidence Collection")
    click.echo("=" * 30)
    
    if not click.confirm("Do you want to add evidence files to these risks?"):
        return {}
    
    evidence_mapping = {}
    
    # Ask user about evidence strategy
    if len(risk_associations) > 1:
        click.echo(f"\nYou have {len(risk_associations)} risk-asset associations.")
        same_evidence = click.confirm("Do you want to use the same evidence file for all risks?")
    else:
        same_evidence = False
    
    if same_evidence:
        # Collect one evidence file for all risks
        click.echo(f"\n📁 Select evidence file to use for all {len(risk_associations)} risks:")
        evidence_file = prompt_for_evidence_file()
        if evidence_file:
            # Upload evidence for each risk
            for association in risk_associations:
                try:
                    upload_evidence_to_risk(sdk, association['risk_key'], evidence_file)
                    evidence_mapping[association['risk_key']] = evidence_file
                    click.echo(f"✓ Uploaded evidence for risk '{association['risk_id']}' on asset '{association['asset_key']}'")
                except Exception as e:
                    click.echo(f"❌ Error uploading evidence for risk '{association['risk_id']}': {e}")
    else:
        # Collect evidence individually for each risk
        for association in risk_associations:
            click.echo(f"\n📁 Evidence for risk '{association['risk_id']}' on asset '{association['asset_key']}':")
            if click.confirm("Add evidence for this specific risk?"):
                evidence_file = prompt_for_evidence_file()
                if evidence_file:
                    try:
                        upload_evidence_to_risk(sdk, association['risk_key'], evidence_file)
                        evidence_mapping[association['risk_key']] = evidence_file
                        click.echo(f"✓ Uploaded evidence for risk '{association['risk_id']}'")
                    except Exception as e:
                        click.echo(f"❌ Error uploading evidence: {e}")
    
    return evidence_mapping


def prompt_for_evidence_file():
    """
    Prompt user for evidence file path with validation.
    Similar to definition file prompting but for evidence.
    
    :return: Expanded file path or None if cancelled
    """
    click.echo("💡 Evidence file path can be:")
    click.echo("   • Absolute path: /full/path/to/screenshot.png")
    click.echo("   • Relative to current directory: ./evidence/screenshot.png")
    click.echo("   • Relative to home directory: ~/Documents/evidence.pdf")
    
    # Show current working directory to help user
    current_dir = os.getcwd()
    click.echo(f"📁 Current directory: {current_dir}")
    
    while True:
        local_path = click.prompt("Enter path to evidence file", type=str)
        
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
        
        return expanded_path


def upload_evidence_to_risk(sdk, risk_key, evidence_file_path):
    """
    Upload evidence file to Chariot at the path "evidence/<risk_key>".
    If the evidence file is markdown and contains screenshots, process them first.
    
    :param sdk: Chariot SDK instance
    :param risk_key: The risk key to associate evidence with
    :param evidence_file_path: Local path to evidence file
    """
    evidence_filename = os.path.basename(evidence_file_path)
    chariot_path = f"evidence/{risk_key}"
    
    try:
        # Check if this is a markdown file that might contain screenshots
        if evidence_file_path.lower().endswith(('.md', '.markdown')):
            # Read the evidence file content
            with open(evidence_file_path, 'r', encoding='utf-8') as f:
                evidence_content = f.read()
            
            # Process any screenshots in the evidence file
            processed_content, screenshot_success = process_definition_screenshots(
                sdk, evidence_content, evidence_file_path
            )
            
            if not screenshot_success:
                raise Exception("Screenshot processing failed")
            
            # Upload processed content if screenshots were found and processed
            if processed_content != evidence_content:
                # Screenshots were processed, upload the modified content
                with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(processed_content)
                    temp_file.flush()
                    
                    try:
                        result = sdk.files.add(temp_file.name, chariot_filepath=chariot_path)
                        click.echo(f"  ✓ Evidence uploaded: {evidence_filename} -> {chariot_path}")
                    finally:
                        # Clean up temporary file
                        os.unlink(temp_file.name)
            else:
                # No screenshots to process, upload original file
                result = sdk.files.add(evidence_file_path, chariot_filepath=chariot_path)
                click.echo(f"  ✓ Evidence uploaded: {evidence_filename} -> {chariot_path}")
        else:
            # Not a markdown file, upload directly
            result = sdk.files.add(evidence_file_path, chariot_filepath=chariot_path)
            click.echo(f"  ✓ Evidence uploaded: {evidence_filename} -> {chariot_path}")
        
    except Exception as e:
        raise Exception(f"Failed to upload evidence: {e}")


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
    risk_associations = []  # Track successful risk associations for evidence collection
    
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
                
                # Track risk association for evidence collection
                risk_associations.append({
                    'risk_key': risk['key'],
                    'risk_id': risk_id,
                    'asset_key': asset_key
                })
                
                # Add definition as an attribute if specified
                if definition_name:
                    try:
                        sdk.attributes.add(risk['key'], 'definition', definition_name)
                        click.echo(f"  ✓ Associated definition file '{definition_name}' with the risk")
                    except Exception as e:
                        click.echo(f"  ⚠ Warning: Could not associate definition file: {e}")
                        
            except Exception as e:
                click.echo(f"❌ Error adding risk to asset {asset_key}: {e}")
    
    # Collect evidence for successfully created risk associations
    if risk_associations:
        collect_evidence_for_risks(sdk, risk_associations)
    
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
@click.option('--bulk', type=click.Path(exists=True), help='Path to CSV file for bulk processing')
@cli_handler
def add_finding_command(sdk, bulk):
    """
    Interactive script for adding security findings/risks to assets.
    
    Supports two modes:
    - Interactive mode (default): Guides you through entering risk and asset information
    - Bulk mode (--bulk): Processes findings from a CSV file
    """
    if bulk:
        # Bulk processing mode
        process_bulk_findings(sdk, bulk)
    else:
        # Interactive mode (existing workflow)
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
