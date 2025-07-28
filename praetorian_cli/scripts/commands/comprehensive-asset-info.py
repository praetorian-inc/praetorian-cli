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


def get_error_diagnosis(error_details):
    """Provide specific diagnosis based on error details"""
    if not error_details:
        return "Unknown authentication error"
    
    error_lower = error_details.lower()
    
    if "user pool client" in error_lower and "does not exist" in error_lower:
        return "Cognito user pool client configuration issue - CLI environment mismatch"
    elif "resourcenotfoundexception" in error_lower:
        return "AWS resource not found - likely environment or region configuration issue"
    elif "accessdenied" in error_lower:
        return "Access denied - credential or permission issue"
    elif "invaliduserpoolconfiguration" in error_lower:
        return "User pool configuration problem"
    elif "tokenexpired" in error_lower or "expired" in error_lower:
        return "Authentication token has expired"
    else:
        return f"Unrecognized authentication error: {error_details[:100]}..."


@click.command('comprehensive-asset-info')
@click.argument('asset_key', required=True)
@click.option('--output-dir', '-o', default='.', help='Output directory for the JSON file')
@click.option('--include-file-content', '-c', is_flag=True, default=False, 
              help='Include file contents for small files (< 1MB)')
@click.option('--debug', '-d', is_flag=True, default=False, help='Enable debug output')
@cli_handler
def comprehensive_asset_info_command(sdk, asset_key, output_dir, include_file_content, debug):
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
    
    try:
        click.echo("=== COMPREHENSIVE ASSET INFO COLLECTOR ===")
        click.echo(f"Starting collection for asset: {asset_key}")
        click.echo(f"Output directory: {output_dir}")
        click.echo(f"Include file content: {include_file_content}")
        click.echo(f"Debug mode: {debug}")
        
        if debug:
            click.echo(f"SDK object: {sdk}")
            click.echo(f"SDK type: {type(sdk)}")
        
        asset_data = {
            "asset_key": asset_key,
            "collection_timestamp": datetime.now().isoformat(),
            "asset_details": None,
            "asset_attributes": [],
            "asset_risks": [],
            "risk_definitions": [],
            "associated_files": []
        }
        
        click.echo("\n🔐 Testing authentication...")
        auth_working = False
        auth_error_details = None
        
        try:
            test_result, _ = sdk.search.by_term("test")
            click.echo("✅ Authentication successful")
            auth_working = True
        except Exception as auth_error:
            click.echo("❌ Authentication failed!", err=True)
            auth_error_details = str(auth_error)
            
            if "ResourceNotFoundException" in auth_error_details:
                if "User pool client" in auth_error_details:
                    click.echo("🔍 DIAGNOSIS: Cognito user pool client configuration issue")
                    click.echo("   This typically means the CLI is not properly configured for your environment")
                elif "does not exist" in auth_error_details:
                    click.echo("🔍 DIAGNOSIS: AWS resource not found")
                    click.echo("   This suggests environment or region configuration issues")
            elif "AccessDenied" in auth_error_details:
                click.echo("🔍 DIAGNOSIS: Access denied - credential or permission issue")
            elif "InvalidUserPoolConfiguration" in auth_error_details:
                click.echo("🔍 DIAGNOSIS: User pool configuration problem")
            else:
                click.echo(f"🔍 DIAGNOSIS: Unknown authentication error: {auth_error_details}")
            
            click.echo("\n📋 AUTHENTICATION TROUBLESHOOTING STEPS:")
            click.echo("1. 🔑 Login: Run 'praetorian chariot login' to authenticate")
            click.echo("2. 🔄 Refresh: If already logged in, try logging out and back in")
            click.echo("3. 🌐 Environment: Verify you're connecting to the correct environment")
            click.echo("4. ⏰ Expiry: Check if your credentials have expired")
            click.echo("5. 🔧 Config: Verify your CLI configuration with 'praetorian chariot config'")
            click.echo("6. 🏥 Health: Test basic connectivity with 'praetorian chariot list assets --page first'")
            click.echo("\n💡 ADDITIONAL DIAGNOSTICS:")
            click.echo(f"   Error details: {auth_error_details}")
            click.echo("   If this persists, contact your administrator with the above error details")
            
            click.echo("\n⚠️  The script will continue but all API calls will fail.")
            click.echo("   A diagnostic file will still be created with troubleshooting information.")
        
        click.echo("\n1. Collecting asset details...")
        if not auth_working:
            click.echo("⚠️ Skipping asset details due to authentication failure")
            asset_data["error"] = "Authentication failed - unable to collect data"
            asset_data["auth_error_details"] = auth_error_details
            asset_identifier = sanitize_filename(asset_key.replace('#', '_').replace('/', '_'))
        else:
            try:
                asset_details = sdk.assets.get(asset_key, details=True)
                if debug:
                    click.echo(f"Asset details response: {asset_details}")
                asset_data["asset_details"] = asset_details
                
                if not asset_details:
                    click.echo(f"❌ Asset {asset_key} not found!", err=True)
                    asset_data["error"] = "Asset not found"
                    asset_identifier = "asset_not_found"
                else:
                    click.echo("✅ Asset details collected successfully")
                    asset_identifier = asset_details.get('dns', asset_details.get('identifier', 'unknown_asset'))
                    click.echo(f"Asset identifier: {asset_identifier}")
            except Exception as e:
                click.echo(f"❌ Error getting asset details: {e}", err=True)
                if debug:
                    import traceback
                    click.echo(f"Traceback: {traceback.format_exc()}")
                asset_data["error"] = f"Error getting asset details: {e}"
                asset_identifier = "error_asset"
        
        collection_steps = [
            ("asset attributes", lambda: sdk.assets.attributes(asset_key)),
            ("asset risks", lambda: sdk.assets.associated_risks(asset_key)),
            ("risk definitions", lambda: sdk.definitions.list()),
        ]
        
        for step_num, (step_name, step_func) in enumerate(collection_steps, 2):
            click.echo(f"\n{step_num}. Collecting {step_name}...")
            if not auth_working:
                click.echo(f"⚠️ Skipping {step_name} due to authentication failure")
            else:
                try:
                    if step_name == "risk definitions":
                        result, _ = step_func()
                        asset_data["risk_definitions"] = result
                        click.echo(f"✅ Found {len(result)} {step_name}")
                        if debug and result:
                            click.echo(f"Sample {step_name}: {result[:2]}")
                    else:
                        result = step_func()
                        key = step_name.replace(" ", "_")
                        asset_data[key] = result
                        click.echo(f"✅ Found {len(result)} {step_name}")
                        if debug and result:
                            click.echo(f"Sample {step_name}: {result[:2]}")
                except Exception as e:
                    click.echo(f"❌ Error getting {step_name}: {e}", err=True)
                    if debug:
                        import traceback
                        click.echo(f"Traceback: {traceback.format_exc()}")
        
        click.echo("\n5. Collecting associated files...")
        if not auth_working:
            click.echo("⚠️ Skipping file collection due to authentication failure")
        else:
            try:
                if 'asset_identifier' in locals():
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
                    click.echo(f"✅ Total unique files found: {len(unique_files)}")
                else:
                    click.echo("⚠️ Skipping file collection due to missing asset identifier")
            except Exception as e:
                click.echo(f"❌ Error collecting files: {e}", err=True)
                if debug:
                    import traceback
                    click.echo(f"Traceback: {traceback.format_exc()}")
        
        if include_file_content and asset_data["associated_files"] and auth_working:
            click.echo("\n6. Downloading file contents...")
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
        elif include_file_content and not auth_working:
            click.echo("\n6. Skipping file content download due to authentication failure")
        
        if not auth_working:
            asset_data["troubleshooting"] = {
                "authentication_failed": True,
                "error_details": auth_error_details,
                "diagnosis": get_error_diagnosis(auth_error_details),
                "troubleshooting_steps": [
                    "Run 'praetorian chariot login' to authenticate",
                    "If already logged in, try logging out and back in",
                    "Verify you're connecting to the correct environment",
                    "Check if your credentials have expired",
                    "Verify your CLI configuration with 'praetorian chariot config'",
                    "Test basic connectivity with 'praetorian chariot list assets --page first'",
                    "Contact your administrator if the issue persists"
                ],
                "common_solutions": {
                    "cognito_user_pool_error": "Usually indicates CLI environment configuration issue - try 'praetorian chariot login'",
                    "access_denied": "Check your credentials and permissions",
                    "resource_not_found": "Verify environment and region configuration"
                },
                "next_steps": "Fix authentication and re-run this script to collect actual asset data"
            }
            
        click.echo("\n7. Saving results...")
        safe_identifier = sanitize_filename(asset_identifier)
        output_filename = f"{safe_identifier}_comprehensive_info.json"
        output_path = os.path.join(output_dir, output_filename)
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(asset_data, f, indent=2, default=str)
        
        if auth_working:
            click.echo(f"✅ Comprehensive asset information saved to: {output_path}")
        else:
            click.echo(f"🔧 Diagnostic information saved to: {output_path}")
            click.echo("   This file contains troubleshooting steps and error details.")
            click.echo("   Fix authentication and re-run to collect complete asset data.")
        
        click.echo("\n=== COLLECTION SUMMARY ===")
        click.echo(f"Asset Key: {asset_key}")
        click.echo(f"Asset Identifier: {asset_identifier}")
        click.echo(f"Authentication: {'✓' if auth_working else '✗'}")
        click.echo(f"Asset Details: {'✓' if asset_data['asset_details'] else '✗'}")
        click.echo(f"Attributes: {len(asset_data['asset_attributes'])}")
        click.echo(f"Risks: {len(asset_data['asset_risks'])}")
        click.echo(f"Risk Definitions: {len(asset_data['risk_definitions'])}")
        click.echo(f"Associated Files: {len(asset_data['associated_files'])}")
        click.echo(f"Output File: {output_path}")
        if not auth_working:
            click.echo("⚠️  Authentication failed - see troubleshooting section in output file")
        click.echo("=== COLLECTION COMPLETE ===")
        
    except Exception as e:
        click.echo(f"❌ FATAL ERROR: {e}", err=True)
        import traceback
        click.echo(f"Full traceback: {traceback.format_exc()}", err=True)
        raise


def register(script_group: click.MultiCommand):
    """Register the comprehensive asset info command with the script group"""
    script_group.add_command(comprehensive_asset_info_command)
