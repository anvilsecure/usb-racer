import os
import subprocess
import glob
import asyncio
import threading
import typing
import logging
import time

from .usb_ctypes import *

class GadgetError(Exception):
    pass

class LoggerMixin:

    def log_is_enabled(self, level : int | str):
        return self.logger.isEnabledFor(level)
    
    def debug(self, fmt, *args, **kwargs):
        self.logger.debug(fmt, *args, **kwargs)
    
    def info(self, fmt, *args, **kwargs):
        self.logger.info(fmt, *args, **kwargs)
    
    def warning(self, fmt, *args, **kwargs):
        self.logger.warning(fmt, *args, **kwargs)
    
    def error(self, fmt, *args, **kwargs):
        self.logger.error(fmt, *args, **kwargs)
        

class FSMixin(LoggerMixin):
    """
    Creates directiores and folders based on a "base_path" field.
    """

    def _mkdir(self, path : str):
        path = os.path.join(self.base_path, path)
        self.debug("mkdir: %s", path)
        os.makedirs(path, exist_ok=True)
    
    def _write(self, string : str, path : str):
        path = os.path.join(self.base_path, path)
        self.debug("write to: %s", path)
        with open(path, "w") as f:
            f.write(string)
    
    def _rm(self, path : str):
        for f in glob.glob(os.path.join(self.base_path, path)):
            self.debug("rm: %s", f)
            os.remove(f)
    
    def _rmdir(self, path : str):
        for f in glob.glob(os.path.join(self.base_path, path)):
            self.debug("rmdir: %s", f)
            os.rmdir(f)

class Gadget(FSMixin):
    vendor_id : int
    product_id : int
    serial_number : str
    manufacture : str
    product : str
    bcd_device : int
    bcd_usb : int
    device_class : int
    device_subclass : int
    gadget_path : str

    configs : list["Configuration"]
    stop_event : asyncio.Event
    
    logger = logging.getLogger("Gadget")

    def __init__(self,
                vendor_id : int,
                product_id : int,
                serial_number : str = "",
                manufacture : str = "",
                product : str = "",
                bcd_device : int = 0x0100,
                bcd_usb : int = 0x0200,
                device_class : int = 0x0,
                device_subclass : int = 0x0,
                gadget_path : str = "/sys/kernel/config/usb_gadget/g1",
                udc : str = None):
                
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial_number = serial_number
        self.manufacture = manufacture
        self.product = product
        self.bcd_device = bcd_device
        self.bcd_usb = bcd_usb
        self.device_class = device_class
        self.device_subclass = device_subclass
        self.gadget_path = gadget_path
        self.udc = udc

        self.configs = []

        self.load_modules()

        if self.udc == None:
            # try to grab the first UDC we see
            udcs = os.listdir("/sys/class/udc")
            if len(udcs) == 0:
                raise GadgetError("No udc found in /sys/class/udc... need to modprobe something?")
            self.udc = udcs[0]

    @property
    def base_path(self):
        return self.gadget_path
    
    def add_configuration(self, config : "Configuration") -> "Configuration":
        self.configs.append(config)
        config.index = len(self.configs)
        return config

    def load_modules(self):
        subprocess.run(["modprobe", "libcomposite"], check=True)
    

    def setup(self):
        self.setup_config()

        for config in self.configs:
            config.setup()

    def setup_config(self):
        # first delete whatever happens to be there

        # functions from configs
        self._rm("configs/*.*/*.*")
        # string directories
        self._rmdir("configs/*.*/strings/*")
        # the configs
        self._rmdir("configs/*.*")
        # functions
        self._rmdir("functions/*.*")
        # strings
        self._rmdir("strings/*")
        # gadget
        self._rmdir("")


        # setup some strings
        self._mkdir("strings/0x409")
        self._write(self.serial_number, "strings/0x409/serialnumber")
        self._write(self.manufacture, "strings/0x409/manufacturer")
        self._write(self.product, "strings/0x409/product")

        #setup ids
        self._write(f"0x{self.vendor_id:04x}", "idVendor")
        self._write(f"0x{self.product_id:04x}", "idProduct")
        self._write(f"0x{self.bcd_device:04x}", "bcdDevice")
        self._write(f"0x{self.bcd_usb:04x}", "bcdUSB")
        self._write(f"0x{self.device_class:x}", "bDeviceClass")
        self._write(f"0x{self.device_subclass:x}", "bDeviceSubClass")

        # setup the configs
        for config in self.configs:
            config.setup_config()
            
    def cleanup(self):
        self._write("", "UDC")

        for config in self.configs:
            config.cleanup()
    
    def enable(self):
        self._write(self.udc, "UDC")

    async def run(self):
        self.stop_event = asyncio.Event()
        try:
            self.setup()

            self.enable()

            await self.stop_event.wait()
        finally:
            self.cleanup()
    
    def stop(self):
        self.stop_event.set()


class Configuration(FSMixin):
    gadget : Gadget

    name : str
    index : str
    max_power : int

    functions : list["Function"]
    
    logger = logging.getLogger("Gadget/Config")
    
    def __init__(self, gadget : Gadget, name : str, max_power : int = 120):
        self.gadget = gadget
        self.name = name
        self.max_power = max_power
        self.functions = []

    @property
    def base_path(self):
        return os.path.join(self.gadget.base_path, "configs", f"c.{self.index}")
    
    def add_function(self, function : "Function") -> "Function":
        self.functions.append(function)
        return function
    
    def setup(self):
        for func in self.functions:
            func.setup()

    def setup_config(self):
        self._mkdir("strings/0x409")
        self._write(self.name, "strings/0x409/configuration")
        self._write(f"{self.max_power}", "MaxPower")

        for func in self.functions:
            func.setup_config()

    def cleanup(self):
        for func in self.functions:
            func.cleanup()

