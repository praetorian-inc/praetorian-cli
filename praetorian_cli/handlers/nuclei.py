"""Nuclei template management handler for the Guard platform."""
from urllib.parse import quote

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


SEVERITY_STYLES = {
    'critical': {'fg': 'red', 'bold': True},
    'high':     {'fg': 'red'},
    'medium':   {'fg': 'yellow'},
    'low':      {'fg': 'cyan'},
    'info':     {'dim': True},
}


def _style_severity(severity):
    """Return a click-styled severity string."""
    key = (severity or '').lower()
    style = SEVERITY_STYLES.get(key, {})
    return click.style(severity or 'unknown', **style)


@chariot.group('nuclei')
def nuclei():
    """Manage Nuclei vulnerability scanning templates — list, view, and commit template changes.

    Interact with the Guard Nuclei template library: browse templates by
    severity, tag, or author; inspect individual template content; explore
    available branches; and commit new or updated templates back to the store.
    """


@nuclei.command('list')
@cli_handler
@click.option('--severity', default=None, help='Filter by severity (critical, high, medium, low, info)')
@click.option('--tag', default=None, help='Filter by tag')
@click.option('--author', default=None, help='Filter by template author')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def list_templates(sdk, severity, tag, author, json_output):
    """List Nuclei templates, with optional filtering.

    \b
    Templates are displayed with their ID, severity, tags, and author.
    Severity is colour-coded for quick scanning:
      critical  red bold
      high      red
      medium    yellow
      low       cyan
      info      dim

    \b
    Examples:
        guard nuclei list
        guard nuclei list --severity critical
        guard nuclei list --tag cve
        guard nuclei list --author praetorian --json-output
    """
    params = {}
    if severity:
        params['severity'] = severity
    if tag:
        params['tag'] = tag
    if author:
        params['author'] = author

    path = 'nuclei-templates'
    if params:
        qs = '&'.join(f'{k}={quote(str(v), safe="")}' for k, v in params.items())
        path = f'{path}?{qs}'

    data = sdk.get(path)

    if json_output:
        print_json(data)
        return

    templates = data if isinstance(data, list) else data.get('templates') or data.get('data') or []

    if not templates:
        click.echo(click.style('No templates found.', dim=True))
        return

    if templates and isinstance(templates[0], str):
        click.echo(click.style(f'{len(templates)} template(s)', bold=True))
        click.echo(click.style('─' * 80, dim=True))
        for path in templates:
            if path.startswith('.'):
                continue
            click.echo(f'  {path}')
        return

    id_width = max((len(str(t.get('id', t.get('path', '')))) for t in templates), default=40)
    id_width = min(id_width, 70)

    header = (
        click.style(f"{'ID':<{id_width}}", bold=True)
        + '  '
        + click.style(f"{'SEVERITY':<10}", bold=True)
        + '  '
        + click.style(f"{'TAGS':<30}", bold=True)
        + '  '
        + click.style('AUTHOR', bold=True)
    )
    click.echo(header)
    click.echo(click.style('─' * (id_width + 60), dim=True))

    for tpl in templates:
        template_id = str(tpl.get('id') or tpl.get('path') or '')
        sev = tpl.get('severity') or tpl.get('info', {}).get('severity', '')
        tags_raw = tpl.get('tags') or tpl.get('info', {}).get('tags', [])
        if isinstance(tags_raw, list):
            tags_str = ', '.join(tags_raw)
        else:
            tags_str = str(tags_raw)
        tpl_author = tpl.get('author') or tpl.get('info', {}).get('author', '')
        if isinstance(tpl_author, list):
            tpl_author = ', '.join(tpl_author)

        row = (
            f"{template_id:<{id_width}}"
            + '  '
            + _style_severity(sev).ljust(10 + (len(_style_severity(sev)) - len(sev)))
            + '  '
            + f"{tags_str:<30}"
            + '  '
            + str(tpl_author)
        )
        click.echo(row)


