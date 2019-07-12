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


def query(db, sql, args=()):
    rows = db.execute(sql, args).fetchall()
    w = [0] * 10
    for row in rows:
        for i, col in enumerate(row):
            w[i] = max(w[i], len(str(col)))

    for row in rows:
        r = [""] * 10
        for i, col in enumerate(row):
            r[i] = "%*s" % (- w[i] - 1, str(col))
        if row[0] == 1:
            pre = "\033[31m"
        else:
            pre = "\033[0;32;m"
        print(pre + "".join(r) + "\033[0m")


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
    "--db", "db_name",
    default="pypi.db",
    help="packages database",
    type=click.Path(file_okay=True),
    show_default=True,
)
@click.option(
    "-l", "--limit",
    default=200,
    help="limit",
    show_default=True,
)
def main(overall, update, web, db_name, limit):

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

    db_file.create_function("hf", 1, humanfriendly.format_size)
    db_file.create_function("url", 1, "https://pypi.org/project/{}/".format)
    db_file.create_function("bl", 1, lambda name: name in blacklist)

    print("Total size")
    query(db_file, "select hf(sum(size)) from file")

    print("Blacklisted size")
    query(db_file, "select hf(sum(size)) from file where bl(name)=1")

    print(f"First {limit} fat projects")
    query(db_file, "select bl(name),name,hf(sum(size)) as total_size,count(*),url(name) "
                   "from file group by name order by sum(size) desc,name asc limit ?", (limit,))

    db_file.close()


if __name__ == "__main__":
    main()
