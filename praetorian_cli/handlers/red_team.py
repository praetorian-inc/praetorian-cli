import json
import sys

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json

# POLICY: stdin cannot be both the JSON payload channel and Click's confirmation
# channel. Every command that takes a JSON body therefore accepts `-f/--file`,
# and `-f -` selects the original stdin behavior explicitly. A destructive
# command reads its payload from a file so that @click.confirmation_option can
# still reach the controlling terminal to prompt.
JSON_FILE_HELP = 'Read the JSON body from PATH ("-" reads stdin)'


def _load_json_body(path=None):
    """Load a JSON request body from `path`, or from stdin when `path` is None or '-'."""
    if path in (None, '-'):
        if sys.stdin.isatty():
            raise click.UsageError('Pipe JSON input via stdin, or pass --file PATH')
        data = sys.stdin.read().strip()
        source = 'stdin'
    else:
        try:
            with open(path) as f:
                data = f.read().strip()
        except OSError as e:
            raise click.UsageError(f'Cannot read JSON body from {path}: {e.strerror}')
        source = path

    if not data:
        raise click.UsageError(f'No JSON body provided on {source}')
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        raise click.UsageError('Invalid JSON input')


def _json_option(inline_value, inline_flag, file_path, file_flag):
    """Resolve a JSON value supplied either inline on argv or from a file.

    The two forms are mutually exclusive: an inline string is visible in process
    listings and shell history, so a caller who has moved a value into a file is
    not silently given the argv one back.
    """
    if inline_value and file_path:
        raise click.UsageError(
            f'{inline_flag} and {file_flag} are mutually exclusive; pass only one')
    if file_path:
        return _load_json_body(file_path)
    if not inline_value:
        return None
    try:
        return json.loads(inline_value)
    except json.JSONDecodeError:
        raise click.UsageError('Invalid JSON input')


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
@click.option('--file', '-f', 'body_file', default=None, help=JSON_FILE_HELP)
def plan(sdk, tag, sha, body_file):
    """ Run terraform plan from a builder state JSON

    \b
    The builder state is read from --file, or from stdin when --file is omitted
    or given as "-".

    \b
    Example usages:
        cat builder.json | guard red-team deployment plan
        guard red-team deployment plan --file builder.json
    """
    print_json(sdk.red_team.deployment_terraform(
        'plan', _load_json_body(body_file), tag=tag, sha=sha))


@deployment.command()
@cli_handler
@praetorian_only
@click.option('--tag', default=None, help='Infrastructure version tag')
@click.option('--sha', default=None, help='Git commit SHA')
@click.option('--file', '-f', 'body_file', default=None, help=JSON_FILE_HELP)
@click.confirmation_option(prompt='Apply the Terraform deployment?')
def apply(sdk, tag, sha, body_file):
    """ Run terraform apply from a builder state JSON

    \b
    Prompts for confirmation; --yes skips the prompt. The builder state is read
    from --file, or from stdin when --file is omitted or given as "-". Pass the
    builder state with --file to leave stdin free for the confirmation prompt --
    when the payload is piped in instead, the prompt has no input to read and
    the command aborts unless --yes is given.

    \b
    Example usages:
        guard red-team deployment apply --file builder.json
        cat builder.json | guard red-team deployment apply --yes
    """
    print_json(sdk.red_team.deployment_terraform(
        'apply', _load_json_body(body_file), tag=tag, sha=sha))


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


@deployment.command('tags')
@cli_handler
@praetorian_only
def deployment_tags(sdk):
    """ List available infrastructure version tags

    \b
    Example usages:
        guard red-team deployment tags
    """
    print_json(sdk.red_team.deployment_tags())


# ===================== Campaigns =====================

@red_team.group()
def campaign():
    """ Red Team phishing campaigns """
    pass


@campaign.command()
@cli_handler
@praetorian_only
@click.option('--file', '-f', 'body_file', default=None, help=JSON_FILE_HELP)
def create(sdk, body_file):
    """ Create or update a campaign from JSON

    \b
    The campaign document is read from --file, or from stdin when --file is
    omitted or given as "-".

    \b
    Example usages:
        cat campaign.json | guard red-team campaign create
        guard red-team campaign create --file campaign.json
    """
    print_json(sdk.red_team.campaign_create(_load_json_body(body_file)))


@campaign.command('delete')
@cli_handler
@praetorian_only
@click.option('--key', required=True, help='Campaign key')
@click.confirmation_option(prompt='Delete this campaign?')
def campaign_delete(sdk, key):
    """ Delete a campaign

    \b
    Prompts for confirmation.

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
@click.option('--file', '-f', 'body_file', default=None, help=JSON_FILE_HELP)
def targets(sdk, campaign_id, segment, body_file):
    """ Set campaign targets from JSON

    \b
    Replaces the full target roster. The roster is read from --file, or from
    stdin when --file is omitted or given as "-".

    \b
    Example usages:
        cat targets.json | guard red-team campaign targets --id camp-1
        guard red-team campaign targets --id camp-1 --file targets.json
    """
    body = _load_json_body(body_file)
    if isinstance(body, dict):
        target_list = body.get('targets')
        if target_list is None:
            raise click.UsageError(
                "Expected JSON with 'targets' key or a JSON array of targets")
    elif isinstance(body, list):
        target_list = body
    else:
        raise click.UsageError(
            'Expected JSON array or object with \'targets\' key')
    print_json(sdk.red_team.campaign_targets(
        campaign_id, target_list, segment=segment))


@campaign.command()
@cli_handler
@praetorian_only
@click.option('--id', 'campaign_id', required=True, help='Campaign ID')
@click.confirmation_option(
    prompt='Authorize this campaign to go live? '
           'This sends live phishing email to real recipients.')
def authorize(sdk, campaign_id):
    """ Authorize a campaign to go live

    \b
    Prompts for confirmation. Once authorized, the campaign sends live phishing
    email to every recipient on its target roster.

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
@click.option('--limit', type=int, default=None,
              help='Maximum number of events to return')
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
@click.option('--file', '-f', 'body_file', default=None, help=JSON_FILE_HELP)
def update(sdk, body_file):
    """ Update a parked domain from JSON

    \b
    The domain document is read from --file, or from stdin when --file is
    omitted or given as "-".

    \b
    Example usages:
        echo '{"domain":"evil.com","status":"in-use"}' | guard red-team domain update
        guard red-team domain update --file domain.json
    """
    print_json(sdk.red_team.domain_update(_load_json_body(body_file)))


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


