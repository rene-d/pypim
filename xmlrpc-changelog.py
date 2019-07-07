#! /usr/bin/env python3

# ref: https://warehouse.pypa.io/api-reference/xml-rpc/

"""
Retrieve a list events since a given serial
"""

import sqlite3
import json
import os
import sys
import click
import xmlrpc.client
import logging
import datetime

logger = logging.getLogger("xmlrpc-changelog")


class ColoredFormatter(logging.Formatter):

    COLORS = {
        logging.DEBUG: "\033[0;32m",
        logging.INFO: "\033[1;36m",
        logging.WARNING: "\033[1;33m",
        logging.ERROR: "\033[0;31m",
        logging.FATAL: "\033[1;41m",
    }

    def __init__(self, msg, **kwargs):
        logging.Formatter.__init__(self, msg, **kwargs)
        self.use_color = sys.stderr.isatty()

    def format(self, record):
        saved_levelname = record.levelname
        levelno = record.levelno
        if self.use_color and levelno in ColoredFormatter.COLORS:
            record.levelname = ColoredFormatter.COLORS[levelno] + record.levelname + "\033[0m"
        line = logging.Formatter.format(self, record)
        record.levelname = saved_levelname
        return line


def init_logger(kwargs):
    """
    initialize the logger with a colored console and a file handlers
    """

    filename = kwargs.get("logfile", None)

    if kwargs.get("verbose", False):
        level = logging.DEBUG
    elif kwargs.get("non_verbose", False):
        level = logging.WARNING
    else:
        level = logging.INFO

    logger.setLevel(logging.DEBUG)

    # create console handler and set level
    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = ColoredFormatter("%(asctime)s:%(levelname)s:%(message)s", datefmt="%H:%M:%S")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if filename:
        # create file handler and set level to debug
        ch = logging.FileHandler(filename)
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    else:
        # if no file handler, we can reduce the level as asked
        logger.setLevel(level)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, default=False, help="verbose mode")
@click.option("-nv", "--non-verbose", is_flag=True, default=False, help="no so much verbose")
@click.option("-lf", "--logfile", help="logfile")
@click.option("--db", show_default=True, help="db", default="pypi.db")
@click.option("-s", "--last_serial", help="last_serial", default=0)
@click.option("-j", "--json", is_flag=True, default=False, help="save changelog in JSON")
@click.option("--test", is_flag=True, default=False, help="test.pypi.org")
def main(**kwargs):

    init_logger(kwargs)

    if kwargs["test"]:
        uri = "https://test.pypi.org/pypi"
    else:
        uri = "https://pypi.org/pypi"

    client = xmlrpc.client.ServerProxy(uri)

    # server last_serial
    last_serial = client.changelog_last_serial()
    logger.info(f"server last_serial = {last_serial}")

    if kwargs["last_serial"] != 0:
        last_serial = kwargs["last_serial"]
        logger.info(f"using last_serial = {last_serial}")
    else:
        try:
            db = sqlite3.connect(os.path.expanduser(kwargs["db"]))
            db.row_factory = sqlite3.Row

            # the db' last_serial
            last_serial = db.execute("select last_serial from pypi_last_serial").fetchone()[0]
            logger.info(f"mirror last_serial = {last_serial}")
            db.close()
        except Exception as e:
            logger.error("impossible de lire la base de données: %s", e)
            exit()

    # changelog since db last serial or argument
    logger.info(f"calling changelog_since_serial({last_serial})")
    changelog = client.changelog_since_serial(last_serial)

    if kwargs["json"]:
        json.dumps(changelog, open("changelog.json", "w"), indent=2)
        logger.info(f"received {len(changelog)} changes")
    else:
        lp = max(len(package) for package, _, _, _, _ in changelog if package)
        lr = max(len(release) for _, release, _, _, _ in changelog if release)
        with open("changelog.txt", "w") as fp:
            for package, release, timestamp, event, serial in changelog:
                d = datetime.datetime.fromtimestamp(timestamp).isoformat()
                line = "%*s %*s %s %d %s" % (-lp, package, -lr, release, d, serial, event)
                print(line, file=fp)
                logger.debug(line)

    updated = set(change[0] for change in changelog)
    max_serial = max(change[4] for change in changelog)

    logger.info(f"received: {len(updated)} updated, {max_serial} max_serial")

    # events = set()
    # for package, release, timestamp, event, serial in changelog:
    #     if event.startswith("add ") or event.startswith("change ") or event.startswith("remove "):
    #         p = event.find(" file ")
    #         if p != -1:
    #             p += 5
    #         else:
    #             p = event.find(" ", event.find(" ") + 1)
    #         event = event[0:p + 1].strip()
    #     events.add(event)
    # print("\n".join(sorted(events)))

    # logger.debug("changelog\n%s", json.dumps(changelog, indent=2))


if __name__ == "__main__":
    main()
