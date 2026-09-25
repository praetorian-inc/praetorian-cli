import ipaddress
import json
import re

from rich.box import MINIMAL
from rich.prompt import Confirm
from rich.table import Table

from ..constants import DEFAULT_COLORS
from ..utils import agent_display_id, is_v2_agent


DEFAULT_RULE_IDS = (
    'deny-unspecified',
    'deny-loopback',
    'deny-docker-api',
    'deny-control-plane',
)
SENSITIVE_DEFAULT_RULE_IDS = {
    'deny-loopback',
    'deny-docker-api',
    'deny-control-plane',
}
NETWORK_POLICY_ERROR_MESSAGES = {
    'invalid_endpoint_id': 'The endpoint ID is invalid.',
    'endpoint_not_found': 'The selected Aegis v2 endpoint was not found.',
    'endpoint_identity_unavailable': 'Endpoint identity data is temporarily unavailable.',
    'network_policy_unavailable': 'The endpoint network policy is temporarily unavailable.',
    'endpoint_connectivity_unavailable': 'Live endpoint connectivity data is temporarily unavailable.',
    'endpoint_not_connected': 'The endpoint must connect before its network policy can be changed.',
    'endpoint_revoked': 'The endpoint is revoked and its network policy is read-only.',
    'network_policy_agent_upgrade_required': (
        'Agent upgrade required. This endpoint does not support universal host egress policy.'
    ),
    'invalid_network_policy_request': 'Guard rejected the network policy request.',
    'invalid_network_policy': 'The network policy is invalid.',
    'network_policy_revision_conflict': (
        'The network policy changed concurrently. Review the latest policy and retry.'
    ),
}


def handle_network_policy(menu, args):
    """View or change host-enforced egress policy for the selected Aegis v2 endpoint."""
    if args and args[0].lower() in ('help', '-h', '--help'):
        show_network_policy_help(menu)
        return

    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    endpoint_id, support = _selected_endpoint(menu)
    if not endpoint_id:
        menu.pause()
        return

    try:
        operation = parse_policy_operation(args)
        policy = menu.sdk.aegis.get_endpoint_network_policy(endpoint_id)
        if operation['kind'] == 'show':
            print_network_policy(menu.console, policy, colors, support)
        else:
            _require_editable_endpoint(support)
            updated_fields, change = apply_policy_operation(policy, operation)
            if updated_fields is None:
                menu.console.print(f"\n  [{colors['dim']}]{change}[/{colors['dim']}]\n")
            elif operation['yes'] or Confirm.ask(
                f'  {change} Save this endpoint network policy?',
                default=False,
            ):
                updated = menu.sdk.aegis.update_endpoint_network_policy(
                    endpoint_id,
                    _policy_revision(policy),
                    updated_fields['disabledDefaultRuleIds'],
                    updated_fields['customDenyRules'],
                )
                menu.console.print(
                    f"\n  [{colors['success']}]Endpoint network policy saved[/{colors['success']}]"
                )
                print_network_policy(menu.console, updated, colors, support)
            else:
                menu.console.print('  Cancelled')
    except ValueError as exc:
        menu.console.print(f"\n[{colors['error']}]Error: {exc}[/{colors['error']}]\n")
    except Exception as exc:
        menu.console.print(
            f"\n[{colors['error']}]{network_policy_error_message(exc)}[/{colors['error']}]\n"
        )
    menu.pause()


def show_network_policy_help(menu):
    menu.console.print("""
  Aegis v2 Endpoint Network Policy Commands

  policy                              Show policy status and every deny rule
  policy show                         Show policy status and every deny rule
  policy default remove <rule-id>     Remove a built-in deny rule
  policy default restore <rule-id>    Restore a built-in deny rule
  policy deny add <IP-or-CIDR>        Deny all traffic to an address or network
  policy deny add <IP-or-CIDR> --tcp-ports 22,443
                                      Deny selected TCP ports only
  policy deny remove <number>         Remove a custom rule by its displayed number
  policy deny remove <IP-or-CIDR> [--tcp-ports 22,443]
                                      Remove an exact custom rule

  Mutation commands prompt before saving. Add --yes to skip confirmation.
  Destinations must be canonical IP addresses or CIDRs; hostnames are not accepted.

  Built-in rule IDs:
    deny-unspecified, deny-loopback, deny-docker-api, deny-control-plane
""")
    menu.pause()


