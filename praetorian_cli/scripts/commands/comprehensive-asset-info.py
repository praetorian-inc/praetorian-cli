"""
Comprehensive Asset Information Collector

This script collects all information associated with an asset including:
- Asset details with attributes and risks
- All asset attributes  
- All vulnerabilities/risks for the asset
- All risk definitions
- All files associated with the asset

Usage: praetorian chariot script comprehensive-asset-info <asset_key>
Example: praetorian chariot script comprehensive-asset-info "#asset#example.com#domain"
"""

import json
import os
from datetime import datetime

import click
from praetorian_cli.handlers.cli_decorators import cli_handler


def sanitize_filename(filename):
    """Sanitize filename for safe file creation"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


@click.command('comprehensive-asset-info')
@click.argument('asset_key', required=True)
@click.option('--output-dir', '-o', default='.', help='Output directory for the JSON file')
@click.option('--include-file-content', '-c', is_flag=True, default=False, 
              help='Include file contents for small files (< 1MB)')
@cli_handler
def comprehensive_asset_info_command(sdk, asset_key, output_dir, include_file_content):
    """Collect comprehensive information about an asset
    
    ASSET_KEY is the full key of the asset (e.g., "#asset#example.com#domain")
    
    This command collects:
    - Asset details with attributes and risks
    - All asset attributes
    - All vulnerabilities/risks for the asset  
    - All risk definitions
    - All files associated with the asset
    
    The collected data is saved to a JSON file named after the asset.
    """
    
    click.echo(f"Collecting comprehensive information for asset: {asset_key}")
    
    asset_data = {
        "asset_key": asset_key,
        "collection_timestamp": datetime.now().isoformat(),
        "asset_details": None,
        "asset_attributes": [],
        "asset_risks": [],
        "risk_definitions": [],
        "associated_files": []
    }
    
    try:
        click.echo("Collecting asset details...")
        asset_details = sdk.assets.get(asset_key, details=True)
        asset_data["asset_details"] = asset_details
        
        if not asset_details:
            click.echo(f"Asset {asset_key} not found!", err=True)
            return
            
        asset_identifier = asset_details.get('dns', asset_details.get('identifier', 'unknown_asset'))
        
        click.echo("Collecting asset attributes...")
        asset_attributes = sdk.assets.attributes(asset_key)
        asset_data["asset_attributes"] = asset_attributes
        click.echo(f"Found {len(asset_attributes)} attributes")
        
        click.echo("Collecting asset risks...")
        asset_risks = sdk.assets.associated_risks(asset_key)
        asset_data["asset_risks"] = asset_risks
        click.echo(f"Found {len(asset_risks)} risks")
        
        click.echo("Collecting risk definitions...")
        definitions, _ = sdk.definitions.list()
        asset_data["risk_definitions"] = definitions
        click.echo(f"Found {len(definitions)} risk definitions")
        
        click.echo("Collecting associated files...")
        
        file_prefixes = [
            asset_identifier,
            f"whois/{asset_identifier}",
            f"whois-history/{asset_identifier}",
            f"proofs/{asset_identifier}",
        ]
        
        all_files = []
        for prefix in file_prefixes:
            try:
                files, _ = sdk.files.list(prefix_filter=prefix)
                if files:
                    all_files.extend(files)
                    click.echo(f"Found {len(files)} files with prefix '{prefix}'")
            except Exception as e:
                click.echo(f"Error searching files with prefix '{prefix}': {e}", err=True)
        
        try:
            all_available_files, _ = sdk.files.list()
            related_files = [f for f in all_available_files if asset_identifier in f.get('name', '')]
            all_files.extend(related_files)
            if related_files:
                click.echo(f"Found {len(related_files)} additional files containing '{asset_identifier}'")
        except Exception as e:
            click.echo(f"Error searching all files: {e}", err=True)
        
        seen_files = set()
        unique_files = []
        for file_info in all_files:
            file_key = file_info.get('key', file_info.get('name', ''))
            if file_key not in seen_files:
                seen_files.add(file_key)
                unique_files.append(file_info)
        
        asset_data["associated_files"] = unique_files
        click.echo(f"Total unique files found: {len(unique_files)}")
        
        if include_file_content:
            click.echo("Downloading file contents...")
            for file_info in asset_data["associated_files"]:
                file_name = file_info.get('name', '')
                if file_name:
                    try:
                        file_size = file_info.get('size', 0)
                        if file_size < 1024 * 1024:
                            content = sdk.files.get_utf8(file_name)
                            file_info['content'] = content
                            click.echo(f"Downloaded content for: {file_name}")
                        else:
                            file_info['content'] = f"File too large ({file_size} bytes) - content not downloaded"
                    except Exception as e:
                        file_info['content'] = f"Error downloading file: {e}"
                        click.echo(f"Error downloading {file_name}: {e}", err=True)
        
        safe_identifier = sanitize_filename(asset_identifier)
        output_filename = f"{safe_identifier}_comprehensive_info.json"
        output_path = os.path.join(output_dir, output_filename)
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(asset_data, f, indent=2, default=str)
        
        click.echo(f"\nComprehensive asset information saved to: {output_path}")
        
        click.echo("\n=== COLLECTION SUMMARY ===")
        click.echo(f"Asset Key: {asset_key}")
        click.echo(f"Asset Identifier: {asset_identifier}")
        click.echo(f"Asset Details: {'✓' if asset_data['asset_details'] else '✗'}")
        click.echo(f"Attributes: {len(asset_data['asset_attributes'])}")
        click.echo(f"Risks: {len(asset_data['asset_risks'])}")
        click.echo(f"Risk Definitions: {len(asset_data['risk_definitions'])}")
        click.echo(f"Associated Files: {len(asset_data['associated_files'])}")
        click.echo(f"Output File: {output_path}")
        
    except Exception as e:
        click.echo(f"Error collecting asset information: {e}", err=True)
        raise


def register(script_group: click.MultiCommand):
    """Register the comprehensive asset info command with the script group"""
    script_group.add_command(comprehensive_asset_info_command)
