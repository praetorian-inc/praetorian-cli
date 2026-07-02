"""Client-side web-auth recipe schema and validation.

Mirrors the backend's webauth.ValidateRecipe so the CLI/SDK reject a bad
recipe before the broker round-trip. The backend remains the source of truth
and re-validates; this is a fast-fail convenience.

Prefer HTTP-based recipes (http/extract/capture) — they replay far more
reliably than browser steps. For browser-driven logins use the
discover-login method (`guard add credential webauth-discover`) and let the
recorder agent build the recipe.
"""
import re

_VAR_RE = re.compile(r'\{\{(\w+)\}\}')
_HTTP_METHODS = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}
_TOTP_SECRET_INPUT = 'totp_secret'

# HTTP-based kinds (preferred). Browser kinds work but are fragile to replay.
HTTP_KINDS = {'http', 'extract', 'capture'}
BROWSER_KINDS = {'navigate', 'click', 'type', 'totp', 'cookie', 'load_request'}
OUTPUT_KINDS = {'cookie', 'capture'}


def validate_recipe(steps, inputs=None):
    """Validate a recipe (list of step dicts). Raises ValueError on any problem.

    :param steps: the recipe — a list of {'kind': ..., ...} step objects
    :param inputs: dict of named inputs referenced as {{key}} in step fields
    """
    inputs = inputs or {}
    if not isinstance(steps, list) or not steps:
        raise ValueError('recipe must be a non-empty JSON array of steps')

    defined = set(inputs)
    emits_output = False
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise ValueError(f'step {i}: must be a JSON object')
        kind = s.get('kind')
        if not kind:
            raise ValueError(f'step {i}: missing "kind"')
        _validate_step(i, kind, s)

        for tmpl in _templated_fields(kind, s):
            for ref in _VAR_RE.findall(tmpl or ''):
                if ref not in defined:
                    raise ValueError(
                        f'step {i}: unresolved {{{{{ref}}}}} — not in inputs and '
                        'not defined by a prior extract')
        if kind == 'totp' and _TOTP_SECRET_INPUT not in defined:
            raise ValueError(f'step {i}: totp requires "{_TOTP_SECRET_INPUT}" in inputs')
        if kind == 'extract':
            defined.add(s['save_as'])
        if kind in OUTPUT_KINDS:
            emits_output = True

    if not emits_output:
        raise ValueError('recipe has no output: add a capture (or cookie) step')


def _validate_step(i, kind, s):
    # Required fields are always strings; enforcing that here keeps the template
    # scan and string ops (startswith, .values()) from raising raw TypeErrors.
    def req(field):
        v = s.get(field)
        if not v:
            raise ValueError(f'step {i} ({kind}): {field} is required')
        if not isinstance(v, str):
            raise ValueError(f'step {i} ({kind}): {field} must be a string')

    if kind == 'navigate' or kind == 'load_request':
        req('url')
    elif kind == 'click':
        req('selector')
    elif kind == 'type':
        req('selector')
        req('value')
    elif kind == 'totp':
        has_one, has_many = bool(s.get('selector')), bool(s.get('selectors'))
        if has_one == has_many:
            raise ValueError(f'step {i} (totp): exactly one of selector or selectors is required')
        if has_many and (not isinstance(s['selectors'], list) or len(s['selectors']) != 6):
            raise ValueError(f'step {i} (totp): selectors must be a list of 6 entries')
    elif kind == 'cookie':
        pass
    elif kind == 'http':
        if str(s.get('method', '')).upper() not in _HTTP_METHODS:
            raise ValueError(f'step {i} (http): unsupported method {s.get("method")!r}')
        req('url')
        if 'body' in s and not isinstance(s['body'], str):
            raise ValueError(f'step {i} (http): body must be a string')
        headers = s.get('headers')
        if headers is not None and (not isinstance(headers, dict)
                                    or not all(isinstance(v, str) for v in headers.values())):
            raise ValueError(f'step {i} (http): headers must be an object of string values')
    elif kind == 'extract':
        req('save_as')
        req('from')
        _validate_extract_from(i, s)
    elif kind == 'capture':
        req('name')
        req('value')
    else:
        raise ValueError(f'step {i}: unknown kind {kind!r}')


def _validate_extract_from(i, s):
    frm = s['from']
    if frm == 'response_body':
        if bool(s.get('jsonpath')) == bool(s.get('regex')):
            raise ValueError(f'step {i} (extract): from="response_body" requires exactly one of jsonpath or regex')
        if s.get('regex'):
            try:
                rx = re.compile(s['regex'])
            except re.error as e:
                raise ValueError(f'step {i} (extract): regex compile: {e}')
            if rx.groups != 1:
                raise ValueError(f'step {i} (extract): regex needs exactly one capture group, got {rx.groups}')
        return
    for prefix in ('response_header:', 'response_cookie:', 'request_header:'):
        if frm.startswith(prefix):
            if not frm[len(prefix):]:
                raise ValueError(f'step {i} (extract): from="{prefix}" needs a name')
            return
    raise ValueError(f'step {i} (extract): unsupported from {frm!r}')


def _templated_fields(kind, s):
    if kind == 'navigate':
        return [s.get('url', '')]
    if kind in ('type', 'capture'):
        return [s.get('value', '')]
    if kind == 'http':
        return [s.get('url', ''), s.get('body', '')] + list((s.get('headers') or {}).values())
    return []
