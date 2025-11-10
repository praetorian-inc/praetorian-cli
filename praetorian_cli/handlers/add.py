import datetime
import json
import os.path

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import error, parse_configuration_value
from praetorian_cli.sdk.model.globals import AddRisk, Asset, Seed, Kind


@chariot.group()
def add():
    """ Add an entity to Chariot """
    pass


@add.command()
@cli_handler
@click.option('-d', '--dns', required=True, help='The DNS of the asset')
@click.option('-n', '--name', required=False, help='The name of the asset, e.g, IP address')
@click.option('-t', '--type', 'asset_type', required=False, help='The type of the asset (asset, repository, etc.)', default=Kind.ASSET.value)
@click.option('-s', '--status', type=click.Choice([s.value for s in Asset]), required=False,
              default=Asset.ACTIVE.value, help=f'Status of the asset', show_default=True)
@click.option('-f', '--surface', required=False, default='', help=f'Attack surface of the asset', show_default=False)
def asset(sdk, name, dns, asset_type, status, surface):
    """ Add an asset

    Add an asset to the Chariot database. This command requires a DNS name for the asset.
    Optionally, a name can be provided to give the asset more specific information,
    such as IP address. If no name is provided, the DNS name will be used as the name.
    The DNS is the group and the name is the specific identifier. This is for legacy reasons.

    The type can be one of the following: asset, addomain, repository, webapplication.

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
        - praetorian chariot add asset --dns https://example.com --name 'Example Web Application' --type webapplication
    """
    if not name:
        name = dns
    sdk.assets.add(dns, name, asset_type, status, surface)


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
@click.option('-g', '--config', help='JSON configuration string')
@click.option('-s', '--credential', 'credentials', help='Credential ID to use with the job', multiple=True)
def job(sdk, key, capabilities, config, credentials):
    """ Schedule scan jobs for an asset or an attribute

    This command schedules the relevant discovery and vulnerability scans for
    the specified asset or attribute. Make sure to quote the key, since it
    contains the "#" sign.

    \b
    Example usages:
        - praetorian chariot add job --key "#asset#example.com#1.2.3.4"
        - praetorian chariot add job --key "#asset#example.com#1.2.3.4" -c subdomain -c portscan
        - praetorian chariot add job --key "#attribute#ssh#22#asset#api.www.example.com#1.2.3.4"
        - praetorian chariot add job --key "#asset#example.com#1.2.3.4" --config '{"run-type":"login"}'
        - praetorian chariot add job --key "#asset#example.com#1.2.3.4" --config '{"run-type":"login"} --credential "E4644F37-6985-40B4-8D07-5311516D98F1"'
    """
    sdk.jobs.add(key, capabilities, config, credentials)


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
@click.option('-t', '--type', 'seed_type', default='asset', help='Asset type (e.g., asset, addomain)')
@click.option('-s', '--status', type=click.Choice([s.value for s in Seed]),
              default=Seed.PENDING.value, help='The status of the seed', show_default=True)
@click.option('-f', '--field', 'field_list', multiple=True, 
              help='Field in format name:value (can be specified multiple times)')
def seed(sdk, seed_type, status, field_list):
    """ Add a seed

    Add a seed to the Chariot database. Seeds are now assets with special labeling.
    You can specify the asset type and provide dynamic fields using --fields.

    \b
    Example usages:
        - praetorian chariot add seed --type asset --field dns:example.com
        - praetorian chariot add seed --type asset --field dns:example.com --status A
        - praetorian chariot add seed --type asset --field dns:example.com --field name:1.2.3.4
        - praetorian chariot add seed --type addomain --field domain:corp.local --field objectid:S-1-5-21-2701466056-1043032755-2418290285
    """
    # Collect dynamic fields from the --fields option
    dynamic_fields = {}
    
    # Parse field_list entries (name:value format)
    for field in field_list:
        if ':' in field:
            # Split only once to allow colons in the value
            name, value = field.split(':', 1)
            dynamic_fields[name] = value
        else:
            error(f"Field '{field}' is not in the format name:value")
            return
    
    # Call the updated add method with type and dynamic fields
    sdk.seeds.add(status=status, seed_type=seed_type, **dynamic_fields)


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
@click.option('-e', '--entry', required=False, multiple=True,
              help='Key-value pair in format key=value. Can be specified multiple times to set multiple values.')
