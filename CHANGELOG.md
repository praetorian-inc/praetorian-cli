# Changelog

## 1.1.3 (2024-07-03)

- [Breaking Change] Allow `list attributes` command to filter by risk/asset key only
- [Bug Fix] Limit the number of options available to `add risk` command
- [Breaking Change] Remove `seeds` and `references` related commands from the CLI
- [New Feature] Add Nessus integration in plugins
- [Bug Fix] Remove the update job command from the CLI

## 1.1.2 (2024-06-27)

- [New Feature] Renamed `--scripts` to `--plugin` flag to run scripts as plugins.
- [New Feature] Added `plugin` command to run extended functionalities as CLI commands.
- [Bug Fix] Add class tags for manual uploads and risk definitions
- [New Plugin] Added `report` plugin to generate client reports using internal templates.

## 1.0.4

- [New Feature] Added GitLab integration

## 1.0.3

- [Bug Fix] Fixed `chariot test` command
- [New Feature] Added Azure org-level integration
- [New Feature] Now run scripts from any directory as plugins with --script flag

## 1.0.2

- [Bug Fix] Delete command was not making correct API calls.
- [Bug Fix] Update command was unable to handle <KEY> argument and was throwing an error.
- [Doc Update] For add command, clearer instructions are added for the `--key` argument.

## 1.0.1

- Updated the `link` actions for a corresponding update in the backend API.

## 1.0.0

Initial open-source release.

