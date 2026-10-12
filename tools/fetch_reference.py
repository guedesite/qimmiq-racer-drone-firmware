"""Download a fixed set of public upstream references; no firmware flashing."""
import json
import urllib.request
from pathlib import Path

ROOT = 'https://api.github.com/repos/librepilot/LibrePilot'
OUT = Path('analysis/upstream')


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'firmware-research'})
    return urllib.request.urlopen(req, timeout=30).read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # The dump embeds this prefix as a little-endian uint32: bytes 84 cc 68 bf.
    try:
        commit = json.loads(get(ROOT + '/commits/bf68cc84'))
        (OUT / 'commit.json').write_text(json.dumps(commit, indent=2), encoding='utf-8')
        revision = commit['sha']
        print('Exact commit:', revision)
    except Exception as error:
        raise RuntimeError('Exact commit lookup failed; refusing to substitute a newer revision: ' + str(error))
    tree = json.loads(get(ROOT + '/git/trees/' + revision + '?recursive=1'))
    paths = [x['path'] for x in tree['tree'] if x['type'] == 'blob']
    selected = [p for p in paths if
                ('coptercontrol' in p and p.endswith(('board-info.mk', 'pios_board.c', 'board_hw_defs.c', '.ld')))
                or p.endswith(('firmwareinfotemplate.c', 'firmware_info.c.template', 'pios_iap.h',
                               'flightmodesettings.xml', 'stabilizationdesired.xml',
                               'manualcontrolsettings.xml', 'stabilization.c', 'stabilizationinnerloop.c',
                               'stabilizationouterloop.c', 'innerloop.c', 'outerloop.c',
                               'manualcontrol.c', 'actuator.c', 'pid.c'))
                or ('coptercontrol' in p and p.endswith('pios_board.h'))
                or ('coptercontrol' in p and p.endswith('pios_board.c'))
                or ('STM32103CB' in p and p.endswith('.ld'))]
    manifest = []
    for path in selected:
        url = 'https://raw.githubusercontent.com/librepilot/LibrePilot/' + revision + '/' + path
        try:
            target = OUT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(get(url))
            manifest.append({'path': path, 'url': url, 'revision': revision})
            print(path)
        except Exception as error:
            print(path, error)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
