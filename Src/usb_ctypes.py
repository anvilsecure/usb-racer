from ctypes import *
import enum
import struct

from ctype_utils import PrettyStructure

FUNCTIONFS_DESCRIPTORS_MAGIC = 1
FUNCTIONFS_STRINGS_MAGIC = 2
FUNCTIONFS_DESCRIPTORS_MAGIC_V2 = 3

class FUNCTIONFS_FLAGS(enum.IntFlag):
    HAS_FS_DESC = 1
    HAS_HS_DESC = 2
    HAS_SS_DESC = 4
    HAS_MS_OS_DESC = 8
    VIRTUAL_ADDR = 16
    EVENTFD = 32
    ALL_CTRL_RECIP = 64
    CONFIG0_SETUP = 128

class USB_DT(enum.IntEnum):
    INTERFACE = 0x04
    ENDPOINT = 0x05

class USB_CLASS(enum.IntEnum):
    MASS_STORAGE = 8

class USB_DIR(enum.IntFlag):
    OUT = 0
    IN = 0X80

class USB_ENDPOINT_XFER(enum.IntEnum):
    BULK = 2

class USBStructure(PrettyStructure):
    _pack_ = 1

class usb_functionfs_strings_head(USBStructure):
    _fields_ = [
        ("magic", c_uint32),
        ("length", c_uint32),
        ("str_count", c_uint32),
        ("lang_count", c_uint32),
    ]


class usb_functionfs_descs_head_v2(USBStructure):
    _fields_ = [
        ("magic", c_uint32),
        ("length", c_uint32),
        ("flags", c_uint32),
        ("fs_count", c_uint32),
        ("hs_count", c_uint32),
        ("ss_count", c_uint32),
    ]

class usb_functionfs_descs_head(USBStructure):
    _fields_ = [
        ("magic", c_uint32),
        ("length", c_uint32),
        ("fs_count", c_uint32),
        ("hs_count", c_uint32),
    ]

class usb_interface_descriptor(USBStructure):
    _fields_ = [
	    ("bLength", c_uint8),
		("bDescriptorType", c_uint8),
		("bInterfaceNumber", c_uint8),
		("bAlternateSetting", c_uint8),
		("bNumEndpoints", c_uint8),
		("bInterfaceClass", c_uint8),
		("bInterfaceSubClass", c_uint8),
		("bInterfaceProtocol", c_uint8),
		("iInterface", c_uint8),
    ]

class usb_endpoint_descriptor_no_audio(USBStructure):
    _fields_ = [
        ("bLength", c_uint8),
        ("bDescriptorType", c_uint8),
        ("bEndpointAddress", c_uint8),
        ("bmAttributes", c_uint8),
        ("wMaxPacketSize", c_uint16),
        ("bInterval", c_uint8),
    ]

def build_descriptors_v2(fs_descs : list[Structure] = [], hs_descs : list[Structure] = [], ss_descs : list[Structure] = []):
    fs_descs_bytes = b"".join(fs_descs)
    hs_descs_bytes = b"".join(hs_descs)
    ss_descs_bytes = b"".join(ss_descs)

    flags = 0

    if len(fs_descs) > 0:
        flags |= FUNCTIONFS_FLAGS.HAS_FS_DESC
    if len(hs_descs) > 0:
        flags |= FUNCTIONFS_FLAGS.HAS_HS_DESC
    if len(ss_descs) > 0:
        flags |= FUNCTIONFS_FLAGS.HAS_SS_DESC

    header = usb_functionfs_descs_head_v2(
        magic = FUNCTIONFS_DESCRIPTORS_MAGIC_V2,
        length = sizeof(usb_functionfs_descs_head_v2) + len(fs_descs_bytes) + len(hs_descs_bytes) + len(ss_descs_bytes),
        flags = flags,
        fs_count = len(fs_descs),
        hs_count = len(hs_descs),
        ss_count = len(ss_descs)
    )

    return b"".join((header, fs_descs_bytes, hs_descs_bytes, ss_descs_bytes))

def build_descriptors_v1(fs_descs : list[Structure] = [], hs_descs : list[Structure] = [], ss_descs : list[Structure] = []):
    fs_descs_bytes = b"".join(fs_descs)
    hs_descs_bytes = b"".join(hs_descs)
    ss_descs_bytes = b"".join(ss_descs)

    header = usb_functionfs_descs_head(
        magic = FUNCTIONFS_DESCRIPTORS_MAGIC,
        length = sizeof(usb_functionfs_descs_head) + len(fs_descs_bytes) + len(hs_descs_bytes) + len(ss_descs_bytes),
        fs_count = len(fs_descs),
        hs_count = len(hs_descs),
    )

    return b"".join((header, fs_descs_bytes, hs_descs_bytes, ss_descs_bytes))

def build_strings(lang_code : int, strings : list[str]):
    data = struct.pack("<H", lang_code)
    str_data = "\0".join(strings) + "\0"
    data += str_data.encode()

    header = usb_functionfs_strings_head(
        magic = FUNCTIONFS_STRINGS_MAGIC,
        length = sizeof(usb_functionfs_strings_head) + len(data),
        str_count = len(strings),
        lang_count = 1,
    )

    return bytes(header) + data



class USB_FUNCTIONFS_EVENT_TYPE(enum.IntEnum):
    BIND = 0
    UNBIND = 1
    ENABLE = 2
    DISABLE = 3
    SETUP = 4
    SUSPEND = 5
    RESUME = 6


class USB_TYPE(enum.IntFlag):
    STANDARD = 0x00
    CLASS = 0x01
    VENDOR = 0x02
    RESERVED = 0x03

class USB_RECIP(enum.IntFlag):
    DEVICE = 0x00
    INTERFACE = 0x01
    ENDPOINT = 0x02 
    OTHER = 0x03


class usb_ctrlrequest(USBStructure):
    _fields_ = [
        ("bRequestType_recip", c_uint8, 5),
        ("bRequestType_type", c_uint8, 2),
        ("bRequestType_in", c_uint8, 1),
        ("bRequest", c_uint8),
        ("wValue", c_uint16),
        ("wIndex", c_uint16),
        ("wLength", c_uint16),
    ]


class usb_functionfs_event(USBStructure):
    _fields_ = [
        ("setup", usb_ctrlrequest),
        ("type", c_uint8),
        ("_pad", c_uint8*3),
    ]

