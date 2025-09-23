import click
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.ui.conversation import ConversationMenu


@chariot.command()
@cli_handler
def conversation(chariot):
    """
    Start an interactive conversation with Chariot's AI security assistant.
    
    The AI assistant can help you:
    - Query your attack surface data using natural language
    - Run security scans and analyze results
    - Provide intelligent security recommendations
    - Answer questions about vulnerabilities and threats
    
    \b
    Examples:
        praetorian chariot conversation
        
    \b
    Once in the conversation interface, you can:
    - Type naturally to chat with the AI
    - Use /help to see available commands
    - Use /list to see your conversation history
    - Use /new to start a fresh conversation
    """
    try:
        menu = ConversationMenu(chariot)
        menu.run()
    except KeyboardInterrupt:
        click.echo("\nGoodbye!")
    except Exception as e:
        click.echo(f"Error starting conversation interface: {e}", err=True)