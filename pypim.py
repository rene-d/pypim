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
from html import escape
import pathlib
import re
import pickle
from plugins import filename_name, latest_name


# packages too big or updated too frequently
TOOFAT = [
    "cupy", "cupy-%",  # CuPy : NumPy-like API accelerated with CUDA
    "mxnet", "mxnet-%",  # Apache MXNet is a deep learning framework
    "tf-nightly%",  # nightly TensorFlow
]

# threats detected by Kaspersky
THREATS = [
    "Cuckoo",
    "secret_miner",
    "androwarn",
    "thug",
    "gpgmailencrypt",
    "crackmapexec",
    "escposprinter",
    "kayobe",
    "kalabash-amavis",
    "modoboa_amavis",
    "avocado-framework-plugin-vt",
    "grr-response-test",
    "modoboa-amavis",
    "edeposit.amqp.antivir",
    "jabbercracky",
    "ecxclient",
    "test-typo-pypi",
    "rigpy",
    "vxstreamlib",
    "Pythonic",
    "formasaurus",
    "pytagora",
    "pytagora2",
    "plainbox",
    "duxlot",
    "babysploit",
    "manim",
    "csirtg_mail",
    "lda",
    "scrapyc",
]

SCAM = [
    # useless when offline
    "aws%",
    "azure%",
    "cmsplugin%",
    "github%",
    "google-cloud%",
    "mastercard%",
    # bullshit (among tons not listed...)
    "0",
    "0-._.-._.-._.-._.-._.-._.-0"
    "0.0.1",
    "0-core-client",
    "aliyun%",
    "nester%",
    "raptus%",
    "Bravo",
    # requirements badly written
    "pcu",
    "bareasgi-cors",
    "bareasgi-graphql-next",
    "candid",
    "wechat-mchpay",
    "eGo",
    "Flask-Z3950",
]


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
        logging.debug("enter CtrlC")
        self.ctrl_c = False

        def _handler(sig, frame):
            nonlocal self
            self.ctrl_c = True
            print('\nCtrlC: exit requested... another ^C to force')
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            if self.throw:
                raise KeyboardInterrupt

        signal.signal(signal.SIGINT, _handler)
        return self

    def __exit__(self, type, value, traceback):
        logging.debug("exit CtrlC")
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
    # logging.debug(f"{sql}")
    # logging.debug(f"{params!r}")
    if not isinstance(params, tuple) and not isinstance(params, list):
        params = (params,)
    row = db.execute(sql, params).fetchone()
    # logging.debug(f"{row!r}")
    if row and isinstance(row[0], int):
        return int(row[0])
    else:
        return default_value


def create_db(db, db_json):
    """
    initalize the both databases
        db          decoded metadata into SQL tables
        db_json     the raw metadata in JSON format
    """

    db_json.executescript("""\
-- package JSON metadata
create table if not exists package (
    name            text not null primary key,
    last_serial     integer not null,
    metadata        blob
);
""")
    logging.debug("metadata database initialized")

    db.executescript("""\
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
    -- downloads
    filename        text,
    has_sig         text,
    -- md5_digest
    packagetype     text,
    python_version  text,
    requires_python text,
    size            integer not null,
    upload_time     datetime,
    url             text
);

-- indices
create unique index if not exists package_uk on package (name,last_serial);
create unique index if not exists release_pk on release (name,release);
create index if not exists release_fk on release (name);
create index if not exists file_fk on file (name,release);
""")
    logging.debug("packages database initialized")


def delete_package(db, name):
    """
    delete a package from all the tables
    """
    cur = db.cursor()
    cur.execute("delete from file where name=?", (name,))
    cur.execute("delete from release where name=?", (name,))
    cur.execute("delete from requires_dist where name=?", (name,))
    cur.execute("delete from classifier where name=?", (name,))
    cur.execute("delete from package where name=?", (name,))
    cur.close()


