# This file largely mirror the model definitions in the model package in backend.

def asset_key(dns, name):
    return "#asset#%s#%s" % (dns, name)
