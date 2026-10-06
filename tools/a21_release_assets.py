"""Package already frozen A21 evidence, without physics, QPs or SHA256 checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import zipfile

PARENTS = (2001, 2005, 2003, 2007, 2013)
ARMS = ('BASE_G', 'PRIMAL_G', 'DUAL_G', 'BOTH_G', 'RANDOM_G', 'BOTH_PG', 'RANDOM_PG')
TAG = 'v0.3.0-a21-two-sided-anatomy'


def build(public_root, evidence_root, output):
    public_root, evidence_root, output = map(lambda p: Path(p).resolve(),
                                            (public_root, evidence_root, output))
    output.mkdir(parents=True, exist_ok=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=public_root,
                                     text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=public_root,
                                    text=True)
    if dirty:
        raise ValueError('PUBLIC_SNAPSHOT_MUST_BE_COMMITTED')
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=public_root,
                                      text=True).split('\0')
    paths = [p for p in tracked if p]
    forbidden = ('private/', '.git/', '.venv/', '.venv_nn/', '__pycache__/', 'runs/', 'dist/')
    for name in paths:
        path = public_root / name
        if name.startswith(forbidden) or path.is_symlink():
            raise ValueError('FORBIDDEN_OR_SYMLINK_PUBLIC_MEMBER')
        if name.startswith(('results/a21/anatomy/caches/', 'results/a21/anatomy/diagnostics/')) and not name.endswith('README.md'):
            raise ValueError('OFFLINE_ARRAYS_IN_GIT_BUNDLE')
    main_path = output / ('a20-opm-imaging-' + TAG + '.zip')
    offline_path = output / ('a21-offline-diagnostics-' + TAG + '.zip')
    for path in (main_path, offline_path):
        if path.exists():
            raise FileExistsError('EXISTING_RELEASE_ASSET_WILL_NOT_BE_REPLACED')

    prefix = 'a20-opm-imaging-' + TAG + '/'
    with zipfile.ZipFile(main_path, 'x', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as archive:
        for name in sorted(paths):
            archive.write(public_root / name, prefix + name)
        archive.writestr(prefix + 'RELEASE_SNAPSHOT.json', json.dumps(dict(
            public_commit=source, release_tag=TAG, new_physics=False,
            new_SHA256_checks=0, large_offline_arrays_separate=True), indent=2) + '\n')

    names = []
    for parent in PARENTS:
        names.extend(f'results/a21/anatomy/caches/{parent}_17.{ext}' for ext in ('npz', 'json'))
        names.extend(f'results/a21/anatomy/diagnostics/{parent}_17_{arm}.npz' for arm in ARMS)
    inventory = [dict(path=name, bytes=(evidence_root / name).stat().st_size) for name in names]
    marker = '''# ORACLE / OFFLINE / DIAGNOSTIC ONLY

This archive contains paid full J/H, primal/adjoint oracle currents, bases, frozen
reference/QP steps, normal-cone vectors and diagnostic decompositions from five
historically exposed iteration-17 Gaussian states. It is for independent offline
verification only. Do not expose these arrays to any online proposal builder.

Extract this ZIP at the public repository root to restore the original
results/a21/anatomy/caches and results/a21/anatomy/diagnostics paths. It contains
no Maxwell LU/workspace, truth payload, SSH/private files or environment install.
See results/a21/REPRODUCE.md and tools/a21_review.py. No new physics or QP was run
to create this asset. Historical source/hash fields were preserved; no new
SHA256 check was performed.
'''
    with zipfile.ZipFile(offline_path, 'x', compression=zipfile.ZIP_STORED,
                         allowZip64=True) as archive:
        archive.writestr('A21_OFFLINE_DIAGNOSTIC_ONLY.md', marker)
        archive.writestr('A21_OFFLINE_ARRAY_INVENTORY.json', json.dumps(dict(
            scope='ORACLE_OFFLINE_FROZEN_QUADRATIC', public_source_commit=source,
            original_physics_source_commit='5c6bcb02bb4ab88f7b46f07bca4ca3f4e38a067c',
            parents=list(PARENTS), iterations=[17], arrays=inventory,
            no_new_physics=True, new_SHA256_checks=0), indent=2) + '\n')
        for name in names:
            if (evidence_root / name).is_symlink():
                raise ValueError('SYMLINK_DIAGNOSTIC_MEMBER')
            archive.write(evidence_root / name, name)

    assets = []
    for path in (main_path, offline_path):
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP_CRC_FAILURE')
            members = archive.namelist()
            if any(Path(member).is_absolute() or '..' in Path(member).parts for member in members):
                raise ValueError('UNSAFE_ARCHIVE_PATH')
        assets.append(dict(name=path.name, bytes=path.stat().st_size,
                           members=len(members), ZIP_CRC='PASS'))
    qa = dict(schema='a21.release_archive_qa.v1', status='PASS',
              public_source_commit=source, release_tag=TAG, assets=assets,
              offline_arrays=len(inventory), no_new_physics=True,
              old_releases_unchanged=True, new_SHA256_checks=0)
    (output / 'A21_ARCHIVE_QA.json').write_text(json.dumps(qa, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(qa))
    return qa


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.public_root, args.evidence_root, args.output)
