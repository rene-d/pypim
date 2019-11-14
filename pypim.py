#! /usr/bin/env python3
# rene-d 2019

"""
PyPIM: PyPI.org Intelligent Mirroring
"""

import xmlrpc.client
import json
import sqlite3
import click
import logging
import sys
import time
import requests
import signal
from collections import defaultdict
from packaging.version import parse
from packaging.utils import canonicalize_name  # lowercase, only hyphen PEP503
from html import escape
import pathlib
import re
import pickle
from datetime import timedelta
from urllib.parse import urlparse
from plugins import filename_name, latest_name
from plugins.blacklist import get_blacklist
import shutil
import humanfriendly as hf
import os.path


# create logger for our app
logger = logging.getLogger("pypim")


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
            record.levelname = (
                ColoredFormatter.COLORS[levelno] + record.levelname + "\033[0m"
            )
        line = logging.Formatter.format(self, record)
        record.levelname = saved_levelname
        return line


def win_term():
    """
    set the Windows console to understand the ANSI color codes
    """

    from platform import system as platform_system

    if platform_system() == "Windows":
        import ctypes

        kernel32 = ctypes.windll.kernel32

        # https://docs.microsoft.com/en-us/windows/console/setconsolemode
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        mode = ctypes.wintypes.DWORD()
        if kernel32.GetConsoleMode(
            kernel32.GetStdHandle(STD_OUTPUT_HANDLE), ctypes.byref(mode)
        ):
            mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(kernel32.GetStdHandle(STD_OUTPUT_HANDLE), mode)


