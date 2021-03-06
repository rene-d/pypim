#! /usr/bin/env python3

# ref: https://warehouse.pypa.io/api-reference/xml-rpc/

"""
retourne la liste des packages
cf. https://warehouse.pypa.io/api-reference/xml-rpc/
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

    client = xmlrpc.client.ServerProxy(uri)
    urls = client.release_urls(name, release)

    print(json.dumps(urls, indent=2))


if __name__ == "__main__":
    main()