class Function(FSMixin):
    config : Configuration

    instance_name : str
    
    logger = logging.getLogger("Gadget/Function")

    def __init__(self, config : Configuration, instance_name : str):
        self.config = config
        self.instance_name = instance_name

    @property
    def name(self):
        raise NotImplementedError()

    @property
    def base_path(self):
        return os.path.join(self.config.gadget.base_path, "functions", self.function_dir)

    @property
    def function_dir(self):
        return f"{self.name}.{self.instance_name}"
    
    def setup(self):
        pass
    
    def setup_config(self):
        self._mkdir("")

        os.symlink(self.base_path, os.path.join(self.config.base_path, self.function_dir))
    
    def cleanup(self):
        pass


class FFSFunction(Function):
    
    logger = logging.getLogger("Gadget/FFSFunction")

    def __init__(self, config : Configuration, instance_name : str, fs_descs=[], hs_descs=[], ss_descs=[], strings=[], lang=0x409):
        super().__init__(config, instance_name)
        self.fs_descs = fs_descs
        self.hs_descs = hs_descs
        self.ss_descs = ss_descs
        self.strings = strings
        self.lang = lang
        self.ep0 = None
        self.enabled = False

    @property
    def name(self):
        return "ffs"
    
    @property
    def dev_path(self):
        return f"/dev/{self.instance_name}"
    
    def ep_path(self, index : int):
        return f"{self.dev_path}/ep{index}"

    def open_ep(self, index : int, mode : str):
        path = self.ep_path(index)
        
        self.debug("Opening ep: %s", path)
        
        return open(path, mode, buffering=0)

    def setup(self):
        self.setup_ep0()

    def setup_config(self):
        super().setup_config()

        os.makedirs(self.dev_path, exist_ok=True)
        subprocess.run(["mount", "-t", "functionfs", self.instance_name, self.dev_path], check=True)
    
    def cleanup(self):
        # remove our IOs
        asyncio.get_running_loop().remove_reader(self.ep0)
        self.ep0.close()
        self.ep0 = None

        # try our best to unmount
        time.sleep(0.5) # give a bit of time for the kernel to cleanup...
        subprocess.run(["umount", self.dev_path], check=False)
        time.sleep(0.5) # give a bit of time for the kernel to cleanup...
        self._rmdir(self.dev_path)

        super().cleanup()

    def setup_ep0(self):
        self.ep0 = self.open_ep(0, "rb+")
        try:
            self.ep0.write(build_descriptors_v2(fs_descs=self.fs_descs, hs_descs=self.hs_descs, ss_descs=self.ss_descs))
        except OSError as err:
            self.ep0.write(build_descriptors_v1(fs_descs=self.fs_descs, hs_descs=self.hs_descs, ss_descs=self.ss_descs))
        
        self.ep0.write(build_strings(self.lang, self.strings))
        
        asyncio.get_running_loop().add_reader(self.ep0, self.ep0_read)
    
    def ep0_read(self):
        event = usb_functionfs_event()
        self.ep0.readinto(event)

        event_type = USB_FUNCTIONFS_EVENT_TYPE(event.type)
        self.handle_ffs_event(event_type, event)
    
    def handle_ffs_event(self, event_type : USB_FUNCTIONFS_EVENT_TYPE, event : usb_functionfs_event):
        self.debug("FFS event: %s", USB_FUNCTIONFS_EVENT_TYPE(event_type).name)
        
        if event_type == USB_FUNCTIONFS_EVENT_TYPE.SETUP:
            self.handle_setup(event.setup)
        elif event_type == USB_FUNCTIONFS_EVENT_TYPE.ENABLE:
            self.handle_enable()
        elif event_type == USB_FUNCTIONFS_EVENT_TYPE.DISABLE:
            self.handle_disable()
    
    def handle_setup(self, ctrl_request : usb_ctrlrequest):
        ctrl_request.show()
        if ctrl_request.bRequestType_in:
            self.ep0.write(b"")
        else:
            self.ep0.read(1000)
    
    def handle_enable(self):
        self.enabled = True

    def handle_disable(self):
        self.enabled = False



class EPReader(threading.Thread):
    """
    Linux for some reason does not support polling on epX endpoints (while it does on ep0...).
    So this class is used to spawn a thread and read data and call a callback on the event loop.
    """

    def __init__(self, file : typing.BinaryIO, read_size : int, callback : typing.Callable[[bytes], None], runloop : asyncio.BaseEventLoop | None = None):
        super().__init__()
        self.file = file
        self.read_size = read_size
        self.stop = False
        self.callback = callback
        self.runloop = runloop if runloop != None else asyncio.get_running_loop()

    def run(self):
        while not self.stop:
            try:
                data = self.file.read(self.read_size)
            except Exception as err:
                print(f"Failed to read from {self.file}:", err)
                break

            if len(data) == 0 or self.stop:
                break # our file was closed... just stop
            self.runloop.call_soon_threadsafe(self.callback, data)
    
    def close(self):
        self.stop = True
        self.file.close()