def add_package(db, orig_name, data):
    """
    add a package from the JSON metadata
    """

    cur = db.cursor()

    info = data["info"]
    name = info["name"]

    if name != orig_name:
        logging.eror(f"{name} != {orig_name}")
        assert name == orig_name

    classifiers = info["classifiers"]
    requires_dist = info["requires_dist"]

    del info["classifiers"]
    del info["downloads"]  # unused
    del info["project_urls"]  # unused
    del info["requires_dist"]

    # ajoute le last_serial (plutôt que dans une table séparée)
    last_serial = data["last_serial"]
    info['last_serial'] = last_serial

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

    for release, files in data["releases"].items():

        # add release
        insert_row(cur, "release", {"name": name, "release": release})

        # add distribution files
        for file in files:
            file["name"] = name
            file["release"] = release

            del file["digests"]
            del file["downloads"]
            del file["md5_digest"]

            insert_row(cur, "file", file)

    cur.close()

    logging.debug(f"package added: {name} {last_serial}")

    return last_serial


def update_list(client, db, db_json, clear_ignore=False):
    """
    download and update the list of packages with their last_serial
    """

    db_serial = fetch_value(db, "select last_serial from pypi_last_serial")
    logging.info(f"db serial: {db_serial}")

    # ----- changelog_last_serial -----
    last_serial = client.changelog_last_serial()
    last_serial_time = int(time.time())
    logging.info(f"server serial: {last_serial}")

    if last_serial == db_serial:
        logging.info("database is up to date")
    else:
        logging.info(f"update events: {last_serial - db_serial}")
        db.execute("delete from pypi_last_serial")
        db.execute("insert into pypi_last_serial (last_serial, timestamp) values (?,?)",
                   (last_serial, last_serial_time))

        # ----- list_packages_with_serial -----
        packages = client.list_packages_with_serial()
        logging.info("packages listed: %d", len(packages))
        # serials = packages.values()
        # logging.info("min serial: %d", min(serials))
        # logging.info("max serial: %d", max(serials))

        ignore_flags = defaultdict(lambda: False)
        if not clear_ignore:
            # fetch the ignore flags
            for row in db.execute("select name,ignore from list_packages"):
                ignore_flags[row[0]] = row[1]

        # replace the list of packages with the fresh one, ignore flag preserved
        logging.info("refill table list_packages")
        old_max_serial = fetch_value(db, "select max(last_serial) from list_packages")
        db.execute("delete from list_packages")
        db.executemany("insert into list_packages (name,last_serial,ignore) values (?,?,?)",
                       [(name, last_serial, ignore_flags[name])
                        for name, last_serial in packages.items()])

        db.execute("update list_packages set ignore=false where last_serial>?", (old_max_serial,))

        updated = fetch_value(db, "select count(*) from list_packages where last_serial>?", old_max_serial)
        logging.info(f"updated: {updated}")

        with open("updated.txt", "wt") as fp:
            for row in db.execute("select name from list_packages where last_serial>?", (old_max_serial,)):
                name = row[0]
                print(name, file=fp)
                logging.debug(f"updated: {name}")

    # print some stats
    total = fetch_value(db, "select count(*) from list_packages")
    logging.info(f"packages: {total}")

    ignored = fetch_value(db, "select count(*) from list_packages where ignore")
    logging.info(f"ignored: {ignored}")

    zz = fetch_value(db, "select max(last_serial) from package")
    xx = fetch_value(db, "select count(*) from list_packages where last_serial>?", (zz,))
    logging.info(f"download: {xx}")

    db.commit()


