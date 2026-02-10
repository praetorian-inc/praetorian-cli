import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.sdk.model.globals import Risk, Seed, Asset


@chariot.group()
def update():
    """ Update an entity in Guard """
    pass


@update.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-s', '--status', type=click.Choice([s.value for s in Asset]), help='The status of the asset')
@click.option('-f', '--surface', required=False, default='', help=f'Attack surface of the asset', show_default=False)
def asset(chariot, key, status, surface):
    """ Update the status or surface of an asset

    \b
    Argument:
        - KEY: the key of an existing asset

    \b
    Example usages:
        - guard update asset "#asset#www.example.com#1.2.3.4" -s F
        - guard update asset "#asset#www.example.com#1.2.3.4" -f internal
    """
    chariot.assets.update(key, status, surface)


@update.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-s', '--status', type=click.Choice([s.value for s in Risk]), help=f'Status of the risk')
@click.option('-c', '--comment', default='', help='Comment for the risk')
@click.option('-r', '--remove-comment', type=int, default=None, help='Remove comment at index (0, 1, ... or -1 for most recent)')
def risk(chariot, key, status, comment, remove_comment):
    """ Update the status and comment of a risk

    \b
    Argument:
        - KEY: the key of an existing risk

    \b
    Example usages:
        - guard update risk "#risk#www.example.com#CVE-2024-23049" --status OH --comment "Open it as a high severity risk"
        - guard update risk "#risk#www.example.com#open-ssh-port" --status RH --comment "John stopped sshd on the server"
        - guard update risk "#risk#www.example.com#CVE-2024-23049" --remove-comment 0
        - guard update risk "#risk#www.example.com#CVE-2024-23049" --remove-comment -1
    """
    if comment and remove_comment is not None:
        raise click.UsageError("Cannot use --comment and --remove-comment together")

    chariot.risks.update(key, status, comment, remove_comment)


@update.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-s', '--status', type=click.Choice([s.value for s in Seed]), required=True,
              help='The status of the seed')
def seed(chariot, key, status):
    """ Update the status of a seed

    \b
    Argument:
        - KEY: the key of an existing seed

    \b
    Example usages:
        - guard update seed "#asset#example.com#example.com" -s A
        - guard update seed "#asset#1.1.1.0/24#1.1.1.0/24" -s F
    """
    
    chariot.seeds.update(key, status)

@update.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-s', '--status', type=click.Choice([s.value for s in Seed]), required=True,
              help='The status of the preseed')
def preseed(chariot, key, status):
    """ Update the status of a preseed

    \b
    Argument:
        - KEY: the key of an existing preseed

    \b
    Example usages:
        - guard update preseed "#preseed#whois+company#Example Company" -s A
    """
    chariot.preseeds.update(key, status)


@update.command()
@cli_handler
@click.argument('schedule_id', required=True)
@click.option('--pause', 'action', flag_value='pause', help='Pause the schedule')
@click.option('--resume', 'action', flag_value='resume', help='Resume the schedule')
def schedule(chariot, schedule_id, action):
    """ Pause or resume a capability schedule

    \b
    Argument:
        - SCHEDULE_ID: the ID of an existing schedule

    \b
    Example usages:
        - guard update schedule abc123-def456 --pause
        - guard update schedule abc123-def456 --resume
    """
    if not action:
        raise click.UsageError('Must specify --pause or --resume')

    if action == 'pause':
        chariot.schedules.pause(schedule_id)
        click.echo(f'Schedule {schedule_id} paused')
    else:
        chariot.schedules.resume(schedule_id)
        click.echo(f'Schedule {schedule_id} resumed')