from urllib.parse import quote

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


# ---------------------------------------------------------------------------
# Top-level group
# ---------------------------------------------------------------------------

@chariot.group('redteam')
def redteam():
    """ Red team operations: deployments, domain parking, phishing campaigns, and payloads """
    pass


# ---------------------------------------------------------------------------
# deployment sub-group
# ---------------------------------------------------------------------------

@redteam.group('deployment')
def deployment():
    """ Manage red team infrastructure deployments """
    pass


@deployment.command('launch')
@cli_handler
@click.option('--name', required=True, help='Deployment name')
@click.option('--template', required=True, help='Deployment template to use')
@click.option('--region', default=None, help='Cloud region for the deployment')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def deployment_launch(sdk, name, template, region, json_output):
    """ Launch a new red team deployment

    Provisions infrastructure from the specified template. The deployment is
    assigned the given name and optionally placed in a specific cloud region.

    \b
    Example usages:
        guard redteam deployment launch --name op-cobalt --template c2-basic
        guard redteam deployment launch --name op-cobalt --template c2-full --region us-east-1
        guard redteam deployment launch --name op-cobalt --template c2-basic --json-output
    """
    body = {'name': name, 'template': template}
    if region:
        body['region'] = region
    result = sdk.post('red-team/deployment/launch', body)
    if json_output:
        print_json(result)
    else:
        click.echo(click.style('Launched:', fg='green', bold=True) + f' {name}')
        if result:
            for key, value in result.items():
                click.echo(f'  {click.style(key, bold=True)}: {value}')


@deployment.command('delete')
@cli_handler
@click.option('--name', required=True, help='Deployment name to delete')
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def deployment_delete(sdk, name, force):
    """ Delete a red team deployment

    Tears down and removes the named deployment. Use --force to skip the
    interactive confirmation prompt.

    \b
    Example usages:
        guard redteam deployment delete --name op-cobalt
        guard redteam deployment delete --name op-cobalt --force
    """
    if not force:
        click.confirm(f'Delete deployment {click.style(name, fg="yellow")}?', abort=True)
    result = sdk.delete('red-team/deployment/delete', {'name': name}, {})
    click.echo(click.style('Deleted:', fg='red', bold=True) + f' {name}')
    if result:
        print_json(result)


@deployment.command('terraform')
@cli_handler
@click.argument('action', type=click.Choice(['plan', 'apply', 'destroy']))
@click.option('--name', required=True, help='Deployment name')
def deployment_terraform(sdk, action, name):
    """ Run a Terraform action against a deployment

    Executes plan, apply, or destroy for the named deployment. The output
    is streamed back as the backend runs the action.

    \b
    Example usages:
        guard redteam deployment terraform plan --name op-cobalt
        guard redteam deployment terraform apply --name op-cobalt
        guard redteam deployment terraform destroy --name op-cobalt
    """
    result = sdk.post(f'red-team/deployment/terraform/{action}', {'name': name})
    color_map = {'plan': 'cyan', 'apply': 'green', 'destroy': 'red'}
    click.echo(click.style(f'terraform {action}:', fg=color_map[action], bold=True) + f' {name}')
    if result:
        output = result.get('output') or result.get('logs') or result
        if isinstance(output, str):
            click.echo(output)
        else:
            print_json(output)


@deployment.command('details')
@cli_handler
@click.option('--name', required=True, help='Deployment name')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def deployment_details(sdk, name, json_output):
    """ Show details for a specific deployment

    Displays configuration, status, and resource information for the named
    deployment.

    \b
    Example usages:
        guard redteam deployment details --name op-cobalt
        guard redteam deployment details --name op-cobalt --json-output
    """
    result = sdk.get(f'red-team/deployment/details?name={quote(name, safe="")}')
    if json_output:
        print_json(result)
    else:
        if not result:
            click.echo(f'No details found for {name}')
            return
        click.echo(click.style(f'Deployment: {name}', bold=True))
        click.echo(click.style('─' * 40, dim=True))
        for key, value in result.items():
            click.echo(f'  {click.style(key, bold=True)}: {value}')


