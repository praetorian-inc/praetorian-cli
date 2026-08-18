class OSINT:

    def __init__(self, api):
        self.api = api

    def guess_repo(self, cpe=None, technology_name=None):
        body = {}
        if cpe:
            body['cpe'] = cpe
        if technology_name:
            body['technology_name'] = technology_name
        return self.api.post('osint/guess-repo', body)

    def submit(self, repo_url, technology_key=None, goal=None, pipeline=None, scan_mode=None):
        body = {'repo_url': repo_url}
        if technology_key:
            body['technology_key'] = technology_key
        if goal:
            body['goal'] = goal
        if pipeline:
            body['pipeline'] = pipeline
        if scan_mode:
            body['scan_mode'] = scan_mode
        return self.api.post('osint/submit', body)

    def create_technology(self, cpe):
        return self.api.post('osint/create-technology', {'cpe': cpe})
