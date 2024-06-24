import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.utils import Status, Risk
from praetorian_cli.handlers.cli_decorators import cli_handler, status_options


@chariot.group()
@cli_handler
def update(ctx):
    """Update a resource in Chariot"""
    pass


@update.command('risk')
@click.argument('key', required=True)
@click.option('-state', '--state', required=False)
@click.option('-severity', '--severity', required=False)
@click.option('-reason', '--reason', required=False)
@click.option('-comment', '--comment', default="")
@cli_handler
def risks(controller, key, state, severity, reason, comment):
    """ Update a risk"""
    status = ""
    risk_details = controller.my(dict(key=key))
    for risk in risk_details['risks']:
        status += Risk[state].value if state else risk['status'][0]
        status += Risk[severity].value if severity else risk['status'][1]
        if state == "CLOSED":
            status += Risk[reason].value if reason else ""
        controller.update('risk', dict(key=risk_details[key], status=status, comment=comment))


def create_update_command(item_type, status_choices):
    @update.command(item_type, help=f"Update {item_type} using object key")
    @click.argument('key', required=True)
    @status_options(status_choices)
    def command(controller, key, status, comment):
        controller.update(item_type, dict(key=key, status=status, comment=comment))

create_update_command('asset', Status['asset'])
create_update_command('job', Status['job'])
