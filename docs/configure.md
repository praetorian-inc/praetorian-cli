# How to configure the keychain file

This page illustrates the advanced functions of the `configure` command. It is used to set
user credentials and update the keychain file located at `~/.praetorian/keychain.ini`.

## Authentication Methods

The CLI supports two authentication methods:

### API Key Authentication

API key authentication provides secure, token-based access without exposing your password. To use API keys:

1. **Generate an API Key in the Chariot UI:**
   - Navigate to Settings > User Setings > API Keys
   - Click "Add New Token"
   - Provide a descriptive name for your key
   - Copy both the API Key ID and API Key Secret (the secret is only shown once)

2. **Configure the CLI:**

```
$ praetorian configure
Enter your API Key ID: your-api-key-id-here
Enter your API Key secret: [hidden]
Enter the profile name to configure [United States]:
Enter the URL of backend API [https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot]:
Enter the client ID [795dnnr45so7m17cppta0b295o]:
Enter the assume-role account, if any []:
```

### Email/Password Authentication (Praetorian Users only)

Traditional username/password authentication:

```
$ praetorian configure --email
Enter your email: your-email@example.com
Enter your password: [hidden]
Enter the profile name to configure [United States]:
Enter the URL of backend API [https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot]:
Enter the client ID [795dnnr45so7m17cppta0b295o]:
Enter the assume-role account, if any []:
```

## Configuration Options

The configuration fields have the following meanings:

- **API Key ID**: The identifier for your API key (when using API key authentication)
- **API Key Secret**: The secret value for your API key (when using API key authentication)
- **Email**: Your email address (when using email/password authentication)
- **Password**: Your password (when using email/password authentication)
- **Profile name**: The name of a profile section in the keychain file. It is
  useful when you have multiple accounts, or different assume-role settings (see below).
- **URL of backend API**: The URL of the backend. In most cases, use the default value.
- **Client ID**: The client ID of the backend. In most cases, use the default value.
- **Assume-role account**: This is used for assuming role into your organization's main
  account. This is the same as the `--account` option.

## Environment Variables

As an alternative to storing credentials in the keychain file, you can use environment variables:

### For API Key Authentication:
```bash
export PRAETORIAN_CLI_API_KEY_ID=your-api-key-id-here
export PRAETORIAN_CLI_API_KEY_SECRET=your-api-key-secret-here
```

### For Email/Password Authentication:
```bash
export PRAETORIAN_CLI_USERNAME=your-email@example.com
export PRAETORIAN_CLI_PASSWORD=your-password
```

Environment variables take precedence over keychain file settings.

## Multiple profiles

Similar to the pattern used in AWS CLI configuration files, the keychain file is
organized into sections of _profiles_ (names in square brackets). You can use this to configure
multiple access credentials into a single keychain file.

The `configure` command operates in an "upsert" manner with the profiles, including the
default "United States" profile. So, when you run `configure` and provide an
existing profile name, it will update the fields in that profile. When you provide
a new profile name, it will add a new section for the profile, without affecting other
profiles.