def download_metadata(db, db_json):
    """
    download and parse JSON metadata

    only needed (missing and updated) packages will be downloaded

    the raw JSON metadata is stored into db_json
    the metadata is parsed and stored into tables of db
    """

    # requests session to download the JSON metadata
    session = requests.Session()

    sql = """\
select name from package where name not in (select name from list_packages)
"""
    for name, in db.execute(sql).fetchall():
        delete_package(db, name)

    with CtrlC() as ctrl_c:

        # fetch the list of packages that are:
        #  - not ignored
        #  - modified (different last_serial) or missing
        sql = """\
select lp.name,lp.last_serial,p.last_serial
from list_packages as lp
left join package as p on lp.name=p.name
where lp.ignore=false
  and (p.last_serial<lp.last_serial
       or p.name is null)
order by lp.last_serial
"""
        rows = db.execute(sql).fetchall()
        logging.info(f"metadata to download: {len(rows)}")

        processed = 0

        for row in rows:

            if ctrl_c:
                break

            name = row[0]
            logging.info(f"bump package {name} from serial {row[2]} to {row[1]}")

            try:
                url = f"https://pypi.org/pypi/{name}/json"
                req = session.get(url, headers={"Content-Type": "application/json"})
                if req.status_code == 404:
                    # weird... package is listed in list_packages
                    # but not accessible from pypi.org
                    # probably when package has no release
                    raise FileNotFoundError

                data = req.content

                # parse and store the metadata
                delete_package(db, name)
                last_serial = add_package(db, name, json.loads(data))

                # store the raw JSON
                db_json.execute("replace into package (name,last_serial,metadata) values (?,?,?)",
                                (name, last_serial, data))

                db_json.commit()
                db.commit()

            except (sqlite3.IntegrityError, sqlite3.InterfaceError,
                    json.decoder.JSONDecodeError, Exception) as e:
                logging.error(f"error {name} {e!r}")
                db.execute("update list_packages set ignore=true where name=?", (name, ))
                db.commit()

            processed += 1

    logging.info(f"packages processed: {processed}")
    if len(rows) != processed:
        logging.warning(f"packages remainging: {len(rows) - processed}")

    session.close()


def build_index(name, last_serial, releases):
    """
    create the index.html page for the given name/releases/last_serial
    """

    index_html = list()

    versions = sorted(map(lambda v: (parse(v), v), releases.keys()))

    for _, r in versions:
        for f in releases[r]:
            url = f['url']
            url = url[len("https://files.pythonhosted.org/"):]

            if f['requires_python']:
                req = escape(f['requires_python'])
                index_html.append(f"""\
<a href="../../{url}#sha256={f['digests']['sha256']}" data-requires-python="{req}">{f['filename']}</a><br/>
""")
            else:
                index_html.append(f"""\
<a href="../../{url}#sha256={f['digests']['sha256']}">{f['filename']}</a><br/>
""")
    index_html = f"""\
<!DOCTYPE html>
<html>
  <head>
    <title>Links for {name}</title>
  </head>
  <body>
    <h1>Links for {name}</h1>
""" + "".join(index_html) + f"""\
  </body>
</html>
<!--SERIAL {last_serial}-->\
"""
    return index_html


def normalize(name):
    """
    normalize a package name: lowercase, only hyphen
    """
    name = name.lower()
    name = name.replace("_", "-")
    name = name.replace(".", "-")
    return name


def compute_requirements(db, blacklist=set()):
    """
    analyse les requirements pour ne pas exclure des packages indispensables
    """

    conditions = defaultdict(set)
    for iteration in range(1, 10):
        added = 0
        name_cond_pattern = re.compile(r"^(.+?)(?:\s\((.+)\))?$")
        for name, dist, in db.execute("select name, requires_dist from requires_dist"):

            # ne pas considérer des dépendances de paquets qu'on ne veut pas
            if name in blacklist:
                continue

            m = dist.split(";", maxsplit=2)
            if len(m) > 1:
                # ignore les requirements qui déclare une extra feature dependency
                # https://setuptools.readthedocs.io/en/latest/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies
                extra = m[1].replace(" ", "")
                if extra.find("extra==") != -1:
                    continue

            m = name_cond_pattern.match(m[0].strip())

            dist = m.group(1)
            cond = m.group(2)

            # on ignore les requirements d'extra feature
            if dist.find('[') != -1:
                continue

            if dist in blacklist:
                # la dépendance de name est blacklistée, on blackliste name aussi
                logging.debug(f"{name} blacklisted because of {dist}")
                blacklist.add(name)
                added += 1
                if name in conditions:
                    del conditions[name]
            else:
                if cond:
                    conditions[dist].add(cond)

        if added:
            logging.info(f"iteration {iteration}: packages added to the blacklist: {added}")
        else:
            break

    f = pathlib.Path("conditions.txt")
    f.open("w").write("".join(sorted(f"{i:30} {j}\n" for i, j in conditions.items())))
    logging.info(f"packages with requirement conditions: {len(conditions)}")

    return conditions


