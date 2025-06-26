# Praetorian CLI and SDK

[![Python Version](https://img.shields.io/badge/Python-v3.9+-blue)](https://www.python.org/)
[![pip Version](https://img.shields.io/badge/pip-v23.0+-blue)](https://pypi.org/project/praetorian-cli/)
[![License](https://img.shields.io/badge/License-MIT-007EC6.svg)](LICENSE)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20covenant-2.1-007EC6.svg)](CODE_OF_CONDUCT.md)
[![Open Source Libraries](https://img.shields.io/badge/Open--source-%F0%9F%92%9A-28a745)](https://opensource.org/)
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg?style=flat)](https://github.com/praetorian-inc/chariot-ui/issues)

:link: [Chariot Platform](https://chariot.praetorian.com)
:book: [Documentation](https://docs.praetorian.com)
:bookmark: [PyPI](https://pypi.org/project/praetorian-cli/)

# Table of Contents

- [Description](#description)
- [Getting started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Signing up](#signing-up-and-configuration)
- [Using the CLI](#using-the-cli)
- [Using scripts](#using-scripts)
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

- Python v3.9 or above
- pip v23.0 or above

## Installation

Install the Python package using this command:

```zsh
pip install praetorian-cli
```

## Signing up

Register for an account for [Chariot](http://chariot.praetorian.com) using the instructions
in [our documentation](https://docs.praetorian.com/hc/en-us/articles/38048335323547-Account-Creation-and-Attack-Surface-Setup).

## Authentication

Once you can properly access Chariot through the UI. You can obtain API credentials through the UI under
Settings -> User Settings -> API Keys. Be sure to careful copy the API credentials you created as
you will need to provide them to the CLI for interacting with Chariot. 

**Note**: SSO Organizations should provision access through API Keys as well.

### Using API Keys 

This is the authentication method for CLI. You can authenticate using either a keychain file or environment variables.

#### Using the keychain file

This method stores your API key in a keychain file.

1. Run `praetorian configure` and follow the prompts to set up authentication. 
Use the default values for `profile name`, `URL of backend API`, and `client ID`.
2. It creates `~/.praetorian/keychain.ini`, which should read like this:

```
[United States]
name = chariot
client_id = 795dnnr45so7m17cppta0b295o
api = https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot
api_key_id = your-api-key-id-here
api_key_secret = your-api-key-here
```

#### Using environment variables

This method uses in-memory environment variables to pass your API key to
the CLI. There is no need for a keychain file on disk. This enables you to choose
a credential storage method suitable for your use cases. To use this method, set the
following environment variable:

```zsh
export PRAETORIAN_CLI_API_KEY_ID=your-api-key-id-here
export PRAETORIAN_CLI_API_KEY_SECRET=your-api-key-here
```

For more advanced configuration options or managing access in SSO organizations see
[the documentation on configuration](https://github.com/praetorian-inc/praetorian-cli/blob/main/docs/configure.md).

# Using the CLI

The CLI is a command and option utility for accessing the full suite of Chariot's API. You can see the documentation for commands
using the `help` option:

```zsh
praetorian chariot --help
```

As an example, run the following command to retrieve the list of all assets in your account:

```zsh
praetorian --account chariot+example@praetorian.com chariot list assets
```

You can obtain the `account` argument by viewing the email of the first user on the Users page in your Chariot account, as shown below:

<img width="482" alt="image" src="https://github.com/user-attachments/assets/7c1024c9-7b74-46b1-87c5-af44671b1ec8" />

To get detailed information about a specific asset, run:

```zsh
praetorian --account chariot+example@praetorian.com chariot get asset <ASSET_KEY>
```

# Developers

Both CLI and SDK is open-source in this repository. The SDK is installed along with the `praetorian-cli`
package. You can extend Chariot by creating scripts using the SDK.

## SDK

Integrate the SDK into your own Python application with the following steps:

1. Include the dependency ``praetorian-cli`` in your project.
2. Import the Chariot class ``from praetorian_cli.sdk.chariot import Chariot``.
3. Import the Keychain class ``from praetorian_cli.sdk.keychain import Keychain``.
4. Call any function of the Chariot class, which expose the full backend API. See example below:

```python
from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain

chariot = Chariot(Keychain(account='chariot+example@praetorian.com'))
chariot.add('asset', dict(name='example.com', dns='example.com'))
```

The best place to explore the SDK is the code of the CLI, especially
[the handlers of the CLI](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/handlers)

You can inspect the handler code to see how each CLI command is implemented with the SDK.

## Developing external scripts

The CLI has a scripting engine that allow external scripts to be executed within the CLI's framework, taking
advantage of the SDK, `click`, and authentication.

To add those external scripts to the CLI, set the `PRAETORIAN_SCRIPTS_PATH`
environment to point to directories where you store additional extension scripts.

Those external scripts are available under the `script` commands. To see a list of them:

```zsh
praetorian --account chariot+example@praetorian.com chariot script --help
```

For developing scripts, you can refer to
this [readme file](https://github.com/praetorian-inc/praetorian-cli/blob/main/docs/script-development.md).


## Contributing

We welcome contributions from the community, from scripts, to the core CLI and SDK. To contribute, fork this
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
