"""Fetch historical ARM compiler and a local Python 2 build interpreter source."""
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from prepare_baseline import download

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/baseline/toolchains'
ARM = ('https://launchpad.net/gcc-arm-embedded/4.9/4.9-2014-q4-major/+download/'
       'gcc-arm-none-eabi-4_9-2014q4-20141203-linux.tar.bz2')
PYTHON = 'https://www.python.org/ftp/python/2.7.18/Python-2.7.18.tgz'


def fetch(url):
    target = OUT / url.rsplit('/', 1)[1]
    download(url, target)
    data = target.read_bytes()
    result = {'url': url, 'file': target.name, 'size': len(data),
              'sha256': hashlib.sha256(data).hexdigest()}
    if url == ARM:
        expected = urllib.request.urlopen(url + '/+md5', timeout=30).read().decode().split()[0]
        if hashlib.md5(data).hexdigest() != expected:
            raise ValueError('Historical ARM SDK MD5 mismatch')
        result['upstream_md5_verified'] = expected
    print(target.name, len(data), 'bytes', flush=True)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        result = list(executor.map(fetch, [ARM, PYTHON]))
    (ROOT / 'analysis/baseline/toolchain_downloads.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
