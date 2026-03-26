import click
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group(invoke_without_command=True)
@cli_handler
@click.pass_context
def aegis(ctx, sdk):
    """Aegis management commands"""
    if ctx.invoked_subcommand is None:
        # No subcommand was invoked, run the default interactive interface
        from praetorian_cli.ui.aegis.menu import run_aegis_menu
        run_aegis_menu(sdk)


# Add the shared commands to the CLI group
# Each shared command gets wrapped to inject the CLI context

@aegis.command('list')
@cli_handler
@click.option('--details', is_flag=True, help='Show detailed agent information')
@click.option('--filter', help='Filter agents by hostname or other properties')
@click.pass_context
def list_agents(ctx, sdk, details, filter):
    """List Aegis agents with optional details"""
    click.echo(sdk.aegis.format_agents_list(details=details, filter_text=filter))


@aegis.command('ssh')
@cli_handler
@click.argument('client_id', required=True)
@click.option('-u', '--user', help='SSH username (prepends user@ to hostname)')
@click.argument('args', nargs=-1)
@click.pass_context
def ssh(ctx, sdk, client_id, user, args):
    """Connect to an Aegis agent via SSH.

    Pass native ssh flags after client_id; they are forwarded to ssh.

    Common options (forwarded to ssh):
      -L [bind_address:]port:host:hostport   Local port forward (repeatable)
      -R [bind_address:]port:host:hostport   Remote port forward (repeatable)
      -D [bind_address:]port                 Dynamic SOCKS proxy
      -i IDENTITY_FILE                       Identity (private key) file
      -l USER                                Remote username (alternative to -u/--user)
      -o OPTION=VALUE                        Extra ssh config option
      -p PORT                                SSH port
      -v/-vv/-vvv                            Verbose output
    """
    agent = sdk.aegis.get_by_client_id(client_id)
    if not agent:
        click.echo(f"Agent not found: {client_id}", err=True)
        return

    options = list(args)
    sdk.aegis.ssh_to_agent(agent=agent, options=options, user=user, display_info=True)


