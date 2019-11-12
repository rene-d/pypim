#! /usr/bin/env python3

"""
extract project names from a clamav report
"""

import logging
import click
import pathlib
import re


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("report", type=click.File("r"))
def main(report):

    names = set()

    for i in report:
        if "/packages/" not in i:
            continue
        i = i.strip()
        if not i.endswith("FOUND"):
            continue
        i = i.split(" ")
        p = pathlib.Path(i[0][:-1])

        a = re.match(r"^(.+?)(_\d.+)$", p.name)
        if a is None:
            a = re.match(r"^(.+?)(\-\d.+)$", p.name)
        if a is None:
            logging.critical(i)
            exit()
        name = a.group(1)
        names.add(name)

    print(names)


if __name__ == "__main__":
    main()
