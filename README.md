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
    - [Signing up](#signing-up)
- [Using the CLI](#using-the-cli)
- [Developer SDK](#developer-sdk)
- [Extending the CLI with script plugins](#extending-the-cli-with-script-plugins)
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

## Signing up

1. Register for an account for [Chariot](http://preview.chariot.praetorian.com) using the instructions
   in [our documentation](https://docs.praetorian.com/hc/en-us/articles/25784233986587-Account-Setup-and-Initial-Seeding).
2. Download the keychain file using [this link](https://preview.chariot.praetorian.com/keychain.ini).
3. Place the keychain file at ``~/.praetorian/keychain.ini``.
4. Add your username and password to the keychain file. Your file should read like this:

```
[United States]
name = chariot
client_id = 795dnnr45so7m17cppta0b295o
api = https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot
username = lara.lynch@acme.com
password = 8epu9bQ2kqb8qwd.GR
```

## Using the CLI

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

## Using plugins

The CLI has a plugin engine for implementing more complex workflows.

There are two types of plugins:

- **Scripts**: Invoked using the `--plugin` option, they perform additional processing on the data returned by the
  CLI command.
- **Commands**: Invoked using the `plugin <plugin_name>` command, they are standalone commands that extend the CLI with
  a relatively
  complex workflow.

### Examples of plugin scripts

For example, this command uses `my-process-domain.py` to further process the data from `praetorian chariot get asset`:

```zsh
praetorian chariot get asset <ASSET_KEY> --plugin ~/code/my-process-domain.py
```

The CLI also comes with some built-in scripts in
[this directory](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/plugins/scripts). They
are invoked by name:

```zsh
praetorian chariot get asset <ASSET_KEY> --plugin list_assets
```

### Examples of plugin commands

Plugin commands add end-to-end functions as commands grouped under `plugin`. To see a list
of them:

```zsh
praetorian chariot plugin --help
```

Different Praetorian teams extend the CLI using plugin commands. For example this command is used by our team
in the creation of client reports using internal templates:

```zsh
praetorian chariot plugin report
```

You can find the list of plugin commands that comes with the CLI in
[this directory](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/plugins/commands)

If you have ideas on new plugin commands and scripts, contribute them!

For developing plugins, you can refer to
this [readme file](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plugins/README.md).

## Developer SDK

The Praetorian SDK is installed along with the `praetorian-cli` package. Integrate the SDK into your
own Python application with the following steps:

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

The best place to explore the SDK is
[the handlers of the CLI](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/handlers)

## Contributing

We welcome contributions from the community, from plugins, to the core CLI and SDK. To contribute, fork this
repository and following the
[GitHub instructions](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project)
to create pull requests.

By contributing, you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Support

If you have any questions or need support, please open an issue or reach out via
[support@praetorian.com](mailto:support@praetorian.com).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
