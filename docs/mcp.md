# Hosted MCP in Claude Code

Guard hosts an MCP server that lets [Claude Code](https://code.claude.com) read and change your
Guard data: assets, seeds, vulnerabilities, technologies, settings, files, members, exports, and
retests. It uses an existing Guard API key, so there is no separate login or OAuth app, and
nothing to install beyond this CLI.

```zsh
guard agent mcp headers --help
```

## Before you start

- **The hosted MCP preview must be enabled for your Guard account.** Ask your Praetorian contact.
  Until it is enabled, every MCP call returns `403 preview_disabled`.
- **Use a dedicated API key for each AI client.** Create one in Guard under **User Profile → API
  Keys → Add API Key**, and copy its ID and secret. The secret is shown only once. Start with a
  **Read Only** key, and only use a key with write access once you're comfortable with the
  setup. The MCP server can never do more than the key's role allows, or more than your own
  role in the account.
- **Use Claude Code 2.1.330 or later**, and a CLI release that includes `guard agent mcp headers`.

## Create a CLI profile for the key

```zsh
guard configure
```

When prompted:

| Prompt | Value |
|--------|-------|
| API Key ID / secret | The dedicated key you just created |
| Profile name | For example `MCP` |
| URL of backend API | Press `Enter` to keep the default |
| Assume-role account | Your Guard account username, for example `company@example.com`. Every MCP request runs in this account |

Check the profile:

```zsh
guard --profile MCP agent mcp headers > /dev/null && echo ok
```

## Add Guard to Claude Code

Replace `/Users/you/.local/bin/guard` with the full path of your installed `guard` command, as
printed by `which guard`, and use your own account:

```zsh
claude mcp add-json --scope user guard '{
  "type": "http",
  "url": "https://api.app.guard.praetorian.com/api/v1/mcp",
  "headersHelper": "/Users/you/.local/bin/guard --profile MCP --account company@example.com agent mcp headers"
}'
```

The full path matters because Claude Code may not run the helper with your shell's `PATH`, for
example when it starts from an IDE.

`--scope user` keeps the entry in your private Claude Code configuration, not in a shared project
file.

Claude Code runs the `headersHelper` command whenever it connects or reconnects, and again after an
authentication failure, so the one-hour token is renewed for you. The command prints a **sensitive
bearer token** for Claude Code. Don't run it with `--debug`, paste its output into a chat, or replace
it with a static `Authorization` header.

## Check the connection

```zsh
claude mcp get guard
```

Then start `claude`, run `/mcp`, and check that `guard` shows as connected with its tools. Try a
read, for example "list my pending seeds".

## Changes that need your confirmation

Reads and ordinary edits run immediately. Changes that the Guard UI asks you to confirm also need
confirmation here:

- Approving, rejecting, freezing, or deleting assets and seeds
- Changing a seed's tags
- Changing a vulnerability's status
- Disabling TypeSafe
- Removing scan or hunt profiles
- Acknowledging new host overrides

For these, Guard replies with a short summary that starts with "Please, confirm the following
action:", and Claude asks you before doing anything. If you say yes, Claude repeats the same request
with a single-use approval and the change runs once. If you say no, nothing changes.

An approval can't be reused, and it stops working if the request or the record changes in the
meantime.

## Revoking access

- **Removing the connector** (`claude mcp remove guard`) only removes your local configuration. The
  key keeps working.
- **Revoking the key** in Guard, under **User Profile → API Keys** or (for Admins) **Settings → Access
  Logs → Account API Keys**, cuts it off everywhere at once, including tokens already issued.
- **Revoking a key that several clients share** cuts off all of them. Give each client its own key.

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| `403 preview_disabled` | The MCP preview isn't enabled for this account |
| `401` | The key was revoked or expired, or the profile has the wrong secret |
| `403` on a specific tool | Your role, or the key's role, doesn't allow that operation |
| Data from the wrong account | Check the assume-role account in the profile, or the `--account` value in `headersHelper` |
| Helper times out | Claude Code allows the helper 10 seconds. If a change timed out, check its result in Guard before retrying |

## Supported clients

This setup is for Claude Code. Claude web, Claude Desktop custom connectors, and ChatGPT connectors
need OAuth sign-in, which Guard's MCP server doesn't use. It also uses the hosted customer-API tool
catalog, not the local `guard agent mcp start` server.
