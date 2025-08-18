# This file largely mirror the model definitions in the model package in chariot-client.

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

def seed_asset_key(dns):
    return f'#asset#{dns}#{dns}'

def preseed_key(type, title, value):
    return f'#preseed#{type}#{title}#{value}'

def setting_key(name):
    return f'#setting#{name}'

def configuration_key(name):
    return f'#configuration#{name}'