def init_logger(kwargs):
    """
    initialize the logger with a colored console and a file handlers
    """

    win_term()

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
    formatter = ColoredFormatter(
        "%(asctime)s:%(levelname)s:%(message)s", datefmt="%H:%M:%S"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if filename:
        # create file handler and set level to debug
        ch = logging.FileHandler(filename)
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    else:
        # if no file handler, we can reduce the level as asked
        logger.setLevel(level)


class CtrlC:
    """
    class context to catch Ctrl-C event

    usage:
        with CtrlC as ctrl_c:
            <loop>
                if ctrl_c:
                    break
                <do something>
    """

    def __init__(self, throw=False):
        """
        initializer
        param: throw: if True, raise a KeyboardInterrupt
        """
        self.throw = throw

    def __enter__(self):
        logger.debug("enter CtrlC")
        self.ctrl_c = False

        def _handler(sig, frame):
            nonlocal self
            self.ctrl_c = True
            print("\nCtrlC: exit requested... another ^C to force")
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            if self.throw:
                raise KeyboardInterrupt

        signal.signal(signal.SIGINT, _handler)
        return self

    def __exit__(self, type, value, traceback):
        logger.debug("exit CtrlC")
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    def __bool__(self):
        return self.ctrl_c


def insert_row(cur, table, row):
    """
    insert a dict into a SQLite3 table
    """
    columns = ",".join(row.keys())
    placeholders = ":" + ",:".join(row.keys())
    query = f"insert into {table} ({columns}) values ({placeholders})"
    cur.execute(query, row)


def fetch_value(db, sql, params=(), default_value=0):
    """
    fetch the first value of the first row of a select statement
    """
    # logger.debug(f"{sql}")
    # logger.debug(f"{params!r}")
    if not isinstance(params, tuple) and not isinstance(params, list):
        params = (params,)
    row = db.execute(sql, params).fetchone()
    # logger.debug(f"{row!r}")
    if row and isinstance(row[0], int):
        return int(row[0])
    else:
        return default_value


def get_meta_db_path(db):
    for i in db.execute("pragma database_list;"):
        if i[1] == "main":
            f = pathlib.Path(i[2])
            f = f.with_name(f.stem + "_json" + f.suffix)
            logger.debug(f"using json db: {f}")
            return f.as_posix()


def create_db(db, use_meta_db):
    """
    initalize the both databases
        db          decoded metadata into SQL tables
        db_json     the raw metadata in JSON format
    """

    if use_meta_db:
        db.execute("attach database ? as meta_db", (get_meta_db_path(db),))
        db.executescript(
            """\
-- package JSON metadata
create table if not exists meta_db.package (
    name            text not null primary key,
    last_serial     integer not null,
    metadata        blob
);
"""
        )
        db.execute("detach database meta_db")

    db.executescript(
        """\
-- response of changelog_last_serial()
create table if not exists pypi_last_serial (
    last_serial     integer not null,
    timestamp       integer
);

-- response of list_packages_with_serial
create table if not exists list_packages (
    name            text not null primary key,
    last_serial     integer not null,
    ignore          boolean
);

-- package info
create table if not exists package (
    name            text not null primary key,
    last_serial     number not null,
    author          text,
    author_email    text,
    bugtrack_url    text,
    -- classifiers
    description     text,
    description_content_type text,
    docs_url        text,
    download_url    text,
    -- "downloads": { "last_day": -1, "last_month": -1, "last_week": -1 },
    home_page       text,
    keywords        text,
    license         text,
    maintainer      text,
    maintainer_email text,
    package_url     text,
    platform        text,
    project_url     text,
    -- "project_urls": { "Download": "UNKNOWN", "Homepage": "https://github.com/pypa/sampleproject" },
    release_url     text,
    -- requires_dist
    requires_python text,
    summary         text,
    version         text
);

-- classifiers of a package
create table if not exists classifier (
    name        text not null,
    classifier  text not null
);

-- requirements of a package
create table if not exists requires_dist (
    name            text not null,
    requires_dist   text not null
);

-- releases of a package
create table if not exists release (
    name        text not null,
    release     text not null
);

-- files of a release
create table if not exists file (
    name            text not null,
    release         text not null,
    comment_text    text,
    -- digests md5 sha256
    -- "downloads": -1
    filename        text,
    has_sig         text,
    -- md5_digest
    sha256_digest   text,
    packagetype     text,
    python_version  text,
    requires_python text,
    size            integer not null,
    upload_time     datetime,
    upload_time_iso_8601 datatime,
    url             text
);

-- indexes
create unique index if not exists package_uk on package (name,last_serial);
create unique index if not exists release_pk on release (name,release);
create index if not exists release_fk on release (name);
create index if not exists file_fk on file (name,release);
create unique index if not exists file_url on file (url);

-- triggers
create trigger if not exists classifier_trigger
    after delete on package for each row
    begin
        delete from classifier where old.name=name;
    end;

create trigger if not exists requires_dist_trigger
    after delete on package for each row
    begin
        delete from requires_dist where old.name=name;
    end;

create trigger if not exists release_trigger
    after delete on package for each row
    begin
        delete from release where old.name=name;
    end;

create trigger if not exists file_trigger
    after delete on package for each row
    begin
        delete from file where old.name=name;
    end;

"""
    )
    logger.debug("packages database initialized")


def delete_package(cur, name, use_meta_db):
    """
    delete a package from all the tables
    """

    cur.execute("delete from package where name=?", (name,))
    if use_meta_db:
        cur.execute("delete from meta_db.package where name=?", (name,))


def add_package(db, orig_name, data, use_meta_db):
    """
    add a package from the JSON metadata
    """

    metadata = json.loads(data)

    cur = db.cursor()

    info = metadata["info"]
    name = info["name"]

    if name != orig_name:
        logger.eror(f"{name} != {orig_name}")
        assert name == orig_name

    delete_package(cur, name, use_meta_db)

    classifiers = info["classifiers"]
    requires_dist = info["requires_dist"]

    del info["classifiers"]
    del info["downloads"]  # unused
    del info["project_urls"]  # unused
    del info["requires_dist"]

    # ajoute le last_serial (plutôt que dans une table séparée)
    last_serial = metadata["last_serial"]
    info["last_serial"] = last_serial

    # add the package
    insert_row(cur, "package", info)

    # add classifiers
    row = dict({"name": name})
    for classifier in classifiers:
        row["classifier"] = classifier
        insert_row(cur, "classifier", row)

    # add requirements
    if requires_dist:
        row = dict({"name": name})
        for dist in requires_dist:
            row["requires_dist"] = dist
            insert_row(cur, "requires_dist", row)

    for release, files in metadata["releases"].items():

        # add release
        insert_row(cur, "release", {"name": name, "release": release})

        # add distribution files
        for file in files:
            file["name"] = name
            file["release"] = release

            # we need only the SHA256 digest
            file["sha256_digest"] = file["digests"]["sha256"]

            # we don't care about these fields
            del file["digests"]
            del file["downloads"]
            del file["md5_digest"]

            insert_row(cur, "file", file)

    # store the raw JSON
    if use_meta_db:
        cur.execute(
            "insert into meta_db.package (name,last_serial,metadata) values (?,?,?)",
            (name, last_serial, data),
        )

    cur.close()

    logger.debug(f"package added: {name} {last_serial}")


def update_list(client, db, clear_ignore=False):
    """
    download and update the list of packages with their last_serial
    """

    db_serial = fetch_value(db, "select last_serial from pypi_last_serial")
    logger.info(f"db serial: {db_serial}")

    # ----- changelog_last_serial -----
    last_serial_time = int(time.time())
    last_serial = client.changelog_last_serial()
    logger.info(f"server serial: {last_serial}")

    if last_serial == db_serial:
        logger.info("database is up to date")
    else:
        # the server serial is different from ours: we have to update

        logger.info(f"update events: {last_serial - db_serial}")
        db.execute("delete from pypi_last_serial")
        db.execute(
            "insert into pypi_last_serial (last_serial, timestamp) values (?,?)",
            (last_serial, last_serial_time),
        )

        # ----- list_packages_with_serial -----
        packages = client.list_packages_with_serial()
        logger.info("packages listed: %d", len(packages))

        ignore_flags = defaultdict(lambda: False)
        if not clear_ignore:
            # fetch the ignore flags
            # for packages not modified since the last update
            for row in db.execute(
                "select name,ignore from list_packages where last_serial<=?",
                (db_serial,),
            ):
                ignore_flags[row[0]] = row[1]

        # replace the list of packages with the fresh one, ignore flag preserved
        logger.info("refill table list_packages")
        db.execute("delete from list_packages")
        db.executemany(
            "insert into list_packages (name,last_serial,ignore) values (?,?,?)",
            [
                (name, last_serial, ignore_flags[name])
                for name, last_serial in packages.items()
            ],
        )

        # print the list of updated packages
        for row in db.execute(
            "select name from list_packages where last_serial>?", (db_serial,)
        ):
            name = row[0]
            logger.debug(f"updated: {name}")

        updated = fetch_value(
            db, "select count(*) from list_packages where last_serial>?", db_serial
        )
        logger.info(f"updated: {updated}")

    # print some stats
    total = fetch_value(db, "select count(*) from list_packages")
    logger.info(f"packages: {total}")

    ignored = fetch_value(db, "select count(*) from list_packages where ignore=1")
    logger.info(f"ignored: {ignored}")

    db.commit()


def download_metadata(db, use_meta_db, pypi_uri, whitelist_cond=None):
    """
    download and parse JSON metadata

    only needed (missing and updated) packages will be downloaded

    the raw JSON metadata is stored into a separated database, attached to db
    the metadata is parsed and stored into tables of db
    """

    if use_meta_db:
        db.execute("attach database ? as meta_db", (get_meta_db_path(db),))

    # update metadata only from whitelist
    if whitelist_cond:
        whitelist = set()
        canonicalize_named_names = dict(
            (canonicalize_name(name), name)
            for name, in db.execute("select name from list_packages")
        )
        for cond in whitelist_cond:
            m = re.match(r"^([^=<>~]+)(.*)?$", cond)
            name = canonicalize_name(m.group(1))
            if name in canonicalize_named_names:
                name = canonicalize_named_names[name]
            whitelist.add(name)
        logger.info("use white list: %r", whitelist)
    else:
        whitelist = None

    # requests session to download the JSON metadata
    session = requests.Session()

    # remove packages that are no longer listed
    sql = """\
select name from package where name not in (select name from list_packages)
"""
    for (name,) in db.execute(sql).fetchall():
        logger.debug(f"package removed from pypi: {name}")
        delete_package(db, name, use_meta_db)
    db.commit()

    with CtrlC() as ctrl_c:

        # fetch the list of packages that are:
        #  - not ignored
        #  - modified (different last_serial) or missing
        sql = """\
select lp.name,lp.last_serial,p.last_serial
from list_packages as lp
left join package as p on lp.name=p.name
where lp.ignore=0
  and (p.last_serial<lp.last_serial or p.name is null)
order by lp.last_serial
"""
        rows = db.execute(sql).fetchall()
        logger.info(f"metadata to download: {len(rows)}")

        processed = 0

        for row in rows:

            if ctrl_c:
                break

            name = row[0]

            if whitelist and name not in whitelist:
                continue

            logger.info(f"bump package {name} from serial {row[2]} to {row[1]}")

            try:
                url = f"{pypi_uri}/{name}/json"
                req = session.get(url, headers={"Content-Type": "application/json"})
                if req.status_code == 404:
                    # weird... package is listed in list_packages
                    # but not accessible from pypi.org
                    # it occurs probably when the package has no release
                    raise FileNotFoundError

                data = req.content

                # parse and store the metadata
                add_package(db, name, data, use_meta_db)

            except (
                sqlite3.IntegrityError,
                sqlite3.InterfaceError,
                json.decoder.JSONDecodeError,
                Exception,
            ) as e:
                logger.error(f"error {name} : {e!r}")
                db.execute("update list_packages set ignore=1 where name=?", (name,))

            processed += 1

        db.commit()

        logger.info(f"packages processed: {processed}")
        if len(rows) != processed:
            logger.warning(f"packages remaining: {len(rows) - processed}")

        if ctrl_c:
            logger.warning("terminated")
            exit(0)

    session.close()

    # sanitize metadata database...
    if use_meta_db:
        db.execute(
            "delete from meta_db.package where name not in (select name from package)"
        )
        db.commit()
        db.execute("detach database meta_db")


def build_index(name, last_serial, releases, web_root):
    """
    create the index.html page for the given name/releases/last_serial
    """

    index_html = list()

    versions = sorted(map(lambda v: (parse(v), v), releases.keys()))

    for _, r in versions:
        for f in releases[r]:
            path = urlparse(f["url"]).path[1:]

            # if file is present, we add it to the index regardless of the filters
            p = web_root / path
            if not p.is_file():
                continue

            if f["requires_python"]:
                req = escape(f["requires_python"])
                index_html.append(
                    f"""\
<a href="../../{path}#sha256={f['digests']['sha256']}" data-requires-python="{req}">{f['filename']}</a><br/>
"""
                )
            else:
                index_html.append(
                    f"""\
<a href="../../{path}#sha256={f['digests']['sha256']}">{f['filename']}</a><br/>
"""
                )
    index_html = (
        f"""\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for {name}</title>
  </head>
  <body>
    <h1>Links for {name}</h1>
"""
        + "".join(index_html)
        + f"""\
  </body>
</html>
<!--SERIAL {last_serial}-->\
"""
    )

    return index_html


def compute_requirements(db, blacklist=set()):
    """
    analyse les requirements pour ne pas exclure des packages indispensables
    """

    conditions = defaultdict(set)
    for iteration in range(1, 10):
        added = 0
        name_cond_pattern = re.compile(r"^(.+?)(?:\s\((.+)\))?$")
        for name, dist in db.execute("select name, requires_dist from requires_dist"):

            # ne pas considérer des dépendances de paquets qu'on ne veut pas
            if name in blacklist:
                continue

            m = dist.split(";", maxsplit=2)
            if len(m) > 1:
                # ignore les requirements qui déclarent une extra feature dependency
                # https://setuptools.readthedocs.io/en/latest/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies
                extra = m[1].replace(" ", "")
                if extra.find("extra==") != -1:
                    continue

            m = name_cond_pattern.match(m[0].strip())

            dist = m.group(1)
            cond = m.group(2)

            # on ignore les requirements d'extra feature
            if dist.find("[") != -1:
                continue

            if dist in blacklist:
                # la dépendance de name est blacklistée, on blackliste name aussi
                logger.debug(f"{name} blacklisted because of {dist}")
                blacklist.add(name)
                added += 1
                if name in conditions:
                    del conditions[name]
            else:
                if cond:
                    conditions[dist].add(cond)

        if added:
            logger.info(
                f"iteration {iteration}: packages added to the blacklist: {added}"
            )
        else:
            break

    # f = pathlib.Path("conditions.log")
    # f.open("w").write("".join(sorted(f"{i:30} {j}\n" for i, j in conditions.items())))
    logger.info(f"packages with requirement conditions: {len(conditions)}")

    return conditions


def get_cached_list(filename, getter):
    f = pathlib.Path(filename + ".cache")
    if f.is_file():
        resource = pickle.load(f.open("rb"))
    else:
        resource = getter()
        pickle.dump(resource, f.open("wb"), pickle.HIGHEST_PROTOCOL)
    return resource


def download_packages(
    db,
    web_root,
    dry_run=False,
    whitelist_cond=None,
    only_whitelist=False,
    no_index=False,
    keep_releases=3,
    remove_filtered_releases=False,
    save_progress=True,
):

    if only_whitelist:
        # download only the listed packages
        blacklist = set()
        conditions = defaultdict(list)
    else:
        # the blacklist and calculated requirement conditions
        blacklist, _ = get_cached_list("blacklist", lambda: get_blacklist(db))
        conditions = get_cached_list(
            "conditions", lambda: compute_requirements(db, blacklist)
        )

    # the whitelist
    if (isinstance(whitelist_cond, tuple) or isinstance(whitelist_cond, list)) and len(
        whitelist_cond
    ) != 0:
        whitelist = defaultdict(set)
        canonicalize_named_names = dict(
            (canonicalize_name(name), name)
            for name, in db.execute("select name from list_packages")
        )
        for cond in whitelist_cond:
            m = re.match(r"^([^=<>~]+)(.*)?$", cond)
            name = canonicalize_name(m.group(1))
            if name in canonicalize_named_names:
                name = canonicalize_named_names[name]
            whitelist[name].add(m.group(2))

        for name, conds in whitelist.items():
            logger.info(f"whitelist: {name} {conds}")
            conditions[name] = set(conditions[name]).union(conds)
            if name in blacklist:
                logger.info(f"unblacklisting {name}")
                blacklist.remove(name)

    # initialize plugins borrowed and adapted from bandersnatch
    filter_releases = latest_name.LatestReleaseFilter()
    filter_releases.configuration = {"latest_release": {"keep": keep_releases}}
    filter_releases.initialize_plugin()

    filter_platform = filename_name.ExcludePlatformFilter()
    filter_platform.configuration = {
        "blacklist": {"platforms": "windows macos freebsd"}
    }
    filter_platform.initialize_plugin()

    exist = 0
    download = 0
    download_size = 0
    processed = 0

    removed_files = 0
    removed_size = 0

    if save_progress:
        # add the "done" list to the blacklist (faster)
        z = web_root / "done"
        if z.exists():
            for i in z.open():
                blacklist.add(i.strip())

    session = requests.Session()

    with CtrlC(True) as ctrl_c:

        try:
            count = fetch_value(db, "select count(*) from package")
            progress = 0

            for name, last_serial, version in db.execute(
                "select name,last_serial,version from package"
            ):

                progress += 1
                if progress % 5000 == 0:
                    logger.info(
                        f"packages processed: {progress}/{count} {progress / count * 100:.1f}%"
                    )

                # if a whitelist is provided, ignore blacklist and other packages
                if only_whitelist:
                    if name not in conditions:
                        continue
                elif name in blacklist:
                    continue

                logger.debug(f"process {name}")

                # rebuild the JSON metadata (only needed fields)
                # this is equivalent to:
                #   data = json.loads(metadata)
                #   info = data['info']
                #   last_serial = data['last_serial']
                #   releases = data['releases']
                info = {"name": name, "version": version}
                releases = defaultdict(list)
                sql = "select release,filename,url,size,requires_python,sha256_digest,python_version from file where name=?"  # noqa
                for row in db.execute(sql, (name,)):
                    releases[row[0]].append(
                        {
                            "filename": row[1],
                            "url": row[2],
                            "size": row[3],
                            "requires_python": row[4],
                            "digests": {"sha256": row[5]},
                            "python_version": row[6],
                        }
                    )

                unfiltered_releases = releases.copy()
                removed_desc = []

                filter_releases.filter(
                    info, releases, conditions.get(name, None), removed_desc
                )
                filter_platform.filter(info, releases, removed_desc)

                if remove_filtered_releases:
                    # clean unwanted releases (too old, by platform)
                    for desc in removed_desc:
                        filename = web_root / urlparse(desc["url"]).path[1:]

                        if filename.exists():
                            removed_files += 1
                            removed_size += filename.stat().st_size
                            if not dry_run:
                                filename.unlink()
                                try:
                                    filename.parent.rmdir()
                                except OSError:
                                    # not empty, should not occur
                                    pass
                            logger.debug(f"unlink filtered {filename}")

                else:
                    # download selected files in selected releases
                    for r in releases.values():
                        for f in r:
                            url = f["url"]
                            path = urlparse(url).path[1:]

                            filename = web_root / path
                            if filename.exists() and filename.stat().st_size == int(
                                f["size"]
                            ):
                                exist += 1
                            else:
                                download += 1
                                download_size += int(f["size"])

                                logger.info(
                                    f"download {name}  {f['filename']}  {f['size']} bytes"
                                )
                                logger.debug(f"file: {filename}")

                                if not dry_run:
                                    if filename.parent.is_file():
                                        filename.parent.unlink()
                                    filename.parent.mkdir(exist_ok=True, parents=True)

                                    with session.get(url, stream=True) as r:
                                        with filename.open("wb") as f:
                                            shutil.copyfileobj(r.raw, f)

                if not no_index:
                    # build the index.html file
                    simple_index = build_index(
                        name, last_serial, unfiltered_releases, web_root
                    )

                    if not dry_run:
                        p = web_root / "simple" / canonicalize_name(name) / "index.html"
                        p.parent.mkdir(exist_ok=True, parents=True)
                        with p.open("w") as fp:
                            fp.write(simple_index)

                processed += 1

                # save progress
                if save_progress:
                    with open(web_root / "done", "a") as fp:
                        print(name, file=fp)

        except KeyboardInterrupt:
            logger.warning("interrupt")

        except Exception as e:
            logger.error(f"{e!r}")
            raise e

        logger.info(
            f"processed={processed} exist={exist} download={download} download_size={hf.format_size(download_size)} ({download_size} bytes)"
        )  # noqa

        if remove_filtered_releases:
            logger.info(f"files removed: {removed_files}")
            logger.info(
                f"space recovered: {hf.format_size(removed_size)} ({removed_size} bytes)"
            )

        if ctrl_c:
            logger.warning("terminated")
            exit(0)


def remove_orphans(db, web_root, dry_run):
    """
    find and delete files that are no longer listed in any release of any project
    """

    p = web_root
    lp = len(p.as_posix())

    logger.info(f"looking for orphan files in {p}")

    removed_files = 0
    removed_size = 0
    p /= "packages"
    for f in p.glob("**/*"):
        if f.is_file():
            url = "https://files.pythonhosted.org" + f.as_posix()[lp:]
            # nota: indexing by url is important here...
            n = fetch_value(db, "select count(*) from file where url=?", (url,))
            if n == 0:
                removed_files += 1
                removed_size += f.stat().st_size
                if not dry_run:
                    f.unlink()
                # problem: globbing fails is we remove the current directory
                # try:
                #     f.parent.rmdir()
                # except OSError:
                #     # not empty, should not occur
                #     pass
                logger.debug(f"unlink orphan {f}")

    logger.info(f"files removed: {removed_files}")
    logger.info(
        f"space recovered: {hf.format_size(removed_size)} ({removed_size} bytes)"
    )


def run(update=False, metadata=False, packages=False, **kwargs):
    """
    effective main() function
    """

    use_meta_db = kwargs["raw"]
    pypi_uri = "https://pypi.org/pypi"
    if kwargs["test"]:
        pypi_uri = "https://test.pypi.org/pypi"

    db = sqlite3.connect(kwargs["db"])
    client = xmlrpc.client.ServerProxy(pypi_uri)

    create_db(db, use_meta_db)

    web_root = pathlib.Path(kwargs["web"]).expanduser()
    dry_run = kwargs["dry_run"]
    no_index = kwargs["no_index"]
    keep_releases = kwargs["keep_releases"]

    whitelist = kwargs["add"]
    for fn in kwargs["add_list"]:
        whitelist = list(whitelist)
        with open(fn) as fp:
            for r in fp:
                whitelist.append(r.strip())

    if kwargs["remove_orphans"]:
        remove_orphans(db, web_root, dry_run)

    elif kwargs["remove_unwanted"]:
        only_wl = len(whitelist) != 0
        download_packages(
            db,
            web_root,
            dry_run,
            whitelist,
            only_wl,
            no_index,
            keep_releases,
            True,
            False,
        )

    elif not update and not metadata and not packages:
        logger.warning("nothing to do, did you mess up -u, -m, -p ?")
    else:
        if update:
            logger.info("*** update project list ***")
            update_list(client, db)

        if metadata:
            if kwargs["whitelist"]:
                logger.info("*** download metadata (whitelist) ***")
                download_metadata(db, use_meta_db, pypi_uri, whitelist)
            else:
                logger.info("*** download metadata ***")
                download_metadata(db, use_meta_db, pypi_uri)

            # remove the file where we save the download progress
            z = web_root / "done"
            if z.exists():
                z.unlink()

        if packages:
            logger.info("*** download packages ***")
            download_packages(
                db,
                web_root,
                dry_run,
                whitelist,
                kwargs["whitelist"],
                no_index,
                keep_releases,
                False,
                not kwargs["force"],
            )

    db.close()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, default=False, help="verbose mode")
