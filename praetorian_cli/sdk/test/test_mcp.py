import pytest

from praetorian_cli.handlers.agent import DEFAULT_MCP_TOOLS
from praetorian_cli.sdk.mcp_server import MCPServer
from praetorian_cli.sdk.test.utils import selected_test_target, setup_chariot, make_test_values, clean_test_entities

# Sensitive tool names that MCPServer discovery would build from the fake
# chariot below. Every one of these returns or embeds secret material
# (broker credentials, API keys, webhook auth PINs, account assumption,
# red team phishing infrastructure and live campaign authorization).
SENSITIVE_SAMPLES = (
    'credentials_get',
    'credentials_list',
    'credentials_add',
    'keys_get',
    'keys_list',
    'keys_add',
    'integrations_get',
    'integrations_list',
    'webhook_get_url',
    'webhook_upsert',
    'accounts_list',
    'accounts_assume_role',
    # red_team_dns_list is the regression case: it used to be exposed by
    # default because it rode the '*_list' allow pattern.
    'red_team_dns_list',
    'red_team_campaign_authorize',
)


class _FakeSearch:
    def __init__(self):
        self.api = object()

    def by_query(self, query):
        """Search entities by query."""
        return []


class _FakeAssets:
    def __init__(self):
        self.api = object()

    def get(self, key):
        """Get an asset."""
        return {}

    def list(self, offset=None):
        """List assets."""
        return []


class _FakeRisks:
    def __init__(self):
        self.api = object()

    def add(self, name):
        """Add a risk."""
        return {}

    def list(self, offset=None):
        """List risks."""
        return []


class _FakeCredentials:
    def __init__(self):
        self.api = object()

    def get(self, credential_id):
        """Get a credential, including its raw secret."""
        return {}

    def list(self, offset=None):
        """List credentials."""
        return []

    def add(self, resource_key):
        """Add a credential."""
        return {}


class _FakeKeys:
    def __init__(self):
        self.api = object()

    def get(self, key):
        """Get an API key."""
        return {}

    def list(self, offset=None):
        """List API keys."""
        return []

    def add(self, name):
        """Add an API key."""
        return {}


class _FakeIntegrations:
    def __init__(self):
        self.api = object()

    def get(self, key):
        """Get an integration, whose record embeds the webhook auth PIN."""
        return {}

    def list(self, offset=None):
        """List integrations."""
        return []


class _FakeWebhook:
    def __init__(self):
        self.api = object()

    def get_url(self):
        """Get the webhook URL, which embeds the auth PIN."""
        return ''

    def upsert(self):
        """Create or rotate the webhook."""
        return ''


class _FakeAccounts:
    def __init__(self):
        self.api = object()

    def list(self, offset=None):
        """List accounts."""
        return []

    def assume_role(self, account_email):
        """Assume the role of another account."""
        return None


class _FakeRedTeam:
    def __init__(self):
        self.api = object()

    def dns_list(self, domain, offset=None):
        """List DNS records for a red team domain."""
        return []

    def campaign_authorize(self, campaign_id):
        """Authorize a campaign to send live phishing email."""
        return {}


class _FakeChariot:
    """Offline stand-in for the Chariot SDK object MCP discovery walks."""

    def __init__(self):
        self.search = _FakeSearch()
        self.assets = _FakeAssets()
        self.risks = _FakeRisks()
        self.credentials = _FakeCredentials()
        self.keys = _FakeKeys()
        self.integrations = _FakeIntegrations()
        self.webhook = _FakeWebhook()
        self.accounts = _FakeAccounts()
        self.red_team = _FakeRedTeam()


def _discovered(allowed):
    """Discovered tool names for a fake chariot under the given allowlist."""
    return MCPServer(_FakeChariot(), allowed).discovered_tools


