import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


# Status → display color mapping
_STATUS_COLORS = {
    'open': 'yellow',
    'in_progress': 'cyan',
    'completed': 'green',
    'rejected': 'red',
}


def _colorize_status(status):
    """Return a click-styled status string."""
    color = _STATUS_COLORS.get(status, 'white')
    return click.style(status, fg=color, bold=True)


@chariot.group('remediation')
def remediation():
    """Manage remediation plans — create, track, and auto-generate pull requests for vulnerability fixes.

    Remediation plans tie a risk to an action plan, an optional assignee, and a
    lifecycle status (open → in_progress → completed / rejected).  The `pr`
    subcommand can auto-generate a GitHub pull request from the plan text.
    """
    pass


@remediation.command('list')
@cli_handler
@click.option('--status', default=None,
              type=click.Choice(['open', 'in_progress', 'completed', 'rejected']),
              help='Filter by remediation status')
@click.option('--json-output', is_flag=True, default=False,
              help='Emit raw JSON instead of formatted output')
def list_remediations(sdk, status, json_output):
    """List remediation plans for the current engagement.

    \b
    Options:
        --status     Show only plans in the given lifecycle state
        --json-output  Dump raw JSON response

    \b
    Example usages:
        - guard remediation list
        - guard remediation list --status open
        - guard remediation list --status completed --json-output
    """
    params = {}
    if status:
        params['status'] = status

    result = sdk.my({'type': 'remediation', **params})

    if json_output:
        print_json(result)
        return

    plans = result if isinstance(result, list) else result.get('remediations', [])
    if not plans:
        click.echo('No remediation plans found.')
        return

    for plan in plans:
        key = plan.get('key', '')
        s = plan.get('status', 'open')
        assignee = plan.get('assignee', '')
        plan_text = plan.get('plan', '')
        summary = (plan_text[:72] + '…') if len(plan_text) > 72 else plan_text

        risk_key = plan.get('risk_key', plan.get('riskKey', ''))

        status_str = _colorize_status(s)
        assignee_str = click.style(assignee, fg='white', dim=True) if assignee else click.style('(unassigned)', dim=True)

        click.echo(f'{click.style(key, bold=True)}')
        click.echo(f'  Risk:     {risk_key}')
        click.echo(f'  Status:   {status_str}')
        click.echo(f'  Assignee: {assignee_str}')
        if summary:
            click.echo(f'  Plan:     {summary}')
        click.echo()


@remediation.command('show')
@cli_handler
@click.argument('key', required=True)
@click.option('--json-output', is_flag=True, default=False,
              help='Emit raw JSON instead of formatted output')
def show_remediation(sdk, key, json_output):
    """Show details for a single remediation plan.

    \b
    Argument:
        - KEY: the key of an existing remediation plan

    \b
    Example usages:
        - guard remediation show "#remediation#api.example.com#CVE-2024-1234"
        - guard remediation show "#remediation#api.example.com#CVE-2024-1234" --json-output
    """
    result = sdk.get('remediation', {'key': key})
    if not result:
        error(f'Remediation plan not found: {key}')

    if json_output:
        print_json(result)
        return

    plan = result if isinstance(result, dict) else (result[0] if result else {})
    s = plan.get('status', 'open')
    click.echo(click.style('Remediation Plan', bold=True))
    click.echo(f'  Key:      {plan.get("key", key)}')
    click.echo(f'  Risk:     {plan.get("risk_key", plan.get("riskKey", ""))}')
    click.echo(f'  Status:   {_colorize_status(s)}')
    assignee = plan.get('assignee', '')
    click.echo(f'  Assignee: {assignee if assignee else click.style("(unassigned)", dim=True)}')
    click.echo(f'  Created:  {plan.get("created", "")}')
    click.echo(f'  Updated:  {plan.get("updated", "")}')
    click.echo()
    click.echo(click.style('Plan:', bold=True))
    click.echo(plan.get('plan', ''))


@remediation.command('create')
@cli_handler
@click.option('--risk-key', required=True, help='Key of the risk this plan addresses')
@click.option('--plan', required=True, help='Remediation plan description / action text')
@click.option('--assignee', default=None, help='Email of the engineer assigned to this plan')
@click.option('--json-output', is_flag=True, default=False,
              help='Emit raw JSON of the created plan')
