from ctypes import *
import enum

from ctype_utils import PrettyStructure, PrettyBigEndianStructure


# for the USB Bulk transport
CBW_MAGIC = 0x43425355
CSW_MAGIC = 0x53425355

class CMDDir(enum.IntEnum):
    HOST_TO_DEVICE = 0
    DEVICE_TO_HOST = 1

class CSWStatus(enum.IntEnum):
    PASSED = 0
    FAILED = 1
    PHASE_ERROR = 2


class CBW(PrettyStructure):
    _pack_ = 1
    _fields_ = [
        ("dCBWSignature", c_uint32),
        ("dCBWTag", c_uint32),
        ("dCBWDataTransferLength", c_uint32),
        ("bmCBWFlags_reserved", c_uint8, 7),
        ("bmCBWFlags_dir", c_uint8, 1),
        ("bCBWLUN", c_uint8, 4),
        ("reserved_1", c_uint8, 4),
        ("bCBWCBLength", c_uint8, 5),
        ("reserved_2", c_uint8, 3),
    ]

class CSW(PrettyStructure):
    _pack_ = 1
    _fields_ = [
        ("dCSWSignature", c_uint32),
        ("dCSWTag", c_uint32),
        ("dCSWDataResidue", c_uint32),
        ("bCSWStatus", c_uint8),
    ]

# for the SCSI commands
class SCSICmds(enum.IntEnum):
    TEST_UNIT_READY = 0x00
    REQUEST_SENSE = 0x03
    INQUIRY = 0x12
    MODE_SENSE = 0x1a
    PREVENT_ALLOW_MEDIUM_REMOVAL = 0x1e
    READ_CAPACITY = 0x25
    READ_10 = 0x28
    WRITE_10 = 0x2a

class SenseKeys(enum.IntEnum):
    NO_SENSE = 0x00
    RECOVERED_ERROR = 0x01
    NOT_READ = 0x02
    MEDIUM_ERROR = 0x03
    HARDWARE_ERROR = 0x04
    ILLEGAL_REQUEST = 0x05
    UNIT_ATTENTION = 0x06
    DATA_PROTECT = 0x07
    BLANK_CHECK = 0x08
    VENDOR_SPECIFIC = 0x09
    COPY_ABORTED = 0x0a
    ABORTED_COMMAND = 0xb
    VOLUME_OVERFLOW = 0x0d
    miscompare = 0x0E

class SCSICmd(PrettyBigEndianStructure):
    _pack_ = 1

class TestUnitReadyCmd(SCSICmd):
    _fields_ = [
        ("opcode", c_uint8),
        ("reserved", c_uint32),
        ("control", c_uint8),
    ]

class RequestSenseCmd(SCSICmd):
    _fields_ = [
        ("opcode", c_uint8),

        ("reserved_1", c_uint8, 7),
        ("desc", c_uint8, 1),

        ("reserved_2", c_uint8),
        ("reserved_3", c_uint8),
        ("allocation_length", c_uint8),
        ("control", c_uint8),
    ]

class RequestSenseData(SCSICmd):
    _fields_ = [
        ("valid", c_uint8, 1),
        ("response_code", c_uint8, 7),

        ("obsolete_1", c_uint8),
        
        ("filemark", c_uint8, 1),
        ("eom", c_uint8, 1),
        ("ili", c_uint8, 1),
        ("reserved_1", c_uint8, 1),
        ("sense_key", c_uint8, 4),

        ("information", c_uint32),
        ("additional_sense_length", c_uint8),
        ("command_specific_info", c_uint32),
        ("additonal_sense_code", c_uint8),
        ("additional_sense_code_qualifer", c_uint8),
        ("field_replaceable_unit_code", c_uint8),
        ("sense_key_specific", c_uint8*3),
    ]

class InquiryCmd(SCSICmd):
    _fields_ = [
        ("opcode", c_uint8),

        ("reserved_1", c_uint8, 7),
        ("evpd", c_uint8, 1),

        ("page_code", c_uint8),
        ("allocation_length", c_uint16),
        ("control", c_uint8),
    ]

