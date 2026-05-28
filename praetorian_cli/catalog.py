"""Capability catalog: guard's /capabilities API is the source of truth."""

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


def _as_list(v) -> list:
    if v is None or v == '':
        return []
    return v if isinstance(v, list) else [v]


def _ci(raw: Dict[str, Any], *keys, default=None):
    """Case-insensitive get across candidate keys (API uses PascalCase)."""
    lowered = {k.lower(): v for k, v in raw.items()}
    for k in keys:
        if k.lower() in lowered and lowered[k.lower()] not in (None, ''):
            return lowered[k.lower()]
    return default


@dataclass
class Parameter:
    name: str
    description: str = ''
    type: str = 'string'
    default: str = ''
    required: bool = False
    options: List[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, raw: Dict[str, Any]) -> 'Parameter':
        return cls(
            name=_ci(raw, 'Name', default=''),
            description=_ci(raw, 'Description', default=''),
            type=_ci(raw, 'Type', default='string'),
            default=str(_ci(raw, 'Default', default='') or ''),
            required=bool(_ci(raw, 'Required', default=False)),
            options=_as_list(_ci(raw, 'Options', default=[])),
        )


@dataclass
class Capability:
    name: str
    title: str = ''
    target: List[str] = field(default_factory=list)
    description: str = ''
    category: List[str] = field(default_factory=list)
    surface: str = ''
    runs_on: str = ''
    version: str = ''
    executor: str = ''
    integration: bool = False
    parameters: List[Parameter] = field(default_factory=list)

    @classmethod
    def from_api(cls, raw: Dict[str, Any]) -> 'Capability':
        name = _ci(raw, 'Name', default='')
        return cls(
            name=name,
            title=_ci(raw, 'Title', default=name),
            target=_as_list(_ci(raw, 'Target', default=[])),
            description=_ci(raw, 'Description', default=''),
            category=_as_list(_ci(raw, 'Category', default=[])),
            surface=_ci(raw, 'Surface', default=''),
            runs_on=_ci(raw, 'RunsOn', 'Runs_On', default=''),
            version=_ci(raw, 'Version', default=''),
            executor=_ci(raw, 'Executor', default=''),
            integration=bool(_ci(raw, 'Integration', default=False)),
            parameters=[Parameter.from_api(p) for p in _as_list(_ci(raw, 'Parameters', default=[]))],
        )


def _score(cap: 'Capability', q: str) -> Optional[float]:
    """Higher is better; None means filtered out."""
    if not q:
        return 0.0
    name = cap.name.lower()
    hay = ' '.join([name, cap.title.lower(), cap.description.lower(),
                    ' '.join(cap.category)]).lower()
    if name == q:
        return 100.0
    if name.startswith(q):
        return 90.0 - (len(name) - len(q)) * 0.1
    if q in hay:
        return 70.0
    ratio = SequenceMatcher(None, q, name).ratio()
    if ratio >= 0.6:
        return 40.0 + ratio * 10
    return None


def rank_search(caps, query='', *, category='', surface='', target='', tag=''):
    q = (query or '').lower().strip()
    out = []
    for cap in caps:
        if category and category not in cap.category:
            continue
        if surface and cap.surface != surface:
            continue
        if target and target not in cap.target:
            continue
        if tag and tag not in cap.category and tag not in cap.target:
            continue
        s = _score(cap, q)
        if s is None:
            continue
        out.append((s, cap))
    out.sort(key=lambda t: (-t[0], t[1].name))
    return [c for _, c in out]


_PRAETORIAN_DIR = os.path.join(os.path.expanduser('~'), '.praetorian')
DEFAULT_CACHE_PATH = os.path.join(_PRAETORIAN_DIR, 'capabilities-cache.json')
DEFAULT_BUNDLED_PATH = os.path.join(
    os.path.dirname(__file__), 'modules', 'capabilities_snapshot.json')
CACHE_TTL_SECONDS = 86400


def _atomic_write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class CapabilityCatalog:
    def __init__(self, sdk, cache_path=DEFAULT_CACHE_PATH, bundled_path=DEFAULT_BUNDLED_PATH):
        self.sdk = sdk
        self.cache_path = cache_path
        self.bundled_path = bundled_path
        self._caps = None
        self.source = ''

    def _cache_stale(self) -> bool:
        if not os.path.isfile(self.cache_path):
            return True
        return (time.time() - os.path.getmtime(self.cache_path)) > CACHE_TTL_SECONDS

    def refresh(self, force=False) -> bool:
        if not force and not self._cache_stale():
            return False
        try:
            raw, _ = self.sdk.capabilities.list()
            caps = raw if isinstance(raw, list) else raw.get('capabilities', raw.get('data', []))
            _atomic_write_json(self.cache_path, {'capabilities': caps})
            self._caps = [Capability.from_api(c) for c in caps]
            self.source = 'live'
            return True
        except Exception:
            return False

    def _load_file(self, path):
        with open(path) as f:
            data = json.load(f)
        return data.get('capabilities', data) if isinstance(data, dict) else data

    def all(self):
        if self._caps is not None:
            return self._caps
        if self.refresh():
            return self._caps
        if os.path.isfile(self.cache_path):
            try:
                age = int((time.time() - os.path.getmtime(self.cache_path)) / 3600)
                self._caps = [Capability.from_api(c) for c in self._load_file(self.cache_path)]
                self.source = f'cached ({age}h old)'
                return self._caps
            except (json.JSONDecodeError, OSError):
                pass
        if os.path.isfile(self.bundled_path):
            try:
                self._caps = [Capability.from_api(c) for c in self._load_file(self.bundled_path)]
                self.source = 'bundled'
                return self._caps
            except (json.JSONDecodeError, OSError):
                pass
        self._caps = []
        self.source = 'empty'
        return self._caps

    def get(self, name: str):
        n = name.lower()
        for c in self.all():
            if c.name.lower() == n:
                return c
        return None

    def search(self, query='', **filters):
        return rank_search(self.all(), query, **filters)
