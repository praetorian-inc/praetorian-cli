import os

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error


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


@chariot.group()
def marcus():
    """ Marcus Aurelius — Guard's AI operator

    \b
    Invoke Marcus to read files, ingest engagement data, create findings,
    add seeds, run tools, and analyze your attack surface.
    """
    pass


@marcus.command('read')
@cli_handler
@click.argument('path')
@click.option('--local', is_flag=True, default=False, help='Path is a local file (upload to Guard first)')
@click.option('--instructions', '-i', default='', help='Additional instructions for Marcus')
def marcus_read(sdk, path, local, instructions):
    """ Have Marcus read and analyze a file

    Read a file from Guard storage (or upload a local file) and have Marcus
    analyze it. Marcus can extract findings, identify assets, suggest seeds,
    and create risks based on what it reads.

    \b
    Example usages:
        guard marcus read "vault/engagement/sow.pdf"
        guard marcus read "proofs/example.com/screenshot.png"
        guard marcus read ./local-report.md --local
        guard marcus read "vault/nessus-export.csv" -i "create risks for critical findings"
    """
    import json, time

    # If local file, upload to Guard first
    if local:
        import os
        if not os.path.exists(path):
            error(f'Local file not found: {path}')
        filename = os.path.basename(path)
        guard_path = f'home/{filename}'
        click.echo(f'Uploading {path} to Guard as {guard_path}...', err=True)
        sdk.files.add(path, guard_path)
        path = guard_path

    base_instruction = f'Read the file at "{path}" using the file_read tool.'
    if instructions:
        message = f'{base_instruction} {instructions}'
    else:
        message = (
            f'{base_instruction} Analyze its contents and tell me what you found. '
            f'If it contains engagement scope information (domains, IPs, CIDRs), offer to add them as seeds. '
            f'If it contains vulnerability findings, offer to create risks. '
            f'If it contains credentials or secrets, flag them.'
        )

    _send_and_poll(sdk, message, timeout=180)


@marcus.command('ingest')
@cli_handler
@click.argument('path')
@click.option('--scope', is_flag=True, default=False, help='Auto-add discovered scope as seeds')
@click.option('--findings', is_flag=True, default=False, help='Auto-create risks from findings')
def marcus_ingest(sdk, path, scope, findings):
    """ Have Marcus read a file and automatically ingest data into Guard

    Like 'marcus read' but with automatic action — Marcus will create seeds,
    risks, and assets without asking for confirmation.

    \b
    Example usages:
        guard marcus ingest "vault/engagement/sow.pdf" --scope
        guard marcus ingest "vault/nessus-results.csv" --findings
        guard marcus ingest "vault/client-scope.md" --scope --findings
    """
    actions = []
    if scope:
        actions.append('Add any discovered domains, IPs, and CIDRs as seeds using seed_add.')
    if findings:
        actions.append('Create risks for any vulnerability findings you identify.')
    if not actions:
        actions.append('Add scope items as seeds and create risks for any findings.')

    action_text = ' '.join(actions)
    message = (
        f'Read the file at "{path}" using the file_read tool. '
        f'Analyze its contents thoroughly. {action_text} '
        f'Take action automatically — do not ask for confirmation. '
        f'Report what you created when done.'
    )

    _send_and_poll(sdk, message, timeout=300)


@marcus.command('do')
@cli_handler
@click.argument('instruction')
def marcus_do(sdk, instruction):
    """ Give Marcus a direct instruction to execute

    Marcus operates in agent mode with full access to tools: seed_add, job
    (run scans), file_read, spawn_agent (brutus, julius, etc.), and more.

    \b
    Example usages:
        guard marcus do "add example.com as a seed and start discovery"
        guard marcus do "run nuclei on all assets with port 443"
        guard marcus do "create a risk for CVE-2024-1234 on asset api.example.com"
        guard marcus do "generate an executive summary"
        guard marcus do "onboard new engagement from vault/sow.pdf"
    """
    _send_and_poll(sdk, instruction, timeout=300)


