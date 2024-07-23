"""
This plugin command pulls data from a Nessus DB export and creates the assets 
and risks in the Chariot platform.

Example usage:
    praetorian chariot plugin nessus --file <PATH_TO_SCAN.nessus>
"""
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import click

from praetorian_cli.sdk.chariot import Chariot


def report_vulns(controller: Chariot, file: str):
    """ Run the Nessus DB integrations plugin """

    def parse_host_scan(reportHost):
        name = reportHost.find('HostProperties/tag[@name="host-ip"]').text
        dns = reportHost.find('HostProperties/tag[@name="host-fqdn"]')
        if dns is not None:
            dns = dns.text
        else:
            dns = name

        asset_key = ''
        for item in reportHost.iter('ReportItem'):
            if item.get('severity') == '0':
                continue

            if asset_key == '':
                asset = controller.add('asset', dict(
                    dns=dns, name=name, status='F'))
                asset_key = asset[0]['key']

            vuln = item.get('pluginName').replace(' ', '-').lower()
            status = 'T' + item.find('risk_factor').text[0].upper()
            description = item.find('description').text

            proof_of_exploit = item.find('plugin_output')
            print(f'Adding {status} risk: "{vuln}" for "{dns}"')
            controller.add('risk', dict(
                key=asset_key, name=vuln, source='nessus', status=status, comment=description))
            if proof_of_exploit is not None:
                controller._upload(f'{dns}/{vuln}', proof_of_exploit.text)

    try:
        main = ET.parse(file)
    except Exception as e:
        click.echo(f'Unable to import file {file}. Error: {e}.', err=True)
        exit(1)

    root = main.getroot()
    with ThreadPoolExecutor(max_workers=10) as executor:
        for reportHost in root.iter('ReportHost'):
            executor.submit(parse_host_scan, reportHost)
