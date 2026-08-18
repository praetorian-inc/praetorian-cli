import json
import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json


def _read_json_body():
    data = sys.stdin.read().strip()
    if not data:
        raise click.UsageError('No JSON body provided on stdin')
    return json.loads(data)


@chariot.group('red-team')
def red_team():
    """ Red Team operations """
    pass


# ===================== Deployment =====================

@red_team.group()
def deployment():
    """ Red Team deployment lifecycle """
    pass


@deployment.command()
@cli_handler
@praetorian_only
@click.option('--id', 'desired_id', default=None, help='Desired deployment ID')
def launch(sdk, desired_id):
    """ Launch a new Red Team deployment

    \b
    Example usages:
        guard red-team deployment launch
        guard red-team deployment launch --id my-deploy
    """
    print_json(sdk.red_team.deployment_launch(desired_id=desired_id))


@deployment.command('delete')
@cli_handler
@praetorian_only
@click.option('--force', is_flag=True, default=False, help='Force deletion')
@click.confirmation_option(prompt='Delete the Red Team deployment?')
def deploy_delete(sdk, force):
    """ Delete the Red Team deployment

    \b
    Prompts for confirmation.

    \b
    Example usages:
        guard red-team deployment delete
        guard red-team deployment delete --force
    """
    print_json(sdk.red_team.deployment_delete(force=force))


@deployment.command()
@cli_handler
@praetorian_only
def details(sdk):
    """ Get current deployment details

    \b
    Example usages:
        guard red-team deployment details
    """
    print_json(sdk.red_team.deployment_details())


@deployment.command()
@cli_handler
@praetorian_only
def history(sdk):
    """ Get deployment history

    \b
    Example usages:
        guard red-team deployment history
    """
    print_json(sdk.red_team.deployment_history())


@deployment.command('last-inputs')
@cli_handler
@praetorian_only
def last_inputs(sdk):
    """ Get the last submitted builder configuration

    \b
    Example usages:
        guard red-team deployment last-inputs
    """
    print_json(sdk.red_team.deployment_last_inputs())


@deployment.command('node-schema')
@cli_handler
@praetorian_only
@click.option('--tag', default=None, help='Infrastructure version tag')
def node_schema(sdk, tag):
    """ Get the node catalog schema for infrastructure

    \b
    Example usages:
        guard red-team deployment node-schema
        guard red-team deployment node-schema --tag v1.2.3
    """
    print_json(sdk.red_team.deployment_node_schema(tag=tag))


@deployment.command()
@cli_handler
@praetorian_only
@click.option('--tag', default=None, help='Infrastructure version tag')
@click.option('--sha', default=None, help='Git commit SHA')
def plan(sdk, tag, sha):
    """ Run terraform plan from a builder state JSON on stdin

    \b
    Example usages:
        cat builder.json | guard red-team deployment plan
    """
    print_json(sdk.red_team.deployment_terraform(
        'plan', _read_json_body(), tag=tag, sha=sha))


@deployment.command()
@cli_handler
@praetorian_only
@click.option('--tag', default=None, help='Infrastructure version tag')
@click.option('--sha', default=None, help='Git commit SHA')
@click.confirmation_option(prompt='Apply the Terraform deployment?')
def apply(sdk, tag, sha):
    """ Run terraform apply from a builder state JSON on stdin

    \b
    Prompts for confirmation.

    \b
    Example usages:
        cat builder.json | guard red-team deployment apply
    """
    print_json(sdk.red_team.deployment_terraform(
        'apply', _read_json_body(), tag=tag, sha=sha))


@deployment.command()
@cli_handler
@praetorian_only
@click.option('--collaborators', required=True,
              help='Comma-separated list of collaborator emails')
def collaborators(sdk, collaborators):
    """ Update deployment collaborators

    \b
    Example usages:
        guard red-team deployment collaborators --collaborators user1@co.com,user2@co.com
    """
    collabs = [c.strip() for c in collaborators.split(',')]
    print_json(sdk.red_team.deployment_collaborators(collabs))


# ===================== Campaigns =====================

@red_team.group()
def campaign():
    """ Red Team phishing campaigns """
    pass


@campaign.command()
@cli_handler
@praetorian_only
def create(sdk):
    """ Create or update a campaign from JSON on stdin

    \b
    Example usages:
        cat campaign.json | guard red-team campaign create
    """
    print_json(sdk.red_team.campaign_create(_read_json_body()))


@campaign.command('delete')
@cli_handler
@praetorian_only
@click.option('--key', required=True, help='Campaign key')
def campaign_delete(sdk, key):
    """ Delete a campaign

    \b
    Example usages:
        guard red-team campaign delete --key "#campaign#my-campaign"
    """
    print_json(sdk.red_team.campaign_delete(key))


