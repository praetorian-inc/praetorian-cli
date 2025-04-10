# Changelog

## 2.0.7

- [New Feature] Preseeds can now be added or updated
  - See `chariot add preseed` and `chariot update preseed`
- [New Feature] Additional Query operators, fields, and length has been added
- [Bug fix] Removed CLI enforcement of allowed `capability` on `chariot add job`
  - An error will be thrown from Chariot if a capability does not exist

## 2.0.6

- [Bug fix] Fixed the offset calculation for automatic backoffs on large queries.

## 2.0.5

- [New feature] Ability to set a manual surface on an asset and manual capability on a risk. 

## 2.0.4

- [New feature] Optimized page size for graph queries with automatic backoff for large queries.

## 2.0.3

- [Bug fix] Lowered the page size for graph queries.

## 2.0.2

- [New feature] The Chariot.my() function now optimizes the search query when feasible.

## 2.0.1

- [Internal update] The backend API now expects `affiliation` as the agent name
  for asset affiliation. We have updated the CLI to match that.

## 2.0.0

- [Breaking change] The API layer has changed to work with the new my API.
  - See the changes in Chariot.my()
- [Breaking change] There are two changes in the CLI command layer:
  - When searching using terms prefixed by `status:`, `source:`, `name:`,
    and `dns:`, you will now need to provide the `--kind` argument
    to indicate the kind of records you want. Available kinds are:
    `asset`, `risk`, `attribute`, `seed`, `preseed`, and `others`.
  - Searching by the `ip:` prefix is removed.

## 1.6.5

- [New feature] Added ability to add asset with chosen status.

## 1.6.4

- [Breaking change] The `delete` function in the `Chariot` class was renamed to `delete_by_key`.
  The `delete` function is a new one that takes the more general `body` and `query` arguments.
- [New feature] The `chariot delete file` command was added.

## 1.6.3

- [Breaking change] The `agent attribution` command is renamed to `agent affiliation` command.
  - See `praetorian chariot agent affiliation --help` for new invocation syntax.
- [New feature] Added asset as an available type for the `affiliation` command.

## 1.6.2

- [New feature] keychain.ini file is now optional. Users can pass login credentials via
  in-memory environment variables.
- [Bug fix] Process AI attribution results as plain text

## 1.6.1

- [New feature] Added support for risk attribution.
- [Breaking change] Risks.delete() now takes an additional status parameter.
- [Breaking change] Risk statuses were updated. See globals.py for new values.
- [Breaking change] The file download API was updated to be easier to use:
  - Chariot.download() now returns the bytes of the file. It does not save the file.
  - Files.get() now returns the bytes of the file. It does not save the file.
  - Files.save() saves the content of Files.get() in a file.
  - Change usages of Files.get() to Files.save()
  - Change usages of Chariot.download() to Files.save()

## 1.6.0 (2025-01-29)

- [Breaking change] Asset statuses are changed to A, D, P, F. Scan level is
  now set globally for all assets in the Settings page in the Web UI.
- [New feature] Added support for listing statistics on risks, assets, jobs, and more.
- [New feature] Added support for seed approval.
- [New feature] Added support for pre-seed approval.
- [New feature] Added support for pulling detailed information on CVEs.

## 1.5.9 (2024-12-30)

- [New feature] Added support for the discovery-only scan level for attributes.

## 1.5.8 (2024-12-27)

- [New feature] Added support for the discovery-only scan level for seeds.

## 1.5.7 (2024-12-24)

- [New feature] Added support for updating attributes.

## 1.5.6 (2024-12-23)

- [New feature] Added operations for adding, updating, deleting, and retrieving seeds.
- [New feature] Added support for provide username and password using environment
  variables -- `PRAETORIAN_CLI_USERNAME`, `PRAETORIAN_CLI_PASSWORD`.

## 1.5.5 (2024-12-13)

- [New feature] Added version check. The CLI now prompts the user to upgrade if a newer
  version is available on PyPI.
- [Bug fix] Pagination when searching for `#seed` is fixed.

## 1.5.4 (2024-11-22)

- [New feature] Add the option to specify the capabilities to run when adding scan
  jobs for assets.

## 1.5.3 (2024-11-14)

- [Bug] Fixed an error with the `list` and `search` commands.
- [Misc] Additional status of 'P', 'PL' have been added for assets.

## 1.5.2 (2024-10-25)

- [Breaking change] The `D` status for risks is expanded to `DE`, DI`, `DL`, `DM`,
`DH`, and `DC`for the severity levels of exposure, info, low, medium, high, and
critical.`D` is no longer a valid status for risks
- [Misc] Improved in-app documentation, where the `--help` text includes
  more example usages.

## 1.5.1 (2024-10-15)

- [Bug fix] Fixed errors in functions related to principals in
  the Accounts class

## 1.5.0 (2024-10-15)

- [Breaking change] `username`, `password`, `client_id` instance
  attributes of the `Keychain` class are now accessed by functions
  of the same names, ie, `username()`, `password()`, and `client_id()`
- [Breaking change] `api` instance attribute of the `Keychain`
  class is now accessed by the `base_url()` function
- [Breaking change] 'T', 'I', 'R', and 'O' are no longer valid
  statuses for risks
