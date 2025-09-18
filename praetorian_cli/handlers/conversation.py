import click
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.ui.conversation.menu import run_conversation_menu


@click.command()
@cli_handler
def conversation(chariot):
    """Interactive conversation with Chariot AI assistant"""
    run_conversation_menu(chariot)