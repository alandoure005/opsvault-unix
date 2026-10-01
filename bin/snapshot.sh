#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then
    echo "Usage: snapshot.sh SOURCE SNAPSHOT_DIRECTORY" >&2
    exit 2
fi
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$script_dir/../opsvault.py" backup "$1" "$2"