@deployment.command('history')
@cli_handler
@click.option('--name', default=None, help='Filter by deployment name')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def deployment_history(sdk, name, json_output):
    """ View deployment history

    Lists past deployment events. Optionally filter by deployment name.

    \b
    Example usages:
        guard redteam deployment history
        guard redteam deployment history --name op-cobalt
        guard redteam deployment history --json-output
    """
    params = {}
    if name:
        params['name'] = name
    query = '&'.join(f'{k}={quote(str(v), safe="")}' for k, v in params.items())
    path = f'red-team/deployment/history{"?" + query if query else ""}'
    result = sdk.get(path)
    if json_output:
        print_json(result)
    else:
        entries = result if isinstance(result, list) else (result or {}).get('history', result or {}).get('events', [])
        if not isinstance(entries, list):
            entries = []
        if not entries:
            click.echo('No deployment history found.')
            return
        for entry in entries:
            ts = entry.get('timestamp') or entry.get('created_at') or ''
            ev = entry.get('event') or entry.get('action') or entry.get('type') or ''
            dep = entry.get('name') or entry.get('deployment') or ''
            status = entry.get('status') or ''
            status_color = 'green' if status.lower() in ('success', 'ok', 'complete') else 'yellow'
            line = f'  {click.style(ts, dim=True)}  {click.style(dep, bold=True)}  {ev}'
            if status:
                line += f'  [{click.style(status, fg=status_color)}]'
            click.echo(line)


@deployment.command('last-inputs')
@cli_handler
@click.option('--name', required=True, help='Deployment name')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def deployment_last_inputs(sdk, name, json_output):
    """ Get the last inputs used for a deployment

    Retrieves the most recent configuration inputs that were applied to the
    named deployment. Useful for reproducing or auditing a previous run.

    \b
    Example usages:
        guard redteam deployment last-inputs --name op-cobalt
        guard redteam deployment last-inputs --name op-cobalt --json-output
    """
    result = sdk.get(f'red-team/deployment/last-inputs?name={quote(name, safe="")}')
    if json_output:
        print_json(result)
    else:
        if not result:
            click.echo(f'No inputs found for {name}')
            return
        click.echo(click.style(f'Last inputs for: {name}', bold=True))
        click.echo(click.style('─' * 40, dim=True))
        if isinstance(result, dict):
            for key, value in result.items():
                click.echo(f'  {click.style(key, bold=True)}: {value}')
        else:
            print_json(result)


# ---------------------------------------------------------------------------
# deployment collaborators sub-group
# ---------------------------------------------------------------------------

@deployment.group('collaborators')
def deployment_collaborators():
    """ Manage collaborators on a deployment """
    pass


@deployment_collaborators.command('list')
@cli_handler
@click.option('--name', required=True, help='Deployment name')
def collaborators_list(sdk, name):
    """ List collaborators for a deployment

    \b
    Example usages:
        guard redteam deployment collaborators list --name op-cobalt
    """
    result = sdk.get(f'red-team/deployment/collaborators?name={quote(name, safe="")}')
    collaborators = result if isinstance(result, list) else (result or {}).get('collaborators', [])
    if not collaborators:
        click.echo(f'No collaborators found for {name}')
        return
    click.echo(click.style(f'Collaborators on {name}:', bold=True))
    for c in collaborators:
        email = c.get('email') or c.get('username') or c
        role = c.get('role') or ''
        line = f'  {click.style(email, bold=True)}'
        if role:
            line += f'  ({role})'
        click.echo(line)


@deployment_collaborators.command('add')
@cli_handler
@click.option('--name', required=True, help='Deployment name')
@click.option('--email', required=True, help='Collaborator email address')
@click.option('--role', default='viewer', show_default=True, help='Collaborator role (e.g., viewer, admin)')
def collaborators_add(sdk, name, email, role):
    """ Add a collaborator to a deployment

    \b
    Example usages:
        guard redteam deployment collaborators add --name op-cobalt --email analyst@praetorian.com
        guard redteam deployment collaborators add --name op-cobalt --email analyst@praetorian.com --role admin
    """
    result = sdk.post('red-team/deployment/collaborators', {'name': name, 'email': email, 'role': role})
    click.echo(click.style('Added:', fg='green') + f' {email} ({role}) to {name}')
    if result:
        print_json(result)