@domain.command('dns-update')
@cli_handler
@praetorian_only
@click.option('--domain', required=True, help='Domain name')
@click.option('--record-id', required=True, help='DNS record ID')
@click.option('--type', 'record_type', required=True,
              type=click.Choice(['A', 'CNAME', 'MX', 'TXT']),
              help='Record type')
@click.option('--name', required=True, help='Record name')
@click.option('--content', required=True, help='Record value')
@click.option('--ttl', type=int, default=1, help='TTL in seconds (1=auto)')
def dns_update(sdk, domain, record_id, record_type, name, content, ttl):
    """ Update a DNS record for a parked domain

    \b
    Example usages:
        guard red-team domain dns-update --domain evil.com --record-id abc123 --type A --name www --content 1.2.3.4
    """
    print_json(sdk.red_team.dns_update(domain, record_id, record_type, name, content, ttl))


@domain.command('dns-delete')
@cli_handler
@praetorian_only
@click.option('--domain', required=True, help='Domain name')
@click.option('--record-id', required=True, help='DNS record ID')
@click.confirmation_option(prompt='Delete this DNS record?')
def dns_delete(sdk, domain, record_id):
    """ Delete a DNS record

    \b
    Prompts for confirmation.

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


@domain.command('mailgun-domain-delete')
@cli_handler
@praetorian_only
@click.option('--domain', required=True, help='Domain name')
@click.confirmation_option(prompt='Delete the Mailgun domain?')
def mailgun_domain_delete(sdk, domain):
    """ Delete a Mailgun domain

    \b
    Prompts for confirmation.

    \b
    Example usages:
        guard red-team domain mailgun-domain-delete --domain evil.com
    """
    print_json(sdk.red_team.mailgun_domain_delete(domain))


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


@domain.command('mailgun-user-delete')
@cli_handler
@praetorian_only
@click.option('--username', required=True, help='SMTP username')
@click.option('--domain', required=True, help='Domain name')
@click.confirmation_option(prompt='Delete the Mailgun SMTP user?')
def mailgun_user_delete(sdk, username, domain):
    """ Delete a Mailgun SMTP user

    \b
    Prompts for confirmation.

    \b
    Example usages:
        guard red-team domain mailgun-user-delete --username noreply --domain evil.com
    """
    print_json(sdk.red_team.mailgun_user_delete(username, domain))


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
              help='JSON string of phishlet parameters. Values passed inline are '
                   'visible in process listings and shell history; use '
                   '--params-file for anything sensitive')
@click.option('--params-file', default=None,
              help='Read the phishlet parameters JSON from PATH ("-" reads stdin). '
                   'Use this for OAuth client IDs/secrets, session tokens, and '
                   'other sensitive values')
@click.option('--unauth-url', default=None,
              help='URL for unauthenticated visitors')
def configure(sdk, node, domain, phishlet, params, params_file, unauth_url):
    """ Configure Evilginx on a phishkit node

    \b
    Phishlet parameters carry secret material (OAuth client IDs and secrets,
    session tokens). Pass them with --params-file: a value given inline with
    --params is visible in process listings and shell history.

    \b
    Example usages:
        guard red-team evilginx configure --node n1 --domain evil.com --phishlet o365
        guard red-team evilginx configure --node n1 --domain evil.com --phishlet o365 --params '{"landing_path":"/login"}'
        guard red-team evilginx configure --node n1 --domain evil.com --phishlet o365 --params-file phishlet-params.json
    """
    phishlet_params = _json_option(params, '--params', params_file, '--params-file')
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
              help='JSON string of template variables. Values passed inline are '
                   'visible in process listings and shell history; use '
                   '--variables-file for anything sensitive')
@click.option('--variables-file', default=None,
              help='Read the template variables JSON from PATH ("-" reads stdin). '
                   'Use this for keys, tokens, and other sensitive values')
def payload_generate(sdk, shellcode, variables, variables_file):
    """ Generate a payload from shellcode

    \b
    Pass template variables with --variables-file when any of them is sensitive:
    a value given inline with --variables is visible in process listings and
    shell history.

    \b
    Example usages:
        guard red-team payload-generate --shellcode beacon.bin
        guard red-team payload-generate --shellcode beacon.bin --variables '{"dll_filename":"update.dll"}'
        guard red-team payload-generate --shellcode beacon.bin --variables-file payload-vars.json
    """
    vars_dict = _json_option(variables, '--variables', variables_file, '--variables-file')
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
