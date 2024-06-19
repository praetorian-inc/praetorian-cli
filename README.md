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
praetorian chariot get assets --script hello-world
````

See the [Contributing](#contributing) section for more information on how to add your own plugin scripts.

For more examples, visit [our documentation](https://docs.praetorian.com).

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
chariot.add('seed', dict(dns='example.com', status='AS'))
```

You can see example usages of the SDK
in [the handlers of the CLI](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/handlers)

For more examples and API documentation, visit [our documentation](https://docs.praetorian.com).

## Extending the CLI with script plugins

The CLI has a plugin engine for you to extend the CLI without changing its internals. Your script
is imported to the CLI context so it has full and authenticated access to the SDK.

To run a script, add the `--script` option after the CLI command, for example:

```zsh
$ praetorian chariot list seeds --script ~/code/my-process-seeds.py
```

For built in [scripts](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/scripts) you only need the script name:

```zsh
$ praetorian chariot get seed 'SEED_KEY' --script list-assets
```

To work with the plugin engine, the script needs to implement a `process` function that takes 4 arguments:
   - `controller`: This object holds the authentication context and provide functions for accessing the
      Chariot backend API
   - `cmd`: This dictionary holds the information of which CLI command is executed. It tells you the product,
     action, and type of the CLI command. For example, you can use this to find out whether it is a `list` command
     on `assets`.
   - `cli_kwargs`: This dictionary contains the additional options the user provided to the CLI, such
     as `--details`, `--term`, `--page`, `ASSET_KEY`, etc.
   - `output`: This is the raw output of the CLI.

Try out the [`hello-world`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/scripts/hello-world.py)
script to have a concrete look at the content of those arguments, using the following command:

 ```zsh
praetorian chariot list seeds --details --script hello-world
```

A typical script uses the arguments in the following manners:
- Check for input correctness using information in `cmd` and `cli_kwargs`.
- Parse the CLI `output` to extract relevant data.
- Use the authenticated session in `controller` to further issue API calls to operate
  on the data.

See this in action in the 
[`list-assets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/scripts/list-assets.py) and 
[`validate-secrets.py`](https://github.com/praetorian-inc/praetorian-cli/blob/main/praetorian_cli/scripts/validate-secrets.py)
scripts.

If you think your script will be useful for the offensive security community, contribute it!

## Contributing

We welcome contributions from the community, from plugin scripts, to the core CLI and SDK. To contribute, fork this
repository and following the
[GitHub instructions](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project)
to create pull requests.

By contributing, you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Support

If you have any questions or need support, please open an issue or reach out via
[support@praetorian.com](mailto:support@praetorian.com).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