@campaign.command()
@cli_handler
@praetorian_only
@click.option('--id', 'campaign_id', required=True, help='Campaign ID')
@click.option('--segment', default=None, help='Target segment name')
def targets(sdk, campaign_id, segment):
    """ Set campaign targets from JSON on stdin

    \b
    Replaces the full target roster.

    \b
    Example usages:
        cat targets.json | guard red-team campaign targets --id camp-1
    """
    body = _read_json_body()
    target_list = body.get('targets', body) if isinstance(body, dict) else body
    print_json(sdk.red_team.campaign_targets(
        campaign_id, target_list, segment=segment))


@campaign.command()
@cli_handler
@praetorian_only
@click.option('--id', 'campaign_id', required=True, help='Campaign ID')
def authorize(sdk, campaign_id):
    """ Authorize a campaign to go live

    \b
    Example usages:
        guard red-team campaign authorize --id camp-1
    """
    print_json(sdk.red_team.campaign_authorize(campaign_id))


@campaign.command()
@cli_handler
@praetorian_only
@click.option('--id', 'campaign_id', required=True, help='Campaign ID')
def funnel(sdk, campaign_id):
    """ Get campaign funnel metrics

    \b
    Example usages:
        guard red-team campaign funnel --id camp-1
    """
    print_json(sdk.red_team.campaign_funnel(campaign_id))


@campaign.command()
@cli_handler
@praetorian_only
@click.option('--id', 'campaign_id', required=True, help='Campaign ID')
@click.option('--limit', type=int, default=None, help='Max events (default 50)')
def activity(sdk, campaign_id, limit):
    """ Get campaign activity events

    \b
    Example usages:
        guard red-team campaign activity --id camp-1
        guard red-team campaign activity --id camp-1 --limit 100
    """
    print_json(sdk.red_team.campaign_activity(campaign_id, limit=limit))


# ===================== Domain parking =====================

@red_team.group()
def domain():
    """ Red Team domain parking and DNS """
    pass


@domain.command()
@cli_handler
@praetorian_only
def update(sdk):
    """ Update a parked domain from JSON on stdin

    \b
    Example usages:
        echo '{"domain":"evil.com","status":"in-use"}' | guard red-team domain update
    """
    print_json(sdk.red_team.domain_update(_read_json_body()))


@domain.command('dns-list')
@cli_handler
@praetorian_only
@click.option('--domain', required=True, help='Domain name')
def dns_list(sdk, domain):
    """ List DNS records for a parked domain

    \b
    Example usages:
        guard red-team domain dns-list --domain evil.com
    """
    print_json(sdk.red_team.dns_list(domain))


@domain.command('dns-create')
@cli_handler
@praetorian_only
@click.option('--domain', required=True, help='Domain name')
@click.option('--type', 'record_type', required=True,
              type=click.Choice(['A', 'CNAME', 'MX', 'TXT']),
              help='Record type')
@click.option('--name', required=True, help='Record name')
@click.option('--content', required=True, help='Record value')
@click.option('--ttl', type=int, default=1, help='TTL in seconds (1=auto)')
def dns_create(sdk, domain, record_type, name, content, ttl):
    """ Create a DNS record for a parked domain

    \b
    Example usages:
        guard red-team domain dns-create --domain evil.com --type A --name www --content 1.2.3.4
    """
    print_json(sdk.red_team.dns_create(domain, record_type, name, content, ttl))


@domain.command('dns-delete')
@cli_handler
@praetorian_only
@click.option('--domain', required=True, help='Domain name')
@click.option('--record-id', required=True, help='DNS record ID')
def dns_delete(sdk, domain, record_id):
    """ Delete a DNS record

    \b
    Example usages:
        guard red-team domain dns-delete --domain evil.com --record-id abc123
    """
    print_json(sdk.red_team.dns_delete(domain, record_id))


@domain.command('mailgun-status')
@cli_handler
@praetorian_only
@click.option('--domain', required=True, help='Domain name')
def mailgun_status(sdk, domain):
    """ Get Mailgun domain status

    \b
    Example usages:
        guard red-team domain mailgun-status --domain evil.com
    """
    print_json(sdk.red_team.mailgun_domain_status(domain))


@domain.command('mailgun-provision')
@cli_handler
@praetorian_only
@click.option('--domain', required=True, help='Domain to provision')
def mailgun_provision(sdk, domain):
    """ Provision a Mailgun domain

    \b
    Example usages:
        guard red-team domain mailgun-provision --domain evil.com
    """
    print_json(sdk.red_team.mailgun_domain_provision(domain))


