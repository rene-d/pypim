#! /usr/bin/env python3

"""
retourne la liste des packages
cf. https://warehouse.pypa.io/api-reference/xml-rpc/
"""

import xmlrpc.client
import json
import click
import sys


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--serial", is_flag=True, default=False, help="serial")
@click.option("--json", is_flag=True, default=False, help="json")
def main(**kwargs):

    client = xmlrpc.client.ServerProxy('https://pypi.org/pypi')

    if kwargs['serial']:
        packages = client.list_packages_with_serial()
    else:
        packages = client.list_packages()

    if kwargs['json']:
        print(json.dumps(packages, indent=2))
    else:
        for package in sorted(packages):
            print(package)


if __name__ == "__main__":
    main()
