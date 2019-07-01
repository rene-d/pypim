#! /bin/bash

filter=.
verbose=
while getopts ":vf:r" option; do
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
            usage
            exit
            ;;
    esac
done
shift $((OPTIND-1))


curl -L ${verbose} -s -H 'Content-Type: application/json' https://pypi.org/pypi/$1/json | (
    [[ ${filter} ]] && jq ${filter} || cat
)
