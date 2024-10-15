# Changelog

## 1.5.0 (2024-10-15)

* [Breaking change] `username`, `password`, `client_id` instance
  attributes of the `Keychain` class are now accessed by functions
  of the same names, ie, `username()`, `password()`, and `client_id()`
* [Breaking change] `api` instance attribute of the `Keychain`
  class is now accessed by the `base_url()` function
* [Breaking change] 'T', 'I', 'R', and 'O' are no longer valid
  statuses for risks

## 1.4.6 (2024-10-04)

* [New Feature] Added high level user account functions in the SDK
* [New Feature] Added data import for Nessus, Qualys, and Rapid7
* [Misc] Improvements made to the debug mode

## 1.4.5 (2024-09-25)

* [Misc] Added Exposure severity for risks
* [Misc] Added Ignored state for risks
* [Misc] 'add job' command no longer need the capability supplied

## 1.4.4 (2024-09-20)

* [Misc] Removed machine statuses
* [Misc] 'add job' command no longer need the capability supplied

## 1.4.3 (2024-09-16)

* [Misc] Added material risk statuses

## 1.4.2 (2024-09-09)

* [Bug Fix] Fixed the display of the next offset

## 1.4.1 (2024-09-09)

* [Bug Fix] Fixed Search.by_exact_key()
* [Misc] Fixed tests

## 1.4.0 (2024-09-08)

* [Misc] Updated entity creation API calls to use PUT instead of POST, aligning
  with a backend API change.

## 1.3.9 (2024-09-03)

* [Misc] Updated the API call for asset creation to align with a backend API change.

## 1.3.8 (2024-08-28)

* [Misc] Risk statuses updated with AI-based actions. See
  [the updated documentation](https://github.com/praetorian-inc/praetorian-cli/blob/main/docs/terminology.md) for
  details.

## 1.3.7 (2024-08-23)

* [Misc] Nessus scripts updated to upload proofs of exploits to new file location
* [Misc] Webhook commands adjusted for the storage of the PIN
* [Misc] Regression tests updated

## 1.3.6 (2024-08-12)

* [New Feature] Added support in sdk to download files as a stream

## 1.3.5 (2024-08-05)

* [Breaking Change] Renamed `plugin` to `script`

## 1.3.4 (2024-08-02)

* [New Feature] Added debug mode for plugin development
* [New Feature] Added out-of-scope and false-positive as reasons for closing a risk
* [New Feature] Added support for setting user_pool_id in the `configure` command
* [Breaking Change] Removed the support for plugin scripts

## 1.3.3 (2024-07-30)

* [Bug fix] Fixed asset delete command.
* [New feature] Options to mark a risk as closed by automation using new `Machine...` states

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