def get_blacklist(db):
    """
    """

    blacklist = set()
    reason = defaultdict(list)

    def filter(title, *requests):
        nonlocal blacklist
        excluded = set()
        for sql in requests:
            logging.debug(f"sql: {sql}")
            excluded = excluded.union(set(name for name, in db.execute(sql).fetchall()))
        for name in excluded:
            reason[name].append(title)
        blacklist = blacklist.union(excluded)
        logging.info(f"{title:>20}: {len(excluded):6}   blacklist:{len(blacklist):6}")

    # remove ignored packaged (packages without release)
    filter("ignored", 'select name from list_packages where ignore')

    # remove packaged listed in TOOFAT
    sql = "select name from list_packages where 0=1"
    sql += "\n".join(f' or name like "{pattern}"' for pattern in TOOFAT)
    filter("toobig", sql)

    # remove packaged listed in THREATS
    sql = "select name from list_packages where 0=1"
    sql += "\n or name in (" + ",".join(f'"{thread}"' for thread in THREATS) + ")"
    filter("threats", sql)

    # remove packaged listed in SCAM
    sql = "select name from list_packages where 0=1"
    sql += "\n".join(f' or name like "{pattern}"' for pattern in SCAM)
    filter("scam", sql)

    # remove Plone (CMS), Django (web), Odoo (ERP) : too many packages
    filter("Framework :: Plone",
           "select distinct name from classifier where classifier like 'Framework :: Plone%'",
           "select name from list_packages where name like 'Products.%' or name like 'collective.%'")

    filter("Framework :: Django",
           "select distinct name from classifier where classifier like 'Framework :: Django'",
           "select name from list_packages where name like 'django%'")

    filter("Framework :: Odoo",
           "select distinct name from classifier where classifier like 'Framework :: Odoo'",
           "select name from list_packages where name like 'odoo%'")

    # remove packages without file
    filter("without file",
           "select name from package where name not in (select distinct name from file)")

    # filter("description UNKNOWN", 'select name from package where description="UNKNOWN"')
    # filter("missing description", 'select name from package where description=""')
    # sql = 'select name from package '
    # sql += 'where (description="" or description="UNKNOWN" or description is null)'
    # sql += '  and (summary="" or summary="UNKNOWN" or summary is null)'
    # filter("bad description", sql)

    # filter(f"upload_time < {MIN_DATE}",
    #        f'select name from file group by name having max(upload_time) < "{MIN_DATE}"')

    return blacklist, reason


def get_cached_list(filename, getter):
    f = pathlib.Path(filename + ".cache")
    if f.is_file():
        resource = pickle.load(f.open("rb"))
    else:
        resource = getter()
        pickle.dump(resource, f.open("wb"), pickle.HIGHEST_PROTOCOL)
    return resource


