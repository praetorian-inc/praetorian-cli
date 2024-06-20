from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.command('upgrade')
@cli_handler
def upgrade(controller):
    """Upgrade your account to managed"""
    controller.upgrade()
