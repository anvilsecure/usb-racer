#!/usr/bin/env python

import argparse
from hexdump import hexdump

import log

parser = argparse.ArgumentParser()
parser.add_argument("path", help="Path to the log file")
args = parser.parse_args()


reader = log.IOLogReader(args.path)

print(f"Block Size={reader.block_size}, Capacity={reader.capacity}, Flags={reader.flags.name}")

for op, offset, count, data in reader.entries():
    print(f"Op: {op.name} Offset: {offset} Count: {count}")
    if len(data) > 0:
        hexdump(data)
