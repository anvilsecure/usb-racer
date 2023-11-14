#!/usr/bin/env python

import random

from mass_storage import *
from mass_storage_ctypes import TestUnitReadyCmd

class CacheFlushStorage(MassStorage):

    def handle_enable(self):
        super().handle_enable()
        self.return_error = False

        asyncio.get_running_loop().add_reader(0, self.on_input)

    def on_input(self):
        print("============================ Triggered!")
        self.return_error = True
        asyncio.get_running_loop().remove_reader(0)

    def handle_test_unit_ready(self, cmd: TestUnitReadyCmd):
        if self.return_error:
            raise MassStorageError("Force an error", random.randint(0,0xff), random.randint(0,0xff), random.randint(0,0xff))
        return super().handle_test_unit_ready(cmd)



if __name__ == "__main__":
    import logging
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to the first disk image")
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--write", type=WritePerms.__getitem__, default=WritePerms.ALLOW)
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG)
    VENDOR_ID = 0x1234
    PRODUCT_ID = 0x4321
    
    
    gadget = Gadget(VENDOR_ID, PRODUCT_ID, manufacture="Anvil", product="Evil Mass Storage")
    config = gadget.add_configuration(Configuration(gadget, "Config-1"))
    func = config.add_function(CacheFlushStorage(config,
                                           args.image, args.block_size,
                                           write_perms=args.write,
                                           vendor_id="Anvil", product_id="Evil Mass", product_ver="0.1"))
    
    asyncio.run(gadget.run())