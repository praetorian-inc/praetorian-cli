import sys
import json

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json, error


def _read_stdin(description):
    """Read raw text from stdin, erroring if it is not piped in or is empty."""
    if sys.stdin.isatty():
        raise click.UsageError(f'{description} is required via stdin')
    content = sys.stdin.read().strip()
    if not content:
        raise click.UsageError(f'{description} is required via stdin')
    return content


def _read_json_stdin(description):
    """Read and parse JSON from stdin."""
    raw = _read_stdin(description)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        error(f'Invalid JSON input: {e}')


# --- Technology ---

@chariot.command('update-technology')
@cli_handler
@click.option('--key', required=True, help='Technology key (CPE-based)')
@click.option('--name', default=None, help='Common name')
@click.option('--comment', default=None, help='Comment about the technology')
def update_technology(chariot, key, name, comment):
    """Update a technology record"""
    body = {'key': key}
    if name is not None:
        body['name'] = name
    if comment is not None:
        body['comment'] = comment
    print_json(chariot.misc.update_technology(body))


# --- Ticket ---

@chariot.group()
def ticket():
    """Ticket lifecycle management"""
    pass


@ticket.command('create')
@cli_handler
@click.option('--risk', required=True, help='Risk key')
@click.option('--account', required=True, help='Integration account key')
@click.option('--template-id', default='', help='Ticket template ID')
def create_ticket(chariot, risk, account, template_id):
    """Create a ticket for a risk"""
    body = {'risk': risk, 'account': account}
    if template_id:
        body['templateId'] = template_id
    print_json(chariot.misc.create_ticket(body))


@ticket.command('refresh')
@cli_handler
@click.option('--provider', required=True, help='Ticket provider (e.g. jira)')
@click.option('--ticket-id', required=True, help='External ticket ID')
def refresh_ticket(chariot, provider, ticket_id):
    """Refresh/fetch a ticket from its provider"""
    print_json(chariot.misc.update_ticket({
        'provider': provider, 'ticketID': ticket_id,
    }))


@ticket.command('delete')
@cli_handler
@click.option('--provider', required=True, help='Ticket provider (e.g. jira)')
@click.option('--ticket-id', required=True, help='External ticket ID')
@click.confirmation_option(prompt='Are you sure you want to delete this ticket?')
def delete_ticket(chariot, provider, ticket_id):
    """Delete a ticket"""
    print_json(chariot.misc.delete_ticket({
        'provider': provider, 'ticketID': ticket_id,
    }))


# --- Monitor (Breach & Attack Simulation) ---

@chariot.group()
def monitor():
    """Breach and attack simulation monitoring"""
    pass


@monitor.command('create')
@cli_handler
@praetorian_only
def create_monitor(chariot):
    """Create a monitoring session (reads JSON from stdin)

    Required fields: name, techniques [{technique_id, name}]
    Optional: filters, executed_at, expires_in (e.g. "168h")
    """
    body = _read_json_stdin('Monitor session JSON')
    print_json(chariot.misc.create_monitor(body))


@monitor.command('update')
@cli_handler
@praetorian_only
@click.option('--id', 'session_id', required=True, help='Monitor session ID')
@click.option('--executed-at', required=True, help='Execution timestamp (RFC3339)')
def update_monitor(chariot, session_id, executed_at):
    """Update a monitoring session execution time"""
    print_json(chariot.misc.update_monitor(session_id, {'executed_at': executed_at}))


@monitor.command('delete')
@cli_handler
@praetorian_only
@click.option('--id', 'session_id', required=True, help='Monitor session ID')
@click.confirmation_option(prompt='Are you sure you want to cancel this session?')
def delete_monitor(chariot, session_id):
    """Cancel a monitoring session"""
    print_json(chariot.misc.delete_monitor(session_id))


# --- Feature flags ---

@chariot.group()
def flag():
    """Feature flag management"""
    pass


@flag.command('set')
@cli_handler
@praetorian_only
@click.argument('name')
def set_flag(chariot, name):
    """Enable a feature flag (requires admin role)"""
    print_json(chariot.misc.set_flag(name))


@flag.command('delete')
@cli_handler
@praetorian_only
@click.argument('name')
@click.confirmation_option(prompt='Are you sure you want to delete this flag?')
def delete_flag(chariot, name):
    """Delete a feature flag (requires admin role)"""
    print_json(chariot.misc.delete_flag(name))


# --- Repository ---

@chariot.command('add-repository')
@cli_handler
@click.option('--name', required=True, help='Repository name')
@click.option('--source-archive-key', required=True, help='S3 key of the uploaded zip')
def add_repository(chariot, name, source_archive_key):
    """Register a previously-uploaded zip as a repository asset"""
    print_json(chariot.misc.create_repository(name, source_archive_key))


# --- Burp ---

@chariot.command('parse-burp')
@cli_handler
@click.option('--url', default=None, help='URL of the API definition')
@click.option('--filename', default=None, help='Filename hint for content parsing')
def parse_burp(chariot, url, filename):
    """Parse a Burp API definition (reads content from stdin if --url not given)"""
    if url:
        print_json(chariot.misc.parse_burp(url=url))
    else:
        if sys.stdin.isatty():
            raise click.UsageError('Provide --url or pipe API definition content via stdin')
        content = sys.stdin.read().strip()
        if not content:
            raise click.UsageError('Provide --url or pipe API definition content via stdin')
        print_json(chariot.misc.parse_burp(content=content, filename=filename))


# --- Vulnerability ---