@click.option('--string', 'string_value', required=False,
              help='Set the configuration value to a string')
@click.option('--integer', 'integer_value', required=False,
              help='Set the configuration value to an integer')
@click.option('--float', 'float_value', required=False,
              help='Set the configuration value to a floating point number')
@praetorian_only
def configuration(sdk, name, entry, string_value, integer_value, float_value):
    """ Add a configuration

    This command adds, or overwrites if exists, a configuration value.

    Configuration values can be provided as a mapping of key-value pairs using
    ``--entry`` (the previous behavior), or as primitive values using
    ``--string``, ``--integer``, or ``--float``.

    \b
    Example usages:
        - praetorian chariot add configuration --name "nuclei" --entry extra-tags=http,sql --entry something=else
        - praetorian chariot add configuration --name "billing-status" --string PAID_MS
        - praetorian chariot add configuration --name "request-timeout" --integer 60
        - praetorian chariot add configuration --name "scoring-threshold" --float 0.85
    """
    config_value = parse_configuration_value(entry, string_value, integer_value, float_value)
    sdk.configurations.add(name, config_value)


@add.command()
@cli_handler
@click.option('-n', '--name', required=True, help='Name of the API key')
@click.option('-e', '--expires', required=True, help='Duration until key expiration, in days', type=int)
def key(sdk, name, expires):
    """ Add an API key

    This command creates a new API key for authentication.

    \b
    Example usages:
        - praetorian chariot add key --name "my-automation-key"
        - praetorian chariot add key --name "ci-cd-key"
    """

    expiresT = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=expires)
    result = sdk.keys.add(name, expires=expiresT.strftime('%Y-%m-%dT%H:%M:%SZ'))
    if 'secret' not in result:
        click.echo(f"Error: secret value was not present in the response")
        return
    click.echo(f'API key created: {result.get("key", "N/A")}')
    click.echo(f'Secret (save this, it will not be shown again): {result["secret"]}')


@add.command()
@cli_handler
@click.option('-u', '--url', required=True, help='The full URL of the page')
@click.option('-p', '--parent', required=False, help='Optional key of the parent WebApplication')
def webpage(sdk, url, parent):
    """ Add a Webpage

    Add a web page to the Chariot database. Webpages can optionally be associated
    with a parent WebApplication or exist independently.

    \b
    Example usages:
        - praetorian chariot add webpage --url https://app.example.com/login
        - praetorian chariot add webpage --url https://app.example.com/admin --parent "#webapplication#https://app.example.com"
    """
    sdk.webpage.add(url, parent)


@add.command()
@cli_handler
@click.option('-r', '--resource-key', required=True, help='The resource key for the credential (e.g., account key)')
@click.option('-c', '--category', required=True,
              type=click.Choice(['integration', 'cloud', 'env-integration']),
              help='The category of the credential')
@click.option('-t', '--type', 'cred_type', required=True,
              help='The type of credential (aws, gcp, azure, static, ssh_key, json, active-directory, default)')
@click.option('-l', '--label', required=True, help='A human-readable label for the credential')
@click.option('-p', '--param', 'parameters', multiple=True,
              help='Parameter in format key=value (can be specified multiple times)')
def credential(sdk, resource_key, category, cred_type, label, parameters):
    """ Add a credential

    This command adds a credential to the credential broker. Credentials can be used
    for authentication with various cloud providers, integrations, and environment services.

    \b
    Example usages:
        - praetorian chariot add credential --resource-key "C.0c6cf7104f516b08-OGMPG" --category env-integration --type active-directory --label "Robb Stark" --param username=robb.stark --param password=sexywolfy --param domain=north.sevenkingdoms.local
        - praetorian chariot add credential -r "C.example-key" -c cloud -t aws --label "AWS Production" -p region=us-east-1 -p role_arn=arn:aws:iam::123456789012:role/MyRole
        - praetorian chariot add credential -r "C.example-key" -c integration -t static --label "API Token" -p token=abc123xyz
    """
    # Parse parameters from key=value format
    params = {}
    for param in parameters:
        if '=' not in param:
            error(f"Parameter '{param}' is not in the format key=value")
            return
        key, value = param.split('=', 1)
        params[key] = value

    try:
        result = sdk.credentials.add(resource_key, category, cred_type, label, params)
        click.echo(json.dumps(result, indent=2))
    except Exception as e:
        error(f'Unable to add credential. Error: {e}')
