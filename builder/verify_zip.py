"""Fail-closed packaging verification, then create the downloadable ZIP."""
from __future__ import annotations
from pathlib import Path
import argparse
import configparser
import zipfile


def validate(stage: Path):
    assert stage.name == 'BitwardenPortable', 'Stage folder name unexpected'
    required = [
        'BitwardenPortable.exe',
        'App/Bitwarden/Bitwarden-Portable.exe',
        'App/AppInfo/appinfo.ini',
        'App/AppInfo/appicon.ico',
        'Data/README-PRESERVE-DURING-UPDATE.txt',
        'Other/Source/BUILD-INFO.txt',
        'Other/Source/SECURITY.txt',
    ] + [f'App/AppInfo/appicon_{n}.png' for n in (16,32,75,128,256)]
    for item in required:
        assert (stage / item).is_file(), f'Missing required file: {item}'
    cfg = configparser.ConfigParser()
    cfg.read(stage / 'App' / 'AppInfo' / 'appinfo.ini', encoding='utf-8')
    assert cfg.get('Details', 'Name') == 'Bitwarden Portable (Community)'
    assert cfg.get('Details', 'Category') == 'Security'
    assert cfg.get('Control', 'Start') == 'BitwardenPortable.exe'
    assert cfg.get('Format', 'Version') == '3.9'
    assert (stage / 'BitwardenPortable.exe').read_bytes()[:2] == b'MZ'
    assert (stage / 'App' / 'Bitwarden' / 'Bitwarden-Portable.exe').stat().st_size > 10_000_000
    # Never package local account data or history from previous runs.
    assert not (stage / 'Data' / 'Bitwarden').exists(), 'Sensitive vault data found in build stage!'
    assert not (stage / 'Data' / 'Temp').exists(), 'Temporary application data found in build stage!'
    allowed_data = {'Data/README-PRESERVE-DURING-UPDATE.txt'}
    for path in stage.rglob('*'):
        if path.is_file() and path.relative_to(stage).as_posix().startswith('Data/'):
            assert path.relative_to(stage).as_posix() in allowed_data, f'Unexpected Data file: {path}'


def package(stage: Path, output: Path):
    validate(stage)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists(): raise FileExistsError('Refusing to overwrite an existing output ZIP')
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for file in sorted(stage.rglob('*')):
            if file.is_file(): z.write(file, Path(stage.name) / file.relative_to(stage))
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert f'{stage.name}/BitwardenPortable.exe' in z.namelist()
    print(f'VERIFIED: {output} ({output.stat().st_size:,} bytes)')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--zip', type=Path, required=True)
    opts = parser.parse_args()
    package(opts.stage, opts.zip)
