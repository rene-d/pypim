#! /usr/bin/env python3

"""
xxx
"""

import click
import sqlite3
import pathlib
from urllib.parse import urlparse
import humanfriendly
import pickle
from plugins.blacklist import get_blacklist
import os.path


def query(db, sql, args=(), sep=" "):
    req = db.execute(sql, args)

    widths = [len(desc[0]) for desc in req.description]

    rows = req.fetchall()

    for row in rows:
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(str(col)))

    fmt = sep.join("{:" + str(i) + "}" for i in widths)
    print(fmt.format(*[desc[0] for desc in req.description]))
    print(fmt.format(*["-" * w for w in widths]).replace("|", "+"))

    for row in rows:
        if row[0] == 1:
            pre = "\033[31m"
        else:
            pre = "\033[0;32;m"
        print(pre + fmt.format(*row) + "\033[0m")


def pretty(size):
    if size is None:
        return "NULL"
    try:
        return humanfriendly.format_size(size)
    except Exception as e:
        print(size, type(size), e)
        return str(size)


def get_cached_list(filename, getter):
    f = pathlib.Path(filename + ".cache")
    if f.is_file():
        resource = pickle.load(f.open("rb"))
    else:
        resource = getter()
        pickle.dump(resource, f.open("wb"), pickle.HIGHEST_PROTOCOL)
    return resource


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-a", "--overall", is_flag=True, default=False, help="overall")
@click.option("-u", "--update", is_flag=True, default=False, help="update")
@click.option(
    "--web",
    default="~/data/pypi",
    help="mirror directory",
    type=click.Path(dir_okay=True),
    show_default=True,
)
@click.option(
    "--db",
    "db_name",
    help="packages database",
    type=click.Path(file_okay=True),
    show_default=True,
)
@click.option("-l", "--limit", default=200, help="limit", show_default=True)
def main(overall, update, web, db_name, limit):

    web = os.path.expanduser(web)
    if db_name is None:
        db_name = os.path.join(web, "pypi.db")
    else:
        db_name = os.path.expanduser(db_name)

    if overall:
        db_file = sqlite3.connect(db_name)
        update = False
    else:
        db_file = sqlite3.connect("files.db")

    db = sqlite3.connect(db_name)
    web = pathlib.Path(web)

    blacklist, _ = get_cached_list("blacklist", lambda: get_blacklist(db))

    if update:
        db_file.execute("drop table if exists file")
        db_file.execute("create table file (name,version,size integer,filename)")

        for name, version, size, url, filename in db.execute(
            "select name,release,size,url,filename from file"
        ):
            url = urlparse(url).path[1:]
            path = web / url
            if path.exists():
                db_file.execute(
                    "insert into file values (?,?,?,?)", (name, version, size, filename)
                )

        db_file.commit()

    db.close()

    db_file.create_function("hf", 1, pretty)
    db_file.create_function("url", 1, "https://pypi.org/project/{}/".format)
    db_file.create_function("url2", 2, "https://pypi.org/project/{}/{}".format)
    db_file.create_function("bl", 1, lambda name: name in blacklist)

    db_file.executescript(
        """\
drop view fat;
create view if not exists fat as
    select name, sum(size) as size, count(distinct version) as versions, count(*) files
    from file
    group by name
    having count(distinct version) >= 256 or sum(size) >= 1048576;
"""
    )

    print("Total size")
    query(db_file, "select hf(sum(size)) from file")

    # print("Blacklisted size")
    # query(db_file, "select hf(sum(size)) from file where bl(name)=1")

    print(f"First {limit} fat projects")
    query(
        db_file,
        "select bl(name) as bl,name,hf(size) as size,versions,files,url(name) as url "
        "from fat order by fat.size desc limit ?",
        (limit,),
    )

    # for name, size in db_file.execute("select name,size from fat  order by size desc limit ?", (limit,)):
    #     query(db_file, "select name,version,hf(sum(size)),count(*),url2(name,version) from file "
    #                    "where name=? group by name,version order by sum(size) ", (name,))

    db_file.close()


if __name__ == "__main__":
    main()