def complete(menu, text, tokens):
    if getattr(menu, 'selected_agent', None) is None:
        return []
    lowered = [token.lower() for token in tokens]
    if len(lowered) <= 1:
        return [item for item in ('show', 'default', 'deny', 'help') if item.startswith(text)]
    if lowered[1] == 'default':
        actions = ('remove', 'restore')
        if len(lowered) <= 2 or (
            len(lowered) == 3 and lowered[2] not in actions
        ):
            return [item for item in actions if item.startswith(text)]
        if len(lowered) <= 3:
            return [item for item in DEFAULT_RULE_IDS if item.startswith(text)]
    if lowered[1] == 'deny':
        actions = ('add', 'remove')
        if len(lowered) <= 2 or (
            len(lowered) == 3 and lowered[2] not in actions
        ):
            return [item for item in actions if item.startswith(text)]
        if text.startswith('-'):
            return [
                item for item in ('--tcp-ports', '--yes', '--help')
                if item.startswith(text)
            ]
    if len(lowered) == 2:
        return [item for item in ('show', 'default', 'deny', 'help') if item.startswith(text)]
    if text.startswith('-'):
        return [item for item in ('--yes', '--help') if item.startswith(text)]
    return []


def parse_policy_operation(args):
    if not args:
        return {'kind': 'show', 'yes': False}
    words = list(args)
    subject = words.pop(0).lower()
    if subject == 'show':
        if words:
            raise ValueError(f'unexpected argument: {words[0]}')
        return {'kind': 'show', 'yes': False}
    if subject == 'default':
        return _parse_default_operation(words)
    if subject == 'deny':
        return _parse_deny_operation(words)
    raise ValueError(f'unknown policy action: {subject}')


def apply_policy_operation(policy, operation):
    _policy_revision(policy)
    if operation['kind'] == 'default':
        return _change_default_rule(
            policy,
            operation['rule_id'],
            remove=operation['action'] == 'remove',
        )
    if operation['kind'] == 'deny-add':
        return _add_custom_rule(
            policy,
            operation['selector'],
            operation['tcp_ports'],
        )
    if operation['kind'] == 'deny-remove':
        return _remove_custom_rule(
            policy,
            operation['selector'],
            operation['tcp_ports'],
            operation['ports_supplied'],
        )
    raise ValueError('unsupported network policy operation')


def canonical_destination(raw):
    value = str(raw or '').strip()
    if not value or '%' in value or any(character.isspace() for character in value):
        raise ValueError('enter a canonical IP address or CIDR')
    try:
        if '/' not in value:
            address = ipaddress.ip_address(value)
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                raise ValueError
            return str(address)
        network = ipaddress.ip_network(value, strict=True)
        if network.prefixlen == 0:
            raise ValueError
        if isinstance(network.network_address, ipaddress.IPv6Address) and network.network_address.ipv4_mapped:
            raise ValueError
        return network.with_prefixlen
    except ValueError as exc:
        raise ValueError('enter a canonical IP address or CIDR') from exc


def parse_tcp_ports(value):
    if value is None or not str(value).strip():
        return []
    raw_ports = [item.strip() for item in str(value).split(',')]
    try:
        ports = [int(item) for item in raw_ports]
    except ValueError as exc:
        raise ValueError('TCP ports must be unique numbers from 1 through 65535') from exc
    if (
        any(not item for item in raw_ports)
        or len(set(ports)) != len(ports)
        or any(port < 1 or port > 65535 for port in ports)
    ):
        raise ValueError('TCP ports must be unique numbers from 1 through 65535')
    return sorted(ports)