@deployment_collaborators.command('remove')
@cli_handler
@click.option('--name', required=True, help='Deployment name')
@click.option('--email', required=True, help='Collaborator email to remove')
def collaborators_remove(sdk, name, email):
    """ Remove a collaborator from a deployment

    \b
    Example usages:
        guard redteam deployment collaborators remove --name op-cobalt --email analyst@praetorian.com
    """
    result = sdk.delete('red-team/deployment/collaborators', {'name': name, 'email': email}, {})
    click.echo(click.style('Removed:', fg='yellow') + f' {email} from {name}')
    if result:
        print_json(result)


# ---------------------------------------------------------------------------
# domains sub-group
# ---------------------------------------------------------------------------

@redteam.group('domains')
def domains():
    """ Manage parked domains for red team operations """
    pass


@domains.command('list')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def domains_list(sdk, json_output):
    """ List all parked domains

    \b
    Example usages:
        guard redteam domains list
        guard redteam domains list --json-output
    """
    result = sdk.get('red-team/domain-parking')
    if json_output:
        print_json(result)
    else:
        entries = result if isinstance(result, list) else (result or {}).get('domains', [])
        if not entries:
            click.echo('No parked domains found.')
            return
        click.echo(click.style('Parked Domains:', bold=True))
        for d in entries:
            domain = d.get('domain') or d.get('name') or d
            provider = d.get('provider') or ''
            status = d.get('status') or ''
            line = f'  {click.style(str(domain), bold=True)}'
            if provider:
                line += f'  provider={provider}'
            if status:
                color = 'green' if status.lower() == 'active' else 'yellow'
                line += f'  [{click.style(status, fg=color)}]'
            click.echo(line)


@domains.command('add')
@cli_handler
@click.option('--domain', required=True, help='Domain name to park')
@click.option('--provider', default=None, help='DNS provider (e.g., cloudflare, route53)')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def domains_add(sdk, domain, provider, json_output):
    """ Add a domain to the parked domains list

    \b
    Example usages:
        guard redteam domains add --domain totallylegit.io
        guard redteam domains add --domain totallylegit.io --provider cloudflare
        guard redteam domains add --domain totallylegit.io --json-output
    """
    body = {'domain': domain}
    if provider:
        body['provider'] = provider
    result = sdk.post('red-team/domain-parking', body)
    if json_output:
        print_json(result)
    else:
        click.echo(click.style('Added domain:', fg='green') + f' {domain}')
        if result:
            for key, value in result.items():
                click.echo(f'  {click.style(key, bold=True)}: {value}')


@domains.command('delete')
@cli_handler
@click.option('--domain', required=True, help='Domain name to remove')
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def domains_delete(sdk, domain, force):
    """ Delete a parked domain

    \b
    Example usages:
        guard redteam domains delete --domain totallylegit.io
        guard redteam domains delete --domain totallylegit.io --force
    """
    if not force:
        click.confirm(f'Delete parked domain {click.style(domain, fg="yellow")}?', abort=True)
    result = sdk.delete('red-team/domain-parking', {'domain': domain}, {})
    click.echo(click.style('Deleted domain:', fg='red') + f' {domain}')
    if result:
        print_json(result)


# ---------------------------------------------------------------------------
# domains dns sub-group
# ---------------------------------------------------------------------------

@domains.group('dns')
def dns():
    """ Manage DNS records for a parked domain """
    pass


@dns.command('list')
@cli_handler
@click.option('--domain', required=True, help='Domain name')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def dns_list(sdk, domain, json_output):
    """ List DNS records for a domain

    \b
    Example usages:
        guard redteam domains dns list --domain totallylegit.io
        guard redteam domains dns list --domain totallylegit.io --json-output
    """
    result = sdk.get(f'red-team/domain-parking/dns/{quote(domain, safe="")}')
    if json_output:
        print_json(result)
    else:
        records = result if isinstance(result, list) else (result or {}).get('records', [])
        if not records:
            click.echo(f'No DNS records for {domain}')
            return
        click.echo(click.style(f'DNS records for {domain}:', bold=True))
        click.echo(f'  {"ID":<20} {"TYPE":<8} {"NAME":<30} {"VALUE":<40} {"TTL"}')
        click.echo(click.style('  ' + '─' * 104, dim=True))
        for r in records:
            rid = str(r.get('id') or r.get('record_id') or '')
            rtype = str(r.get('type') or '')
            rname = str(r.get('name') or '')
            rvalue = str(r.get('value') or r.get('content') or '')
            rttl = str(r.get('ttl') or '')
            click.echo(f'  {rid:<20} {click.style(rtype, fg="cyan"):<17} {rname:<30} {rvalue:<40} {rttl}')


