"""Constantine AI security pipeline — generate exploits, patches, and validations
for vulnerabilities using AI."""
import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


@chariot.group('constantine')
def constantine():
    """Constantine AI security pipeline — generate exploits, patches, and
    validations for vulnerabilities using AI.

    \b
    Constantine provides AI-powered tooling for:
      - Exploit generation for confirmed vulnerabilities
      - Patch and remediation code generation
      - Validation of exploits and patches
      - Pipeline manifest inspection (available presets/modules)
      - OSINT enrichment (repo discovery, finding submission, technology creation)
    """
    pass


# ---------------------------------------------------------------------------
# constantine exploit
# ---------------------------------------------------------------------------

@constantine.command('exploit')
@cli_handler
@click.option('--risk-key', required=True, help='Risk key identifying the vulnerability (e.g. #risk#asset#CVE-...)')
@click.option('--preset', default=None, help='Pipeline preset or module to use (see "constantine manifest")')
@click.option('--json-output', 'json_output', is_flag=True, default=False, help='Emit raw JSON response')
def exploit(sdk, risk_key, preset, json_output):
    """Generate exploit code for a vulnerability.

    Sends the risk to the Constantine AI pipeline which researches the
    vulnerability and returns working proof-of-concept exploit code.
    Generation can take 30–120 seconds.

    \b
    Example usages:
        guard constantine exploit --risk-key "#risk#api.example.com#CVE-2024-1234"
        guard constantine exploit --risk-key "#risk#api.example.com#CVE-2024-1234" --preset web-rce
        guard constantine exploit --risk-key "#risk#api.example.com#CVE-2024-1234" --json-output
    """
    body = {'key': risk_key}
    if preset:
        body['preset'] = preset

    click.echo(
        click.style('Constantine', fg='cyan', bold=True) +
        click.style(' › exploit', fg='white') +
        click.style('  generating…', fg='yellow', dim=True),
        err=True,
    )

    result = sdk.post('/constantine/exploit', body)

    if not result:
        error('No response from Constantine exploit endpoint')

    if json_output:
        print_json(result)
        return

    code = result.get('code') or result.get('exploit') or result.get('result', '')
    notes = result.get('notes') or result.get('explanation', '')

    click.echo(click.style('─' * 60, dim=True))
    if notes:
        click.echo(click.style('Notes:', bold=True))
        click.echo(notes)
        click.echo()
    if code:
        click.echo(click.style('Exploit code:', bold=True))
        click.echo(code)
    else:
        print_json(result)


# ---------------------------------------------------------------------------
# constantine patch
# ---------------------------------------------------------------------------

@constantine.command('patch')
@cli_handler
@click.option('--risk-key', required=True, help='Risk key identifying the vulnerability (e.g. #risk#asset#CVE-...)')
@click.option('--preset', default=None, help='Pipeline preset or module to use (see "constantine manifest")')
@click.option('--json-output', 'json_output', is_flag=True, default=False, help='Emit raw JSON response')
def patch(sdk, risk_key, preset, json_output):
    """Generate patch/remediation code for a vulnerability.

    Sends the risk to the Constantine AI pipeline which produces a patch or
    remediation guide for the identified vulnerability.

    \b
    Example usages:
        guard constantine patch --risk-key "#risk#api.example.com#CVE-2024-1234"
        guard constantine patch --risk-key "#risk#api.example.com#CVE-2024-1234" --preset dependency-upgrade
        guard constantine patch --risk-key "#risk#api.example.com#CVE-2024-1234" --json-output
    """
    body = {'key': risk_key}
    if preset:
        body['preset'] = preset

    result = sdk.post('/constantine/patch', body)

    if not result:
        error('No response from Constantine patch endpoint')

    if json_output:
        print_json(result)
        return

    code = result.get('code') or result.get('patch') or result.get('result', '')
    notes = result.get('notes') or result.get('explanation', '')

    click.echo(click.style('─' * 60, dim=True))
    if notes:
        click.echo(click.style('Notes:', bold=True))
        click.echo(notes)
        click.echo()
    if code:
        click.echo(click.style('Patch / remediation:', bold=True))
        click.echo(code)
    else:
        print_json(result)


# ---------------------------------------------------------------------------
# constantine validate
# ---------------------------------------------------------------------------

@constantine.command('validate')
@cli_handler
@click.option('--risk-key', required=True, help='Risk key identifying the vulnerability')
@click.option('--type', 'validate_type', required=True,
              type=click.Choice(['exploit', 'patch']),
              help='What to validate: the exploit or the patch')
@click.option('--json-output', 'json_output', is_flag=True, default=False, help='Emit raw JSON response')
def validate(sdk, risk_key, validate_type, json_output):
    """Validate an exploit or patch produced by Constantine.

    Runs the Constantine validation stage against an existing exploit or patch
    for the given risk, reporting whether it passes or fails.

    \b
    Example usages:
        guard constantine validate --risk-key "#risk#api.example.com#CVE-2024-1234" --type exploit
        guard constantine validate --risk-key "#risk#api.example.com#CVE-2024-1234" --type patch
        guard constantine validate --risk-key "#risk#api.example.com#CVE-2024-1234" --type patch --json-output
    """
    body = {'key': risk_key, 'type': validate_type}

    result = sdk.post('/constantine/validate', body)

    if not result:
        error('No response from Constantine validate endpoint')

    if json_output:
        print_json(result)
        return

    status = result.get('status') or result.get('verdict', '')
    details = result.get('details') or result.get('reason', '')

    click.echo(click.style('─' * 60, dim=True))
    click.echo(
        click.style('Validation result: ', bold=True) +
        click.style(status, fg='green' if str(status).lower() in ('pass', 'passed', 'valid', 'ok') else 'red', bold=True)
    )
    if details:
        click.echo()
        click.echo(details)


