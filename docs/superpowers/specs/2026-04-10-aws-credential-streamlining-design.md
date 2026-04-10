# AWS Credential Access Streamlining

## Problem

Accessing AWS accounts through Guard requires too many manual steps:

1. `guard list credentials` to find the AWS credential UUID
2. `guard get credential <uuid> --type aws --parameters accountId <id>` to get temp creds
3. Use those creds with `aws organizations list-accounts` to discover sub-accounts
4. Manually create `~/.aws/config` profiles for each account
5. Write a wrapper shell script (`get-creds.sh`) to bridge the CLI's output format to what AWS `credential_process` expects

This design eliminates steps 3-5 and makes step 2 directly usable as a `credential_process`.

## Solution

Two changes to the existing CLI:

### Part 1: `credential-process` format on `get credential`

Add `credential-process` as a new format option for the existing `guard get credential` command. When used, it outputs the JSON format that AWS CLI's `credential_process` expects:

```json
{
  "Version": 1,
  "AccessKeyId": "ASIA...",
  "SecretAccessKey": "...",
  "SessionToken": "...",
  "Expiration": "2026-04-10T12:00:00Z"
}
```

This replaces the wrapper script. The `credential_process` line in `~/.aws/config` becomes:

```ini
credential_process = guard --account chariot+client@praetorian.com get credential <uuid> --type aws --format credential-process --parameters accountId 900867815158
```

### Part 2: `configure credential` command

A new `configure credential` subcommand that automates AWS config generation:

```bash
guard configure credential --account chariot+client@praetorian.com
```

#### Flow

1. Assume role into the provided `--account`
2. List credentials, filter to `type=aws`
3. For each AWS credential:
   a. Fetch temp creds via `get credential`
   b. Create a boto3 Organizations client with those creds
   c. Call `list_accounts()` to discover sub-accounts
   d. If Organizations call succeeds: generate profiles for the root account + each sub-account
   e. If Organizations call fails (not an org): generate a single profile for the root account
4. Append/update profiles in `~/.aws/config`, preserving existing unrelated profiles

#### Profile Naming

The default prefix is derived from the Guard account email: the portion after `+` and before `@`.

- `chariot+proceptbiorobotics@praetorian.com` -> prefix: `proceptbiorobotics`
- `chariot+grant_street_group-ztw@praetorian.com` -> prefix: `grant_street_group-ztw`

Profile names follow the format `{prefix}-{account_id}`:

- `[profile proceptbiorobotics-900867815158]`
- `[profile proceptbiorobotics-123456789012]`

A `--prefix` CLI option overrides the auto-derived prefix.

#### Generated Profile Format

```ini
[profile proceptbiorobotics-900867815158]
credential_process = guard --account chariot+proceptbiorobotics@praetorian.com get credential <uuid> --type aws --format credential-process --parameters accountId 900867815158
region = us-east-1
output = json
```

For the root account (no sub-account context needed):

```ini
[profile proceptbiorobotics-ROOT_ACCOUNT_ID]
credential_process = guard --account chariot+proceptbiorobotics@praetorian.com get credential <uuid> --type aws --format credential-process
region = us-east-1
output = json
```

Note: The root profile omits the `accountId` parameter since credentials are for the root directly. Sub-account profiles include `--parameters accountId <id>` to request credentials scoped to that account.

#### AWS Config File Handling

- Reads existing `~/.aws/config` if present
- Parses all existing profiles
- Adds or updates profiles matching the `{prefix}-*` pattern
- Leaves all other profiles untouched
- Writes the merged result back
- Creates `~/.aws/` directory and config file if they don't exist

## CLI Interface

### `get credential` (modified)

```
guard get credential <credential_id> --type aws --format credential-process [--parameters accountId <id>]
```

- New `credential-process` format value alongside existing `token`, `file`, `env`
- Outputs raw JSON to stdout (no pretty-printing, no extra output) so AWS CLI can parse it

### `configure credential` (new)

```
guard configure credential --account <email> [--prefix <prefix>]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--account` | Yes | - | Guard account email to discover AWS credentials for |
| `--prefix` | No | Derived from email | Override the profile name prefix |

## Files Changed

| File | Change |
|------|--------|
| `praetorian_cli/sdk/entities/credentials.py` | Add `credential-process` handling in `_process_credential_output()` |
| `praetorian_cli/handlers/get.py` | No changes needed (format is passed through) |
| `praetorian_cli/handlers/configure.py` | Add `credential` subcommand to the configure group |
| `praetorian_cli/main.py` | Wire up configure as a group with subcommands |

## Dependencies

- `boto3` — already a dependency (used in `keychain.py` for Cognito). Used here to call Organizations `list_accounts()`.
- `configparser` — stdlib. Used to read/write `~/.aws/config`.

## Edge Cases

- **No AWS credentials found**: Print a message and exit cleanly
- **Multiple AWS credentials**: Process all of them, generating profiles for each
- **Organizations access denied**: Not an error — generate a single root profile and continue
- **Existing profiles with same names**: Overwrite them (they were generated by this tool)
- **No `~/.aws/` directory**: Create it
- **Email without `+` segment**: Use the full local part (before `@`) as prefix