@dns.command('add')
@cli_handler
@click.option('--domain', required=True, help='Domain name')
@click.option('--type', 'record_type', required=True, help='DNS record type (A, CNAME, MX, TXT, etc.)')
@click.option('--name', 'record_name', required=True, help='Record name (use @ for zone apex)')
@click.option('--value', required=True, help='Record value / content')
@click.option('--ttl', default=3600, show_default=True, help='Time-to-live in seconds')
def dns_add(sdk, domain, record_type, record_name, value, ttl):
    """ Add a DNS record to a domain

    \b
    Example usages:
        guard redteam domains dns add --domain totallylegit.io --type A --name @ --value 1.2.3.4
        guard redteam domains dns add --domain totallylegit.io --type CNAME --name mail --value mailgun.org --ttl 300
        guard redteam domains dns add --domain totallylegit.io --type MX --name @ --value "10 mxa.mailgun.org"
    """
    body = {'type': record_type, 'name': record_name, 'value': value, 'ttl': ttl}
    result = sdk.post(f'red-team/domain-parking/dns/{quote(domain, safe="")}', body)
    click.echo(click.style('Added record:', fg='green') + f' {record_type} {record_name} -> {value}')
    if result:
        print_json(result)


@dns.command('update')
@cli_handler
@click.option('--domain', required=True, help='Domain name')
@click.option('--record-id', required=True, help='DNS record ID to update')
@click.option('--type', 'record_type', required=True, help='DNS record type')
@click.option('--name', 'record_name', required=True, help='Record name')
@click.option('--value', required=True, help='Record value / content')
@click.option('--ttl', default=3600, show_default=True, help='Time-to-live in seconds')
def dns_update(sdk, domain, record_id, record_type, record_name, value, ttl):
    """ Update an existing DNS record

    \b
    Example usages:
        guard redteam domains dns update --domain totallylegit.io --record-id abc123 --type A --name @ --value 5.6.7.8
        guard redteam domains dns update --domain totallylegit.io --record-id abc123 --type CNAME --name mail --value mailgun.org --ttl 300
    """
    body = {'type': record_type, 'name': record_name, 'value': value, 'ttl': ttl}
    result = sdk.put(f'red-team/domain-parking/dns/{quote(domain, safe="")}/{quote(str(record_id), safe="")}', body)
    click.echo(click.style('Updated record:', fg='green') + f' {record_id} -> {record_type} {record_name} {value}')
    if result:
        print_json(result)


@dns.command('delete')
@cli_handler
@click.option('--domain', required=True, help='Domain name')
@click.option('--record-id', required=True, help='DNS record ID to delete')
def dns_delete(sdk, domain, record_id):
    """ Delete a DNS record from a domain

    \b
    Example usages:
        guard redteam domains dns delete --domain totallylegit.io --record-id abc123
    """
    result = sdk.delete(f'red-team/domain-parking/dns/{quote(domain, safe="")}/{quote(str(record_id), safe="")}', {}, {})
    click.echo(click.style('Deleted record:', fg='red') + f' {record_id} from {domain}')
    if result:
        print_json(result)


# ---------------------------------------------------------------------------
# domains mailgun sub-group
# ---------------------------------------------------------------------------

@domains.group('mailgun')
def mailgun():
    """ Manage Mailgun integration for a parked domain """
    pass


@mailgun.command('setup')
@cli_handler
@click.option('--domain', required=True, help='Domain to register with Mailgun')
def mailgun_setup(sdk, domain):
    """ Set up Mailgun for a parked domain

    Registers the domain with Mailgun and provisions the required DNS records
    for email sending.

    \b
    Example usages:
        guard redteam domains mailgun setup --domain totallylegit.io
    """
    result = sdk.post(f'red-team/domain-parking/mailgun/domain/{quote(domain, safe="")}', {})
    click.echo(click.style('Mailgun domain registered:', fg='green') + f' {domain}')
    if result:
        print_json(result)


