import sys
import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import error, print_json


@chariot.group()
def onboarding():
    """Cloud onboarding and tenant configuration"""
    pass


@onboarding.command('cloud-init')
@cli_handler
@praetorian_only
@click.option('--provider', required=True, type=click.Choice(['aws', 'azure', 'gcp']),
              help='Cloud provider')
@click.option('--deployment-type', required=True,
              type=click.Choice(['cloudformation', 'terraform', 'manual']),
              help='Deployment method')
def cloud_init(chariot, provider, deployment_type):
    """Initialize cloud integration (reads provider config JSON from stdin)

    Stdin JSON should contain provider-specific fields:
      AWS: account_id, org_account_id, external_id, image_scanning, call_as, targets
      Azure: tenant_id, subscription_id
      GCP: org_id, project_id, workload_pool_id, workload_provider_id
    """
    if sys.stdin.isatty():
        error('Pipe JSON input via stdin (e.g., echo \'{"account_id":"..."}\' | guard onboarding cloud-init ...)')
    raw = sys.stdin.read().strip()
    try:
        config = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        error(f'Invalid JSON input: {e}', quit=True)
    config['provider'] = provider
    config['deployment_type'] = deployment_type
    print_json(chariot.onboarding.cloud_initialize(config))


@onboarding.command('get-domains')
@cli_handler
@praetorian_only
def get_domains(chariot):
    """Get allowed customer domains"""
    print_json(chariot.onboarding.get_customer_domains())


@onboarding.command('set-domains')
@cli_handler
@praetorian_only
def set_domains(chariot):
    """Set allowed customer domains (reads JSON array from stdin)"""
    if sys.stdin.isatty():
        error('Pipe JSON input via stdin (e.g., echo \'["example.com"]\' | guard onboarding set-domains)')
    raw = sys.stdin.read().strip()
    if not raw:
        error('Domains JSON array is required via stdin', quit=True)
    try:
        domains = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f'Invalid JSON input: {e}', quit=True)
    print_json(chariot.onboarding.set_customer_domains(domains))


@onboarding.command('verify-host-overrides')
@cli_handler
@praetorian_only
def verify_host_overrides(chariot):
    """Verify host override settings (reads JSON map of host->IP from stdin)"""
    if sys.stdin.isatty():
        error('Pipe JSON input via stdin (e.g., echo \'{"host":"1.2.3.4"}\' | guard onboarding verify-host-overrides)')
    raw = sys.stdin.read().strip()
    if not raw:
        error('Host overrides JSON map is required via stdin', quit=True)
    try:
        overrides = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f'Invalid JSON input: {e}', quit=True)
    print_json(chariot.onboarding.verify_host_overrides(overrides))


@onboarding.command('get-scim-settings')
@cli_handler
@praetorian_only
def get_scim_settings(chariot):
    """Get SCIM tenant settings"""
    print_json(chariot.onboarding.get_scim_settings())


@onboarding.command('set-scim-settings')
@cli_handler
@praetorian_only
def set_scim_settings(chariot):
    """Update SCIM tenant settings (reads JSON from stdin)

    JSON fields: scim_managed (bool), default_scim_role (readonly|analyst|admin),
    scim_identity_claim (string), group_role_mapping (object)
    """
    if sys.stdin.isatty():
        error('Pipe JSON input via stdin (e.g., echo \'{"scim_managed":true}\' | guard onboarding set-scim-settings)')
    raw = sys.stdin.read().strip()
    if not raw:
        error('SCIM settings JSON is required via stdin', quit=True)
    try:
        settings = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f'Invalid JSON input: {e}', quit=True)
    print_json(chariot.onboarding.set_scim_settings(settings))
