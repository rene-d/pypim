#! /usr/bin/env python3

"""
Retrieve a list of the releases for the given package_name
"""

import xmlrpc.client
import json
import click


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("name")
@click.option("--test", is_flag=True, default=False, help="test.pypi.org")
def main(name, test):

    if test:
        uri = "https://test.pypi.org/pypi"
    else:
        uri = "https://pypi.org/pypi"

    # ref: https://warehouse.pypa.io/api-reference/xml-rpc/
    client = xmlrpc.client.ServerProxy(uri)

    releases = client.package_releases(name, True)
    print(json.dumps(releases, indent=2))


if __name__ == "__main__":
    main()