@mailgun.command('teardown')
@cli_handler
@click.option('--domain', required=True, help='Domain to remove from Mailgun')
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def mailgun_teardown(sdk, domain, force):
    """ Remove a domain from Mailgun

    Deletes the Mailgun domain registration and cleans up associated
    DNS entries.

    \b
    Example usages:
        guard redteam domains mailgun teardown --domain totallylegit.io
        guard redteam domains mailgun teardown --domain totallylegit.io --force
    """
    if not force:
        click.confirm(f'Tear down Mailgun for {click.style(domain, fg="yellow")}?', abort=True)
    result = sdk.delete(f'red-team/domain-parking/mailgun/domain/{quote(domain, safe="")}', {}, {})
    click.echo(click.style('Mailgun domain removed:', fg='yellow') + f' {domain}')
    if result:
        print_json(result)


@mailgun.command('user')
@cli_handler
@click.option('--domain', required=True, help='Mailgun domain for the user')
@click.option('--email', required=True, help='Email address to create as a Mailgun user')
def mailgun_user(sdk, domain, email):
    """ Create a Mailgun user for a domain

    Provisions a Mailgun SMTP user tied to the specified domain, enabling
    sending email as that address.

    \b
    Example usages:
        guard redteam domains mailgun user --domain totallylegit.io --email hr@totallylegit.io
    """
    result = sdk.post('red-team/domain-parking/mailgun/user', {'domain': domain, 'email': email})
    click.echo(click.style('Mailgun user created:', fg='green') + f' {email}')
    if result:
        print_json(result)


# ---------------------------------------------------------------------------
# campaign sub-group
# ---------------------------------------------------------------------------

@redteam.group('campaign')
def campaign():
    """ Manage phishing campaigns """
    pass


@campaign.command('create')
@cli_handler
@click.option('--name', required=True, help='Campaign name')
@click.option('--template', required=True, help='Email template to use')
@click.option('--from-name', required=True, help='Sender display name')
@click.option('--from-email', required=True, help='Sender email address')
@click.option('--subject', default=None, help='Email subject line')
def campaign_create(sdk, name, template, from_name, from_email, subject):
    """ Create a new phishing campaign

    Provisions a campaign shell. Targets are added separately via
    'campaign targets add'. The campaign must be authorized before launch.

    \b
    Example usages:
        guard redteam campaign create --name "Q3 Phish" --template invoice-lure --from-name "Payroll" --from-email payroll@totallylegit.io
        guard redteam campaign create --name "Q3 Phish" --template invoice-lure --from-name "Payroll" --from-email payroll@totallylegit.io --subject "Action Required: Invoice"
    """
    body = {
        'name': name,
        'template': template,
        'from_name': from_name,
        'from_email': from_email,
    }
    if subject:
        body['subject'] = subject
    result = sdk.put('red-team/campaigns', body)
    click.echo(click.style('Campaign created:', fg='green', bold=True))
    if result:
        campaign_id = result.get('id') or result.get('campaign_id') or ''
        if campaign_id:
            click.echo(f'  {click.style("ID", bold=True)}: {campaign_id}')
        for key, value in result.items():
            if key not in ('id', 'campaign_id'):
                click.echo(f'  {click.style(key, bold=True)}: {value}')


@campaign.command('delete')
@cli_handler
@click.argument('campaign_id')
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def campaign_delete(sdk, campaign_id, force):
    """ Delete a phishing campaign

    \b
    Example usages:
        guard redteam campaign delete abc-123
        guard redteam campaign delete abc-123 --force
    """
    if not force:
        click.confirm(f'Delete campaign {click.style(campaign_id, fg="yellow")}?', abort=True)
    result = sdk.delete('red-team/campaigns', {'id': campaign_id}, {})
    click.echo(click.style('Campaign deleted:', fg='red') + f' {campaign_id}')
    if result:
        print_json(result)


# ---------------------------------------------------------------------------
# campaign targets sub-group
# ---------------------------------------------------------------------------

@campaign.group('targets')
def campaign_targets():
    """ Manage targets for a phishing campaign """
    pass


