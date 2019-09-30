#! /usr/bin/env python3

"""
remove blacklisted packages
"""

import pickle
import click
import sqlite3
import pathlib
from urllib.parse import urlparse
import humanfriendly as hf
import os.path


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, default=False, help="verbose mode")
@click.option(
    "--web",
    default="~/data/pypi",
    help="mirror directory",
    type=click.Path(dir_okay=True),
    show_default=True,
)
@click.option(
    "--db", help="packages database", type=click.Path(file_okay=True), show_default=True
)
def main(verbose, web, db):
    """
    remove blacklisted projects from the mirror
    """

    web = os.path.expanduser(web)
    if db is None:
        db = os.path.join(web, "pypi.db")
    else:
        db = os.path.expanduser(db)

    bl = pickle.load(open("blacklist.cache", "rb"))[0]
    conn = sqlite3.connect(db)
    web = pathlib.Path(web)

    total = 0
    count = 0
    for name, url, size in conn.execute("select name,url,size from file"):
        if name not in bl:
            continue

        url = urlparse(url).path[1:]
        path = web / url
        if path.exists():
            path.unlink()
            try:
                path.parent.rmdir()
            except OSError:
                # not empty, should not occur
                pass

            total += size
            count += 1

            if verbose:
                print(f"removed: {path} ({size} bytes)")

    print(f"files removed: {count}")
    print(f"space freed: {hf.format_size(total)}")


if __name__ == "__main__":
    main()
