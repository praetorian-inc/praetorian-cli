"""Capability catalog: guard's /capabilities API is the source of truth."""

from dataclasses import dataclass, field
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
