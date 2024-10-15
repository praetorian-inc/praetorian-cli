# How to configure the keychain file

This page illustrates the advanced functions of the `configure` command. It is used to set
user credentials and update the keychain file located at `~/.praetorian/keychain.ini`.
The `configure` command asks questions as follows:

```
$ praetorian configure
Enter your Praetorian credentials to store in the keychain
Enter your email:
Enter your password:
Enter the profile name [United States]:
Enter the URL of backend API [https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot]:
Enter the client ID [795dnnr45so7m17cppta0b295o]:
Enter the assume-role account, if any []:
```

They have the following meanings:

- **Email**: this is the email address you used to sign up.
- **Password**: Your password.
- **Profile name**: The name of a profile section in the keychain file. It is
  useful when you have multiple accounts, or different assume-role settings (see below).
- **URL of backend API**: The URL of the backend. In most cases, use the default value.
- **Client ID**: The client ID of the backend. In most cases, use the default value.
- **Assume-role account**: This is used for assuming role into your organization's main
  account. This is the same as the `--account` option.

## Multiple profiles

Similar to the pattern used in AWS CLI configuration files, the keychain file is
organized into sections of _profiles_ (names in square brackets). You can use this to configure
multiple access credentials into a single keychain file.

The `configure` command operates in an "upsert" manner with the profiles, including the
default "United States" profile. So, when you run `configure` and provide an
existing profile name, it will update the fields in that profile. When you provide
a new profile name, it will add a new section for the profile, without affecting other
profiles.

## Authentication in organizations that use SSO

SSO-enabled accounts can use CLI by inviting password-based accounts as collaborators.
These collaborator accounts can assume into the main account using the `--account` option
in the CLI with the value of the email address of the main account.

You can also set this in a profile in the keychain file. Run `praetorian configure` and
answer the prompt `Enter assume-role account` with the email address of the main account.

Your keychain file will then read like this:

```
[United States]
name = chariot
client_id = 795dnnr45so7m17cppta0b295o
api = https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot
username = lara.lynch@acme.com
password = 8epu9bQ2kqb8qwd.GR
account = security.team@acme.com
```

There are two common approaches to manage CLI access in SSO organizations:

1. Sign up a service account for CLI access, e.g. security.team+cli@acme.com. In the master
   account, invite security-team+cli@acme.com as a collaborator. All CLI users share the
   keychain for the service account.
3. Add each CLI user as a collaborator in the master account. Every CLI user signs up using
   password-based authentication.

We recommend the first approach.
