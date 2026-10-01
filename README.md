# OpsVault

[![CI](https://github.com/alandoure005/opsvault-unix/actions/workflows/ci.yml/badge.svg)](https://github.com/alandoure005/opsvault-unix/actions/workflows/ci.yml)

A Unix backup-and-restore toolkit that records SHA-256 manifests, detects corruption, and verifies restored content before making the destination visible.

## Quick start

Requires Linux or macOS, Python 3.10+, and a POSIX shell. No root access or third-party Python packages are required.

```sh
python3 -m unittest discover -s tests -v
mkdir -p demo/source/empty
printf 'important sample data
' > demo/source/notes.txt
sh bin/snapshot.sh demo/source demo/snapshot-001
python3 opsvault.py verify demo/snapshot-001
python3 opsvault.py restore demo/snapshot-001 demo/recovered
cmp demo/source/notes.txt demo/recovered/notes.txt
sh bin/host-report.sh .
```

Use a new snapshot and restore destination on each run. Existing destinations are rejected rather than replaced.

## Snapshot format

```text
snapshot-001/
  manifest.json       # format version, directory names, file sizes and hashes
  data/               # copied source contents, including empty directories
```

Backup fingerprints the source, copies it into a staging directory, compares both source and copy against the original fingerprint, then renames the staged snapshot into place. Restore validates the manifest and copied content before publishing the destination. Staging directories live next to the destination so rename remains on one filesystem. A Unix advisory lock serializes OpsVault writers sharing a destination parent.

## Recovery runbook

1. Stop application writers before backing up. For databases, first produce an application-consistent export using the database's own tools.
2. Create a snapshot outside the source tree.
3. Run `verify` and copy the snapshot to independent storage if required.
4. Periodically restore to a fresh directory and run the application's own validation.
5. Switch the application to recovered data only after that validation.

`host-report.sh` prints UTC time, OS details, uptime, and disk usage using read-only Unix commands. `snapshot.sh` is suitable for a scheduler once absolute source and destination paths are supplied; no schedules are installed automatically.

## Guarantees and limits

Checks cover file bytes, file sizes, directory structure, unexpected files, and missing files. Symbolic links, sockets, devices, and other special files are rejected. Source-nested destinations and unsafe manifest paths are rejected.

The source and snapshots must be trusted, quiescent directories. Pre/post fingerprints can detect many changes but do not make live backups transactionally consistent or protect against hostile concurrent filesystem mutation. Checksums detect corruption; they do not authenticate a snapshot because an attacker could replace both data and manifest.

This is a content backup: ownership, permission bits, ACLs, extended attributes, sparse layout, and timestamps are not guaranteed to be preserved. There is no encryption, compression, remote transfer, automatic deletion, or retention policy. Atomic visibility is not a guarantee of power-loss durability; files and parent directories are not explicitly synchronized to disk.

## Tests

Tests exercise binary-content round trips, empty directories, corruption, destination preservation, source symlinks, nested destinations, path traversal in manifests, and unexpected files. CI runs the suite and shell syntax checks on Linux and macOS.