class InquiryData(SCSICmd):
    _fields_ = [
        ("peripheral_qualifier", c_uint8, 3),
        ("peripheral_type", c_uint8, 5),

        ("rmb", c_uint8, 1),
        ("reserved_1", c_uint8, 7),

        ("version", c_uint8),

        ("obsolete_1", c_uint8, 2),
        ("norm_aca", c_uint8, 1),
        ("hisup", c_uint8, 1),
        ("response_data_format", c_uint8, 4),

        ("additional_length", c_uint8),

        ("sccs", c_uint8, 1),
        ("acc", c_uint8, 1),
        ("alua", c_uint8, 2),
        ("three_pc", c_uint8, 1),
        ("reserved_2", c_uint8, 2),
        ("protect", c_uint8, 1),

        ("bque", c_uint8, 1),
        ("enc_serv", c_uint8, 1),
        ("vs_1", c_uint8, 1),
        ("multi_p", c_uint8, 1),
        ("mc_hngr", c_uint8, 1),
        ("obsolete_2", c_uint8, 2),
        ("addr_16", c_uint8, 1),

        ("obsolete_4", c_uint8, 2),
        ("wbus_16", c_uint8, 1),
        ("sync", c_uint8, 1),
        ("linked", c_uint8, 1),
        ("obsolete_3", c_uint8, 1),
        ("cmd_que", c_uint8, 1),
        ("vs_2", c_uint8, 1),

        ("vendor_id", c_char*8),
        ("product_id", c_char*16),
        ("product_ver", c_char*4),

        # vendor specific stuff after this
    ]

class ReadCapacityCmd(SCSICmd):
    _fields_ = [
        ("opcode", c_uint8),
        ("reserved_1", c_uint8),
        ("logical_block_address", c_uint32),
        ("reserved_2", c_uint16),

        ("reserved_3", c_uint8, 7),
        ("pmi", c_uint8, 1),

        ("control", c_uint8),
    ]

class ReadCapacityData(SCSICmd):
    _fields_ = [
        ("returned_logical_block_address", c_uint32),
        ("logical_block_length", c_uint32),
    ]

class ModeSenseCmd(SCSICmd):
    _fields_ = [
        ("opcode", c_uint8),

        ("reserved_2", c_uint8, 4),
        ("dbd", c_uint8, 1),
        ("reserved_1", c_uint8, 3),

        ("pc", c_uint8, 2),
        ("page_code", c_uint8, 6),

        ("subpage_code", c_uint8),
        ("allocation_length", c_uint8),
        ("control", c_uint8),
    ]

class ModeSenseData(SCSICmd):
    _fields_ = [
        ("mode_data_length", c_uint8),
        ("medium_type", c_uint8),
        ("device_specific_param", c_uint8),
        ("block_descriptor_length", c_uint8),
    ]

class Read10Cmd(SCSICmd):
    _fields_ = [
        ("opcode", c_uint8),

        ("rdprotect", c_uint8, 3),
        ("dpo", c_uint8, 1),
        ("fua", c_uint8, 1),
        ("reserved_1", c_uint8, 1),
        ("fua_nv", c_uint8, 1),
        ("obsolete_1", c_uint8, 1),

        ("logical_block_address", c_uint32),

        ("reserved_2", c_uint8, 3),
        ("group_number", c_uint8, 5),

        ("transfer_length", c_uint16),
        ("control", c_uint8),
    ]

class Write10Cmd(SCSICmd):
    _fields_ = [
        ("opcode", c_uint8),
    
        ("wrprotect", c_uint8, 3),
        ("dpo", c_uint8, 1),
        ("fua", c_uint8, 1),
        ("reserved_1", c_uint8, 1),
        ("fua_nv", c_uint8, 1),
        ("obsolete_1", c_uint8, 1),

        ("logical_block_address", c_uint32),

        ("reserved_2", c_uint8, 3),
        ("group_number", c_uint8, 5),

        ("transfer_length", c_uint16),
        ("control", c_uint8),
    ]

