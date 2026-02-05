import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def agent():
    """ A collection of AI features """
    pass


@agent.command()
@cli_handler
@click.argument('key')
def affiliation(sdk, key):
    """ Get affiliation data for risks and assets

    The AI agent retrieves affiliation information for the asset or risk. This command
    waits up to 3 minutes for the results.

    \b
    Example usages:
        - guard agent affiliation "#risk#www.praetorian.com#CVE-2024-1234"
        - guard agent affiliation "#asset#praetorian.com#www.praetorian.com"
    """
    click.echo("Polling for the affiliation data for up to 3 minutes.")
    click.echo(sdk.agents.affiliation(key))

@agent.group()
def mcp():
    """ Guard's MCP server """
    pass

@mcp.command()
@cli_handler
@click.option('--allowed', '-a', type=str, multiple=True, default=['search_by_query', '*_list', '*_get'])
def start(sdk, allowed):
    """ Starts the Guard MCP server

    \b
    Example usages:
        - guard agent mcp start
        - guard agent mcp start -a search_by_term -a risk_add
        - guard agent mcp start -a search_* -a risk_add

    \b
    Claude code configuration/usage:
        - claude mcp add chariot -- guard agent mcp start # read-only
        - claude mcp add chariot -- guard agent mcp start -a search_by_query -a risk_add -a asset_add # select write tools
        - claude "show me my chariot assets from the example.com domain"
        - claude "show me my chariot assets with port 22 open"
        - claude "run a portscan on every discovered ip for example.com"
    """
    if len(allowed) == 0:
        allowed = None
    sdk.agents.start_mcp_server(allowed)

@mcp.command()
@click.option('--allowed', '-a', type=str, multiple=True, default=['search_by_query', '*_list', '*_get'])
@cli_handler
def tools(sdk, allowed):
    """ Lists available mcp tools

    \b
    Example usages:
        - guard agent mcp tools
        - guard agent mcp tools -a search_* -a risk_add
    """
    for  tool in dict.keys(sdk.agents.list_mcp_tools(allowed)):
        click.echo(tool)

@agent.command()
@cli_handler
def conversation(sdk):
    """ Interactive conversation with Guard AI assistant
    
    Start an interactive chat session with the Guard AI assistant.
    The AI can help you query security data, understand findings,
    and provide insights about your attack surface.
    
    \b
    Commands within conversation:
        - help    Show available commands and query examples
        - clear   Clear the screen  
        - new     Start a new conversation
        - quit    Exit the conversation
    
    \b
    Example queries:
        - "Find all active assets"
        - "Show me critical risks"
        - "What assets do we have for example.com?"
        
    \b
    Usage:
        guard agent conversation
    """
    from praetorian_cli.ui.conversation import run_textual_conversation
    run_textual_conversation(sdk)