@campaign_targets.command('list')
@cli_handler
@click.argument('campaign_id')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def targets_list(sdk, campaign_id, json_output):
    """ List all targets in a campaign

    \b
    Example usages:
        guard redteam campaign targets list abc-123
        guard redteam campaign targets list abc-123 --json-output
    """
    result = sdk.get(f'red-team/campaigns/{quote(campaign_id, safe="")}/targets')
    if json_output:
        print_json(result)
    else:
        targets = result if isinstance(result, list) else (result or {}).get('targets', [])
        if not targets:
            click.echo(f'No targets in campaign {campaign_id}')
            return
        click.echo(click.style(f'Targets in campaign {campaign_id} ({len(targets)} total):', bold=True))
        click.echo(f'  {"EMAIL":<35} {"FIRST":<15} {"LAST":<15} {"PARAMS"}')
        click.echo(click.style('  ' + '─' * 80, dim=True))
        for t in targets:
            email = t.get('email', '')
            first = t.get('first_name') or t.get('first', '')
            last = t.get('last_name') or t.get('last', '')
            params = t.get('params') or t.get('parameters') or {}
            param_str = ', '.join(f'{k}={v}' for k, v in params.items()) if isinstance(params, dict) else ''
            click.echo(f'  {email:<35} {first:<15} {last:<15} {param_str}')


@campaign_targets.command('add')
@cli_handler
@click.argument('campaign_id')
@click.option('--email', required=True, help='Target email address')
@click.option('--first', required=True, help='Target first name')
@click.option('--last', required=True, help='Target last name')
@click.option('--param', 'params', multiple=True, help='Extra template parameters as KEY=VALUE (repeatable)')
def targets_add(sdk, campaign_id, email, first, last, params):
    """ Add a target to a phishing campaign

    Template parameters (--param) are injected into the email template
    alongside the standard first/last name substitutions.

    \b
    Example usages:
        guard redteam campaign targets add abc-123 --email jdoe@acme.com --first John --last Doe
        guard redteam campaign targets add abc-123 --email jdoe@acme.com --first John --last Doe --param department=Finance --param manager=Jane
    """
    body = {'email': email, 'first_name': first, 'last_name': last}
    if params:
        parsed = {}
        for p in params:
            if '=' not in p:
                error(f"Parameter '{p}' is not in the format KEY=VALUE")
            k, v = p.split('=', 1)
            parsed[k] = v
        body['params'] = parsed
    result = sdk.post(f'red-team/campaigns/{quote(campaign_id, safe="")}/targets', body)
    click.echo(click.style('Target added:', fg='green') + f' {first} {last} <{email}>')
    if result:
        print_json(result)


@campaign_targets.command('remove')
@cli_handler
@click.argument('campaign_id')
@click.option('--email', required=True, help='Target email address to remove')
def targets_remove(sdk, campaign_id, email):
    """ Remove a target from a campaign

    \b
    Example usages:
        guard redteam campaign targets remove abc-123 --email jdoe@acme.com
    """
    result = sdk.delete(f'red-team/campaigns/{quote(campaign_id, safe="")}/targets', {'email': email}, {})
    click.echo(click.style('Target removed:', fg='yellow') + f' {email}')
    if result:
        print_json(result)


# ---------------------------------------------------------------------------
# campaign actions
# ---------------------------------------------------------------------------

@campaign.command('authorize')
@cli_handler
@click.argument('campaign_id')
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def campaign_authorize(sdk, campaign_id, force):
    """ Authorize a campaign for launch

    Marks the campaign as approved for sending. This step is required
    before targets will receive emails.

    \b
    Example usages:
        guard redteam campaign authorize abc-123
        guard redteam campaign authorize abc-123 --force
    """
    if not force:
        click.confirm(f'Authorize campaign {click.style(campaign_id, fg="yellow")} for launch?', abort=True)
    result = sdk.post(f'red-team/campaigns/{quote(campaign_id, safe="")}/authorize', {})
    click.echo(click.style('Campaign authorized:', fg='green', bold=True) + f' {campaign_id}')
    if result:
        print_json(result)


