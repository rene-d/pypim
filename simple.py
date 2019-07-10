#! /usr/bin/env python3

"""
Simple HTTP server that mimics https://pypi.org/simple/
"""

import tornado.ioloop
import tornado.web
import tornado.log
import sqlite3
from packaging.utils import canonicalize_name  # lowercase, only hyphen PEP503
import logging
from collections import defaultdict
import pathlib
import click
from pypim import build_index


class SimpleHandler(tornado.web.RequestHandler):
    """
    handler for /simple/<package>/
    returns the releases files list
    """

    def initialize(self, database, path):
        self.db = database
        self.path = path

    def get(self, name):

        try:
            cur = self.db.cursor()

            r = cur.execute(
                "select name,last_serial from package where name=?",
                (canonicalize_name(name),),
            ).fetchone()
            if r is None:
                # tornado.log.gen_log.error(f"project {name} not found in index")
                raise tornado.web.HTTPError(403)

            name, last_serial = r

            tornado.log.gen_log.info(f"serving {name} {last_serial}")

            releases = defaultdict(list)
            sql = "select release,filename,url,size,requires_python,sha256_digest from file where name=?"
            for row in cur.execute(sql, (name,)):
                releases[row[0]].append(
                    {
                        "filename": row[1],
                        "url": row[2],
                        "size": row[3],
                        "requires_python": row[4],
                        "digests": {"sha256": row[5]},
                    }
                )

            html = build_index(name, last_serial, releases, self.path)

            self.write(html)

        finally:
            cur.close()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, default=False, help="verbose mode")
@click.option("-p", "--port", help="HTTP listening port", default=8000, type=int)
@click.option(
    "--web",
    default="~/data/pypi",
    help="mirror directory",
    type=click.Path(dir_okay=True),
    show_default=True,
)
@click.option(
    "--db",
    default="pypi.db",
    help="packages database",
    type=click.Path(file_okay=True),
    show_default=True,
)
def main(verbose, port, web, db):
    if verbose:
        tornado.log.gen_log.setLevel(logging.DEBUG)

    path = pathlib.Path(web).expanduser()
    database = sqlite3.connect(db")

    app = tornado.web.Application(
        [
            (r"/simple/([^/]+)/?", SimpleHandler, {"database": database, "path": path}),
            (
                r"/(packages/.*)",
                tornado.web.StaticFileHandler,
                {"path": path.as_posix()},
            ),
        ],
        autoreload=True,
    )

    app.listen(port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
