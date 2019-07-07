#! /usr/bin/env python3
# rene-d 2019

"""
Populate sha256_digest column with the JSON metadata field
"""

import sqlite3
import json


db = sqlite3.connect("pypi_json.db")
db.execute("attach database ? as Z", ("pypi.db",))
count = 0

for row in db.execute("select name,metadata from package"):
    name = row[0]
    for release, files in json.loads(row[1])["releases"].items():
        for file in files:
            r = db.execute(
                "update Z.file set sha256_digest=? where name=? and release=? and filename=? and sha256_digest is null",
                (file["digests"]["sha256"], name, release, file["filename"]),
            )
            # assert r.rowcount == 1

            count += 1
            if count % 1000 == 0:
                print(count)
                db.commit()

db.commit()
