# PyPIM

PyPI Intelligent Mirror

## Introduction

There are many mirroring tools for [PyPI.org](https://pypi.org). The well-known [Bandersnatch](https://bandersnatch.readthedocs.io) works fine but cannot ensure dependencies.

That's why PyPIM has been written :

* whitelist
* blacklist
* filter by platforms
* retain only recent releases
* respect the dependencies

But computing dependencies is time and space comsuming. The whole package metadata are required and easy to reach.

## Using PyPIM

```
Usage: pypim.py [OPTIONS]

Options:
  -v, --verbose       verbose mode
  -nv, --non-verbose  no so much verbose
  -n, --dry-run       dry run
  -u, --update        update list of packages
  -m, --metadata      download JSON metadata
  -p, --packages      mirror packages
  -a, --add TEXT      package name
  -h, --help          Show this message and exit.
```

### Fetch the list of packages

```bash
./pypim.py -u
```
The script uses the [XML-RPC API](https://warehouse.readthedocs.io/api-reference/xml-rpc/#mirroring-support) to fetch the list of packages and their `last_serial` (a growing-only internal counter).

### Download the package metadata

Based on the previous list of packages, the script uses the [JSON API](
```bash
./pypim.py -m
```
The script uses the [XML-RPC API](https://warehouse.readthedocs.io/api-reference/json/) to download the package metadata.

The response, in JSON, is made of 4 sections:

* `info` : package description
* `last_serial` : a number
* `releases` : list of releases
* `urls`: files of the current releases

The metadata is stored in both raw and decoded formats, in two [SQLite3](https://www.sqlite.org) databases.

### Download the packages

```bash
./pypim.py -p [-a name1] [-a name2[==version]]...
```

#### Exclude packages

#### Filter by platforms

#### Keep only recents releases

#### Respect the dependencies

#### Add a whitelist

## Some reference links

* [PEP 426 -- Metadata for Python Software Packages 2.0](https://www.python.org/dev/peps/pep-0426/)
* [PEP 566 -- Metadata for Python Software Packages 2.1](https://www.python.org/dev/peps/pep-0566/)
* [Warehouse](https://warehouse.readthedocs.io) : web application that runs [PyPI](https://pypi.org)
* [PIP configuration file](https://pip.pypa.io/en/stable/user_guide/#config-file)
* [PyPI API](https://warehouse.readthedocs.io/api-reference/)
