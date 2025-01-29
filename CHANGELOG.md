# Changelog

## 1.6.0 (2025-01-29)

* [Breaking change] Asset statuses are changed to A, D, P, F. Scan level is
  now set globally for all assets in the Settings page in the Web UI.
* [New feature] Added support for listing statistics on risks, assets, jobs, and more.
* [New feature] Added support for seed approval.
* [New feature] Added support for pre-seed approval.
* [New feature] Added support for pulling detailed information on CVEs.

## 1.5.9 (2024-12-30)

* [New feature] Added support for the discovery-only scan level for attributes.

## 1.5.8 (2024-12-27)

* [New feature] Added support for the discovery-only scan level for seeds.

## 1.5.7 (2024-12-24)

* [New feature] Added support for updating attributes.

## 1.5.6 (2024-12-23)

* [New feature] Added operations for adding, updating, deleting, and retrieving seeds.
* [New feature] Added support for provide username and password using environment
  variables -- `PRAETORIAN_CLI_USERNAME`, `PRAETORIAN_CLI_PASSWORD`.

## 1.5.5 (2024-12-13)

* [New feature] Added version check. The CLI now prompts the user to upgrade if a newer
  version is available on PyPI.
* [Bug fix] Pagination when searching for `#seed` is fixed.

## 1.5.4 (2024-11-22)

* [New feature] Add the option to specify the capabilities to run when adding scan
  jobs for assets.

## 1.5.3 (2024-11-14)

* [Bug] Fixed an error with the `list` and `search` commands.
* [Misc] Additional status of 'P', 'PL' have been added for assets.

## 1.5.2 (2024-10-25)

* [Breaking change] The `D` status for risks is expanded to `DE`, DI`, `DL`, `DM`,
  `DH`, and `DC` for the severity levels of exposure, info, low, medium, high, and
  critical. `D` is no longer a valid status for risks
* [Misc] Improved in-app documentation, where the `--help` text includes
  more example usages.

## 1.5.1 (2024-10-15)

* [Bug fix] Fixed errors in functions related to principals in
  the Accounts class

## 1.5.0 (2024-10-15)

* [Breaking change] `username`, `password`, `client_id` instance
  attributes of the `Keychain` class are now accessed by functions
  of the same names, ie, `username()`, `password()`, and `client_id()`
* [Breaking change] `api` instance attribute of the `Keychain`
  class is now accessed by the `base_url()` function
* [Breaking change] 'T', 'I', 'R', and 'O' are no longer valid
  statuses for risks

