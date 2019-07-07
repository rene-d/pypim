#! /usr/bin/env python3

"""
Retrieve metadata describing a specific release
"""

import xmlrpc.client
import json
import click


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("name")
@click.argument("release")
@click.option("--test", is_flag=True, default=False, help="test.pypi.org")
def main(name, release, test):

    if test:
        uri = "https://test.pypi.org/pypi"
    else:
        uri = "https://pypi.org/pypi"

    # ref: https://warehouse.pypa.io/api-reference/xml-rpc/
    client = xmlrpc.client.ServerProxy(uri)

    data = client.release_data(name, release)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
