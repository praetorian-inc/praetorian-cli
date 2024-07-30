import json
from enum import Enum

import click


class Asset(Enum):
    ACTIVE = "A"
    ACTIVE_HIGH = "AH"
    ACTIVE_LOW = "AL"
    FROZEN = "F"
    DELETED = "D"


class Risk(Enum):
    TRIAGE_INFO = "TI"
    TRIAGE_LOW = "TL"
    TRIAGE_MEDIUM = "TM"
    TRIAGE_HIGH = "TH"
    TRIAGE_CRITICAL = "TC"
    OPEN_INFO = "OI"
    OPEN_LOW = "OL"
    OPEN_MEDIUM = "OM"
    OPEN_HIGH = "OH"
    OPEN_CRITICAL = "OC"
    CLOSED_INFO = "CI"
    CLOSED_LOW = "CL"
    CLOSED_MEDIUM = "CM"
    CLOSED_HIGH = "CH"
    CLOSED_CRITICAL = "CC"
    CLOSED_INFO_ACCEPTED = "CIA"
    CLOSED_LOW_ACCEPTED = "CLA"
    CLOSED_MEDIUM_ACCEPTED = "CMA"
    CLOSED_HIGH_ACCEPTED = "CHA"
    CLOSED_CRITICAL_ACCEPTED = "CCA"
    CLOSED_INFO_REJECTED = "CIR"
    CLOSED_LOW_REJECTED = "CLR"
    CLOSED_MEDIUM_REJECTED = "CMR"
    CLOSED_HIGH_REJECTED = "CHR"
    CLOSED_CRITICAL_REJECTED = "CCR"
    CLOSED_MACHINE = "M"
    CLOSED_MACHINE_INFO = "MI"
    CLOSED_MACHINE_LOW = "ML"
    CLOSED_MACHINE_MEDIUM = "MM"
    CLOSED_MACHINE_HIGH = "MH"
    CLOSED_MACHINE_CRITICAL = "MC"


class AddRisk(Enum):
    """ AddRisk is a subset of Risk. These are the only valid statuses when creating manual risks """
    TRIAGE_INFO = "TI"
    TRIAGE_LOW = "TL"
    TRIAGE_MEDIUM = "TM"
    TRIAGE_HIGH = "TH"
    TRIAGE_CRITICAL = "TC"


Status = {'asset': Asset, 'risk': Risk, 'add-risk': AddRisk}

key_set = {'assets': '#asset#', 'jobs': '#job#', 'risks': '#risk#', 'accounts': '#account#',
           'definitions': '#file#definitions/', 'integrations': '#account#', 'attributes': '#attribute#',
           'files': '#file#'}

AssetPriorities = {'comprehensive': Asset.ACTIVE_HIGH.value, 'standard': Asset.ACTIVE.value,
                   'discover': Asset.ACTIVE_LOW.value, 'frozen': Asset.FROZEN.value}


def my_result(controller, key, filter="", offset="", pages=1):
    resp = controller.my(dict(key=key, offset=offset), pages)
    result = {'data': []}
    for key, value in resp.items():
        if isinstance(value, list):
            result['data'] += value
    if filter != "":  # filter by name or member only for accounts
        result['data'] = [item for item in resp['accounts'] if filter == item['name'] or filter == item['member']]
    if resp.get('offset'):
        result['offset'] = json.dumps(resp['offset'])
    return result


def paginate(controller, key, item_type="", filter="", offset="", details=False, page="no"):
    pages = 100 if page == 'all' else 1
    while True:
        result = my_result(controller, key, filter, offset, pages)
        result = handle_results(result, item_type)
        display_list(result, details)

        if 'offset' not in result or page == 'all' or page == 'no':
            break

        print("Press any key to view next or 'q' to quit")
        if click.getchar() == 'q':
            break
        offset = result['offset']

    if 'offset' in result and not details:
        print(f'There are more results. Add the following argument to the command to view them:')
        print(f"--offset '{result['offset']}'")


def handle_results(result, item_type):
    if item_type == 'integrations':
        result['data'] = [item for item in result['data'] if '@' not in item['member'] and item['member'] != 'settings']
    elif item_type == 'accounts':
        result['data'] = [item for item in result['data'] if '@' in item['member']]
    elif item_type == 'definitions':
        for hit in result.get('data', []):
            hit['key'] = hit['key'].split("definitions/")[-1]
    return result


def display_list(result, details):
    if details:
        print(json.dumps(result, indent=4))
    else:
        for hit in result.get('data', []):
            print(f"{hit['key']}")