def network_policy_lines(policy, support=True):
    revision = _policy_revision(policy)
    applied_revision = _integer_field(policy, 'appliedRevision', default=0)
    application_status = str(policy.get('applicationStatus') or 'pending_validation')
    if application_status == 'applied' and applied_revision != revision:
        application_status = 'applying'

    lines = [
        f"Endpoint network policy: {policy.get('endpointId') or 'unknown'}",
        f'Desired revision: {revision}',
        f'Applied revision: {applied_revision}',
        f"Application: {_format_status(application_status)}",
        f"Host validation: {_format_status(str(policy.get('validationStatus') or 'pending_validation'))}",
        f"Last updated: {policy.get('updatedAt') or 'Default policy'}",
    ]
    if support is False:
        lines.append('Warning: agent upgrade required; policy editing is read-only.')
    elif support is None:
        lines.append('Warning: agent capability is unknown; policy editing is read-only.')
    if policy.get('applicationError'):
        lines.append(f"Application error: {policy['applicationError']}")

    connectivity = policy.get('protectedConnectivity')
    lines.append('Protected connectivity:')
    if isinstance(connectivity, dict) and connectivity.get('addresses'):
        for address in connectivity['addresses']:
            if isinstance(address, dict):
                lines.append(
                    f"  {_format_status(str(address.get('category') or 'unknown'))}: "
                    f"{address.get('address') or 'unknown'}"
                )
    else:
        lines.append('  None reported')
    if not isinstance(connectivity, dict) or not connectivity.get('complete'):
        lines.append('  Warning: live gateway and DNS information is incomplete or unavailable.')

    disabled = set(_disabled_default_rule_ids(policy))
    lines.append('Default deny rules:')
    for rule in _default_rules(policy):
        rule_id = str(rule.get('id') or '')
        enabled = rule.get('enabled')
        if not isinstance(enabled, bool):
            enabled = rule_id not in disabled
        lines.append(
            f"  [{'enabled' if enabled else 'removed'}] {rule_id}: "
            f"{rule.get('label') or rule_id}"
        )
        if rule.get('description'):
            lines.append(f"    {rule['description']}")
        for deny_rule in rule.get('rules') or []:
            if isinstance(deny_rule, dict):
                lines.append(f"    {_format_custom_rule(deny_rule)}")

    lines.append('Custom deny rules:')
    custom_rules = _custom_deny_rules(policy)
    if not custom_rules:
        lines.append('  None')
    for index, rule in enumerate(custom_rules, 1):
        lines.append(f'  {index}. {_format_custom_rule(rule)}')
    return lines


def print_network_policy(console, policy, colors=None, support=True):
    colors = colors or DEFAULT_COLORS
    lines = network_policy_lines(policy, support)
    status_rows = lines[:6]
    remainder = lines[6:]

    status = Table(
        title='Endpoint Network Policy',
        show_header=False,
        border_style=colors['dim'],
        box=MINIMAL,
        padding=(0, 2),
        pad_edge=False,
    )
    status.add_column('Field', style=f"bold {colors['primary']}", no_wrap=True)
    status.add_column('Value')
    for line in status_rows:
        label, value = line.split(': ', 1)
        status.add_row(label, value)
    console.print()
    console.print(status)
    for line in remainder:
        style = colors['warning'] if line.strip().startswith('Warning:') else None
        console.print(line, style=style, markup=False)
    console.print()


def network_policy_error_message(error):
    payload = _extract_error_payload(str(error))
    code = str(payload.get('error') or '')
    if code == 'network_policy_fundamental_conflict':
        rule = payload.get('rule') or 'the requested rule'
        category = _format_status(str(payload.get('category') or 'protected connectivity'))
        address = payload.get('address') or 'a protected address'
        return f'Cannot apply {rule}: it contains protected {category} address {address}.'
    if code in NETWORK_POLICY_ERROR_MESSAGES:
        return NETWORK_POLICY_ERROR_MESSAGES[code]
    status = _extract_status(str(error))
    if status:
        return f'Endpoint network policy request failed with HTTP {status}. Try again or re-run with --debug.'
    return 'Endpoint network policy request failed. Try again or re-run with --debug.'