class TestMCPSensitiveTools:
    """ENG-6639: sensitive tools must be deny-by-default in the MCP server.

    Contract under test:
    - mcp_server.SENSITIVE_TOOL_PATTERNS names the sensitive families
      ('accounts_*', 'credentials_*', 'integrations_*', 'keys_*',
      'red_team_*', 'webhook_*').
    - A tool matching a sensitive pattern is NEVER exposed by wildcard
      allow patterns, and NEVER exposed when allowable_tools is
      None/empty; it is exposed ONLY when an allow entry equals the tool
      name exactly (explicit opt-in, e.g. 'credentials_get').
    - Non-sensitive tools keep current semantics: no allowlist means
      allowed; otherwise fnmatch against the allow patterns.
    - The CLI default profile (handlers.agent.DEFAULT_MCP_TOOLS =
      ['search_by_query', '*_list', '*_get']) must therefore expose only
      non-sensitive read tools.
    """

    def test_default_profile_exposes_read_tools(self):
        tools = _discovered(list(DEFAULT_MCP_TOOLS))
        assert 'search_by_query' in tools
        assert 'assets_get' in tools
        assert 'assets_list' in tools
        assert 'risks_list' in tools

    def test_default_profile_denies_all_sensitive_tools(self):
        tools = _discovered(list(DEFAULT_MCP_TOOLS))
        for name in SENSITIVE_SAMPLES:
            assert name not in tools, (
                f'{name} is exposed under the default read-only MCP profile'
            )

    def test_no_allowlist_still_denies_sensitive_tools(self):
        tools = _discovered(None)
        assert 'assets_list' in tools
        for name in SENSITIVE_SAMPLES:
            assert name not in tools, (
                f'{name} is exposed with no allowlist configured'
            )

    def test_wildcards_never_match_sensitive_tools(self):
        tools = _discovered(
            ['credentials_*', 'keys_*', 'integrations_*', 'webhook_*', 'accounts_*', '*']
        )
        for name in SENSITIVE_SAMPLES:
            assert name not in tools, (
                f'{name} is exposed via a wildcard allow pattern'
            )

    def test_exact_name_exposes_only_that_tool(self):
        tools = _discovered(['credentials_get'])
        assert 'credentials_get' in tools
        assert 'credentials_list' not in tools
        assert 'keys_get' not in tools

    def test_exact_name_exposes_a_red_team_tool(self):
        # Deny-by-default must not silently become deny-always: 'red_team_*' is a
        # sensitive family, but an exact-name allow entry is still the documented
        # way to opt one member in. red_team_dns_list is the regression case --
        # it lost its '*_list' wildcard exposure, not its exact-name exposure.
        tools = _discovered(['red_team_dns_list'])
        assert 'red_team_dns_list' in tools
        assert 'red_team_campaign_authorize' not in tools

    def test_exact_name_composes_with_default_profile(self):
        tools = _discovered(list(DEFAULT_MCP_TOOLS) + ['credentials_list'])
        assert 'credentials_list' in tools
        assert 'credentials_get' not in tools
        assert 'assets_list' in tools

    def test_wildcards_still_match_non_sensitive_tools(self):
        tools = _discovered(['risks_*'])
        assert 'risks_add' in tools
        assert 'risks_list' in tools
        assert 'assets_list' not in tools


@pytest.mark.coherence
class TestMCP:

    def setup_class(self):
        profile, account = selected_test_target()
        self.sdk = setup_chariot(profile, account)
        make_test_values(self)

    def test_mcp_default(self):
        mcp = MCPServer(self.sdk)
        assert 'search_by_term' in mcp.discovered_tools
        assert len(mcp.discovered_tools['search_by_term']['doc']) > 0
        assert 'assume_role' not in mcp.discovered_tools

    def test_mcp_configurable(self):
        mcp = MCPServer(self.sdk, ['risks_*'])
        assert 'search_by_term' not in mcp.discovered_tools
        assert 'risks_add' in mcp.discovered_tools
        assert len(mcp.discovered_tools['risks_add']['doc']) > 0
        assert 'assume_role' not in mcp.discovered_tools

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
