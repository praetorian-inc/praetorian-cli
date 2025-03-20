import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.sdk.model.globals import Risk, Seed, Asset


@chariot.group()
def update():
    """ Update an entity in Chariot """
    pass


@update.command()
@cli_handler
@click.argument('key', required=True)
@click.option('-s', '--status', type=click.Choice([s.value for s in Asset]), required=True,
              help='The status of the asset')
def asset(chariot, key, status):
    """ Update the status of an asset

    \b
    Argument:
        - KEY: the key of an existing asset

    \b
    Example usages:
        - praetorian chariot update asset "#asset#www.example.com#1.2.3.4" -s F
    """
    chariot.assets.update(key, status)


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
        - praetorian chariot update seed "#seed#domain#example.com" -s A
        - praetorian chariot update seed "#seed#ip#1.1.1.0/24" -s F
    """
    chariot.seeds.update(key, status)
