#!/usr/bin/env python

def main():
    import logging
    import argparse
    import asyncio

    from mass.gadget import Gadget, Configuration
    from mass.mass_storage import MassStorage, WritePerms
    from mass.disks import MMapDiskImage, COWDiskImage
    from mass.log import IOLogger

    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to disk image")
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--write", type=WritePerms.__getitem__, default=WritePerms.ALLOW)
    parser.add_argument("--cow", help="Path to copy on write file (creates/expects a .metadata file next to it)")
    parser.add_argument("--log", help="Log IO operations to file")
    parser.add_argument("--log-data", action="store_true", default=False, help="Include data within the log file")
    parser.add_argument("--debug-level", default=logging.WARNING)
    args = parser.parse_args()

    logging.basicConfig(level=args.debug_level)
    VENDOR_ID = 0x1234
    PRODUCT_ID = 0x4321

    if args.cow != None:
        disk = COWDiskImage(args.image, args.block_size, args.cow)
    else:
        disk = MMapDiskImage(args.image, args.block_size)

    if args.log != None:
        disk = IOLogger(args.log, args.log_data, disk)

    gadget = Gadget(VENDOR_ID, PRODUCT_ID, manufacture="Anvil", product="Evil Mass Storage")
    config = gadget.add_configuration(Configuration(gadget, "Config-1"))
    func = config.add_function(MassStorage(config,
                                            disk,
                                            write_perms=args.write,
                                            vendor_id="Anvil", product_id="Evil Mass", product_ver="0.1"))

    asyncio.run(gadget.run())


if __name__ == "__main__":
    main()
    