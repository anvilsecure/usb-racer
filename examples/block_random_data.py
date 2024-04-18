#!/usr/bin/env python
import logging
import argparse
import asyncio
import random

from usbracer.gadget import Gadget, Configuration
from usbracer.mass_storage import MassStorage, WritePerms
from usbracer.disks import MMapDiskImage, DiskOverrideImage, DiskImage
from usbracer.log import IOLogger

VENDOR_ID = 0x1234
PRODUCT_ID = 0x4321

def block_parser(s):
    if '-' in s:
        start, end = s.split('-')
        return int(start, 0), int(end, 0)
    else:
        return int(s, 0)

parser = argparse.ArgumentParser()
parser.add_argument("image", help="Path to disk image")
parser.add_argument("--block-size", type=int, default=512)
parser.add_argument("block", nargs="+", type=block_parser, help="Blocks (single ints) or block ranges (as a start-end) to return random data when read")
parser.add_argument("--debug-level", default=logging.INFO)
args = parser.parse_args()

logging.basicConfig(level=args.debug_level)

def random_data(disk : DiskImage, offset : int, count : int) -> bytes:
    return random.randbytes(disk.block_size * count)


disk = DiskOverrideImage(
    MMapDiskImage(args.image, args.block_size),
    read_overrides=list(map(lambda block : (block, random_data), args.block)))

print(disk.read_overrides)

gadget = Gadget(VENDOR_ID, PRODUCT_ID, manufacture="Anvil", product="Random data block storage device")
config = gadget.add_configuration(Configuration(gadget, "Config-1"))
func = config.add_function(MassStorage(config,
                                        disk,
                                        vendor_id="Anvil", product_id="Random Data", product_ver="0.1"))

asyncio.run(gadget.run())