@click.option(
    "-nv", "--non-verbose", is_flag=True, default=False, help="no so much verbose"
)
@click.option("-lf", "--logfile", help="logfile")
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="dry run (do not download packages)",
)
@click.option(
    "-u", "--update", is_flag=True, default=False, help="update list of projects"
)
@click.option(
    "-m", "--metadata", is_flag=True, default=False, help="download JSON metadata"
)
@click.option("-p", "--packages", is_flag=True, default=False, help="mirror packages")
@click.option(
    "-w",
    "--whitelist",
    is_flag=True,
    default=False,
    help="ONLY process projects within the whitelist",
)
@click.option("-a", "--add", multiple=True, help="project name")
@click.option(
    "-r",
    "-A",
    "--add-list",
    multiple=True,
    help="project list",
    type=click.Path(exists=True),
)
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
@click.option("--remove-orphans", is_flag=True, help="find and remove orphan files")
@click.option("--remove-unwanted", is_flag=True, help="find and remove unwanted files")
@click.option(
    "--raw", is_flag=True, help="store raw JSON metadata in a separated database"
)
@click.option("--test", is_flag=True, help="use test.pypi.org")
@click.option("--no-index", is_flag=True, help="do not create /simple/xxx/index.html")
@click.option(
    "-k",
    "--keep-releases",
    default=3,
    help="releases to keep",
    type=int,
    show_default=True,
)
@click.option(
    "--force", is_flag=True, help="do not use/save progress when mirroring packages"
)
def main(**kwargs):
    """
    Python Package Intelligent Mirroring

    Mirrors the official Python Package Index (https://PyPI.org) with maximum control.

    \b
    Example:
        pypim.py -lf mirror.log -nv -u -m -p -a PyXB==1.2.3 -A <(pip3 freeze)
    """

    start_time = time.time()
    init_logger(kwargs)

    kwargs["web"] = os.path.expanduser(kwargs["web"])
    if kwargs["db"] is None:
        kwargs["db"] = os.path.join(kwargs["web"], "pypi.db")
    else:
        kwargs["db"] = os.path.expanduser(kwargs["db"])

    logger.info("PyPIM started")
    logger.debug(f"args {kwargs!r}")

    run(**kwargs)

    elapsed_time = time.time() - start_time
    logger.info(f"PyPIM completed in {timedelta(seconds=elapsed_time)}")


if __name__ == "__main__":
    main()
