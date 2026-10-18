"""Build a Bitwarden portable folder from the verified, official Windows portable EXE.

Never reads local vault state. Never downloads an installer or modified binary.
All network content is limited to official Bitwarden GitHub release and tagged icon.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import urllib.request


REPOSITORY = 'bitwarden/clients'
VERSION_RE = re.compile(r'20\d{2}\.\d{1,2}\.\d{1,3}$')
GITHUB_API = 'https://api.github.com/repos/bitwarden/clients/releases/tags/'
# Publisher SHA-256 values can be cross-checked at the GitHub release assets page.
# Keep trusted values for the known first build and use GitHub's asset digest on later builds.
PINNED_CHECKSUMS = {
    '2026.10.0': '3643f049c980d07353211dd4643e663d5eec8d9e197db031e0c1cd1981c2641b',
}


def sha256_file(file: Path) -> str:
    result = hashlib.sha256()
    with file.open('rb') as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def get_json(url: str, token: str = '') -> dict:
    if not url.startswith(GITHUB_API):
        raise ValueError('API endpoint must be from the official Bitwarden GitHub repository')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'BitwardenPortableCommunityBuilder/1.0', 'X-GitHub-Api-Version': '2022-11-28'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def validate_release(release: dict, version: str, expected_override: str = '') -> tuple[str, str]:
    if not VERSION_RE.fullmatch(version):
        raise ValueError('Use a concrete stable numeric version such as 2026.10.0')
    if release.get('tag_name') != f'desktop-v{version}' or release.get('draft') or release.get('prerelease'):
        raise ValueError('Release is not the requested published stable Desktop version')
    wanted = f'Bitwarden-Portable-{version}.exe'
    matches = [a for a in release.get('assets', []) if a.get('name') == wanted and a.get('state') == 'uploaded']
    if len(matches) != 1:
        raise ValueError(f'Official release must have exactly one uploaded {wanted} (not commercial or installer)')
    asset = matches[0]
    url = asset.get('browser_download_url', '')
    prefix = f'https://github.com/bitwarden/clients/releases/download/desktop-v{version}/'
    if url != prefix + wanted:
        raise ValueError('Official release asset URL does not match the expected GitHub path')
    digest = asset.get('digest') or ''
    api_sha = digest[7:].lower() if re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest) else ''
    pinned = PINNED_CHECKSUMS.get(version, '')
    supplied = expected_override.lower().strip()
    if supplied and not re.fullmatch(r'[0-9a-f]{64}', supplied):
        raise ValueError('Manual SHA-256 must be 64 hexadecimal characters')
    if len({x for x in (pinned, api_sha, supplied) if x}) > 1:
        raise ValueError('Official release digest, pinned checksum, and manually supplied checksum disagree')
    expected = pinned or api_sha or supplied
    if not expected:
        raise ValueError('Official GitHub asset digest unavailable. Supply the official SHA-256 explicitly or skip this release.')
    return url, expected


def download(url: str, destination: Path, max_size: int) -> None:
    headers = {'User-Agent': 'BitwardenPortableCommunityBuilder/1.0'}
    req = urllib.request.Request(url, headers=headers)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=120) as response, destination.open('wb') as writer:
        total = 0
        while True:
            chunk = response.read(2 * 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_size:
                raise RuntimeError('Download exceeded maximum expected size')
            writer.write(chunk)
    if destination.stat().st_size < 1_000:
        raise RuntimeError('Download too small; expected an application or official icon')


def render_icons(icon: Path, appinfo: Path) -> None:
    from PIL import Image
    with icon.open('rb') as f:
        assert f.read(4) == b'\x00\x00\x01\x00', 'Expected an official Windows ICO'
    with Image.open(icon) as base:
        ico = base.ico
        available = ico.sizes()
        if not available:
            raise ValueError('Official icon has no image sizes')
        for pixels in (16, 32, 75, 128, 256):
            found = (pixels, pixels)
            if found in available:
                png = ico.getimage(found)
            else:
                nearest = min(available, key=lambda x: abs(x[0]-pixels))
                png = ico.getimage(nearest).resize((pixels,pixels), Image.Resampling.LANCZOS)
            png.convert('RGBA').save(appinfo / f'appicon_{pixels}.png', format='PNG')


def build(version: str, stage_dir: Path, cache_dir: Path, token: str = '', expected_override: str = '') -> None:
    if not VERSION_RE.fullmatch(version):
        raise ValueError('Version must be an official numeric Desktop release, such as 2026.10.0')
    if stage_dir.exists():
        raise RuntimeError(f'Refusing to overwrite existing staging folder: {stage_dir}')
    release = get_json(GITHUB_API + f'desktop-v{version}', token)
    binary_url, checksum = validate_release(release, version, expected_override)

    binary = cache_dir / f'Bitwarden-Portable-{version}.exe'
    icon_url = f'https://raw.githubusercontent.com/bitwarden/clients/desktop-v{version}/apps/desktop/resources/icon.ico'
    official_icon = cache_dir / f'Bitwarden-icon-{version}.ico'
    print('Downloading the OFFICIAL portable executable (large download; this may take several minutes).')
    download(binary_url, binary, max_size=750 * 1024 * 1024)
    real_checksum = sha256_file(binary)
    if real_checksum != checksum:
        binary.unlink(missing_ok=True)
        raise RuntimeError(f'Official Bitwarden executable SHA-256 mismatch: expected {checksum}, got {real_checksum}')
    with binary.open('rb') as reader:
        if reader.read(2) != b'MZ':
            raise RuntimeError('Verified file was not a Windows executable')
    print(f'Verified official portable executable SHA-256: {real_checksum}')

    download(icon_url, official_icon, max_size=2 * 1024 * 1024)
    with official_icon.open('rb') as reader:
        if reader.read(4) != b'\x00\x00\x01\x00':
            raise RuntimeError('Official icon was not a Windows ICO')

    program = stage_dir / 'App' / 'Bitwarden'
    appinfo = stage_dir / 'App' / 'AppInfo'
    data = stage_dir / 'Data'
    other = stage_dir / 'Other' / 'Source'
    for folder in (program, appinfo, data, other):
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, program / 'Bitwarden-Portable.exe')
    shutil.copy2(official_icon, appinfo / 'appicon.ico')
    render_icons(official_icon, appinfo)

    (data / 'README-PRESERVE-DURING-UPDATE.txt').write_text(
        'PRIVATE VAULT DATA: this Data folder contains encrypted vault cache and account state. '
        'Do NOT upload Data to GitHub or share it. Preserve the complete Data folder when updating.\n', encoding='utf-8')
    (other / 'BUILD-INFO.txt').write_text(
        f'Official Bitwarden portable release: https://github.com/bitwarden/clients/releases/tag/desktop-v{version}\n'
        f'Official unmodified EXE SHA-256: {checksum}\n'
        f'Official icon source: {icon_url}\n'
        'Independent community packaging; not affiliated with Bitwarden or PortableApps.com.\n'
        'This is a portable ZIP; it is not an official PortableApps.com PAF installer.\n', encoding='utf-8')
    (other / 'SECURITY.txt').write_text(
        'The official portable edition does not include Windows Secure Storage or Process Isolation.\n'
        'Use full-disk encryption, a strong master password and two-step login.\n'
        'Never publish the Data folder, even to a private GitHub repository.\n'
        'Desktop-to-browser integration may register Windows native messaging locations.\n', encoding='utf-8')
    (other / 'OFFICIAL-LICENSE-URL.txt').write_text(
        f'See official license files for this release: https://github.com/bitwarden/clients/tree/desktop-v{version}\n', encoding='utf-8')
    version_four = version + '.0'
    app_info_text = f'''[Format]
Type=PortableApps.comFormat
Version=3.9

[Details]
Name=Bitwarden Portable (Community)
AppID=BitwardenPortable-CommunityBuild
BaseAppName=Bitwarden
Publisher=Bitwarden, Inc. (app) / Independent community packaging
Homepage=https://github.com/bitwarden/clients
Category=Security
Description=Bitwarden official portable desktop app with local data folder
Language=Multilingual

[License]
Shareable=true
OpenSource=true
Freeware=true
CommercialUse=true

[Version]
PackageVersion={version_four}
DisplayVersion={version}

[Control]
Icons=1
Start=BitwardenPortable.exe
'''
    (appinfo / 'appinfo.ini').write_text(app_info_text, encoding='utf-8')
    print(f'Prepared verified folder at: {stage_dir}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--stage', type=Path, default=Path('stage/BitwardenPortable'))
    parser.add_argument('--cache', type=Path, default=Path('cache'))
    parser.add_argument('--sha256', default='')
    args = parser.parse_args()
    build(args.version, args.stage, args.cache, os.getenv('GITHUB_TOKEN', ''), args.sha256)

if __name__ == '__main__':
    main()
