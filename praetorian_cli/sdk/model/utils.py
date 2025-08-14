# This file largely mirror the model definitions in the model package in chariot-client.

import click    


def asset_key(dns, name):
    return f'#asset#{dns}#{name}'

def ad_domain_key(dns, name):
    return f'#addomain#{dns}#{name}'

def repository_key(dns, name):
    return f'#repository#{dns}#{name}'

def integration_key(dns, name):
    return f'#integration#{dns}#{name}'

def risk_key(dns, name):
    return f'#risk#{dns}#{name}'


def attribute_key(name, value, source_key):
    return f'#attribute#{name}#{value}{source_key}'


def seed_key(type, dns):
    return f'#seed#{type}#{dns}'


def preseed_key(type, title, value):
    return f'#preseed#{type}#{title}#{value}'

def setting_key(name):
    return f'#setting#{name}'

def configuration_key(name):
    return f'#configuration#{name}'

def seed_status(type, status_code):
    return f'{type}#{status_code}'


def get_dict_from_entries(entry):
    config_dict = {}
    for item in entry:
        if '=' not in item:
            click.echo(f"Error: Entry '{item}' is not in the format key=value")
            return

        if item.count('=') > 1:
            click.echo(f"Error: Entry '{item}' contains multiple '=' characters. Format should be key=value")
            return

        key, value = item.split('=', 1)

        if not key:
            click.echo("Error: Key cannot be empty")
            return

        if not value:
            click.echo("Error: Value cannot be empty")
            return

        config_dict[key] = value