def download_packages(db, db_json, web_root, dry_run=False, whitelist_cond=None, only_whitelist=False):

    # the root of the mirror
    web_root = pathlib.Path(web_root).expanduser()

    if only_whitelist:
        # download only the listed packages
        blacklist = set()
        conditions = defaultdict(list)
    else:
        # the blacklist and calculated requirement conditions
        blacklist, _ = get_cached_list("blacklist", lambda: get_blacklist(db))
        conditions = get_cached_list("conditions", lambda: compute_requirements(db, blacklist))

    # the whitelist
    if (isinstance(whitelist_cond, tuple) or isinstance(whitelist_cond, list)) and len(whitelist_cond) != 0:
        whitelist = defaultdict(set)
        normalized_names = dict((normalize(name), name) for name, in db.execute("select name from list_packages"))
        for cond in whitelist_cond:
            m = re.match(r"^([^=<>~]+)(.*)?$", cond)
            name = normalized_names[normalize(m.group(1))]
            whitelist[name].add(m.group(2))

        for name, conds in whitelist.items():
            logging.info(f"whitelist: {name} {conds}")
            conditions[name] = set(conditions[name]).union(conds)
            if name in blacklist:
                del blacklist[name]

    # initialize plugins borrowed from bandersnatch
    filter_releases = latest_name.LatestReleaseFilter()
    filter_releases.configuration = {"latest_release": {"keep": 3}}
    filter_releases.initialize_plugin()

    filter_platform = filename_name.ExcludePlatformFilter()
    filter_platform.configuration = {"blacklist": {"platforms": "windows macos freebsd"}}
    filter_platform.initialize_plugin()

    exist = 0
    download = 0
    download_size = 0
    index = 0

    # ajoute la liste des "done" à la blacklist
    z = pathlib.Path("done.txt")
    if z.exists():
        for i in z.open():
            blacklist.add(i.strip())

    downloaded = open("downloaded.txt", "a")

    session = requests.Session()

    with CtrlC(True):
        try:

            for name, data in db_json.execute("select name, metadata from package"):

                # if a whitelist is provided, ignore blacklist and other packages
                if only_whitelist:
                    if name not in conditions:
                        continue
                elif name in blacklist:
                    continue

                logging.debug(f"process {name}")

                data = json.loads(data)
                info = data['info']
                last_serial = data['last_serial']
                releases = data['releases']

                filter_releases.filter(info, releases, conditions.get(name, None))
                filter_platform.filter(info, releases)

                h = build_index(name, last_serial, releases)
                index += 1

                if not dry_run:
                    p = web_root / "simple" / normalize(name) / "index.html"
                    p.parent.mkdir(exist_ok=True, parents=True)
                    with p.open("w") as fp:
                        fp.write(h)

                for r in releases.values():
                    for f in r:
                        url = f['url']
                        url = url[len("https://files.pythonhosted.org/"):]

                        file = web_root / url
                        if file.exists() and file.stat().st_size == int(f['size']):
                            exist += 1
                        else:
                            download += 1
                            download_size += int(f["size"])

                            logging.info(f"download {name}  {f['filename']}  {f['size']} bytes")
                            logging.debug(f"file: {file}")

                            print(f['url'], file=downloaded)

                            if not dry_run:
                                if file.parent.is_file():
                                    file.parent.unlink()
                                file.parent.mkdir(exist_ok=True, parents=True)
                                with file.open("wb") as fp:
                                    fp.write(session.get(f['url']).content)

                with open("done.txt", "a") as fp:
                    print(name, file=fp)

        except Exception as e:
            logging.error(f"{e!r}")
            raise e

        except KeyboardInterrupt:
            logging.warning("interrupt")

    downloaded.close()

    print(f"index={index} exist={exist} download={download} download_size={download_size}")


def run(update=False, metadata=False, packages=False,  **kwargs):

    db = sqlite3.connect("pypi.db")
    db_json = sqlite3.connect("pypi_json.db")
    client = xmlrpc.client.ServerProxy('https://pypi.org/pypi')

    create_db(db, db_json)

    white_list = kwargs["add"]
    for fn in kwargs["add_list"]:
        white_list = list(white_list)
        with open(fn) as fp:
            for r in fp:
                white_list.append(r.strip())

    if not update and not metadata and not packages and len(white_list) == 0:
        logging.warning("nothing to do, did you mess up -u, -m, -p or -a/-A ?")
    else:
        if update:
            update_list(client, db, db_json)

        if metadata:
            download_metadata(db, db_json)

        if packages or len(white_list) != 0:
            web_root = kwargs["web"]
            dry_run = kwargs["dry_run"]
            only_wl = not packages
            download_packages(db, db_json, web_root, dry_run, white_list, only_wl)

    db_json.close()
    db.close()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, default=False, help="verbose mode")
@click.option("-nv", "--non-verbose", is_flag=True, default=False, help="no so much verbose")
@click.option("-n", "--dry-run", is_flag=True, default=False, help="dry run")
@click.option("-u", "--update", is_flag=True, default=False, help="update list of packages")
@click.option("-m", "--metadata", is_flag=True, default=False, help="download JSON metadata")
@click.option("-p", "--packages", is_flag=True, default=False, help="mirror packages")
@click.option("-a", "--add", multiple=True, help="package name (trigger mirroring)")
@click.option("-A", "--add-list", multiple=True, help="package list (trigger mirroring)",
              type=click.Path(exists=True))
@click.option("--web", default="~/data/pypi", help="mirror directory")
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
    elif kwargs["non_verbose"]:
        logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", datefmt="%H:%M:%S", level=logging.WARNING)
    else:
        logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", datefmt="%H:%M:%S", level=logging.INFO)

    run(**kwargs)


if __name__ == "__main__":
    main()
