# ENG-3042 — Fix Guard CLI/console tool argument handling

Linear: https://linear.app/praetorianlabs/issue/ENG-3042
Parent: OFFSEC-2383 (Marcus + long-username-list crash — **not in this sub-ticket**)

## Problem

Running Brutus via `guard run tool` (CLI) or `run brutus` (console) is broken in several ways:

1. **Wrong target flag.** `BrutusPlugin._build()` in `praetorian_cli/runners/local.py:207-214` emits `-t <target>`. In Brutus `-t` is `--threads`, not the target. The target flag is `--target`, and single-target mode also requires `--protocol <proto>`. Result: Brutus rejects the invocation with a threads-parse error.
2. **CLI rejects extra arguments.** `guard run tool` (`handlers/run.py:127-137`) uses fixed Click options. A user running `guard run tool brutus 10.0.1.5:2200 -U users.txt --protocol ssh` gets a Click "no such option" error — Click parses before the plugin ever sees the target.
3. **Console has no passthrough.** `_cmd_run` in `ui/console/commands/tools.py` only recognises `--ask` and `--wait`. There is no way to pass `-U`, `--protocol`, `--spray`, etc. from the console. The help text for the tool's own options is never shown.
4. **Some other local plugins use the same `-t` pattern** (`julius`, `nerva`, `nero`). Unverified against each binary's real flag set.

The workaround Hunter landed on was `go install`-ing Brutus directly and bypassing the CLI entirely, which defeats the point of `guard run tool`.

## Out of scope

- Marcus crashing on long username lists (tracked under OFFSEC-2383, Noah).
- Backend/remote job support for arbitrary tool args. Remote jobs take structured JSON config; adding raw-arg passthrough there would require a backend change. This sub-ticket keeps remote semantics as-is and explicitly rejects passthrough with `--remote`.
- Auto-translating passthrough flags into remote JSON config. Fragile and asymmetric (no sensible translation for `--spray` / `--badkeys-only`, etc.).

## Design

### A. Fix `BrutusPlugin`

Update `_build()` to:
- Emit `--target <target>`.
- Emit `--protocol <proto>` when the target or config specifies one. Resolution order:
  1. `config['protocol']` if the caller passes it explicitly via `-c '{"protocol":"ssh"}'`.
  2. Inferred from `target` if it matches `host:port` and the port is a well-known service (22→ssh, 3389→rdp, 21→ftp, 445→smb, 23→telnet, 3306→mysql, 5432→postgres). Keep the table minimal — anything unknown falls through.
  3. Otherwise omit `--protocol` and rely on the user passing it via trailing passthrough args.
- Preserve existing `-u`/`-p` emission for `config['usernames']` / `config['passwords']`.
- Accept a `pass_through` list argument that is appended last, so user-provided flags always win over defaults.

```python
class BrutusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['--target', target]
        proto = config.get('protocol') or _infer_protocol(target)
        if proto and not _has_flag(pass_through, '--protocol'):
            args.extend(['--protocol', proto])
        if config.get('usernames') and not _has_flag(pass_through, '-u', '-U'):
            args.extend(['-u', config['usernames']])
        if config.get('passwords') and not _has_flag(pass_through, '-p', '-P'):
            args.extend(['-p', config['passwords']])
        if pass_through:
            args.extend(pass_through)
        return args
```

`_has_flag` is a small helper that checks whether any of the given flags appear in the passthrough list — so a caller's `-U users.txt` suppresses the structured-config `-u` and there's no duplicate flag conflict.

### B. `ToolPlugin.build_args` signature update

Extend the base method signature to accept a `pass_through` list and thread it through every concrete plugin. Plugins that don't care about it still accept the kwarg (ignored by default). This is a small surface change touching all plugins in `local.py` but keeps the extension additive.

### C. `guard run tool` CLI

Add trailing-args support to the `tool` command:

```python
@run.command(
    'tool',
    context_settings={'ignore_unknown_options': True, 'allow_extra_args': True},
)
@click.argument('tool_name')
@click.argument('target')
@click.argument('tool_args', nargs=-1, type=click.UNPROCESSED)
@click.option('-c', '--config', ...)
@click.option('--credential', ...)
@click.option('--wait', ...)
@click.option('--ask', 'use_agent', ...)
@click.option('--local', ...)
@click.option('--remote', ...)
def tool(sdk, tool_name, target, tool_args, ...):
```

Effects:
- `guard run tool brutus 10.0.1.5:2200 --protocol ssh -U users.txt` — unknown options `-U`/`--protocol` get collected into `tool_args`.
- `guard run tool brutus 10.0.1.5:2200 -- --wait foo` — the `--` forces everything after to `tool_args`, so a tool's own `--wait` (or any flag that collides with ours) still passes through.
- `tool_args` flows into `_run_local` → `plugin.build_args(target, config, pass_through=list(tool_args))`.
- If `tool_args` is non-empty and the resolved path is remote (either `--remote` explicit, or local fallback not installed and `--remote` inferred), fail loudly:
  *"Extra args after the target are only supported when running locally. Install the tool locally (`guard run install <tool>`) or encode the settings as JSON via `-c '{...}'`."*