@campaign.command('funnel')
@cli_handler
@click.argument('campaign_id')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def campaign_funnel(sdk, campaign_id, json_output):
    """ Show campaign funnel metrics

    Displays a visual pipeline showing email delivery and engagement at
    each stage (sent → delivered → opened → clicked).

    \b
    Example usages:
        guard redteam campaign funnel abc-123
        guard redteam campaign funnel abc-123 --json-output
    """
    result = sdk.get(f'red-team/campaigns/{quote(campaign_id, safe="")}/funnel')
    if json_output:
        print_json(result)
        return

    if not result:
        click.echo(f'No funnel data for campaign {campaign_id}')
        return

    sent = int(result.get('sent') or 0)
    delivered = int(result.get('delivered') or 0)
    opened = int(result.get('opened') or 0)
    clicked = int(result.get('clicked') or 0)

    def pct(numerator, denominator):
        if denominator == 0:
            return '  —  '
        return f'{numerator / denominator * 100:5.1f}%'

    bar_width = 40

    def bar(count, total):
        if total == 0:
            return click.style('░' * bar_width, dim=True)
        filled = round(count / total * bar_width)
        return click.style('█' * filled, fg='cyan') + click.style('░' * (bar_width - filled), dim=True)

    click.echo()
    click.echo(click.style(f'Campaign Funnel: {campaign_id}', bold=True))
    click.echo(click.style('─' * 60, dim=True))
    click.echo()

    rows = [
        ('Sent', sent, sent, 'white'),
        ('Delivered', delivered, sent, 'green'),
        ('Opened', opened, delivered, 'yellow'),
        ('Clicked', clicked, opened, 'red'),
    ]

    for label, count, denom, color in rows:
        p = pct(count, denom)
        b = bar(count, sent)
        click.echo(f'  {click.style(label, bold=True, fg=color):<18} {b}  {click.style(str(count), bold=True):>6}  ({p})')
        if label != 'Clicked':
            click.echo(f'  {"":18}  {"▼":^{bar_width}}')

    click.echo()
    click.echo(click.style('─' * 60, dim=True))
    click.echo(f'  Overall click rate: {click.style(pct(clicked, sent), fg="cyan", bold=True)}')
    click.echo()


@campaign.command('activity')
@cli_handler
@click.argument('campaign_id')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def campaign_activity(sdk, campaign_id, json_output):
    """ View the activity feed for a campaign

    Lists recent events (sends, opens, clicks, bounces) in chronological
    order.

    \b
    Example usages:
        guard redteam campaign activity abc-123
        guard redteam campaign activity abc-123 --json-output
    """
    result = sdk.get(f'red-team/campaigns/{quote(campaign_id, safe="")}/activity')
    if json_output:
        print_json(result)
        return
    events = result if isinstance(result, list) else (result or {}).get('events', [])
    if not events:
        click.echo(f'No activity for campaign {campaign_id}')
        return
    event_colors = {
        'sent': 'white',
        'delivered': 'green',
        'opened': 'yellow',
        'clicked': 'red',
        'bounced': 'magenta',
        'failed': 'red',
    }
    click.echo(click.style(f'Activity feed: {campaign_id}', bold=True))
    click.echo(click.style('─' * 70, dim=True))
    for ev in events:
        ts = ev.get('timestamp') or ev.get('created_at') or ''
        event_type = ev.get('event') or ev.get('type') or ''
        email = ev.get('email') or ev.get('recipient') or ''
        color = event_colors.get(event_type.lower(), 'white')
        click.echo(
            f'  {click.style(ts, dim=True):<28}'
            f'  {click.style(event_type.upper(), fg=color, bold=True):<18}'
            f'  {email}'
        )


# ---------------------------------------------------------------------------
# campaign assistant commands
# ---------------------------------------------------------------------------

@campaign.command('draft')
@cli_handler
@click.option('--template', required=True, help='Email template name or context')
@click.option('--context', required=True, help='Business/scenario context for the email')
@click.option('--tone', default='professional', show_default=True,
              help='Desired tone (e.g., professional, urgent, friendly)')
def campaign_draft(sdk, template, context, tone):
    """ Generate a phishing email pretext draft using the LLM assistant

    Sends the template and context to the AI assistant which returns a
    fully drafted pretext email body ready for review.

    \b
    Example usages:
        guard redteam campaign draft --template invoice-lure --context "Finance team annual vendor audit" --tone urgent
        guard redteam campaign draft --template password-reset --context "IT team rolling out MFA" --tone professional
    """
    body = {'template': template, 'context': context, 'tone': tone}
    result = sdk.post('red-team/campaigns/assistant/draft', body)
    if not result:
        click.echo('No draft returned.')
        return
    draft = result.get('draft') or result.get('content') or result
    click.echo(click.style('Generated Draft:', bold=True))
    click.echo(click.style('─' * 60, dim=True))
    if isinstance(draft, str):
        click.echo(draft)
    else:
        print_json(draft)


