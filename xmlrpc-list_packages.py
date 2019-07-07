#! /usr/bin/env python3

"""
Retrieve a list of the package names
"""

import xmlrpc.client
import json
import click


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--serial", is_flag=True, default=False, help="serial")
@click.option("--json", "json_output", is_flag=True, default=False, help="JSON")
@click.option("--test", is_flag=True, default=False, help="test.pypi.org")
def main(serial, json_output, test):

    if test:
        uri = "https://test.pypi.org/pypi"
    else:
        uri = "https://pypi.org/pypi"

    # ref: https://warehouse.pypa.io/api-reference/xml-rpc/
    client = xmlrpc.client.ServerProxy(uri)

    if serial:
        packages = client.list_packages_with_serial()
    else:
        packages = client.list_packages()

    if json_output:
        print(json.dumps(packages, indent=2))
    else:
        for package in sorted(packages):
            print(package)


if __name__ == "__main__":
    main()
