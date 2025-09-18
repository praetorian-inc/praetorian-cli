import click
from praetorian_cli.handlers.cli_decorators import with_chariot_login_required
from praetorian_cli.ui.conversation.menu import run_conversation_menu


@click.command()
@with_chariot_login_required
@click.pass_context
def conversation(click_context):
    """Interactive conversation with Chariot AI assistant"""
    chariot = click_context.obj
    run_conversation_menu(chariot)