@domain.command('mailgun-user')
@cli_handler
@praetorian_only
@click.option('--username', required=True, help='SMTP username')
@click.option('--domain', required=True, help='Domain name')
def mailgun_user(sdk, username, domain):
    """ Create a Mailgun SMTP user

    \b
    Example usages:
        guard red-team domain mailgun-user --username noreply --domain evil.com
    """
    print_json(sdk.red_team.mailgun_user_create(username, domain))


# ===================== Evilginx =====================

@red_team.group()
def evilginx():
    """ Evilginx phishing infrastructure """
    pass


@evilginx.command()
@cli_handler
@praetorian_only
@click.option('--node', required=True, help='Phishkit node reference')
def phishlets(sdk, node):
    """ List available Evilginx phishlets

    \b
    Example usages:
        guard red-team evilginx phishlets --node node-ref-1
    """
    print_json(sdk.red_team.evilginx_phishlets(node))


@evilginx.command('phishlet-params')
@cli_handler
@praetorian_only
@click.option('--node', required=True, help='Phishkit node reference')
@click.option('--name', required=True, help='Phishlet name')
def phishlet_params(sdk, node, name):
    """ Get parameters for a specific phishlet

    \b
    Example usages:
        guard red-team evilginx phishlet-params --node node-ref-1 --name o365
    """
    print_json(sdk.red_team.evilginx_phishlet_params(node, name))


@evilginx.command()
@cli_handler
@praetorian_only
@click.option('--node', required=True, help='Phishkit node reference')
def lures(sdk, node):
    """ List Evilginx lures

    \b
    Example usages:
        guard red-team evilginx lures --node node-ref-1
    """
    print_json(sdk.red_team.evilginx_lures(node))


@evilginx.command('create-lure')
@cli_handler
@praetorian_only
@click.option('--node', required=True, help='Phishkit node reference')
@click.option('--path', required=True, help='Lure URL path')
def create_lure(sdk, node, path):
    """ Create an Evilginx lure

    \b
    Example usages:
        guard red-team evilginx create-lure --node node-ref-1 --path /login
    """
    print_json(sdk.red_team.evilginx_create_lure(node, path))


@evilginx.command()
@cli_handler
@praetorian_only
@click.option('--node', required=True, help='Phishkit node reference')
@click.option('--domain', required=True, help='Domain to configure')
@click.option('--phishlet', required=True, help='Phishlet name')
@click.option('--params', default=None,
              help='JSON string of phishlet parameters')
@click.option('--unauth-url', default=None,
              help='URL for unauthenticated visitors')
def configure(sdk, node, domain, phishlet, params, unauth_url):
    """ Configure Evilginx on a phishkit node

    \b
    Example usages:
        guard red-team evilginx configure --node n1 --domain evil.com --phishlet o365
        guard red-team evilginx configure --node n1 --domain evil.com --phishlet o365 --params '{"client_id":"abc"}'
    """
    phishlet_params = json.loads(params) if params else None
    print_json(sdk.red_team.evilginx_configure(
        node, domain, phishlet,
        phishlet_params=phishlet_params, unauth_url=unauth_url))


@evilginx.command()
@cli_handler
@praetorian_only
@click.option('--node', required=True, help='Phishkit node reference')
def status(sdk, node):
    """ Get Evilginx configuration status

    \b
    Example usages:
        guard red-team evilginx status --node node-ref-1
    """
    print_json(sdk.red_team.evilginx_status(node))


# ===================== Payload & phishkit =====================

@red_team.command('payload-generate')
@cli_handler
@praetorian_only
@click.option('--shellcode', required=True,
              help='S3 filename of shellcode to embed')
@click.option('--variables', default=None,
              help='JSON string of template variables')
def payload_generate(sdk, shellcode, variables):
    """ Generate a payload from shellcode

    \b
    Example usages:
        guard red-team payload-generate --shellcode beacon.bin
        guard red-team payload-generate --shellcode beacon.bin --variables '{"dll_filename":"update.dll"}'
    """
    vars_dict = json.loads(variables) if variables else None
    print_json(sdk.red_team.payload_generate(shellcode, variables=vars_dict))


@red_team.command('phishkit-nodes')
@cli_handler
@praetorian_only
@click.option('--status', default=None,
              help='Filter by status (e.g. "running", "all")')
def phishkit_nodes(sdk, status):
    """ List phishkit nodes

    \b
    Example usages:
        guard red-team phishkit-nodes
        guard red-team phishkit-nodes --status all
    """
    print_json(sdk.red_team.phishkit_nodes(status=status))
