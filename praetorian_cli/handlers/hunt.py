import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, render_list_results, pagination_size


@chariot.group()
def hunt():
    """Manage Hannibal hunts — launch, monitor, and control automated vulnerability discovery."""
    pass


@hunt.command()
@cli_handler
@click.option('-p', '--prompt', required=True, help='The hunt objective / central mandate')
@click.option('-e', '--expires', type=int, default=72, show_default=True,
              help='Hours until the hunt expires (max 72)')
@click.option('-a', '--agent', type=click.Choice(['hannibal', 'hannibal-cloud', 'hannibal-webapp', 'hannibal-llm']),
              default='hannibal', show_default=True, help='Agent type')
@click.option('-s', '--scope', multiple=True, help='Target asset keys to restrict the hunt (repeatable)')
@click.option('--scope-level', type=click.Choice(['normal', 'strict']), default='normal', show_default=True)
@click.option('--aggressiveness', type=click.Choice(['cautious', 'balanced', 'aggressive']),
              default='balanced', show_default=True)
def launch(sdk, prompt, expires, agent, scope, scope_level, aggressiveness):
    """Launch a new hunt against the current account.

    Example usages:
        guard hunt launch --prompt "Find XSS vulnerabilities in web applications"
        guard hunt launch --prompt "Test API endpoints" --agent hannibal-webapp --expires 24
        guard hunt launch --prompt "Cloud misconfigs" --agent hannibal-cloud --scope "#asset#example.com#1.2.3.4"
    """
    result = sdk.hunts.create(
        prompt=prompt,
        expires_hours=expires,
        agent=agent,
        scope=list(scope) if scope else None,
        scope_level=scope_level,
        aggressiveness=aggressiveness,
    )
    print_json(result)


@hunt.command('list')
@cli_handler
@click.option('-s', '--status', type=click.Choice(['active', 'paused', 'completed', 'stopped', 'expired', 'errored']),
              default=None, help='Filter by hunt status')
@click.option('-d', '--details', is_flag=True, default=False, help='Show detailed information')
@click.option('-p', '--page', type=click.Choice(['first', 'all']), default='first', show_default=True)
def list_hunts(sdk, status, details, page):
    """List hunts for the current account.

    Example usages:
        guard hunt list
        guard hunt list --status active --details
        guard hunt list --page all
    """
    render_list_results(sdk.hunts.list(status=status, pages=pagination_size(page)), details)


@hunt.command()
@cli_handler
@click.argument('uuid')
def status(sdk, uuid):
    """Show detailed status of a hunt.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt status a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    result = sdk.hunts.get(uuid)
    if not result:
        click.secho(f'Hunt {uuid} not found.', fg='red', err=True)
        return
    fields = {
        'uuid': result.get('uuid', result.get('key', '').replace('#hunt#', '')),
        'status': result.get('status'),
        'agent': result.get('agent'),
        'prompt': result.get('prompt', '')[:120],
        'iterations': result.get('iterationCount', 0),
        'findings': result.get('findingsCount', 0),
        'created': result.get('created'),
        'expires': result.get('expiresAt'),
        'lastError': result.get('lastError', ''),
    }
    print_json(fields)


@hunt.command()
@cli_handler
@click.argument('uuid')
def stop(sdk, uuid):
    """Stop a running hunt permanently.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt stop a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    result = sdk.hunts.stop(uuid)
    click.echo(f'Hunt {uuid} stopped.')
    print_json(result)


@hunt.command()
@cli_handler
@click.argument('uuid')
def pause(sdk, uuid):
    """Pause an active hunt.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt pause a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    result = sdk.hunts.pause(uuid)
    click.echo(f'Hunt {uuid} paused.')
    print_json(result)


@hunt.command()
@cli_handler
@click.argument('uuid')
def resume(sdk, uuid):
    """Resume a paused hunt.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt resume a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    result = sdk.hunts.resume(uuid)
    click.echo(f'Hunt {uuid} resumed.')
    print_json(result)


@hunt.command('delete')
@cli_handler
@click.argument('uuid')
@click.confirmation_option(prompt='This will delete the hunt and its artifacts. Findings are preserved. Continue?')
def delete_hunt(sdk, uuid):
    """Delete a hunt. Findings are preserved.

    Argument:
        UUID: the hunt's UUID

    Example usage:
        guard hunt delete a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    sdk.hunts.delete(uuid)
    click.echo(f'Hunt {uuid} deleted.')
