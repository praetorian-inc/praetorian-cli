# Praetorian CLI and SDK

[![Python Version](https://img.shields.io/badge/Python-v3.8+-blue)](https://www.python.org/)
[![pip Version](https://img.shields.io/badge/pip-v23.0+-blue)](https://pypi.org/project/praetorian-cli/)
[![License](https://img.shields.io/badge/License-MIT-007EC6.svg)](LICENSE)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20covenant-2.1-007EC6.svg)](CODE_OF_CONDUCT.md)
[![Open Source Libraries](https://img.shields.io/badge/Open--source-%F0%9F%92%9A-28a745)](https://opensource.org/)
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg?style=flat)](https://github.com/praetorian-inc/chariot-ui/issues)

:link: [Chariot Platform](https://preview.chariot.praetorian.com)
:book: [Documentation](https://docs.praetorian.com)
:bookmark: [PyPI](https://pypi.org/project/praetorian-cli/)
:computer: [Chariot UI](https://github.com/praetorian-inc/chariot-ui)

# Table of Contents

- [Description](#description)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Signing up](#signing-up-and-configuration)
- [Using the CLI](#using-the-cli)
- [Using plugins](#using-plugins)
- [Developers](#developers)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

# Description

Praetorian CLI and SDK are open-source tools for interacting with our products and services. Currently, they support
access to [Chariot](https://www.praetorian.com/proactive-cybersecurity-technology/), our
offensive security platform.
<br> The SDK exposes the full set of APIs that the Chariot UI uses.
<br> The CLI is a fully-featured companion to the Chariot UI.

# Getting Started

## Prerequisites

- Python v3.8 or above
- pip v23.0 or above

## Installation

Install the Python package using this command:

```zsh
pip install praetorian-cli
```

## Signing up and configuration

1. Register for an account for [Chariot](http://preview.chariot.praetorian.com) using the instructions
   in [our documentation](https://docs.praetorian.com/hc/en-us/articles/25784233986587-Account-Setup-and-Initial-Seeding).
2. Run `praetorian configure` and follow the prompts.
3. It creates `~/.praetorian/keychain.ini`, which should read like this:

```
[United States]
name = chariot
client_id = 795dnnr45so7m17cppta0b295o
api = https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot
username = lara.lynch@acme.com
password = 8epu9bQ2kqb8qwd.GR
```

For more advanced configuration options, as well as SSO. See
[the documentation on configuration](https://github.com/praetorian-inc/praetorian-cli/blob/main/docs/configure.md).


# Using the CLI

The CLI is a command and option utility for access to the full suite of Chariot API. See documentation for commands
using the `help` option:

```zsh
praetorian chariot --help
```

As an example, run the following command to retrieve the list of all assets in your account:

```zsh
praetorian chariot list assets
```

To get detailed information about a specific asset, run:

```zsh
praetorian chariot get asset <ASSET_KEY>
```

To try one of our plugin scripts, run:

```zsh
praetorian chariot get asset <ASSET_KEY> --plugin list_assets
````

For more examples, visit [our documentation](https://docs.praetorian.com).

# Using plugins

The CLI has a plugin engine for implementing more complex workflows.

There are two types of plugins:

- **Scripts**: Invoked using the `--plugin` option, they perform additional processing on the data returned by the
  CLI command.
- **Commands**: Invoked using the `plugin <plugin_name>` command, they are standalone commands that extend
  The CLI with a relatively complex workflow.

## Invoking plugin scripts

As a hypothetical example, this command uses `my-process-domain.py` to further process the data from
`praetorian chariot get asset`:

```zsh
praetorian chariot get asset <ASSET_KEY> --plugin ~/code/my-process-domain.py
```

The CLI comes with some built-in scripts in
[this directory](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/plugins/scripts). They
are invoked by name:

```zsh
praetorian chariot get asset <ASSET_KEY> --plugin list_assets
```

## Invoking plugin commands

Plugin commands add end-to-end functions as commands grouped under `plugin`. To see a list
of them:

```zsh
praetorian chariot plugin --help
```

For example this command is used to ingest scan results from Nessus XML export files:

```zsh
praetorian chariot plugin nessus-xml
```

You can find the list of plugin commands that comes with the CLI in
[this directory](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/plugins/commands)


# Developers

Both CLI and SDK is open-source in this repository. The SDK is installed along with the `praetorian-cli`
package. You can extend Chariot by creating scripts and plugins using the SDK. 

## SDK

Integrate the SDK into your own Python application with the following steps:

1. Include the dependency ``praetorian-cli`` in your project.
2. Import the Chariot class ``from praetorian_cli.sdk.chariot import Chariot``.
3. Import the Keychain class ``from praetorian_cli.sdk.keychain import Keychain``.
4. Call any function of the Chariot class, which expose the full backend API. See example below:

```python
from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain

chariot = Chariot(Keychain())
chariot.add('asset', dict(name='example.com', dns='example.com', seed=True))
```

The best place to explore the SDK is the code of the CLI, especially
[the handlers of the CLI](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/handlers)

You can inspect the handler code to see how each CLI command is implemented with the SDK.


## Developing plugins

If you want to take advantage of the scaffolding of the CLI, you can write fully fledged function using
the plugin engine. For developing plugins, you can refer to
this [readme file](https://github.com/praetorian-inc/praetorian-cli/blob/main/docs/plugin-development.md).

If you have ideas on new plugin commands and scripts, contribute them!

## Contributing

We welcome contributions from the community, from plugins, to the core CLI and SDK. To contribute, fork this
repository and following the
[GitHub instructions](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project)
to create pull requests.

By contributing, you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Support

If you have any questions or need support, please open an issue
[here](https://github.com/praetorian-inc/chariot-ui/issues) or reach out via
[support@praetorian.com](mailto:support@praetorian.com).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
