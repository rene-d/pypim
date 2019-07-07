#! /bin/bash

# reference: https://warehouse.pypa.io/api-reference/json/

[[ $1 ]] || set -- -h
filter=.
verbose=
while getopts ":hvf:r" option; do
    case "${option}" in
        f)
            filter=${OPTARG}
            ;;
        v)
            verbose=-v
            ;;
        r)
            unset filter
            ;;
        *)
            echo "Returns metadata (info) about an individual project at the latest version."
            echo "Usage: $0 [options] <project_name>"
            echo "Options"
            echo "  -f EXPR : jq filter"
            echo "  -r      : don't pipe JSON through jq filter"
            echo "  -v      : make curl verbose"
            exit
            ;;
    esac
done
shift $((OPTIND-1))

# jq is required to filter
[[ $filter ]] && /usr/bin/which jq >/dev/null || unset filter

curl -L ${verbose} -s -H 'Content-Type: application/json' https://pypi.org/pypi/$1/json | (
    [[ ${filter} ]] && jq ${filter} || (cat; echo)
)