@aegis.command('cp')
@cli_handler
@click.argument('client_id', required=True)
@click.argument('paths', nargs=2)
@click.option('-u', '--user', help='SSH username')
@click.option('-i', '--identity', 'key', help='Identity (private key) file')
@click.option('--no-rsync', is_flag=True, help='Use scp instead of rsync')
@click.pass_context
def cp(ctx, sdk, client_id, paths, user, key, no_rsync):
    """Copy files to/from an Aegis agent.

    Use a ':' prefix to denote remote paths:

    \b
      Upload:   guard aegis cp <id> ./local_file :/remote/path/
      Download: guard aegis cp <id> :/remote/file ./local_dir/
    """
    src, dst = paths

    src_remote = src.startswith(':')
    dst_remote = dst.startswith(':')

    if src_remote and dst_remote:
        click.echo("Error: both paths cannot be remote", err=True)
        return
    if not src_remote and not dst_remote:
        click.echo("Error: one path must be remote (prefix with ':')", err=True)
        return

    agent = sdk.aegis.get_by_client_id(client_id)
    if not agent:
        click.echo(f"Agent not found: {client_id}", err=True)
        return

    if src_remote:
        direction = 'download'
        remote_path = src[1:]
        local_path = dst
    else:
        direction = 'upload'
        local_path = src
        remote_path = dst[1:]

    ssh_options = []
    if key:
        ssh_options.extend(['-i', key])

    try:
        rc = sdk.aegis.copy_to_agent(
            agent=agent,
            local_path=local_path,
            remote_path=remote_path,
            direction=direction,
            user=user,
            ssh_options=ssh_options,
            display_info=True,
            use_rsync=not no_rsync,
        )
        if rc != 0:
            click.echo(f"Copy failed with exit code {rc}", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@aegis.command('job')
@cli_handler
@click.option('-c', '--capability', 'capabilities', multiple=True, help='Capability to run (e.g., windows-smb-snaffler)')
@click.option('--config', help='JSON configuration string for the job')
@click.argument('client_id', required=True)
@click.pass_context
def job(ctx, sdk, capabilities, config, client_id):
    """Run a job on an Aegis agent"""
    agent = sdk.aegis.get_by_client_id(client_id)
    if not agent:
        click.echo(f"Agent not found: {client_id}", err=True)
        return
    
    try:
        result = sdk.aegis.run_job(
            agent,
            list(capabilities) if capabilities else None,
            config
        )

        if 'capabilities' in result:
            click.echo("Available capabilities:")
            for cap in result['capabilities']:
                name = cap.get('name', 'unknown')
                desc = cap.get('description', '')[:50]
                click.echo(f"  {name:<25} {desc}")
        elif result.get('success'):
            click.echo("✓ Job queued successfully")
            click.echo(f"  Job ID: {result.get('job_id', 'unknown')}")
            click.echo(f"  Status: {result.get('status', 'unknown')}")
        else:
            click.echo("Error: Unknown error", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@aegis.command('info')
@cli_handler
@click.argument('client_id', required=True)
@click.pass_context
def info(ctx, sdk, client_id):
    """Show detailed information for an agent"""
    agent = sdk.aegis.get_by_client_id(client_id)
    if not agent:
        click.echo(f"Agent not found: {client_id}", err=True)
        return
    
    click.echo(agent.to_detailed_string())


@aegis.command('cred-auth')
@cli_handler
@click.argument('client_id', required=True)
@click.argument('credential_id', required=True)
@click.option('--no-wait', is_flag=True, help='Submit task without waiting for completion')
@click.option('--timeout', default=120, type=int, help='Max seconds to wait (default: 120)')
@click.pass_context
def cred_auth(ctx, sdk, client_id, credential_id, no_wait, timeout):
    """Authenticate AD credentials via an Aegis agent.

    Runs the linux-ad-umber-auth management capability on the specified agent
    to validate credentials against a domain controller. Waits for the result
    by default; use --no-wait to return immediately after submission.

    CREDENTIAL_ID is the UUID of the credential stored in Guard.
    """
    import time as _time
    import re
    import sys

    # Validate credential_id is a UUID
    uuid_re = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    if not uuid_re.match(credential_id):
        click.echo("Error: credential_id must be a valid UUID", err=True)
        return

    try:
        result = sdk.aegis.credential_auth(client_id, credential_id)
        task_id = result.get('taskId', '')
        click.echo(f"Task submitted: {task_id}")

        if no_wait or not task_id:
            return

        start = _time.monotonic()
        deadline = start + timeout
        _FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        frame_idx = 0

        try:
            while _time.monotonic() < deadline:
                _time.sleep(5)
                elapsed = int(_time.monotonic() - start)
                frame_idx = (frame_idx + 1) % len(_FRAMES)

                try:
                    task = sdk.aegis.get_management_task(task_id)
                except Exception:
                    _write_status(f"{_FRAMES[frame_idx]} Waiting for agent... ({elapsed}s, retrying)")
                    continue

                current_status = task.get('status', '')
                if current_status in ('AMT_COMPLETED', 'AMT_FAILED'):
                    _clear_status()
                    _print_task_result_cli(task)
                    return

                _write_status(f"{_FRAMES[frame_idx]} Running on agent... ({elapsed}s)")

            _clear_status()
            click.echo(f"Timed out after {timeout}s. Task may still be running.", err=True)
        except KeyboardInterrupt:
            _clear_status()
            click.echo("\nInterrupted — task may still be running in background.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


def _write_status(msg):
    """Overwrite the current line with a status message."""
    import sys
    sys.stderr.write(f"\r\033[K  {msg}")
    sys.stderr.flush()


def _clear_status():
    """Clear the status line."""
    import sys
    sys.stderr.write("\r\033[K")
    sys.stderr.flush()


def _print_task_result_cli(task):
    """Print the full result of a completed/failed management task."""
    import json as _json

    status = task.get('status', '')
    is_success = status == 'AMT_COMPLETED'
    label = '✓' if is_success else '✗'
    click.echo(f"{label} {status}")

    if task.get('errorMessage'):
        click.echo(f"Error: {task['errorMessage']}")

    cmd = task.get('commandResult') or {}
    output_str = cmd.get('output', '')

    # Try to parse output as JSON for structured display
    output_data = None
    if output_str:
        try:
            output_data = _json.loads(output_str)
        except (_json.JSONDecodeError, TypeError):
            pass

    if output_data and isinstance(output_data, dict):
        max_key = max((len(str(k)) for k in output_data), default=0)
        for k, v in output_data.items():
            click.echo(f"  {str(k):<{max_key}}  {v}")
    else:
        if task.get('result'):
            click.echo(f"Result: {task['result']}")
        if cmd:
            click.echo(f"Success:   {cmd.get('success', 'N/A')}")
            click.echo(f"Exit code: {cmd.get('exit_code', 'N/A')}")
        if output_str:
            click.echo("--- Output ---")
            click.echo(output_str)

    if cmd.get('error_output'):
        click.echo("--- Error Output ---", err=True)
        click.echo(cmd['error_output'], err=True)
    if cmd.get('error_message'):
        click.echo(f"Error: {cmd['error_message']}", err=True)


@aegis.command('ingest')
@cli_handler
@click.argument('file', type=click.Path(exists=True))
@click.option('--dry-run', is_flag=True, help='Parse and show summary without sending data')
@click.option('--skip-files', is_flag=True, help='Skip uploading proof file items')
@click.pass_context
def ingest(ctx, sdk, file, dry_run, skip_files):
    """Ingest an Aegis result file into Guard.

    Reads assets, risks, and proof files from a chariot_result.json
    and pushes them to Guard. Assets are created first, then risks
    (linked to those assets), then proof files.
    """
    sdk.aegis.ingest_result(file, dry_run=dry_run, skip_files=skip_files)