def _parse_default_operation(words):
    yes, positional = _split_options(words, allow_tcp_ports=False)
    if len(positional) != 2:
        raise ValueError('expected: policy default <remove|restore> <rule-id>')
    action = {'disable': 'remove', 'enable': 'restore'}.get(
        positional[0].lower(), positional[0].lower(),
    )
    if action not in ('remove', 'restore'):
        raise ValueError(f'unknown default-rule action: {positional[0]}')
    return {
        'kind': 'default',
        'action': action,
        'rule_id': positional[1].lower(),
        'yes': yes,
    }


def _parse_deny_operation(words):
    yes, positional, tcp_ports, ports_supplied = _split_options(
        words,
        allow_tcp_ports=True,
    )
    if len(positional) != 2:
        raise ValueError('expected: policy deny <add|remove> <IP-or-CIDR|rule-number>')
    action = {'delete': 'remove', 'rm': 'remove'}.get(
        positional[0].lower(), positional[0].lower(),
    )
    if action not in ('add', 'remove'):
        raise ValueError(f'unknown custom deny action: {positional[0]}')
    return {
        'kind': f'deny-{action}',
        'selector': positional[1],
        'tcp_ports': tcp_ports,
        'ports_supplied': ports_supplied,
        'yes': yes,
    }


def _split_options(words, allow_tcp_ports):
    yes = False
    tcp_ports = None
    ports_supplied = False
    positional = []
    index = 0
    while index < len(words):
        word = words[index]
        if word in ('-y', '--yes'):
            yes = True
        elif word == '--tcp-ports' and allow_tcp_ports:
            index += 1
            if index >= len(words):
                raise ValueError('--tcp-ports requires a comma-separated value')
            tcp_ports = words[index]
            ports_supplied = True
        elif word.startswith('--tcp-ports=') and allow_tcp_ports:
            tcp_ports = word.split('=', 1)[1]
            ports_supplied = True
        elif word.startswith('-'):
            raise ValueError(f'unknown option: {word}')
        else:
            positional.append(word)
        index += 1
    if allow_tcp_ports:
        return yes, positional, tcp_ports, ports_supplied
    return yes, positional


def _change_default_rule(policy, rule_id, remove):
    rule = _find_default_rule(policy, rule_id)
    disabled = set(_disabled_default_rule_ids(policy))
    currently_removed = rule_id in disabled
    if remove == currently_removed:
        state = 'already removed' if remove else 'already enabled'
        return None, f"Default rule '{rule.get('label') or rule_id}' is {state}."
    if remove:
        disabled.add(rule_id)
        warning = ''
        if rule_id in SENSITIVE_DEFAULT_RULE_IDS:
            warning = ' This may expose host or Guard control services to Aegis workloads.'
        change = f"Remove default deny rule '{rule.get('label') or rule_id}'.{warning}"
    else:
        disabled.remove(rule_id)
        change = f"Restore default deny rule '{rule.get('label') or rule_id}'."
    return _updated_fields(policy, sorted(disabled), _custom_deny_rules(policy)), change


def _add_custom_rule(policy, raw_destination, raw_ports):
    destination = canonical_destination(raw_destination)
    ports = parse_tcp_ports(raw_ports)
    rule = {'destination': destination}
    if ports:
        rule['tcpPorts'] = ports
    rules = _custom_deny_rules(policy)
    if _rule_key(rule) in {_rule_key(candidate) for candidate in rules}:
        return None, f'Custom deny rule {_format_custom_rule(rule)} already exists.'
    rules.append(rule)
    rules.sort(key=_rule_key)
    change = f'Add custom deny rule {_format_custom_rule(rule)}.'
    return _updated_fields(policy, _disabled_default_rule_ids(policy), rules), change


