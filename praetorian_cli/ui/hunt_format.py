from datetime import datetime


def record_value(record, *names):
    """Read the first present field from a mapping or SDK model."""
    for name in names:
        value = (
            record.get(name)
            if isinstance(record, dict)
            else getattr(record, name, None)
        )
        if value is not None:
            return value
    return None


def safe_text(value, limit=500):
    """Collapse untrusted terminal text to printable, bounded content."""
    if value is None:
        return ''
    printable = ''.join(
        character if character.isprintable() else ' '
        for character in str(value)
    )
    return ' '.join(printable.split())[:limit]


def safe_multiline(value):
    """Preserve printable line structure while removing terminal controls."""
    return ''.join(
        character if character in '\n\t' or character.isprintable() else ' '
        for character in str(value or '')
    )


def timestamp_value(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def timestamp_sort_key(value):
    parsed = timestamp_value(value)
    return parsed.timestamp() if parsed is not None else float('-inf')


def format_timestamp(value):
    parsed = timestamp_value(value)
    if parsed is None:
        return '—'
    return parsed.strftime('%Y-%m-%d %H:%M UTC')
