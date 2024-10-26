import os.path

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import AssetPriorities, error
from praetorian_cli.sdk.model.globals import AddRisk


@chariot.group()
def add():
    """ Add an entity to Chariot """
    pass


@add.command()
@cli_handler
@click.option('-d', '--dns', required=True, help='The DNS of the asset')
@click.option('-n', '--name', required=False, help='The name of the asset, e.g, IP address, GitHub repo URL')
@click.option('-p', '--priority', type=click.Choice(AssetPriorities.keys()),
              default='standard', help='The priority of the asset', show_default=True)
def asset(sdk, name, dns, priority):
    """ Add an asset

    Add an asset to the Chariot database. This command requires a DNS name for the asset.
    Optionally, a name can be provided to give the asset more specific information,
    such as IP address. If no name is provided, the DNS name will be used as the name.

    \b
    Example assets:
        - A domain name:   reddit.com
        - An IP addresses: 208.67.222.222
        - A CIDR range:    208.67.222.0/24

    \b
    Example usages:
        - praetorian chariot add asset --dns example.com
        - praetorian chariot add asset --dns example.com --name 1.2.3.4
        - praetorian chariot add asset --dns example.com --name 1.2.3.4 --priority comprehensive
        - praetorian chariot add asset --dns example.com --name 1.2.3.4 --priority discover
    """
    if not name:
        name = dns
    sdk.assets.add(dns, name, AssetPriorities[priority])


@add.command()
@cli_handler
@click.argument('path')
@click.option('-n', '--name', help='The file name in Chariot. Default: the full path of the uploaded file')
def file(sdk, path, name):
    """ Upload a file

    This commands takes the path to a local file and uploads it to the
    Chariot file system. The Chariot file system is where the platform
    stores proofs of exploit, risk definitions, and other supporting data.

    User files reside in the "home/" folder. Those files appear in the app
    at https://chariot.praetorian.com/app/files

    \b
    Arguments:
        - PATH: the local file path to the file you want to upload.

    \b
    Example usages:
        - praetorian chariot add file ./file.txt
        - praetorian chariot add file ./file.txt --name "home/file.txt"
    """
    try:
        sdk.files.add(path, name)
    except Exception as e:
        error(f'Unable to upload file {path}. Error: {e}')


@add.command()
@cli_handler
@click.argument('path')
@click.option('-n', '--name', help='The risk name definition. Default: the filename used')
def definition(sdk, path, name):
    """ Upload a risk definition

    This commands takes the path to the local file and uploads it to the
    Chariot file system as risk definitions. Risk definitions reside
    in the "definitions/" folder in the file system.

    Risk definitions need to be in the Markdown format.

    \b
    Arguments
        - PATH: the local file path to the risk definition file

    \b
    Example usages:
        - praetorian chariot add definition ./CVE-2024-23049
        - praetorian chariot add definition ./CVE-2024-23049.updated.md --name CVE-2024-23049
    """
    if name is None:
        name = os.path.basename(path)
    try:
        sdk.definitions.add(path, name)
    except Exception as e:
        error(f'Unable to upload risk definition file {path}. Error: {e}')


@add.command()
@cli_handler
def webhook(sdk):
    """ Generate an authenticated URL for posting assets and risks

    The command prints the URL of the webhook generated. If the webhook
    is already present, you need to first delete it before generating
    a new one.

    \b
    Example usages:
        - praetorian chariot add webhook
    """
    if sdk.webhook.get_record():
        click.echo('There is an existing webhook. Delete it first before adding a new one.')
    else:
        click.echo(sdk.webhook.upsert())


@add.command()
@cli_handler
@click.argument('name', required=True)
@click.option('-a', '--asset', required=True, help='Key of an existing asset')
@click.option('-s', '--status', type=click.Choice([s.value for s in AddRisk]), required=True,
              help=f'Status of the risk')
@click.option('-comment', '--comment', default='', help='Comment for the risk')
def risk(sdk, name, asset, status, comment):
    """ Add a risk

    This command adds a risk to Chariot. A risk must have an associated asset.
    The asset is specified by its key, which can be retrieved by listing and
    searching the assets.

    \b
    Arguments:
        - NAME: the name of the risk. For example, "CVE-2024-23049".

    \b
    Example usages:
        - praetorian chariot add risk CVE-2024-23049 --asset "#asset#example.com#1.2.3.4" --status TI
        - praetorian chariot add risk CVE-2024-23049 --asset "#asset#example.com#1.2.3.4" --status TC
    """
    sdk.risks.add(asset, name, status, comment)


@add.command()
@cli_handler
@click.option('-k', '--key', required=True, help='Key of an existing asset or attribute')
def job(sdk, key):
    """ Schedule scan jobs for an asset or an attribute

    This command schedules the relevant discovery and vulnerability scans for
    the specified asset or attribute. Make sure to quote the key, since it
    contain the "#" sign.

    \b
    Example usages:
        - praetorian chariot add job --key "#asset#example.com#1.2.3.4"
        - praetorian chariot add job --key "#attribute#ssh#22#asset#api.www.example.com#1.2.3.4"
    """
    sdk.jobs.add(key)


@add.command()
@cli_handler
@click.option('-k', '--key', required=True, help='Key of an existing asset or risk')
@click.option('-n', '--name', required=True, help='Name of the attribute')
@click.option('-v', '--value', required=True, help='Value of the attribute')
def attribute(sdk, key, name, value):
    """ Add an attribute for an asset or risk

    This command adds a name-value attribute for the specified asset or risk.

    \b
    Example usages:
        - praetorian chariot add attribute --key "#risk#www.example.com#CVE-2024-23049" --name https --value 443
        - praetorian chariot add attribute --key "#asset#www.example.com#www.example.com" --name id --value "arn:aws:route53::1654874321:hostedzone/Z0000000EJBHGTFTGH3"
    """
    sdk.attributes.add(key, name, value)