@chariot.command('notify-vulnerability')
@cli_handler
@praetorian_only
def notify_vulnerability(chariot):
    """Dispatch a threat notification for a vulnerability (reads JSON from stdin)"""
    body = _read_json_stdin('Vulnerability JSON')
    print_json(chariot.misc.notify_vulnerability(body))


# --- Integration helpers ---

@chariot.group('integration-setup')
def integration_setup():
    """Integration validation and setup helpers"""
    pass


@integration_setup.command('validate')
@cli_handler
@praetorian_only
def validate_integration(chariot):
    """Validate an integration configuration (reads JSON from stdin)"""
    body = _read_json_stdin('Integration config JSON')
    print_json(chariot.misc.validate_integration(body))


@integration_setup.command('jira-transitions')
@cli_handler
@praetorian_only
def jira_transitions(chariot):
    """Get Jira workflow transitions (reads integration config JSON from stdin)"""
    body = _read_json_stdin('Integration config JSON')
    print_json(chariot.misc.jira_transitions(body))


@integration_setup.command('jira-custom-fields')
@cli_handler
@praetorian_only
def jira_custom_fields(chariot):
    """Get Jira custom fields (reads integration config JSON from stdin)"""
    body = _read_json_stdin('Integration config JSON')
    print_json(chariot.misc.jira_custom_fields(body))


@integration_setup.command('jira-optional-custom-fields')
@cli_handler
@praetorian_only
def jira_optional_custom_fields(chariot):
    """Get Jira optional custom fields (reads integration config JSON from stdin)"""
    body = _read_json_stdin('Integration config JSON')
    print_json(chariot.misc.jira_optional_custom_fields(body))


@integration_setup.command('jira-priorities')
@cli_handler
@praetorian_only
def jira_priorities(chariot):
    """Get Jira priorities (reads integration config JSON from stdin)"""
    body = _read_json_stdin('Integration config JSON')
    print_json(chariot.misc.jira_priorities(body))


@integration_setup.command('linear-teams')
@cli_handler
@praetorian_only
def linear_teams(chariot):
    """Get Linear teams (reads integration config JSON from stdin)"""
    body = _read_json_stdin('Integration config JSON')
    print_json(chariot.misc.linear_teams(body))


@integration_setup.command('linear-workflow-states')
@cli_handler
@praetorian_only
def linear_workflow_states(chariot):
    """Get Linear workflow states (reads integration config JSON from stdin)"""
    body = _read_json_stdin('Integration config JSON')
    print_json(chariot.misc.linear_workflow_states(body))


@integration_setup.command('linear-projects')
@cli_handler
@praetorian_only
def linear_projects(chariot):
    """Get Linear projects (reads integration config JSON from stdin)"""
    body = _read_json_stdin('Integration config JSON')
    print_json(chariot.misc.linear_projects(body))


# --- Risk visited ---

@chariot.command('risk-visited')
@cli_handler
@praetorian_only
@click.argument('key')
@click.option('--comment', default='', help='Visit comment')
def risk_visited(chariot, key, comment):
    """Mark a risk as visited"""
    print_json(chariot.misc.risk_visited(key, comment))


# --- Agent listing ---

@chariot.command('agent-list')
@cli_handler
def agent_list(chariot):
    """List registered agents"""
    print_json(chariot.misc.agent_list())


@chariot.command('agents')
@cli_handler
def agents_list(chariot):
    """List conversation AI agents"""
    print_json(chariot.misc.agents())


# --- Planner (conversation AI) ---

@chariot.group()
def planner():
    """Conversation AI planner management"""
    pass


@planner.command('compact')
@cli_handler
def compact(chariot):
    """Compact a planner conversation (reads JSON from stdin)"""
    body = _read_json_stdin('Compact request JSON')
    print_json(chariot.misc.planner_compact(body))


@planner.command('stop')
@cli_handler
def stop(chariot):
    """Stop a running planner conversation (reads JSON from stdin)"""
    body = _read_json_stdin('Stop request JSON')
    print_json(chariot.misc.planner_stop(body))


@planner.command('interaction')
@cli_handler
def interaction(chariot):
    """Record a planner interaction (reads JSON from stdin)"""
    body = _read_json_stdin('Interaction JSON')
    print_json(chariot.misc.planner_interaction(body))


@planner.command('cost')
@cli_handler
@click.argument('uuid')
def planner_cost(chariot, uuid):
    """Get cost for a planner conversation"""
    print_json(chariot.misc.planner_cost(uuid))


@planner.command('delete')
@cli_handler
@click.argument('uuid')
@click.confirmation_option(prompt='Are you sure you want to delete this conversation?')
def delete_conversation(chariot, uuid):
    """Delete a planner conversation"""
    print_json(chariot.misc.delete_planner(uuid))


# --- Hunt memory/cost ---

@chariot.command('set-hunt-memory')
@cli_handler
@click.argument('uuid')
@click.argument('title')
def set_hunt_memory(chariot, uuid, title):
    """Set hunt memory content (reads content from stdin)"""
    content = _read_stdin('Memory content')
    print_json(chariot.misc.put_hunt_memory(uuid, title, content))


@chariot.command('delete-hunt-memory')
@cli_handler
@click.argument('uuid')
@click.argument('title')
@click.confirmation_option(prompt='Are you sure you want to delete this memory?')
def delete_hunt_memory(chariot, uuid, title):
    """Delete hunt memory by title"""
    print_json(chariot.misc.delete_hunt_memory(uuid, title))


@chariot.command('hunt-cost')
@cli_handler
@click.argument('uuid')
def hunt_cost(chariot, uuid):
    """Get cost for a hunt"""
    print_json(chariot.misc.hunt_cost(uuid))