def create_remediation(sdk, risk_key, plan, assignee, json_output):
    """Create a new remediation plan for a risk.

    \b
    Options:
        --risk-key   (required) Key of the associated risk
        --plan       (required) Free-text description of the remediation steps
        --assignee   Email address of the person responsible for the fix
        --json-output  Return the API response as JSON

    \b
    Example usages:
        - guard remediation create --risk-key "#risk#api.example.com#CVE-2024-1234" --plan "Upgrade openssl to 3.3.1"
        - guard remediation create --risk-key "#risk#api.example.com#CVE-2024-1234" \\
              --plan "Patch via Dependabot PR" --assignee dev@example.com
    """
    body = {
        'risk_key': risk_key,
        'plan': plan,
        'status': 'open',
    }
    if assignee:
        body['assignee'] = assignee

    result = sdk.post('remediation', body)
    if json_output:
        print_json(result)
        return

    created_key = (result or {}).get('key', risk_key)
    click.echo(click.style('Remediation plan created.', fg='green'))
    click.echo(f'  Key: {created_key}')


@remediation.command('update')
@cli_handler
@click.argument('key', required=True)
@click.option('--status',
              type=click.Choice(['open', 'in_progress', 'completed', 'rejected']),
              default=None, help='New lifecycle status')
@click.option('--plan', default=None, help='Updated plan text')
@click.option('--assignee', default=None, help='Reassign to this email address')
@click.option('--json-output', is_flag=True, default=False,
              help='Emit raw JSON of the updated plan')
def update_remediation(sdk, key, status, plan, assignee, json_output):
    """Update an existing remediation plan.

    \b
    Argument:
        - KEY: the key of an existing remediation plan

    \b
    Options:
        --status     New lifecycle status for the plan
        --plan       Replacement plan text
        --assignee   Reassign to a different engineer
        --json-output  Return the API response as JSON

    \b
    Example usages:
        - guard remediation update "#remediation#api.example.com#CVE-2024-1234" --status in_progress
        - guard remediation update "#remediation#api.example.com#CVE-2024-1234" --assignee lead@example.com
        - guard remediation update "#remediation#api.example.com#CVE-2024-1234" --status completed --plan "Patched in v2.3.1"
    """
    if not any([status, plan, assignee]):
        error('Provide at least one of --status, --plan, or --assignee to update.')

    body = {'key': key}
    if status:
        body['status'] = status
    if plan:
        body['plan'] = plan
    if assignee:
        body['assignee'] = assignee

    result = sdk.put('remediation', body)
    if json_output:
        print_json(result)
        return

    click.echo(click.style('Remediation plan updated.', fg='green'))
    click.echo(f'  Key: {key}')
    if status:
        click.echo(f'  Status: {_colorize_status(status)}')


@remediation.command('delete')
@cli_handler
@click.argument('key', required=True)
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def delete_remediation(sdk, key, force):
    """Delete a remediation plan.

    \b
    Argument:
        - KEY: the key of the remediation plan to delete

    \b
    Example usages:
        - guard remediation delete "#remediation#api.example.com#CVE-2024-1234"
        - guard remediation delete "#remediation#api.example.com#CVE-2024-1234" --force
    """
    if not force:
        click.confirm(f'Delete remediation plan {click.style(key, fg="yellow")}?', abort=True)
    sdk.delete('remediation', {'key': key}, {})
    click.echo(click.style('Remediation plan deleted.', fg='red'))
    click.echo(f'  Key: {key}')


@remediation.command('pr')
@cli_handler
@click.argument('key', required=True)
@click.option('--repo', default=None, help='Target GitHub repository (owner/repo)')
@click.option('--branch', default=None, help='Branch to open the pull request against')
@click.option('--json-output', is_flag=True, default=False,
              help='Emit raw JSON of the created pull request')
def create_pr(sdk, key, repo, branch, json_output):
    """Create a pull request from a remediation plan.

    Sends the plan text to the Guard backend, which opens a GitHub pull
    request containing the suggested fix against the specified repository.

    \b
    Argument:
        - KEY: the key of the remediation plan to turn into a PR

    \b
    Options:
        --repo     GitHub repository in owner/repo format
        --branch   Target branch for the pull request (default: main)
        --json-output  Return the API response as JSON

    \b
    Example usages:
        - guard remediation pr "#remediation#api.example.com#CVE-2024-1234" --repo acme/backend
        - guard remediation pr "#remediation#api.example.com#CVE-2024-1234" --repo acme/backend --branch develop
    """
    body = {'key': key}
    if repo:
        body['repo'] = repo
    if branch:
        body['branch'] = branch

    result = sdk.post('remediation/pr', body)
    if json_output:
        print_json(result)
        return

    pr_url = (result or {}).get('url', '')
    click.echo(click.style('Pull request created.', fg='green'))
    if pr_url:
        click.echo(f'  URL: {click.style(pr_url, fg="cyan", underline=True)}')
    else:
        print_json(result)