# ---------------------------------------------------------------------------
# constantine manifest
# ---------------------------------------------------------------------------

@constantine.command('manifest')
@cli_handler
@click.option('--json-output', 'json_output', is_flag=True, default=False, help='Emit raw JSON response')
def manifest(sdk, json_output):
    """Read the Constantine pipeline manifest.

    Returns the list of available presets, modules, and pipeline configuration
    that can be referenced with --preset in other constantine commands.

    \b
    Example usages:
        guard constantine manifest
        guard constantine manifest --json-output
    """
    result = sdk.get('/constantine/manifest')

    if not result:
        error('No response from Constantine manifest endpoint')

    if json_output:
        print_json(result)
        return

    click.echo(click.style('Constantine Pipeline Manifest', bold=True))
    click.echo(click.style('─' * 60, dim=True))

    presets = result.get('presets') or result.get('modules') or []
    if isinstance(presets, list):
        for item in presets:
            if isinstance(item, dict):
                name = item.get('name', '')
                desc = item.get('description', '')
                click.echo(f'  {click.style(name, fg="cyan"):<30}  {desc}')
            else:
                click.echo(f'  {item}')
    elif isinstance(presets, dict):
        for name, desc in presets.items():
            click.echo(f'  {click.style(name, fg="cyan"):<30}  {desc}')
    else:
        print_json(result)


# ---------------------------------------------------------------------------
# constantine osint (nested group)
# ---------------------------------------------------------------------------

@constantine.group('osint')
def osint():
    """OSINT enrichment commands — repository discovery, finding submission,
    and technology entry creation.
    """
    pass


@osint.command('guess-repo')
@cli_handler
@click.option('--asset', required=True, help='Asset key or technology identifier to look up')
@click.option('--json-output', 'json_output', is_flag=True, default=False, help='Emit raw JSON response')
def guess_repo(sdk, asset, json_output):
    """Guess the GitHub repository for a technology or asset.

    Uses OSINT signals to infer the most likely source repository for the
    given asset or technology fingerprint.

    \b
    Example usages:
        guard constantine osint guess-repo --asset "#asset#example.com#nginx/1.24.0"
        guard constantine osint guess-repo --asset "nginx/1.24.0" --json-output
    """
    body = {'key': asset}

    result = sdk.post('/osint/guess-repo', body)

    if not result:
        error('No response from OSINT guess-repo endpoint')

    if json_output:
        print_json(result)
        return

    repo = result.get('repo') or result.get('repository') or result.get('url', '')
    confidence = result.get('confidence', '')

    click.echo(click.style('─' * 60, dim=True))
    if repo:
        click.echo(click.style('Repository: ', bold=True) + click.style(repo, fg='cyan'))
        if confidence:
            click.echo(click.style('Confidence: ', bold=True) + str(confidence))
    else:
        print_json(result)


@osint.command('submit')
@cli_handler
@click.option('--asset', required=True, help='Asset key the finding is associated with')
@click.option('--finding', required=True, help='Finding description or identifier to submit')
@click.option('--source', default=None, help='Source of the OSINT finding (e.g. shodan, censys, github)')
@click.option('--json-output', 'json_output', is_flag=True, default=False, help='Emit raw JSON response')
def submit(sdk, asset, finding, source, json_output):
    """Submit an OSINT finding to Guard.

    Associates an externally-sourced finding with an asset in Guard. The
    finding is queued for triage and risk creation.

    \b
    Example usages:
        guard constantine osint submit --asset "#asset#example.com#api.example.com" --finding "exposed .git directory"
        guard constantine osint submit --asset "#asset#example.com#api.example.com" --finding "exposed .git directory" --source github
        guard constantine osint submit --asset "#asset#example.com#api.example.com" --finding "CVE-2024-1234 confirmed" --source nuclei --json-output
    """
    body = {'key': asset, 'finding': finding}
    if source:
        body['source'] = source

    result = sdk.post('/osint/submit', body)

    if not result:
        error('No response from OSINT submit endpoint')

    if json_output:
        print_json(result)
        return

    status = result.get('status', 'submitted')
    click.echo(
        click.style('Finding submitted: ', bold=True) +
        click.style(status, fg='green')
    )
    ref = result.get('id') or result.get('key', '')
    if ref:
        click.echo(f'Reference: {ref}')


@osint.command('create-tech')
@cli_handler
@click.option('--asset', required=True, help='Asset key to associate the technology with')
@click.option('--name', required=True, help='Technology name (e.g. nginx, OpenSSL)')
@click.option('--version', required=True, help='Technology version string (e.g. 1.24.0)')
@click.option('--json-output', 'json_output', is_flag=True, default=False, help='Emit raw JSON response')
def create_tech(sdk, asset, name, version, json_output):
    """Create a technology entry for an asset from OSINT data.

    Registers a detected technology and version against the given asset so it
    can be enriched, scanned, and matched against vulnerability feeds.

    \b
    Example usages:
        guard constantine osint create-tech --asset "#asset#example.com#api.example.com" --name nginx --version 1.24.0
        guard constantine osint create-tech --asset "#asset#example.com#api.example.com" --name OpenSSL --version 3.0.7 --json-output
    """
    body = {'key': asset, 'name': name, 'version': version}

    result = sdk.post('/osint/create-technology', body)

    if not result:
        error('No response from OSINT create-technology endpoint')

    if json_output:
        print_json(result)
        return

    tech_key = result.get('key') or result.get('id', '')
    click.echo(
        click.style('Technology created: ', bold=True) +
        click.style(f'{name} {version}', fg='cyan')
    )
    if tech_key:
        click.echo(f'Key: {tech_key}')