@nuclei.command('show')
@cli_handler
@click.option('--template-id', required=True, help='Template ID or path to retrieve')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def show_template(sdk, template_id, json_output):
    """Show the full details of a specific Nuclei template.

    \b
    Fetches the template record by its ID or path and prints all available
    fields, including the raw YAML content when present.

    \b
    Examples:
        guard nuclei show --template-id cves/2024/CVE-2024-1234.yaml
        guard nuclei show --template-id CVE-2024-1234 --json-output
    """
    data = sdk.get(f'nuclei-template?id={quote(template_id, safe="")}')

    if not data:
        error(f'Template not found: {template_id}')

    if json_output:
        print_json(data)
        return

    # Pretty-print the main metadata fields
    info = data.get('info') or {}
    sev = data.get('severity') or info.get('severity', '')
    name = data.get('name') or info.get('name', template_id)
    description = data.get('description') or info.get('description', '')
    tags_raw = data.get('tags') or info.get('tags', [])
    tags_str = ', '.join(tags_raw) if isinstance(tags_raw, list) else str(tags_raw)
    author_raw = data.get('author') or info.get('author', '')
    author_str = ', '.join(author_raw) if isinstance(author_raw, list) else str(author_raw)

    click.echo(click.style('Template', bold=True) + f': {name}')
    click.echo(click.style('ID', bold=True)       + f': {template_id}')
    click.echo(click.style('Severity', bold=True) + f': {_style_severity(sev)}')
    if author_str:
        click.echo(click.style('Author', bold=True)   + f': {author_str}')
    if tags_str:
        click.echo(click.style('Tags', bold=True)     + f': {tags_str}')
    if description:
        click.echo(click.style('Description', bold=True) + f': {description}')

    content = data.get('content') or data.get('raw') or data.get('yaml') or ''
    if content:
        click.echo()
        click.echo(click.style('─── Template Content ───', dim=True))
        click.echo(content)


@nuclei.command('branches')
@cli_handler
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def list_branches(sdk, json_output):
    """List available Nuclei template branches.

    \b
    Returns the set of branches from which templates can be fetched or
    committed to in the Guard template store.

    \b
    Examples:
        guard nuclei branches
        guard nuclei branches --json-output
    """
    data = sdk.get('nuclei-templates/branches')

    if json_output:
        print_json(data)
        return

    branches = data if isinstance(data, list) else data.get('branches') or data.get('data') or []

    if not branches:
        click.echo(click.style('No branches found.', dim=True))
        return

    click.echo(click.style('Available branches:', bold=True))
    for branch in branches:
        name = branch if isinstance(branch, str) else branch.get('name', str(branch))
        click.echo(f'  {name}')


@nuclei.command('commit')
@cli_handler
@click.option('--template-id', required=True,  help='Template ID or path (e.g. cves/2024/CVE-2024-1234.yaml)')
@click.option('--content',     required=True,  help='Raw YAML content of the template')
@click.option('--message',     default=None,   help='Commit message describing the change')
@click.option('--branch',      default=None,   help='Target branch (defaults to server default)')
@click.option('--json-output', is_flag=True, default=False, help='Print raw JSON response')
def commit_template(sdk, template_id, content, message, branch, json_output):
    """Commit a new or updated Nuclei template to the Guard template store.

    \b
    Sends the supplied YAML content to the /templates/commit endpoint. Use
    --branch to target a non-default branch and --message to annotate the
    change for the audit log.

    \b
    Examples:
        guard nuclei commit \\
            --template-id cves/2024/CVE-2024-1234.yaml \\
            --content "$(cat CVE-2024-1234.yaml)"

        guard nuclei commit \\
            --template-id custom/my-check.yaml \\
            --content "$(cat my-check.yaml)" \\
            --message "add custom SQL injection check" \\
            --branch feature/new-templates
    """
    body = {
        'id':      template_id,
        'content': content,
    }
    if message:
        body['message'] = message
    if branch:
        body['branch'] = branch

    data = sdk.post('templates/commit', body)

    if not data:
        error('Commit returned an empty response — check the template ID and content.')

    if json_output:
        print_json(data)
        return

    commit_sha = data.get('sha') or data.get('commit') or data.get('id', '')
    status = data.get('status', 'committed')

    click.echo(
        click.style('Template committed successfully.', fg='green', bold=True)
    )
    if commit_sha:
        click.echo(f'  Commit : {commit_sha}')
    click.echo(f'  ID     : {template_id}')
    click.echo(f'  Status : {status}')
    if branch:
        click.echo(f'  Branch : {branch}')
