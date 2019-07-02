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
@click.argument("name")
def main(**kwargs):

    client = xmlrpc.client.ServerProxy('https://pypi.org/pypi')
    releases = client.package_releases(kwargs['name'], True)

    print(json.dumps(releases, indent=2))


if __name__ == "__main__":
    main()
