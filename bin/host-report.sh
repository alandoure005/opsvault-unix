#!/bin/sh
# Read-only operational context; no privileged commands or environment dumps.
set -eu
printf 'UTC time: '
date -u '+%Y-%m-%dT%H:%M:%SZ'
printf '\nSystem\n'
uname -srm
printf '\nUptime\n'
uptime
printf '\nFilesystem usage\n'
df -Pk "${1:-.}"
