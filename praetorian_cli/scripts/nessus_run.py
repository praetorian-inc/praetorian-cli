"""
This script runs as a plugin to the Praetorian CLI.
Example usage:
    praetorian chariot plugin hello
"""
import json
import requests
import urllib3

from praetorian_cli.sdk.chariot import Chariot

api_url = 'https://localhost:8834'
api_key = '375c103f04d93bf4ce2b655bca7c57122b0babc3f8f6f18ef73a9648e928c829'
secret_key = 'f119866b23a09d60d92bc6f289dd9d3f4960c236292345d9ea8962534b091b58'


def nessus_api_req(api: str):
    headers = {
        'X-ApiKeys': f'accessKey={api_key}; secretKey={secret_key}'
    }
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(f'{api_url}/{api}', headers=headers, verify=False)
    return json.loads(response.text)


def report_vulns(controller: Chariot, args, kwargs, strings):
    # """Run the hello plugin"""
    # print('Hello from the hello plugin!')
    # print(f'Arguments: {args}')
    # print(f'Keyword arguments: {kwargs}')
    # print(f'Strings: {strings}')

    url = f'/scans'
    response = nessus_api_req(url)
    for scan in response['scans']:
        scan_id = scan['id']
        url = f'/scans/{scan_id}'
        scan_details = nessus_api_req(url)
        for host in scan_details['hosts']:
            url = f'/scans/{scan_id}/hosts/{host['host_id']}'
            host_details = nessus_api_req(url)
            name = host_details['info']['host-ip']
            dns = host_details['info']['host-ip']
            if 'host-fqdn' in host_details['info']:
                dns = host_details['info']['host-fqdn']



            added = False
            for vuln in host_details['vulnerabilities']:
                if vuln['severity'] == 0:
                    continue
                
                asset_key = None
                if not added: # only added assets with vulns
                    print(f"Asset: {name}"  )
                    print(f"DNS: {dns}")
                    asset = controller.add('asset', dict(
                        dns=dns, name=name, status='F'))
                    asset_key = asset[0]['key']
                    added = True

                print(asset_key)

                # GET /scans/{scan_id}/hosts/{host_id}/plugins/{plugin_id}
                url = f'/scans/{scan_id}/hosts/{
                    host["host_id"]}/plugins/{vuln["plugin_id"]}'
                plugin_details = nessus_api_req(url)
                proof_of_exploit = ''
                for output in plugin_details['outputs']:
                    proof_of_exploit += output['plugin_output']


                risk = plugin_details['info']['plugindescription']['pluginattributes']['risk_information']['risk_factor']
                comment = plugin_details['info']['plugindescription']['pluginattributes']['description']
                vuln = (''.join({vuln['plugin_name']})).replace(' ', '-').lower()
                risk_resp = controller.add('risk', dict(key=asset_key, name=vuln, status='TI', comment=comment))
                print(f"Vuln: {vuln}")
                print(f"Risk: {risk}")
                # print(f"Comment: {comment}")
                # print(f"Proof of Exploit: {proof_of_exploit}")


