import os.path

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import error
from praetorian_cli.sdk.model.globals import AddRisk, Asset, Seed


@chariot.group()
def add():
    """ Add an entity to Chariot """
    pass


@add.command()
@cli_handler
@click.option('-d', '--dns', required=True, help='The DNS of the asset')
@click.option('-n', '--name', required=False, help='The name of the asset, e.g, IP address, GitHub repo URL')
@click.option('-s', '--status', type=click.Choice([s.value for s in Asset]), required=False,
              default=Asset.ACTIVE.value, help=f'Status of the asset', show_default=True)
@click.option('-f', '--surface', required=False, default='', help=f'Attack surface of the asset', show_default=False)
def asset(sdk, name, dns, status, surface):
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
        - praetorian chariot add asset --dns internal.example.com --name 10.2.3.4 --surface internal
    """
    if not name:
        name = dns
    sdk.assets.add(dns, name, status, surface)


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
@click.option('-c', '--comment', default='', help='Comment for the risk')
@click.option('-cap', '--capability', default='', help='Capability that discoverd the risk')
def risk(sdk, name, asset, status, comment, capability):
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
        - praetorian chariot add risk CVE-2024-23049 --asset "#asset#example.com#1.2.3.4" --status TC --capability red-team
    """
    sdk.risks.add(asset, name, status, comment, capability)


@add.command()
@cli_handler
@click.option('-k', '--key', required=True, help='Key of an existing asset or attribute')
@click.option('-c', '--capability', 'capabilities', multiple=True,
              help='Capabilities to run (can be specified multiple times)')
def job(sdk, key, capabilities):
    """ Schedule scan jobs for an asset or an attribute

    This command schedules the relevant discovery and vulnerability scans for
    the specified asset or attribute. Make sure to quote the key, since it
    contains the "#" sign.

    \b
    Example usages:
        - praetorian chariot add job --key "#asset#example.com#1.2.3.4"
        - praetorian chariot add job --key "#asset#example.com#1.2.3.4" -c subdomain -c portscan
        - praetorian chariot add job --key "#attribute#ssh#22#asset#api.www.example.com#1.2.3.4"
    """
    sdk.jobs.add(key, capabilities)


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


@add.command()
@cli_handler
@click.option('-d', '--dns', required=True, help='The DNS of the asset')
@click.option('-s', '--status', type=click.Choice([s.value for s in Seed]),
              default=Seed.PENDING.value, help='The status of the seed', show_default=True)
def seed(sdk, dns, status):
    """ Add a seed

    Add a seed to the Chariot database. This command requires DNS of the seed to be
    specified. When status is not specified, the seed is added as PENDING.

    \b
    Example usages:
        - praetorian chariot add seed --dns example.com
        - praetorian chariot add seed --dns example.com --status A
    """
    sdk.seeds.add(dns, status)


@add.command()
@cli_handler
@click.option('-t', '--type', required=True, help='Preseed type')
@click.option('-l', '--title', required=True, help='Preseed title')
@click.option('-v', '--value', required=True, help='Preseed value')
@click.option('-s', '--status', required=False, default='A', help='Preseed status', show_default=True)
def preseed(sdk, type, title, value, status):
    """ Add a preseed

    This command adds a preseed to the Chariot database. 
    Preseeds default to ACTIVE and cannot be added as PENDING.

    \b 
    Example usages:
        - praetorian chariot add preseed -t "whois+company" -l "Example Company" -v "example company"
        - praetorian chariot add preseed --type "whois+company" --title "Example Company" --value "example company" --status "A"
    """
    sdk.preseeds.add(type, title, value, status)


@add.command()
@cli_handler
@click.option('-n', '--name', required=True, help='Name of the setting')
@click.option('-v', '--value', required=True, help='Value of the setting')
def setting(sdk, name, value):
    """ Add a setting

    This command adds a name-value setting.

    \b
    Example usages:
        - praetorian chariot add setting --name "rate-limit" --value '{"capability-rate-limit": 100}'
    """
    sdk.settings.add(name, value)


@add.command()
@cli_handler
@click.option('-n', '--name', required=True, help='Name of the configuration')
@click.option('-v', '--value', required=True, help='Value of the configuration')
@praetorian_only
def configuration(sdk, name, value):
    """ Add a configuration

    This command adds a name-value configuration.

    \b
    Example usages:
        - praetorian chariot add configuration --name "nuclei" --value '{"extra-tags": "http,sql"}'
    """
    sdk.configurations.add(name, value)
