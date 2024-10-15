import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


@chariot.group()
def imports():
    """ Import data to Chariot """
    pass


@imports.command()
@cli_handler
@click.argument('xml-file')
def insightvm(chariot, xml_file):
    """ Import data from Rapid7 InsightVM

    The export file needs to be in the XML Export 2.0 format. See details at
    https://docs.praetorian.com/hc/en-us/articles/29778072321307-Rapid7-InsightVM

    \b
    Example usages:
        - praetorian chariot import insightvm ~/Downloads/insightvm-report.xml
    """
    chariot.integrations.add_import_integration('insightvm-import', xml_file)


@imports.command()
@cli_handler
@click.argument('csv-file')
def qualys(chariot, csv_file):
    """ Import data from Qualys VMDR

    The export file needs to be in the CSV format. See details at
    https://docs.praetorian.com/hc/en-us/articles/29776468370331-Qualys-VMDR

    \b
    Example usages:
        - praetorian chariot import qualys ~/Downloads/qualys-report.csv
    """
    chariot.integrations.add_import_integration('qualys-import', csv_file)


@imports.command()
@cli_handler
@click.argument('nessus-file')
def nessus(chariot, nessus_file):
    """ Import data from Tenable Nessus

    The export file needs to be in the Tenable Nessus (.nessus) format. See details at
    https://docs.praetorian.com/hc/en-us/articles/28054164449435-Tenable-Nessus

    \b
    Example usages:
        - praetorian chariot import nessus ~/Downloads/nessus-report.nessus
    """
    chariot.integrations.add_import_integration('nessus-import', nessus_file)
