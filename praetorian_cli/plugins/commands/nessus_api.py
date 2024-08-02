"""
This plugin command pulls data from the Nessus API server and creates assets and
risks in the Chariot platform.

Example usage:
    praetorian chariot plugin nessus --url https://localhost:8834 --api-key <API_KEY> --secret-key <SECRET_KEY>
"""
from concurrent.futures import ThreadPoolExecutor

import click
import requests
from requests.packages.urllib3 import disable_warnings, exceptions

from praetorian_cli.sdk.chariot import Chariot


def create_nessus_client(api_url, api_key, secret_key):
    disable_warnings(exceptions.InsecureRequestWarning)

    def nessus_api_req(api: str):
        headers = {
            'X-ApiKeys': f'accessKey={api_key}; secretKey={secret_key}'
        }
        response = requests.get(
            f'{api_url}/{api}', headers=headers, verify=False)
        if not response.ok:
            click.echo(
                f'[{response.status_code}] Request failed' + (f'\nError: {response.text}' if response.text else ''),
                err=True)
            exit(1)
        return response.json()

    return nessus_api_req


def report_vulns(controller: Chariot, url: str, api_key: str, secret_key: str):
    """ Run the Nessus integrations plugin """
    nessus_api_req = create_nessus_client(url, api_key, secret_key)

    url = f'/scans'
    response = nessus_api_req(url)
    for scan in response['scans']:
        scan_id = scan['id']
        url = f'/scans/{scan_id}'
        scan_details = nessus_api_req(url)

        def get_host_scan(scan_id, host):
            url = f"/scans/{scan_id}/hosts/{host['host_id']}"
            host_details = nessus_api_req(url)
            name = host_details['info']['host-ip']
            dns = host_details['info']['host-ip']
            if 'host-fqdn' in host_details['info']:
                dns = host_details['info']['host-fqdn']

            asset_key = ''
            for vuln in host_details['vulnerabilities']:
                if vuln['severity'] == 0:
                    continue

                if asset_key == '':  # only added assets with vulns
                    asset = controller.add('asset', dict(
                        dns=dns, name=name, status='F'))
                    asset_key = asset[0]['key']

                url = f"/scans/{scan_id}/hosts/{host['host_id']}/plugins/{vuln['plugin_id']}"
                plugin_details = nessus_api_req(url)
                proof_of_exploit = ''
                for output in plugin_details['outputs']:
                    proof_of_exploit += output['plugin_output']

                risk = plugin_details['info']['plugindescription']['pluginattributes']['risk_information'][
                    'risk_factor']
                comment = plugin_details['info']['plugindescription']['pluginattributes']['description']
                vuln = (''.join({vuln['plugin_name']})
                        ).replace(' ', '-').lower()
                status = 'T' + risk[0].upper()
                controller.add('risk', dict(
                    key=asset_key, name=vuln, source='nessus', status=status, comment=comment))
                if proof_of_exploit != '':
                    controller._upload(f'{dns}/{vuln}', proof_of_exploit)

    with ThreadPoolExecutor(max_workers=10) as executor:
        for host in scan_details['hosts']:
            executor.submit(get_host_scan, scan_id, host)
