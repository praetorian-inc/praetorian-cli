# This file largely mirror the model definitions in the model package in chariot-client.

def asset_key(dns, name):
    return f'#asset#{dns}#{name}'


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