- If `tool_args` is non-empty and `--ask` (agent) is used, same error. Agent path talks to Marcus, not the binary.

### D. Console `run <tool>`

Update `_cmd_run` in `ui/console/commands/tools.py`:

1. Separate console-owned flags (`--ask`, `--wait`) from tool-specific args:
   ```python
   OWN_FLAGS = {'--ask', '--wait'}
   pass_through = [a for a in args[2:] if a not in OWN_FLAGS]
   use_agent = '--ask' in args
   wait = '--wait' in args
   ```
   Honour the same `--` boundary: everything after a literal `--` goes to `pass_through` regardless, so you can pass `run brutus 10.0.1.5:2200 -- --wait` to forward `--wait` to the binary itself.
2. `run <tool> --help` — if the binary is installed locally, invoke `<tool> --help` via the runner and stream output into the console; otherwise print a message pointing at `guard run install <tool>`.
3. Force-local when `pass_through` is non-empty and the tool is installed. If the tool is not installed, refuse with the same error as the CLI ("install the tool locally or use structured config").
4. When routing to the direct-remote path with no pass_through, behaviour is unchanged.

### E. Audit other plugins

Verify each plugin whose current `_build()` uses `-t`, `-u`, or a `scan` sub-command against the corresponding binary's `--help`. This list covers everything in `TOOL_PLUGINS` today:

| Plugin | Current | Verify | Action if wrong |
|---|---|---|---|
| brutus | `-t <target>` | known bad | fix per §A |
| julius | `-t <target>` | verify | fix if wrong |
| nerva | `-t <target>` | verify | fix if wrong |
| nero | `-t <target>` (via `NervaPlugin`) | verify | fix if wrong |
| nuclei | `-u <target>` | correct (documented) | — |
| titus | `scan <target>` | verify | — |
| trajan | `scan <target>` | verify | — |
| augustus | `scan -t <target>` | verify | fix if wrong |
| gato | `enumerate -t <target>` | verify | fix if wrong |
| cato/florian/hadrian | `scan -u <target>` | verify | fix if wrong |
| vespasian/constantine/caligula | `scan <target>` | verify | fix if wrong |

Audits that fail become small follow-up fixes within the same PR; if a binary isn't readily installable in the sandbox, document it in the plugin as *"verified against vX.Y help"* or flag it for a separate ticket.

### F. Errors and UX

- Errors use the existing `error()` helper (CLI) / `self.console.print('[error]...[/error]')` (console). No new error types.
- `guard run tool <tool> --help` — keep native Click `--help` for the command itself (shows our options and mentions passthrough). Tool-specific help comes from `guard run tool <tool> <any-target> -- --help`, which forwards `--help` to the binary. Document this in the docstring.

## Testing

Unit tests (new file `praetorian_cli/sdk/test/test_run_passthrough.py` alongside existing test layout):

- `BrutusPlugin._build`
  - bare target → `['--target', 'x']`
  - `host:22` → adds `--protocol ssh`
  - `host:9999` → no inferred protocol
  - config with `usernames`/`passwords` → adds `-u`/`-p`
  - pass_through `['-U', 'users.txt']` suppresses structured `-u`
  - pass_through `['--protocol', 'rdp']` suppresses inferred `--protocol ssh`
- `guard run tool` CLI via `click.testing.CliRunner`
  - `guard run tool brutus <target> --protocol ssh -U foo` — tool_args collected
  - `guard run tool brutus <target> -- --wait` — `--wait` after `--` goes to tool_args, not the command's own `--wait`
  - `guard run tool brutus <target> --protocol ssh --remote` — error about remote + passthrough
  - `guard run tool brutus <target> --protocol ssh --ask` — error about agent + passthrough
- Console `_cmd_run`
  - `run brutus key --protocol ssh` forwards `--protocol ssh` to the plugin
  - `run brutus key -- --wait` forwards `--wait`, does NOT trigger console's own wait
  - `run brutus --help` when not installed prints install hint

Mock the binary execution (`LocalRunner.run_streaming`) so tests stay hermetic.

## Rollout / risk

- Pure additive change to plugin signatures (new optional kwarg).
- Click context settings are backward-compatible — existing invocations without trailing args keep working.
- The one behaviour change users will notice: `guard run tool brutus x` will now emit `--target x` instead of `-t x`. That's the bug fix.
- Update `docs/console.md` and the `guard run tool` docstring to show a passthrough example.

## Acceptance

- `guard run tool brutus 10.0.1.5:2200 -U users.txt --protocol ssh` (when brutus is installed locally) runs brutus with the expected flags.
- `run brutus 10.0.1.5:2200 -U users.txt --protocol ssh` in the console does the same.
- `run brutus --help` inside the console prints brutus' own help.
- `guard run tool brutus x --protocol ssh --remote` emits a clear error.
- All new tests pass.
