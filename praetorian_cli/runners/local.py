"""Local capability runner — install and run Praetorian tools locally."""

import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
from typing import Optional

# Where local binaries are installed
INSTALL_DIR = os.path.join(os.path.expanduser('~'), '.praetorian', 'bin')

def _get_installable_tools():
    from praetorian_cli.registry import get_registry
    return get_registry().get_installable_tools()


class _LazyTools:
    def __init__(self):
        self._loaded = None

    def _ensure(self):
        if self._loaded is None:
            self._loaded = _get_installable_tools()
        return self._loaded

    def __contains__(self, key):
        return key in self._ensure()

    def __getitem__(self, key):
        return self._ensure()[key]

    def __iter__(self):
        return iter(self._ensure())

    def __len__(self):
        return len(self._ensure())

    def items(self):
        return self._ensure().items()

    def keys(self):
        return self._ensure().keys()

    def values(self):
        return self._ensure().values()

    def get(self, key, default=None):
        return self._ensure().get(key, default)


INSTALLABLE_TOOLS = _LazyTools()


# Well-known service ports for Brutus protocol auto-detection.
# Keep this minimal: only protocols Brutus natively supports.
_WELL_KNOWN_PORTS = {
    22: 'ssh',
    3389: 'rdp',
    21: 'ftp',
    445: 'smb',
    23: 'telnet',
    3306: 'mysql',
    5432: 'postgres',
}


def _infer_protocol(target: str):
    """Infer protocol from a 'host:port' target using well-known ports.

    Returns the protocol name or None if no inference is possible.
    """
    if not target or ':' not in target:
        return None
    # rsplit so 'host:port' works even if host contains ':'
    _, sep, port_str = target.rpartition(':')
    if not sep:
        return None
    try:
        port = int(port_str)
    except ValueError:
        return None
    return _WELL_KNOWN_PORTS.get(port)


def _has_flag(pass_through, *flags):
    """Return True if any of the given flag names appears in pass_through."""
    if not pass_through:
        return False
    flag_set = set(flags)
    return any(arg in flag_set for arg in pass_through)


def _detect_platform():
    """Detect OS and architecture for binary download."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    os_map = {'darwin': 'darwin', 'linux': 'linux', 'windows': 'windows'}
    arch_map = {
        'x86_64': 'amd64', 'amd64': 'amd64',
        'arm64': 'arm64', 'aarch64': 'arm64',
        'i386': '386', 'i686': '386',
    }

    return os_map.get(system, system), arch_map.get(machine, machine)


def get_binary_path(tool_name: str) -> Optional[str]:
    """Get path to installed binary, checking both install dir and PATH."""
    # Check our install dir first
    local_path = os.path.join(INSTALL_DIR, tool_name)
    if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
        return local_path

    # Check system PATH
    system_path = shutil.which(tool_name)
    if system_path:
        return system_path

    return None


def is_installed(tool_name: str) -> bool:
    return get_binary_path(tool_name) is not None


def install_tool(tool_name: str, force=False) -> str:
    """Download and install a tool from GitHub releases. Returns binary path."""
    if tool_name not in INSTALLABLE_TOOLS:
        lines = [f'Unknown tool: {tool_name}. Installable tools:']
        for name in sorted(INSTALLABLE_TOOLS):
            lines.append(f'  {name:<18} {INSTALLABLE_TOOLS[name]["description"]}')
        raise ValueError('\n'.join(lines))

    if not force and is_installed(tool_name):
        return get_binary_path(tool_name)

    repo = INSTALLABLE_TOOLS[tool_name]['repo']
    os_name, arch = _detect_platform()

    os.makedirs(INSTALL_DIR, exist_ok=True)

    # Get latest release asset URL using gh CLI
    try:
        result = subprocess.run(
            ['gh', 'release', 'download', '--repo', repo,
             '--pattern', f'{tool_name}-{os_name}-{arch}*',
             '--dir', tempfile.gettempdir(), '--clobber'],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f'gh release download failed: {result.stderr.strip()}')
    except FileNotFoundError:
        raise RuntimeError('gh CLI not found. Install GitHub CLI: https://cli.github.com/')

    # Find the downloaded file
    tmp = tempfile.gettempdir()
    downloaded = None
    for f in os.listdir(tmp):
        if f.startswith(f'{tool_name}-{os_name}-{arch}'):
            downloaded = os.path.join(tmp, f)
            break

    if not downloaded:
        raise RuntimeError(f'Download not found for {tool_name}-{os_name}-{arch}')

    # Extract
    binary_path = os.path.join(INSTALL_DIR, tool_name)
    if downloaded.endswith('.tar.gz') or downloaded.endswith('.tgz'):
        with tarfile.open(downloaded, 'r:gz') as tar:
            # Find the binary inside the archive
            for member in tar.getmembers():
                if member.name == tool_name or member.name.endswith(f'/{tool_name}'):
                    member.name = tool_name
                    tar.extract(member, INSTALL_DIR)
                    break
            else:
                # If no exact match, extract first executable-looking file
                for member in tar.getmembers():
                    if member.isfile() and not member.name.endswith(('.md', '.txt', '.yml', '.yaml')):
                        member.name = tool_name
                        tar.extract(member, INSTALL_DIR)
                        break
    elif downloaded.endswith('.zip'):
        import zipfile
        with zipfile.ZipFile(downloaded, 'r') as z:
            for name in z.namelist():
                if name == tool_name or name.endswith(f'/{tool_name}') or name.endswith('.exe'):
                    with z.open(name) as src, open(binary_path, 'wb') as dst:
                        dst.write(src.read())
                    break
    else:
        # Direct binary
        shutil.copy2(downloaded, binary_path)

    # Make executable
    os.chmod(binary_path, 0o755)

    # Record version
    try:
        from praetorian_cli.registry import get_registry
        ver_result = subprocess.run(
            ['gh', 'release', 'view', '--repo', repo, '--json', 'tagName', '-q', '.tagName'],
            capture_output=True, text=True, timeout=15,
        )
        version_tag = ver_result.stdout.strip() if ver_result.returncode == 0 else 'unknown'
        get_registry().record_version(tool_name, version_tag, binary_path)
    except Exception:
        pass

    # Cleanup
    try:
        os.remove(downloaded)
    except OSError:
        pass

    return binary_path


def list_installed() -> dict:
    """Return dict of tool → path for all installed tools."""
    result = {}
    for name in INSTALLABLE_TOOLS:
        path = get_binary_path(name)
        if path:
            result[name] = path
    return result


class LocalRunner:
    """Run a capability binary locally and capture output."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.binary_path = get_binary_path(tool_name)
        if not self.binary_path:
            raise FileNotFoundError(
                f'{tool_name} is not installed. Run "guard run install {tool_name}" to install it.'
            )

    def run(self, args: list, timeout: int = 300) -> subprocess.CompletedProcess:
        """Run the tool with given arguments."""
        cmd = [self.binary_path] + args
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )

    def run_streaming(self, args: list, timeout: int = 300):
        """Run the tool with live stdout streaming."""
        cmd = [self.binary_path] + args
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        return proc


