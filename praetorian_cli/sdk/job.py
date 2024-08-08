class Job:
    def __init__(self, chariot):
        self.chariot = chariot

    def add(self, asset, capability):
        return self.chariot.add('job', dict(asset=asset, capability=capability))

    def get(self, asset) -> list:
        return self.chariot.my(dict(key=f'#job#{asset}'))['jobs']

    def update(self, asset, status):
        return self.chariot.update('job', dict(key=f'#job#{asset}', status=status))

    def delete(self, asset):
        self.chariot.delete('job', key=f'#job#{asset}')
