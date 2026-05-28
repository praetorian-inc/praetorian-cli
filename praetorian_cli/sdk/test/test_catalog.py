from praetorian_cli.catalog import Capability


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