# ── Tool Plugin Registry ─────────────────────────────────────────────────────

class ToolPlugin:
    """Base class for local tool argument builders."""

    def build_args(self, target, extra_config='', pass_through=None):
        config = {}
        if extra_config:
            try:
                config = json.loads(extra_config) if isinstance(extra_config, str) else extra_config
            except (json.JSONDecodeError, TypeError):
                pass
        args = self._build(target, config, pass_through=pass_through)
        return args

    def _build(self, target, config, pass_through=None):
        args = [target]
        if pass_through:
            args.extend(pass_through)
        return args


class BrutusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['--target', target]

        # Protocol precedence: caller passthrough (silent) > config['protocol'] > inferred from port
        caller_has_protocol = _has_flag(pass_through, '--protocol')
        if not caller_has_protocol:
            proto = config.get('protocol') or _infer_protocol(target)
            if proto:
                args.extend(['--protocol', proto])

        if config.get('usernames') and not _has_flag(pass_through, '-u', '-U'):
            args.extend(['-u', config['usernames']])
        if config.get('passwords') and not _has_flag(pass_through, '-p', '-P'):
            args.extend(['-p', config['passwords']])

        if pass_through:
            args.extend(pass_through)
        return args


class NucleiPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['-u', target, '-jsonl']
        if config.get('templates'):
            args.extend(['-t', config['templates']])
        if pass_through:
            args.extend(pass_through)
        return args


class TitusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['scan', target]
        if config.get('validation') == 'true':
            args.append('--validate')
        if pass_through:
            args.extend(pass_through)
        return args


class TrajanPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['scan', target]
        if config.get('token'):
            args.extend(['--token', config['token']])
        if pass_through:
            args.extend(pass_through)
        return args


class JuliusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['-t', target]
        if pass_through:
            args.extend(pass_through)
        return args


class AugustusPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['scan', '-t', target]
        if pass_through:
            args.extend(pass_through)
        return args


class NervaPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['-t', target]
        if pass_through:
            args.extend(pass_through)
        return args


class GatoPlugin(ToolPlugin):
    def _build(self, target, config, pass_through=None):
        args = ['enumerate', '-t', target]
        if config.get('token'):
            args.extend(['--token', config['token']])
        if pass_through:
            args.extend(pass_through)
        return args


class UrlTargetPlugin(ToolPlugin):
    """For tools that take scan -u <target>."""
    def _build(self, target, config, pass_through=None):
        args = ['scan', '-u', target]
        if pass_through:
            args.extend(pass_through)
        return args


class ScanTargetPlugin(ToolPlugin):
    """For tools that take scan <target>."""
    def _build(self, target, config, pass_through=None):
        args = ['scan', target]
        if pass_through:
            args.extend(pass_through)
        return args


# Plugin verification status:
# - brutus:      verified against brutus --help (ENG-3042)
# - nuclei:      -u is the documented URL flag — OK
# - julius/nerva/nero: use -t <target>; unverified against each binary's --help
# - titus/trajan/vespasian/constantine/caligula: `scan <target>` — unverified
# - augustus/gato: `scan -t <target>` / `enumerate -t <target>` — unverified
# - cato/florian/hadrian: `scan -u <target>` — unverified
# Users can always override via `guard run tool <tool> <target> -- <raw args>`.
TOOL_PLUGINS = {
    'brutus':      BrutusPlugin(),
    'nuclei':      NucleiPlugin(),
    'titus':       TitusPlugin(),
    'trajan':      TrajanPlugin(),
    'julius':      JuliusPlugin(),
    'augustus':     AugustusPlugin(),
    'nerva':       NervaPlugin(),
    'gato':        GatoPlugin(),
    'cato':        UrlTargetPlugin(),
    'vespasian':   ScanTargetPlugin(),
    'constantine': ScanTargetPlugin(),
    'florian':     UrlTargetPlugin(),
    'caligula':    ScanTargetPlugin(),
    'hadrian':     UrlTargetPlugin(),
    'nero':        NervaPlugin(),  # uses -t like nerva
}

_default_plugin = ToolPlugin()


def get_tool_plugin(tool_name):
    """Get the argument-builder plugin for a tool, or the default passthrough."""
    return TOOL_PLUGINS.get(tool_name, _default_plugin)
