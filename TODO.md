# TODO

## ~~Save whitelist into the database~~

_Feature implemented by scanning the existing files before creating the content of `index.html`. It should be sufficient._

Manually added releases will be lost during the next mirroring if not asked again.

Example:


```
  $ ./pypim.py -a pyxb==1.2.3
````
downloads PyXB version 1.2.3 (an old version) and the 3 most recent versions.

```
  $ ./pypim.py -a pyxb
```
downloads the 3 most recent versions. The old one, although present in the mirror, will not be referenced in `index.html`.

## ~~Look for previously downloaded releases~~

_Command-line option `--remove-orphans`._

When a release becomes too old, it won't be listed in index.html. And not deleted from disk.

## Look for orphan files

If a previously downloaded file is removed from a release, it will remain in the mirror.

## Write tests 🤪

## Finish the documentation... 😇
