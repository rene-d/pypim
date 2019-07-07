#! /usr/bin/env python3

"""
Retrieve the last event’s serial id
"""

import click
import xmlrpc.client


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--test", is_flag=True, default=False, help="test.pypi.org")
def main(test):

    if test:
        uri = "https://test.pypi.org/pypi"
    else:
        uri = "https://pypi.org/pypi"

    # ref: https://warehouse.pypa.io/api-reference/xml-rpc/
    client = xmlrpc.client.ServerProxy(uri)

    # server last_serial
    last_serial = client.changelog_last_serial()
    print(f"server last_serial = {last_serial}")


if __name__ == "__main__":
    main()
