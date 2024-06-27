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
command line and developer access to [Chariot](https://www.praetorian.com/proactive-cybersecurity-technology/), our
offensive security platform. The SDK exposes the full set of API that the Chariot UI uses. The CLI is a fully-featured
companion to the Chariot UI.

# Getting Started

## Prerequisites

- Python v3.8 or above
- `pip` v23.0 or above

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

The CLI is a command and option utility for access to the full suite of Chariot API. Get quick help
with the `help` command:

```zsh
praetorian chariot --help
```

As an example, run the following command to retrieve the list of all seeds in your account:

```zsh
praetorian chariot list seeds
```

To get detailed information about a specific seed, run:

```zsh
praetorian chariot get seed <SEED_KEY>
```

To try one of our plugin scripts, run:

```zsh
praetorian chariot get seed <SEED_KEY> --plugin list_assets
````

For more examples, visit [our documentation](https://docs.praetorian.com).


## Using plugins

The CLI has a plugin engine for extending the functionality of it without having to change the core internals. In
the section here, we illustrate how to use those. For developing plugins, see the
[readme file](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/plugins/README.md) in the
plugins directory.

There are two types of plugins:
- **Scripts**: a script that carries out additional processing of the output of an existing CLI
  command. An example is a script that invokes TruffleHog to further validate the secrets in exposure risks.
- **Commands**: a command that executes an end-to-end function. An example is a command that
  run a Nessus scan and inject the scan results into Chariot.


### Using a plugin script
A plugin script is invoked by the `--plugin` option, for example: 

```zsh
praetorian chariot get seed <SEED_KEY> --plugin ~/code/my-process-seed.py
```

The CLI ships with built-in scripts in
[this directory](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/plugins/scripts).
For those, you only need to specify the name:

```zsh
praetorian chariot get seed <SEED_KEY> --plugin list_assets
```

### Using a plugin command
Plugin commands add end-to-end function to the CLI as commands grouped under `plugin`. See a listing
of all the plugin commands by running:

```zsh
praetorian chariot plugin --help
```

Different Praetorian teams extend the CLI using plugin commands. Here is an example to streamline our team
in the creation of client reports:

```zsh
praetorian chariot plugin report
```
You can find the list of plugin commands that comes with the CLI in
[this directory](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/plugins/commands) 

If you have ideas on new plugin commands and scripts, contribute them!

Read more about developing scripts and commands in
[this readme file](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/plugins/README.md).


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
chariot.add('seed', dict(name='example.com', dns='example.com'))
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
