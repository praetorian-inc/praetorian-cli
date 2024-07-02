import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
@cli_handler
def link(ctx):
    """Link an account or integration to Chariot"""
    pass


@link.command('chariot')
@cli_handler
@click.argument('username')
def link_account(controller, username):
    """ Link another Chariot account to yours """
    controller.link_account(username, config={})


@link.command('slack')
@cli_handler
@click.argument('webhook')
def link_slack(controller, webhook):
    """ Send all new risks to Slack """
    controller.link_account('slack', {'webhook': webhook})


@link.command('jira')
@cli_handler
@click.argument('url')
@click.argument('user_email')
@click.argument('access_token')
@click.argument('project_key')
@click.argument('issue_type')
def link_jira(controller, url, user_email, access_token, project_key, issue_type):
    """ Create JIRA when a risk is opened """
    config = {'url': url, 'userEmail': user_email, 'accessToken': access_token, 'projectKey': project_key,
              'issueType': issue_type}
    controller.link_account('jira', config)


@link.command('amazon')
@cli_handler
@click.argument('account')
def link_amazon(controller, account):
    """ Enumerate AWS for Assets"""
    controller.link_account('amazon', {}, account)
    print(
        'Account added. Please refer to the instructions in the UI for adding CloudFormation templates to your AWS account.')


@link.command('azure')
@cli_handler
@click.argument('appid')
@click.argument('secret')
@click.argument('tenant')
def link_azure(controller, appid, secret, tenant):
    """ Enumerate Azure for Assets """
    config = {'name': appid, 'secret': secret}
    controller.link_account('azure', config, tenant)


@link.command('gcp')
@cli_handler
@click.argument('keyfile', type=click.File('r'))
@click.argument('project_id')
def link_gcp(controller, keyfile, project_id):
    """ Enumerate GCP for Assets """
    config = dict(keyfile=keyfile.read())
    controller.link_account('gcp', config, project_id)


@link.command('github')
@cli_handler
@click.argument('pat')
@click.argument('organization')
def link_github(controller, pat, organization):
    """ Allow Chariot to scan your private repos """
    controller.link_account('github', {'pat': pat}, organization)


@link.command('ns1')
@cli_handler
@click.argument('ns1_api_key')
def link_ns1(controller, ns1_api_key):
    """ Allow Chariot to retrieve zone information from NS1 """
    controller.link_account('ns1', {'ns1_api_key': ns1_api_key}, 'ns1')


@link.command('crowdstrike')
@cli_handler
@click.argument('client')
@click.argument('secret')
@click.argument('url')
def link_crowdstrike(controller, client, secret, url):
    """ Enumerate Crowdstrike for Assets and Risks """
    config = {'clientID': client, 'secret': secret}
    controller.link_account('crowdstrike', config, url)


@link.command('gitlab')
@cli_handler
@click.argument('pat')
@click.argument('group')
def link_gitlab(controller, pat, group):
    """ Allow Chariot to scan private repos in your GitLab Group"""
    controller.link_account('gitlab', {'pat': pat}, group)
