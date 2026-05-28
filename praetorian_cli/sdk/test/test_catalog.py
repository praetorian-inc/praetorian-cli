from praetorian_cli.catalog import Capability, rank_search


def test_capability_normalizes_agora_shape():
    raw = {
        'Name': 'brutus', 'Title': 'Brutus', 'Target': ['port'],
        'Description': 'Credential testing', 'Category': ['credential'],
        'Surface': 'external', 'RunsOn': 'any', 'Version': '0.2.0',
        'Executor': 'chariot', 'Integration': False,
        'Parameters': [{'Name': 'protocol', 'Description': 'svc', 'Type': 'string',
                        'Default': '', 'Required': False, 'Options': ['ssh', 'rdp']}],
    }
    cap = Capability.from_api(raw)
    assert cap.name == 'brutus'
    assert cap.title == 'Brutus'
    assert cap.target == ['port']
    assert cap.category == ['credential']
    assert cap.surface == 'external'
    assert cap.version == '0.2.0'
    assert cap.parameters[0].name == 'protocol'
    assert cap.parameters[0].options == ['ssh', 'rdp']
    assert cap.parameters[0].required is False


def test_capability_handles_missing_and_scalar_fields():
    cap = Capability.from_api({'Name': 'x', 'Category': 'recon', 'Target': 'port'})
    assert cap.title == 'x'           # falls back to name
    assert cap.category == ['recon']  # scalar coerced to list
    assert cap.target == ['port']     # scalar coerced to list
    assert cap.parameters == []


def _caps():
    return [
        Capability.from_api({'Name': 'nuclei', 'Category': 'scanner', 'Surface': 'external',
                             'Target': ['port'], 'Description': 'vuln scanner', 'Title': 'Nuclei'}),
        Capability.from_api({'Name': 'nuclei_dast', 'Category': 'scanner', 'Surface': 'external',
                             'Target': ['webapp'], 'Description': 'dast', 'Title': 'Nuclei DAST'}),
        Capability.from_api({'Name': 'brutus', 'Category': 'credential', 'Surface': 'internal',
                             'Target': ['port'], 'Description': 'creds', 'Title': 'Brutus'}),
    ]

def test_rank_search_exact_before_prefix_before_fuzzy():
    out = rank_search(_caps(), 'nuclei')
    assert out[0].name == 'nuclei'          # exact wins
    assert out[1].name == 'nuclei_dast'     # prefix next

def test_rank_search_typo_tolerant():
    out = rank_search(_caps(), 'nuclie')    # transposed
    assert out and out[0].name in ('nuclei', 'nuclei_dast')

def test_rank_search_filters():
    out = rank_search(_caps(), '', category='credential')
    assert [c.name for c in out] == ['brutus']
    out = rank_search(_caps(), '', surface='external', target='port')
    assert [c.name for c in out] == ['nuclei']
