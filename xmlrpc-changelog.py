#! /usr/bin/env python3

import sqlite3
import json
import os
import sys
import click
import xmlrpc.client
import logging


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, default=False, help="verbose mode")
@click.option("--db", show_default=True, help="db", default="pypi.db")
@click.option("-s", "--last_serial", help="last_serial", default=0)
def main(**kwargs):

    # verbose/logger
    if sys.stdout.isatty():
        logging.addLevelName(logging.DEBUG, "\033[0;32m%s\033[0m" % logging.getLevelName(logging.DEBUG))
        logging.addLevelName(logging.INFO, "\033[1;36m%s\033[0m" % logging.getLevelName(logging.INFO))
        logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[0m" % logging.getLevelName(logging.WARNING))
        logging.addLevelName(logging.ERROR, "\033[0;31m%s\033[0m" % logging.getLevelName(logging.ERROR))
        logging.addLevelName(logging.FATAL, "\033[1;41m%s\033[0m" % logging.getLevelName(logging.FATAL))

    if kwargs["verbose"]:
        logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", datefmt="%H:%M:%S", level=logging.DEBUG)
        logging.debug("args %r", kwargs)
    else:
        logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", datefmt="%H:%M:%S", level=logging.INFO)

    # https://warehouse.pypa.io/api-reference/xml-rpc/

    # server last_serial
    logging.info(f"calling changelog_last_serial()")
    client = xmlrpc.client.ServerProxy("https://pypi.org/pypi")
    last_serial = client.changelog_last_serial()
    logging.info(f"server last_serial = {last_serial}")

    if kwargs['last_serial'] != 0:
        last_serial = kwargs['last_serial']
        logging.info(f"using last_serial = {last_serial}")
    else:
        try:
            db = sqlite3.connect(os.path.expanduser(kwargs["db"]))
            db.row_factory = sqlite3.Row

            # the db' last_serial
            last_serial = db.execute("select max(last_serial) from last_serial").fetchone()[0]
            logging.info(f"mirror last_serial = {last_serial}")
            db.close()
        except Exception as e:
            logging.error("impossible de lire la base de données: %s", e)
            exit()

    logging.info(f"calling changelog_since_serial({last_serial})")
    client = xmlrpc.client.ServerProxy("https://pypi.org/pypi")
    changelog = client.changelog_since_serial(last_serial)

    json.dump(changelog, open("changelog.txt", "w"), indent=2)
    logging.info(f"received {len(changelog)} changes")

    updated = set(change[0] for change in changelog)
    max_serial = max(change[4] for change in changelog)

    logging.info(f"received: {len(updated)} updated, {max_serial} max_serial")

    # events = set()
    for package, release, timestamp, event, serial in changelog:
        logging.debug("%-32s %-10s %d %d %s", package, release, timestamp, serial, event)

    #     if event.startswith("add ") or event.startswith("change ") or event.startswith("remove "):
    #         p = event.find(" file ")
    #         if p != -1:
    #             p += 5
    #         else:
    #             p = event.find(" ", event.find(" ") + 1)
    #         event = event[0:p + 1].strip()
    #     events.add(event)
    # print("\n".join(sorted(events)))

    # logging.debug("changelog\n%s", json.dumps(changelog, indent=2))


if __name__ == "__main__":
    main()
