import struct
import sys
from pathlib import Path

PAGE = 4096
MAGIC = b'ANDROID!'


def align(n, page=PAGE):
    return (n + page - 1) // page * page


def pad(b, page=PAGE):
    return b + b'\x00' * (align(len(b), page) - len(b))


def build_boot(kernel, out, cmdline=b'', os_version=0):
    header = bytearray(1584)
    struct.pack_into('<8s', header, 0, MAGIC)
    struct.pack_into('<4I', header, 8, len(kernel), 0, os_version, 1584)
    struct.pack_into('<I', header, 40, 4)
    header[44:44 + len(cmdline)] = cmdline
    Path(out).write_bytes(pad(bytes(header)) + pad(kernel))


def main():
    # v0 image -> kernel gzip -> v4 image
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    data = src.read_bytes()
    ksize, = struct.unpack_from('<I', data, 8)
    page, = struct.unpack_from('<I', data, 36)
    kernel = data[page:page + ksize]
    build_boot(kernel, out)
    print(f'{out}: {len(kernel)} byte kernel, image {Path(out).stat().st_size} bytes')


if __name__ == '__main__':
    main()
