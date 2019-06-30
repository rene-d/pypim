#! /bin/bash

filter=.
verbose=
while getopts ":vf:" option; do
    case "${option}" in
        f)
	        filter=${OPTARG}
            ;;
	    v)
	        verbose=-v
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))


curl ${verbose} -s -H 'Content-Type: application/json' https://pypi.org/pypi/$1/json | (
    [[ ${filter} ]] && jq ${filter} || cat
)
