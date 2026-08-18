import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, pagination
from praetorian_cli.handlers.utils import print_json, render_offset, pagination_size


@chariot.group()
def ad():
    """ Active Directory and BloodHound graph queries """
    pass


@ad.command('list-objects')
@cli_handler
@click.argument('object_type')
@click.option('-d', '--domain', default=None, help='Filter to a specific AD domain')
@click.option('-n', '--name', 'name_contains', default=None, help='Filter by name substring')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def list_objects(sdk, object_type, domain, name_contains, as_json, offset, page):
    """ List AD objects by type

    \b
    Object types: user, computer, group, domain, gpo, ou, container,
                  localgroup, localuser, rootca, enterpriseca,
                  certtemplate, ntauthstore, aiaca, issuancepolicy

    \b
    Example usages:
        guard ad list-objects user
        guard ad list-objects user --domain contoso.local
        guard ad list-objects computer --name DC --json
        guard ad list-objects group --domain contoso.local --page all
    """
    results, next_offset = sdk.ad.list_objects(
        object_type, domain=domain, name_contains=name_contains, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('get-object')
@cli_handler
@click.option('-k', '--key', default=None, help='Full Chariot key of the AD object')
@click.option('--objectid', default=None, help='AD objectid / SID')
@click.option('-d', '--domain', default=None, help='AD domain (required with --objectid)')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
def get_object(sdk, key, objectid, domain, as_json):
    """ Get a specific AD object by key or objectid

    \b
    Example usages:
        guard ad get-object --key "#aduser#contoso.local#S-1-5-21-..."
        guard ad get-object --objectid "S-1-5-21-..." --domain contoso.local
    """
    results, _ = sdk.ad.get_object(key=key, objectid=objectid, domain=domain)
    _render(results, None, as_json)


@ad.command('get-relationships')
@cli_handler
@click.option('--source-key', default=None, help='Chariot key of the source AD object')
@click.option('--target-key', default=None, help='Chariot key of the target AD object')
@click.option('--type', 'relationship_type', default=None,
              help='Relationship type (e.g., GenericAll, MemberOf, Owns, WriteDacl)')
@click.option('--source-type', default=None, help='AD type of source node')
@click.option('--target-type', default=None, help='AD type of target node')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def get_relationships(sdk, source_key, target_key, relationship_type,
                      source_type, target_type, as_json, offset, page):
    """ Query AD ACL relationships between objects

    \b
    Example usages:
        guard ad get-relationships --source-key "#aduser#contoso.local#S-1-5-..." --type GenericAll
        guard ad get-relationships --target-key "#adgroup#contoso.local#S-1-5-..." --json
        guard ad get-relationships --type MemberOf --source-type user --page all
    """
    results, next_offset = sdk.ad.get_relationships(
        source_key=source_key, target_key=target_key,
        relationship_type=relationship_type,
        source_type=source_type, target_type=target_type,
        pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('find-attack-path')
@cli_handler
@click.option('--source', required=True, help='Chariot key of the starting AD object')
@click.option('--target', required=True, help='Chariot key of the destination AD object')
@click.option('--max-depth', default=5, type=int, help='Maximum path depth / hops (1-10)')
@click.option('--shortest', default=1, type=int, help='Number of shortest paths to return (1-10)')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
def find_attack_path(sdk, source, target, max_depth, shortest, as_json):
    """ Find shortest attack path between two AD objects

    \b
    Example usages:
        guard ad find-attack-path --source "#aduser#contoso.local#S-1-5-..." \\
            --target "#adgroup#contoso.local#S-1-5-..."
        guard ad find-attack-path --source "#aduser#..." --target "#adgroup#..." --max-depth 3 --json
    """
    results, _ = sdk.ad.find_attack_path(
        source_key=source, target_key=target,
        max_depth=max_depth, shortest=shortest)
    _render(results, None, as_json)


@ad.command('who-can')
@cli_handler
@click.argument('right')
@click.option('--target', required=True, help='Chariot key of the target AD object')
@click.option('--principal-type', default=None, help='Filter principals by type (user, computer, group)')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def who_can(sdk, right, target, principal_type, as_json, offset, page):
    """ Find principals with a specific right over a target

    \b
    Example usages:
        guard ad who-can GenericAll --target "#adgroup#contoso.local#S-1-5-..."
        guard ad who-can WriteDacl --target "#aduser#contoso.local#S-1-5-..." --principal-type user
    """
    results, next_offset = sdk.ad.who_can(
        right, target_key=target, principal_type=principal_type, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('what-can')
@cli_handler
@click.argument('right')
@click.option('--source', required=True, help='Chariot key of the source principal')
@click.option('--target-type', default=None, help='Filter targets by AD type')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def what_can(sdk, right, source, target_type, as_json, offset, page):
    """ Find what objects a principal has a right over

    \b
    Example usages:
        guard ad what-can GenericAll --source "#aduser#contoso.local#S-1-5-..."
        guard ad what-can WriteDacl --source "#aduser#..." --target-type computer --json
    """
    results, next_offset = sdk.ad.what_can(
        source_key=source, right=right, target_type=target_type, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('group-members')
@cli_handler
@click.argument('group_key')
@click.option('-r', '--recursive', is_flag=True, default=False, help='Include nested group members')
@click.option('--member-type', default=None, help='Filter members by type (user, computer, group)')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def group_members(sdk, group_key, recursive, member_type, as_json, offset, page):
    """ List members of an AD group

    \b
    Example usages:
        guard ad group-members "#adgroup#contoso.local#S-1-5-..."
        guard ad group-members "#adgroup#contoso.local#S-1-5-..." --recursive
        guard ad group-members "#adgroup#..." --member-type user --json
    """
    results, next_offset = sdk.ad.group_members(
        group_key, recursive=recursive, member_type=member_type, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('group-memberships')
@cli_handler
@click.argument('object_key')
@click.option('-r', '--recursive', is_flag=True, default=False, help='Include transitive memberships')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def group_memberships(sdk, object_key, recursive, as_json, offset, page):
    """ List all groups an AD object belongs to

    \b
    Example usages:
        guard ad group-memberships "#aduser#contoso.local#S-1-5-..."
        guard ad group-memberships "#aduser#contoso.local#S-1-5-..." --recursive --json
    """
    results, next_offset = sdk.ad.group_memberships(
        object_key, recursive=recursive, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('kerberoastable-users')
@cli_handler
@click.option('-d', '--domain', default=None, help='Filter to a specific AD domain')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def kerberoastable_users(sdk, domain, as_json, offset, page):
    """ Find Kerberoastable users (users with SPNs set)

    \b
    Example usages:
        guard ad kerberoastable-users
        guard ad kerberoastable-users --domain contoso.local --json
    """
    results, next_offset = sdk.ad.kerberoastable_users(
        domain=domain, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('asreproastable-users')
@cli_handler
@click.option('-d', '--domain', default=None, help='Filter to a specific AD domain')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def asreproastable_users(sdk, domain, as_json, offset, page):
    """ Find AS-REP roastable users (no Kerberos pre-authentication)

    \b
    Example usages:
        guard ad asreproastable-users
        guard ad asreproastable-users --domain contoso.local --json
    """
    results, next_offset = sdk.ad.asreproastable_users(
        domain=domain, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('unconstrained-delegation')
@cli_handler
@click.option('-d', '--domain', default=None, help='Filter to a specific AD domain')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def unconstrained_delegation(sdk, domain, as_json, offset, page):
    """ Find computers with unconstrained delegation enabled

    \b
    Example usages:
        guard ad unconstrained-delegation
        guard ad unconstrained-delegation --domain contoso.local --json
    """
    results, next_offset = sdk.ad.unconstrained_delegation(
        domain=domain, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('dcsync-principals')
@cli_handler
@click.option('--domain-key', default=None, help='Chariot key of the AD domain object')
@click.option('-d', '--domain', default=None, help='AD domain name')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def dcsync_principals(sdk, domain_key, domain, as_json, offset, page):
    """ Find principals that can perform DCSync

    \b
    Example usages:
        guard ad dcsync-principals
        guard ad dcsync-principals --domain contoso.local
        guard ad dcsync-principals --domain-key "#addomain#contoso.local#contoso.local" --json
    """
    results, next_offset = sdk.ad.dcsync_principals(
        domain_key=domain_key, domain=domain, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command('tier-zero-objects')
@cli_handler
@click.option('-d', '--domain', default=None, help='Filter to a specific AD domain')
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def tier_zero_objects(sdk, domain, as_json, offset, page):
    """ Find tier-zero / high-value AD objects

    \b
    Example usages:
        guard ad tier-zero-objects
        guard ad tier-zero-objects --domain contoso.local --json
    """
    results, next_offset = sdk.ad.tier_zero_objects(
        domain=domain, pages=pagination_size(page))
    _render(results, next_offset, as_json)


@ad.command()
@cli_handler
@click.option('--json', 'as_json', is_flag=True, default=False, help='Output full JSON')
@pagination
def domains(sdk, as_json, offset, page):
    """ List all Active Directory domains

    \b
    Example usages:
        guard ad domains
        guard ad domains --json
    """
    results, next_offset = sdk.ad.domains(pages=pagination_size(page))
    _render(results, next_offset, as_json)


def _render(results, next_offset, as_json):
    """Render AD query results in key-per-line or full JSON format."""
    if as_json:
        output = dict(data=results)
        if next_offset:
            output['offset'] = next_offset
        print_json(output)
    else:
        for item in results:
            if isinstance(item, dict):
                click.echo(item.get('key', item.get('name', str(item))))
            else:
                click.echo(str(item))
        render_offset(next_offset)