@campaign.command('variants')
@cli_handler
@click.option('--template', required=True, help='Base template to generate variants from')
@click.option('--count', default=3, show_default=True, type=int, help='Number of variants to generate')
def campaign_variants(sdk, template, count):
    """ Generate template variants using the LLM assistant

    Produces multiple distinct variations of a phishing pretext to support
    A/B testing or target-specific personalization.

    \b
    Example usages:
        guard redteam campaign variants --template invoice-lure --count 3
        guard redteam campaign variants --template password-reset --count 5
    """
    body = {'template': template, 'count': count}
    result = sdk.post('red-team/campaigns/assistant/variants', body)
    variants = result if isinstance(result, list) else (result or {}).get('variants', [])
    if not variants:
        click.echo('No variants returned.')
        return
    for i, v in enumerate(variants, 1):
        click.echo(click.style(f'Variant {i}:', bold=True, fg='cyan'))
        click.echo(click.style('─' * 60, dim=True))
        content = v.get('content') or v.get('draft') or v if isinstance(v, dict) else v if isinstance(v, str) else str(v)
        if isinstance(content, str):
            click.echo(content)
        else:
            print_json(content)
        click.echo()


@campaign.command('recommendations')
@cli_handler
@click.argument('campaign_id')
def campaign_recommendations(sdk, campaign_id):
    """ Get LLM-powered recommendations for a campaign

    Analyzes campaign metrics and configuration to suggest improvements
    to targeting, timing, subject lines, or pretext.

    \b
    Example usages:
        guard redteam campaign recommendations abc-123
    """
    result = sdk.post('red-team/campaigns/assistant/recommendations', {'campaign_id': campaign_id})
    if not result:
        click.echo('No recommendations returned.')
        return
    recs = result.get('recommendations') or result.get('content') or result
    click.echo(click.style(f'Recommendations for campaign {campaign_id}:', bold=True))
    click.echo(click.style('─' * 60, dim=True))
    if isinstance(recs, list):
        for i, r in enumerate(recs, 1):
            text = r.get('text') or r.get('recommendation') or r if isinstance(r, (str, dict)) else str(r)
            click.echo(f'  {click.style(str(i) + ".", bold=True, fg="cyan")} {text}')
    elif isinstance(recs, str):
        click.echo(recs)
    else:
        print_json(recs)


# ---------------------------------------------------------------------------
# payload sub-group
# ---------------------------------------------------------------------------

@redteam.group('payload')
def payload():
    """ Generate offensive payloads """
    pass


@payload.command('generate')
@cli_handler
@click.option('--type', 'payload_type', required=True,
              help='Payload type (e.g., shellcode, macro, html-smuggling, hta)')
@click.option('--target', required=True, help='Target platform or description (e.g., windows/x64, office365)')
@click.option('--options', 'options', multiple=True,
              help='Extra generation options as KEY=VALUE (repeatable)')
@click.option('--json-output', is_flag=True, default=False, help='Output raw JSON response')
def payload_generate(sdk, payload_type, target, options, json_output):
    """ Generate an offensive payload

    Sends a generation request to the Guard payload engine. The returned
    artifact can be base64-encoded, a file path, or structured metadata
    depending on the payload type.

    \b
    Example usages:
        guard redteam payload generate --type shellcode --target windows/x64
        guard redteam payload generate --type macro --target office365 --options lhost=192.168.1.1 --options lport=4444
        guard redteam payload generate --type html-smuggling --target chrome --json-output
    """
    body = {'type': payload_type, 'target': target}
    if options:
        parsed = {}
        for opt in options:
            if '=' not in opt:
                error(f"Option '{opt}' is not in the format KEY=VALUE")
            k, v = opt.split('=', 1)
            parsed[k] = v
        body['options'] = parsed
    result = sdk.post('red-team/payload/generate', body)
    if json_output:
        print_json(result)
        return
    if not result:
        click.echo('No payload returned.')
        return
    click.echo(click.style('Payload generated:', fg='green', bold=True))
    click.echo(click.style('─' * 60, dim=True))
    artifact = result.get('payload') or result.get('artifact') or result.get('content')
    metadata = {k: v for k, v in result.items() if k not in ('payload', 'artifact', 'content')}
    if metadata:
        for key, value in metadata.items():
            click.echo(f'  {click.style(key, bold=True)}: {value}')
        if artifact:
            click.echo()
    if artifact:
        if isinstance(artifact, str):
            click.echo(artifact)
        else:
            print_json(artifact)
