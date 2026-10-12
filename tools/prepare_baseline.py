"""Fetch an immutable upstream source archive and record its provenance."""
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

REVISION = 'bf68cc84d471feb0d9346f40f012e6c8e4de4bbb'
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis' / 'baseline'


def download(url, target):
    if target.exists():
        return
    temporary = target.with_suffix(target.suffix + '.partial')
    req = urllib.request.Request(url, headers={'User-Agent': 'firmware-research'})
    with urllib.request.urlopen(req, timeout=60) as response, temporary.open('wb') as stream:
        while True:
            chunk = response.read(1024*1024)
            if not chunk:
                break
            stream.write(chunk)
    temporary.replace(target)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / ('OpenPilot-' + REVISION + '.zip')
    url = 'https://codeload.github.com/librepilot/LibrePilot/zip/' + REVISION
    download(url, archive)
    with zipfile.ZipFile(archive) as zipped:
        for info in zipped.infolist():
            target = (OUT / info.filename).resolve()
            if not target.is_relative_to(OUT.resolve()):
                raise ValueError('Archive path escapes baseline directory')
        zipped.extractall(OUT)
        top = zipped.namelist()[0].split('/')[0]
    source = OUT / top
    # Upstream version-info.py accepts this file in source archives without .git.
    # These values identify the historical release; they are not a new git history.
    version = {'hash': REVISION, 'origin': 'https://github.com/librepilot/LibrePilot',
               'time': '1428248441', 'tag': 'RELEASE-15.02.01',
               'branch': 'RELEASE-15.02.01', 'dirty': False}
    (source / 'version-info.json').write_text(json.dumps(version, indent=2), encoding='utf-8')
    manifest = {'revision': REVISION, 'archive_url': url,
                'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'source_directory': str(source.relative_to(ROOT)),
                'generated_files': ['version-info.json'],
                'target': 'fw_coptercontrol', 'firmware_base': '0x08003000',
                'expected_firmware_sha1': '6c47a76d1d372542e35053159aee896ed1cd1e4e',
                'expected_uavo_sha1': 'e700bb5174d04ca794312e6234a78b01469143df'}
    (OUT / 'provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Source:', source)
    print('Archive SHA256:', manifest['archive_sha256'])


if __name__ == '__main__':
    main()
