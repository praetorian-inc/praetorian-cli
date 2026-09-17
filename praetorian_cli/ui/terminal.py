import sys


def supports_fullscreen(input_stream=None, output_stream=None):
    """Return whether an interactive UI can safely own both terminal streams."""
    input_stream = sys.stdin if input_stream is None else input_stream
    output_stream = sys.stdout if output_stream is None else output_stream
    try:
        return input_stream.isatty() and output_stream.isatty()
    except (AttributeError, OSError, ValueError):
        return False
