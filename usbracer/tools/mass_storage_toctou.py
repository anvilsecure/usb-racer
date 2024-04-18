#!/usr/bin/env python

def main():
    import logging
    import argparse
    import asyncio
    import sys

    from usbracer.disks import MMapDiskImage, TOCOTUDiskImage, FileReadOverride, DiskOverrideImage
    from usbracer.gadget import Gadget, Configuration
    from usbracer.mass_storage import MassStorage        

    parser = argparse.ArgumentParser()
    parser.add_argument("disk", help="Path to disk image")

    group = parser.add_argument_group("Second Image")
    group = group.add_mutually_exclusive_group(required=True)
    group.add_argument("--toggle-image", help="A full image to toggle between")
    group.add_argument("--offset-override", action="append", nargs=2,
        help="The next two arguments are used as an offset and a path, can be specified multipule times")

    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--toggle-delay", type=float, help="Automatically toggles the disks after a delay (in seconds)")
    parser.add_argument("--toggle-read-block", type=int, help="Toggle disks after a read on a specific block")
    parser.add_argument("--debug-level", default=logging.WARNING)
    args = parser.parse_args()

    logging.basicConfig(level=args.debug_level)
    VENDOR_ID = 0x1234
    PRODUCT_ID = 0x4321

    disk = MMapDiskImage(args.disk, args.block_size)

    if args.toggle_image != None:
        disk_b = MMapDiskImage(args.toggle_image, args.block_size)
        disk = TOCOTUDiskImage(disk, disk_b)
    else:
        read_overrides = []
        for offset, path in args.offset_override:
            file_override = FileReadOverride(path, args.block_size, int(offset, 0))
            read_overrides.append((file_override.override_key, file_override))
        disk = DiskOverrideImage(disk)

    gadget = Gadget(VENDOR_ID, PRODUCT_ID, manufacture="Anvil", product="Evil Mass Storage")
    config = gadget.add_configuration(Configuration(gadget, "Config-1"))
    func = config.add_function(MassStorage(config,
                                            disk,
                                            vendor_id="Anvil", product_id="Evil Mass", product_ver="0.1"))

    def toggle():
        if args.toggle_image:
            print("Toggled disk images")
            disk.toggle_disks()
        else:
            if len(disk.read_overrides) == 0:
                print("Added read overrides")
                disk.read_overrides.extend(read_overrides)
            else:
                print("Removed read overides")
                disk.read_overrides.clear()

    async def toggle_disk_keyboard():
        print("Hit the enter key to toggle disks!")
        reader = asyncio.StreamReader()
        await asyncio.get_running_loop().connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
        
        async for line in reader:
            toggle()

    def read_callback(offset : int, num_blocks : int):
        blk = args.toggle_read_block
        if blk >= offset and blk <= (offset + num_blocks):
            def do_toggle():
                print(f"Toggling disks after read on {blk}")
                toggle()
            # let the current handling complete before toggling disks
            asyncio.get_running_loop().call_soon(do_toggle)
            func.read_callbacks.remove(read_callback)

    async def main():
        keyboard_toggle = asyncio.create_task(toggle_disk_keyboard())

        if args.toggle_delay != None:
            print(f"Scheduling a toggle after {args.toggle_delay:.2f} seconds")
            asyncio.get_running_loop().call_later(args.toggle_delay, toggle)
        
        if args.toggle_read_block != None:
            func.read_callbacks.append(read_callback)

        await gadget.run()

    asyncio.run(main())

if __name__ == "__main__":
    main()
    