def _remove_custom_rule(policy, selector, raw_ports, ports_supplied):
    rules = _custom_deny_rules(policy)
    if selector.isdigit() and not ports_supplied:
        index = int(selector) - 1
        if index < 0 or index >= len(rules):
            raise ValueError(f'custom deny rule number must be between 1 and {len(rules)}')
    else:
        destination = canonical_destination(selector)
        ports = parse_tcp_ports(raw_ports)
        key = _rule_key({'destination': destination, 'tcpPorts': ports})
        index = next(
            (candidate for candidate, rule in enumerate(rules) if _rule_key(rule) == key),
            -1,
        )
        if index < 0:
            raise ValueError('matching custom deny rule was not found')
    removed = rules.pop(index)
    change = f'Remove custom deny rule {_format_custom_rule(removed)}.'
    return _updated_fields(policy, _disabled_default_rule_ids(policy), rules), change


def _updated_fields(policy, disabled, rules):
    return {
        'disabledDefaultRuleIds': sorted(disabled),
        'customDenyRules': sorted(rules, key=_rule_key),
    }


def _selected_endpoint(menu):
    agent = getattr(menu, 'selected_agent', None)
    if not agent:
        menu.console.print("\n  No Aegis endpoint selected. Use 'set <id>' to select one.\n")
        return '', None
    if not is_v2_agent(agent):
        menu.console.print('\n  Endpoint network policy is available only for Aegis v2 endpoints.\n')
        return '', None
    return agent_display_id(agent).strip(), getattr(agent, 'network_policy_supported', None)


def _require_editable_endpoint(support):
    if support is False:
        raise ValueError(
            'agent upgrade required; this endpoint does not support universal host egress policy'
        )
    if support is None:
        raise ValueError(
            'agent capability is unknown until the endpoint connects; network policy is read-only'
        )


def _policy_revision(policy):
    return _integer_field(policy, 'revision')


def _integer_field(policy, field, default=None):
    value = policy.get(field) if isinstance(policy, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        if default is not None:
            return default
        raise ValueError(f'network policy response has an invalid {field}')
    return value


def _find_default_rule(policy, rule_id):
    for rule in _default_rules(policy):
        if rule.get('id') == rule_id:
            return rule
    available = ', '.join(rule.get('id', '') for rule in _default_rules(policy))
    raise ValueError(f"unknown default deny rule '{rule_id}'; choose one of: {available}")


def _default_rules(policy):
    rules = policy.get('defaultRules') if isinstance(policy, dict) else None
    if not isinstance(rules, list):
        raise ValueError('network policy response is missing default rules')
    return [dict(rule) for rule in rules if isinstance(rule, dict)]


def _disabled_default_rule_ids(policy):
    values = policy.get('disabledDefaultRuleIds') if isinstance(policy, dict) else None
    if values is None:
        return []
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError('network policy response has invalid disabled default rules')
    return list(values)


def _custom_deny_rules(policy):
    values = policy.get('customDenyRules') if isinstance(policy, dict) else None
    if values is None:
        return []
    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
        raise ValueError('network policy response has invalid custom deny rules')
    rules = []
    for value in values:
        rule = {'destination': str(value.get('destination') or '')}
        ports = value.get('tcpPorts')
        if ports:
            rule['tcpPorts'] = list(ports)
        rules.append(rule)
    return rules


def _rule_key(rule):
    ports = sorted(rule.get('tcpPorts') or [])
    return str(rule.get('destination') or ''), tuple(ports)


def _format_custom_rule(rule):
    ports = sorted(rule.get('tcpPorts') or [])
    traffic = f"TCP {', '.join(str(port) for port in ports)}" if ports else 'all traffic'
    return f"{rule.get('destination') or 'unknown'} · {traffic}"


def _format_status(value):
    return ' '.join(word.capitalize() for word in value.split('_'))


def _extract_error_payload(message):
    match = re.search(r'Error:\s*(\{.*\})', message, flags=re.DOTALL)
    if match:
        try:
            payload = json.loads(match.group(1))
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            pass
    match = re.search(r'"error"\s*:\s*"([^"]+)"', message)
    return {'error': match.group(1)} if match else {}


def _extract_status(message):
    match = re.search(r'\[(\d{3})\]', message)
    return match.group(1) if match else ''
