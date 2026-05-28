import json
import types
import pytest
from praetorian_cli.ui.console.commands.marcus import MarcusCommands


class _Host(MarcusCommands):
    """Bare host exposing MarcusCommands methods for unit testing."""
    def __init__(self):
        pass


@pytest.fixture
def host():
    return _Host()


def test_parse_tool_name_from_structured_content(host):
    content = json.dumps({'name': 'run_capability', 'input': {'capability': 'nuclei'}})
    assert host._parse_tool_name(content, {}) == 'run_capability(nuclei)'

def test_parse_tool_name_falls_back_to_tool(host):
    assert host._parse_tool_name('not json', {}) == 'tool'

def test_parse_tool_result_counts_list(host):
    content = json.dumps({'assets': [1, 2, 3]})
    assert host._parse_tool_result(content) == '3 assets'

def test_infer_tool_from_response_status(host):
    assert host._infer_tool_from_response(json.dumps({'status': 'JF'})) == 'status_check'