def _send_and_poll(sdk, message, timeout=180):
    """Send a message to Marcus in agent mode and poll for the response."""
    import json, time

    url = sdk.url('/planner')
    payload = {'message': message, 'mode': 'agent'}

    response = sdk.chariot_request('POST', url, json=payload)
    if not response.ok:
        error(f'API error: {response.status_code} - {response.text}')
        return

    result = response.json()
    conversation_id = result.get('conversation', {}).get('uuid')

    # Save conversation state for follow-up with `guard ask`
    state_file = os.path.join(os.path.expanduser('~'), '.praetorian', 'conversation_state.json')
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump({'conversation_id': conversation_id}, f)

    last_key = ''
    start_time = time.time()

    while time.time() - start_time < timeout:
        messages, _ = sdk.search.by_key_prefix(f'#message#{conversation_id}#', user=True)
        new_msgs = sorted(
            [m for m in messages if m.get('key', '') > last_key],
            key=lambda x: x.get('key', '')
        )

        for msg in new_msgs:
            role = msg.get('role', '')
            content = msg.get('content', '')
            last_key = msg.get('key', '')

            if role == 'chariot':
                click.echo(content)
                return
            elif role == 'tool call':
                click.echo('Executing...', err=True, nl=False)
            elif role == 'tool response':
                click.echo(' done.', err=True)

        time.sleep(1)

    error(f'Timed out waiting for response ({timeout}s)')


@chariot.command()
@cli_handler
@click.argument('message')
@click.option('-m', '--mode', type=click.Choice(['query', 'agent']), default='agent', help='Conversation mode')
@click.option('--new', 'new_conversation', is_flag=True, default=False, help='Start a new conversation')
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text', help='Output format')
def ask(sdk, message, mode, new_conversation, output_format):
    """One-shot query to Guard AI assistant (Marcus)

    Send a question and get a response inline. Conversation state is preserved
    between calls so follow-up questions work.

    \b
    Example usages:
        - guard ask "what assets have port 22 open?"
        - guard ask "show me critical risks" --mode query
        - guard ask --new "unrelated question"
        - guard ask "summarize findings" --format json
    """
    import json, time, sys

    # Load/save conversation state
    state_file = os.path.join(os.path.expanduser('~'), '.praetorian', 'conversation_state.json')
    conversation_id = None
    if not new_conversation:
        try:
            with open(state_file) as f:
                state = json.load(f)
                conversation_id = state.get('conversation_id')
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # Send message
    url = sdk.url('/planner')
    payload = {'message': message, 'mode': mode}
    if conversation_id:
        payload['conversationId'] = conversation_id

    response = sdk.chariot_request('POST', url, json=payload)
    if not response.ok:
        error(f'API error: {response.status_code} - {response.text}')
        return

    result = response.json()
    if not conversation_id and 'conversation' in result:
        conversation_id = result['conversation'].get('uuid')

    # Save conversation state
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump({'conversation_id': conversation_id}, f)

    # Poll for AI response
    max_wait = 120  # 2 minutes
    start_time = time.time()
    last_key = ''

    while time.time() - start_time < max_wait:
        messages, _ = sdk.search.by_key_prefix(f'#message#{conversation_id}#', user=True)
        new_messages = [m for m in messages if m.get('key', '') > last_key]
        new_messages = sorted(new_messages, key=lambda x: x.get('key', ''))

        for msg in new_messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            last_key = msg.get('key', '')

            if role == 'chariot':
                if output_format == 'json':
                    click.echo(json.dumps({'response': content, 'conversation_id': conversation_id}, indent=2))
                else:
                    click.echo(content)
                return
            elif role == 'tool call':
                if output_format == 'text':
                    click.echo('Executing...', err=True, nl=False)
            elif role == 'tool response':
                if output_format == 'text':
                    click.echo(' done.', err=True)

        time.sleep(1)

    error('Timed out waiting for response')


@chariot.command()
@cli_handler
@click.option('--account', 'console_account', default=None, help='Pre-set engagement account')
def console(sdk, console_account):
    """Interactive operator console for Guard engagements

    Drops into a stateful, context-aware session with tab-completion,
    integrated Marcus AI, and operator-focused commands.

    \b
    Example usages:
        - guard console
        - guard console --account client@example.com
    """
    from praetorian_cli.ui.console import run_console
    run_console(sdk, account=console_account)
