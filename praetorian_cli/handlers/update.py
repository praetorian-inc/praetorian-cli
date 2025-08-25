import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.sdk.model.globals import Risk, Seed, Asset


@chariot.group()
def update():
    """ Update an entity in Chariot """
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
        - praetorian chariot update asset "#asset#www.example.com#1.2.3.4" -s F
        - praetorian chariot update asset "#asset#www.example.com#1.2.3.4" -f internal
    """
    chariot.assets.update(key, status, surface)


@update.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-s', '--status', type=click.Choice([s.value for s in Risk]), help=f'Status of the risk')
@click.option('-c', '--comment', default='', help='Comment for the risk')
def risk(chariot, key, status, comment):
    """ Update the status and comment of a risk

    \b
    Argument:
        - KEY: the key of an existing risk

    \b
    Example usages:
        - praetorian chariot update risk "#risk#www.example.com#CVE-2024-23049" --status OH --comment "Open it as a high severity risk"
        - praetorian chariot update risk "#risk#www.example.com#open-ssh-port" --status RH --comment "John stopped sshd on the server"
    """
    chariot.risks.update(key, status, comment)


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
        - praetorian chariot update seed "#asset#example.com#example.com" -s A
        - praetorian chariot update seed "#asset#1.1.1.0/24#1.1.1.0/24" -s F
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
        - praetorian chariot update preseed "#preseed#whois+company#Example Company" -s A
    """
    chariot.preseeds.update(key, status)