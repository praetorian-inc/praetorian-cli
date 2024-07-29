# Changelog

## 1.3.2 (2024-07-29)

* [Bug fix] Fixed the `--plugin` command option for a number of `list` and `get` commands.
* [New Feature] Added CLI-level regression testing

## 1.3.0 (2024-07-24)

* [New Feature] `configure` command was added to handle the authentication setup. This removes the need for manually
  download and editing the `keychain.ini` file.
* [New Feature] The `delete asset` command was update to soft-delete the asset.
* [New Feature] Risks added by the Nessus plugin commands now have source set to 'nessus'.

## 1.2.3 (2024-07-22)

* [Bug fix] Fixed a dependency issue on Windows system. This is done by removing the `report` plugin command.

## 1.2.2 (2024-07-19)

* [Breaking Change] Removed support for linking integrations using CLI
* [New Feature] Filter assets by attributes using `list assets -attr <Attribute_Name> <Attribute_Value>`
* [New Feature] Allow users to filter attributes by a specific asset or risk key. `list attributes -a <ASSET_KEY>`
* [Bug fix] Add attribute command to use key-value input
* [Bug fix] Updates in list_asset plugin to match the latest attribute modifications.
* [Doc Updates] For various statuses allowed for assets and risks

## 1.2.1 (2024-07-15)

- [Breaking Change] Removed the concept of class for assets, risks, and attributes.
- [Breaking Change] Comments are removed from assets. The `--comment` option is removed
  from the `add asset` and `update asset` commands.
- [New Feature] The risk definition is now included in the `get risk --details` command.
- [New Feature] Performance improvement with session-based authentication.
- [New Feature] Nessus XML plugin now limits concurrency to lower the rate it calls
  the backend API.
- [New Feature] File upload file size limit is increased to 100MB, from 6MB.
- [Bug Fix] Fix the `add job` command.
- [Bug Fix] Handle plain text proof of exploit content.

## 1.2.0 (2024-07-03)

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

- Initial open-source release.

