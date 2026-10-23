"""Build GKI-style (header v4) boot.img and vendor_boot.img that mirror the stock sheng layout.

boot.img      : header v4, kernel = gzip(BootShim + UEFI firmware volume), no ramdisk
vendor_boot   : header v4, vendor ramdisk = UniXNU payload, dtb + bootconfig + ramdisk table
"""
import argparse
import struct
from pathlib import Path

PAGE = 4096
BOOT_MAGIC = b'ANDROID!'
VENDOR_MAGIC = b'VNDRBOOT'


def align(n, page=PAGE):
    return (n + page - 1) // page * page


def pad(b, page=PAGE):
    return b + b'\x00' * (align(len(b), page) - len(b))


def parse_vendor_boot(path):
    data = Path(path).read_bytes()
    (hv, page, kernel_addr, ramdisk_addr, rd_size) = struct.unpack_from('<5I', data, 8)
    cmdline = data[28:28 + 2048]
    tags_addr, = struct.unpack_from('<I', data, 2076)
    name = data[2080:2096]
    header_size, dtb_size = struct.unpack_from('<2I', data, 2096)
    dtb_addr, = struct.unpack_from('<Q', data, 2104)
    tbl_size, entries, entry_size, bc_size = struct.unpack_from('<4I', data, 2112)
    off = page
    rd = data[off:off + rd_size]
    off = align(off + rd_size)
    dtb = data[off:off + dtb_size]
    off = align(off + dtb_size)
    table = data[off:off + tbl_size]
    off = align(off + tbl_size)
    bootconfig = data[off:off + bc_size]
    return dict(header_version=hv, page=page, kernel_addr=kernel_addr, ramdisk_addr=ramdisk_addr,
                cmdline=cmdline, tags_addr=tags_addr, name=name, header_size=header_size,
                dtb_addr=dtb_addr, table=table, entry_size=entry_size, bootconfig=bootconfig,
                dtb=dtb, ramdisk=rd)


def build_boot(kernel, out, os_version=0, cmdline=b''):
    header = bytearray(1584)
    struct.pack_into('<8s', header, 0, BOOT_MAGIC)
    struct.pack_into('<4I', header, 8, len(kernel), 0, os_version, 1584)
    struct.pack_into('<I', header, 40, 4)                     # header_version
    header[44:44 + len(cmdline)] = cmdline
    blobs = pad(bytes(header)) + pad(kernel)
    Path(out).write_bytes(blobs)


def build_vendor_boot(tpl, ramdisk, dtb, out, cmdline=None, name=b''):
    cmdline = tpl['cmdline'] if cmdline is None else cmdline
    # ramdisk table: keep the stock entry but point it at our ramdisk
    entry_size = tpl['entry_size']
    entry = bytearray(tpl['table'][:entry_size])
    struct.pack_into('<2I', entry, 0, len(ramdisk), 0)        # size, offset
    struct.pack_into('<32s', entry, 76, name or b'platform')  # fragment name
    table = bytes(entry)

    header = bytearray(2128)
    struct.pack_into('<8s', header, 0, VENDOR_MAGIC)
    struct.pack_into('<5I', header, 8, 4, PAGE, tpl['kernel_addr'], tpl['ramdisk_addr'], len(ramdisk))
    header[28:28 + 2048] = cmdline[:2048]
    struct.pack_into('<I', header, 2076, tpl['tags_addr'])
    header[2080:2096] = (name or b'')[:16].ljust(16, b'\x00')
    struct.pack_into('<2I', header, 2096, 2128, len(dtb))
    struct.pack_into('<Q', header, 2104, tpl['dtb_addr'])
    struct.pack_into('<4I', header, 2112, len(table), 1, entry_size, len(tpl['bootconfig']))

    blob = pad(bytes(header))
    blob += pad(ramdisk)
    blob += pad(dtb)
    blob += pad(table)
    blob += pad(tpl['bootconfig'])
    Path(out).write_bytes(blob)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stock-vendor-boot', required=True, help='template: the stock vendor_boot.img')
    ap.add_argument('--kernel', required=True, help='gzip(BootShim + firmware volume) from the v0 image')
    ap.add_argument('--ramdisk', required=True, help='UniXNU payload.img')
    ap.add_argument('--dtb', required=True)
    ap.add_argument('--out-boot', default='boot-v4.img')
    ap.add_argument('--out-vendor', default='vendor_boot-v4.img')
    args = ap.parse_args()

    tpl = parse_vendor_boot(args.stock_vendor_boot)
    kernel = Path(args.kernel).read_bytes()
    ramdisk = Path(args.ramdisk).read_bytes()
    dtb = Path(args.dtb).read_bytes()

    build_boot(kernel, args.out_boot)
    build_vendor_boot(tpl, ramdisk, dtb, args.out_vendor)
    print('boot      %10d bytes  kernel %d' % (Path(args.out_boot).stat().st_size, len(kernel)))
    print('vendor    %10d bytes  ramdisk %d  dtb %d  table %d  bootconfig %d' % (
        Path(args.out_vendor).stat().st_size, len(ramdisk), len(dtb), len(tpl['table']), len(tpl['bootconfig'])))


if __name__ == '__main__':
    main()
