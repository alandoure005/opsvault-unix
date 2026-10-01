"""Verified directory snapshots for Unix systems. Requires a quiescent source."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def inventory(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('expected a real directory')
    files, directories = {}, []
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f'symlinks are unsupported: {name}')
        if path.is_file():
            files[name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
        elif path.is_dir():
            directories.append(name)
        else:
            raise ValueError(f'special files are unsupported: {name}')
    return {'files': files, 'directories': directories}


@contextmanager
def destination_lock(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (destination.parent / '.opsvault.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if destination.exists() or destination.is_symlink():
            raise ValueError('destination already exists')
        yield


def safe_destination(source, destination):
    source = Path(source)
    if source.is_symlink():
        raise ValueError('source must not be a symlink')
    source = source.resolve(strict=True)
    destination = Path(destination).absolute()
    resolved = destination.resolve()
    if resolved == source or source in resolved.parents:
        raise ValueError('destination must be outside the source')
    return source, destination


def backup(source, destination):
    source, destination = safe_destination(source, destination)
    with destination_lock(destination):
        before = inventory(source)
        with tempfile.TemporaryDirectory(prefix='.opsvault-stage-', dir=destination.parent) as temp:
            stage = Path(temp) / 'snapshot'
            stage.mkdir()
            shutil.copytree(source, stage / 'data', copy_function=shutil.copyfile)
            after = inventory(stage / 'data')
            if after != before or inventory(source) != before:
                raise ValueError('source changed during backup; stop writers and retry')
            (stage / 'manifest.json').write_text(json.dumps({'version': 1, **after}, indent=2) + '\n')
            os.rename(stage, destination)
    return {'files': len(before['files']), 'bytes': sum(item['bytes'] for item in before['files'].values())}


def verify(snapshot):
    snapshot = Path(snapshot)
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise ValueError('snapshot must be a real directory')
    manifest_path = snapshot / 'manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError('manifest must be a regular file')
    if manifest_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('manifest exceeds 16 MiB')
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict) or set(manifest) != {'version', 'files', 'directories'} or manifest['version'] != 1:
        raise ValueError('unsupported manifest')
    if not isinstance(manifest['files'], dict) or not isinstance(manifest['directories'], list):
        raise ValueError('invalid manifest entries')
    for name in [*manifest['files'], *manifest['directories']]:
        if not isinstance(name, str) or not name or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
            raise ValueError('unsafe manifest path')
    actual = inventory(snapshot / 'data')
    if actual != {'files': manifest['files'], 'directories': manifest['directories']}:
        raise ValueError('snapshot integrity check failed')
    return actual


def restore(snapshot, destination):
    snapshot, destination = safe_destination(snapshot, destination)
    with destination_lock(destination):
        expected = verify(snapshot)
        with tempfile.TemporaryDirectory(prefix='.opsvault-restore-', dir=destination.parent) as temp:
            stage = Path(temp) / 'restored'
            shutil.copytree(snapshot / 'data', stage, copy_function=shutil.copyfile)
            if inventory(stage) != expected:
                raise ValueError('snapshot changed during restore')
            os.rename(stage, destination)
    return {'restored_files': len(expected['files'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('backup', 'restore'):
        command = sub.add_parser(name)
        command.add_argument('source')
        command.add_argument('destination')
    command = sub.add_parser('verify')
    command.add_argument('source')
    args = parser.parse_args()
    try:
        if args.command == 'verify':
            result = verify(args.source)
            print(json.dumps({'valid': True, 'files': len(result['files'])}))
        else:
            print(json.dumps(globals()[args.command](args.source, args.destination)))
    except (OSError, ValueError) as error:
        parser.exit(2, f'opsvault: {error}\n')


if __name__ == '__main__':
    main()
