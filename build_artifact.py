import argparse
import hashlib
import zipfile
from pathlib import Path


FILES = (
    '.gitattributes',
    '.gitignore',
    'ARTIFACT.md',
    'DATA.md',
    'Makefile',
    'README.md',
    'RECONSTRUCTION_APPROACH.md',
    'SECURITY.md',
    'VERSION',
    'build_artifact.py',
    'muse_activity_parser.py',
    'muse_activity_viewer.py',
    'test_muse_activity_parser.py',
    'test_muse_activity_viewer.py',
    'viewer_web/app.js',
    'viewer_web/index.html',
    'viewer_web/styles.css',
)


def archive_info(name):
    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build the public artifact archive')
    parser.add_argument('--output', default='dist/muse-activity-parser-artifact.zip')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = 'muse-activity-parser-artifact'
    checksums = []
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in FILES:
            source = root / relative
            if not source.is_file():
                raise FileNotFoundError(source)
            content = source.read_bytes()
            checksums.append(f'{hashlib.sha256(content).hexdigest()}  {relative}')
            archive.writestr(archive_info(f'{prefix}/{relative}'), content)
        manifest = ('\n'.join(checksums) + '\n').encode()
        archive.writestr(archive_info(f'{prefix}/SHA256SUMS'), manifest)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(output)
    print(f'sha256 {digest}')


if __name__ == '__main__':
    main()
