#!/usr/bin/env python

import asyncio
import enum
import typing
import logging

from .gadget import Gadget, Configuration, FFSFunction, EPReader
from .disks import DiskImage
from .usb_ctypes import *
from .mass_storage_ctypes import *
from .log import IOLogger

BULK_ONLY_TRANSPORT = 0x50

SCSI_TRANSPARENT_CMD_SET =  0x06

MAX_PACKET_SIZE = 0x200

class CLASS_REQUESTS(enum.IntEnum):
    GET_MAX_LUN = 254
    RESET = 255

class WritePerms(enum.Enum):
    ALLOW = 0
    DENY = 1
    DROP = 2

class MassStorageError(Exception):
    
    def __init__(self, msg, sense_key : SenseKeys = SenseKeys.ILLEGAL_REQUEST, sense_code : int = 0x20, sense_qualifier : int = 0):
        super().__init__(msg)
        self.sense_key = sense_key
        self.sense_code = sense_code
        self.sense_qualifier = sense_qualifier

type ReadCallback = typing.Callable[[int, int], bytes | None]
type WriteCallback = typing.Callable[[int, bytes]]

class MassStorage(FFSFunction):

    DESCRIPTORS = [
            usb_interface_descriptor(
                bLength = sizeof(usb_interface_descriptor),
                bDescriptorType = USB_DT.INTERFACE,
                bNumEndpoints = 2,
                bInterfaceClass = USB_CLASS.MASS_STORAGE,
                bInterfaceSubClass = SCSI_TRANSPARENT_CMD_SET,
                bInterfaceProtocol = BULK_ONLY_TRANSPORT,
                iInterface = 0,
            ),
            usb_endpoint_descriptor_no_audio(
                bLength = sizeof(usb_endpoint_descriptor_no_audio),
                bDescriptorType = USB_DT.ENDPOINT,
                bEndpointAddress = 1 | USB_DIR.IN,
                bmAttributes = USB_ENDPOINT_XFER.BULK,
                wMaxPacketSize = MAX_PACKET_SIZE,
                bMaxBurst = 4
            ),
            usb_endpoint_descriptor_no_audio(
                bLength = sizeof(usb_endpoint_descriptor_no_audio),
                bDescriptorType = USB_DT.ENDPOINT,
                bEndpointAddress = 2 | USB_DIR.OUT,
                bmAttributes = USB_ENDPOINT_XFER.BULK,
                wMaxPacketSize = MAX_PACKET_SIZE,
                bMaxBurst = 4
            )
        ]
    
    STRINGS = [
            "Anvil's Envil Mass Storage"
        ]
    

    scsi_handlers : dict[SCSICmds, tuple[SCSICmd, typing.Callable[[type[SCSICmd]], bytes]]]

    def __init__(self, config : Configuration, 
                 image : DiskImage,
                 write_perms : WritePerms = WritePerms.ALLOW,
                 vendor_id : str = "", product_id : str = "", product_ver : str = ""):
        super().__init__(config, "mass0", hs_descs=MassStorage.DESCRIPTORS, strings=MassStorage.STRINGS)
        self.image = image

        self.write_perms = write_perms

        self.vendor_id = vendor_id
        self.product_id = product_id
        self.product_ver = product_ver
        self.ep1 = None
        self.ep2_reader = None

        self.ep2_data_queue = asyncio.Queue()

        self.sense_key = SenseKeys.NO_SENSE
        self.sense_code = 0
        self.sense_qualifier = 0

        self.scsi_handlers = {
            SCSICmds.TEST_UNIT_READY:(TestUnitReadyCmd, self.handle_test_unit_ready),
            SCSICmds.REQUEST_SENSE:(RequestSenseCmd, self.handle_request_sense),
            SCSICmds.INQUIRY:(InquiryCmd, self.handle_inquiry),
            SCSICmds.MODE_SENSE:(ModeSenseCmd, self.handle_mode_sense),
            SCSICmds.READ_CAPACITY:(ReadCapacityCmd, self.handle_read_capacity),
            SCSICmds.READ_10:(Read10Cmd, self.handle_read_cmd),
            SCSICmds.WRITE_10:(Write10Cmd, self.handle_write_cmd),
        }

        self.read_callbacks = list[ReadCallback]()
        self.write_callbacks = list[WriteCallback]()

    def cleanup(self):
        self.handle_disable()

        super().cleanup()
    
    def handle_setup(self, ctrl_request : usb_ctrlrequest):
        if ctrl_request.bRequestType_recip == USB_RECIP.INTERFACE and \
                ctrl_request.bRequestType_type == USB_TYPE.CLASS:
            
            if ctrl_request.bRequest == CLASS_REQUESTS.GET_MAX_LUN:
                # this was a request to get the number of LUN devices
                # just have one... for now
                self.info("Got Get Max LUN Request")
                self.ep0.write(b"\x00")
                return
        
        # was not handled here... give to super class
        super().handle_setup(ctrl_request)
        
    def handle_enable(self):
        super().handle_enable()

        self.ep1 = self.open_ep(1, "wb")

        self.ep2_reader = EPReader(self.open_ep(2, "rb+"), MAX_PACKET_SIZE, self.ep2_received_data)
        self.ep2_reader.start()

        asyncio.create_task(self.ep2_handler())

    
    def handle_disable(self):
        if self.ep2_reader:
            self.ep2_reader.close()
            self.ep2_reader = None

        if self.ep1 != None:
            self.ep1.close()
            self.ep1 = None

        super().handle_disable()
    
    def write_rsp(self, cbw : CBW, scsi_rsp : SCSICmd | None, status : CSWStatus):
        residue = 0

        self.debug("sending response status = %s", status.name)
        if scsi_rsp != None:
            if isinstance(scsi_rsp, SCSICmd):
                if self.log_is_enabled(logging.DEBUG):
                    scsi_rsp.show()
                scsi_rsp = bytes(scsi_rsp)

            # figure out the data residue
            if len(scsi_rsp) < cbw.dCBWDataTransferLength:
                residue = cbw.dCBWDataTransferLength - len(scsi_rsp)
                scsi_rsp += b"\x00" * residue
            elif len(scsi_rsp) > cbw.dCBWDataTransferLength:
                scsi_rsp = scsi_rsp[:cbw.dCBWDataTransferLength]
                status = CSWStatus.PHASE_ERROR

        csw = CSW(
            dCSWSignature = CSW_MAGIC,
            dCSWTag = cbw.dCBWTag,
            dCSWDataResidue = residue,
            bCSWStatus = status,
        )

        if self.log_is_enabled(logging.DEBUG):
            csw.show()

        csw = bytes(csw)

        if scsi_rsp != None:
            if self.log_is_enabled(logging.DEBUG):
                self.debug("Write Data: %s (length=%d)", scsi_rsp[:50].hex(), len(scsi_rsp))
            
            #while len(scsi_rsp) > 0:
            #    self.ep1.write(scsi_rsp[:MAX_PACKET_SIZE])
            #    scsi_rsp = scsi_rsp[MAX_PACKET_SIZE:]
            self.ep1.write(scsi_rsp)

        if self.log_is_enabled(logging.DEBUG):
            self.debug("Write CSW: %s (length=%d)", csw.hex(), len(csw))
        self.ep1.write(csw)

        self.debug("response done!")

    def ep2_received_data(self, data : bytes):
        self.ep2_data_queue.put_nowait(data)

    async def ep2_handler(self):
        while self.enabled:
            data = await self.ep2_data_queue.get()
            await self.handle_cmd(data)

    async def handle_cmd(self, data : bytes):
        cbw = CBW.from_buffer_copy(data[:sizeof(CBW)])
        payload = data[sizeof(CBW):sizeof(CBW)+cbw.bCBWCBLength]


        if self.log_is_enabled(logging.DEBUG):
            cbw.show()

        scsi_rsp = None
        status = CSWStatus.PASSED

        try:
            cmd = SCSICmds(payload[0])
        except:
            cmd = payload[0]

        if cmd in self.scsi_handlers:
            cmd_class, cmd_handler = self.scsi_handlers[cmd]
            try:
                if asyncio.iscoroutinefunction(cmd_handler):
                    scsi_rsp = await cmd_handler(cmd_class.from_buffer_copy(payload[:sizeof(cmd_class)]))
                else:
                    scsi_rsp = cmd_handler(cmd_class.from_buffer_copy(payload[:sizeof(cmd_class)]))
            except MassStorageError as err:
                self.info("Prevented access, returning error")
                self.set_sense(err.sense_key, err.sense_code, err.sense_qualifier)
                status = CSWStatus.FAILED
            except Exception as err:
                self.error("Failed to handle command %s",
                           cmd.name if isinstance(cmd, SCSICmds) else hex(cmd),
                           exc_info=err)
                self.set_sense(SenseKeys.ILLEGAL_REQUEST, 0x26) # just making up a reason
                status = CSWStatus.FAILED
        else:
            cmd_str = cmd.name if isinstance(cmd, SCSICmds) else hex(cmd)
            self.warning("No command registered for: %s payload: %s", cmd_str, payload.hex())
            self.set_sense(SenseKeys.ILLEGAL_REQUEST, 0x26) # Invalid field in paramater list? other drives returned this error so just doing it as well
            status = CSWStatus.FAILED
        

        self.write_rsp(cbw, scsi_rsp, status)
    
    async def ep2_read(self, size : int):
        chunks = []
        while size > 0:
            chunk = await self.ep2_data_queue.get()
            chunks.append(chunk)
            size -= len(chunk)

        return b"".join(chunks)
    
    def set_sense(self, key : SenseKeys, code : int, qualifier : int = 0):
        self.sense_key = key
        self.sense_code = code
        self.sense_qualifier = qualifier

    def handle_test_unit_ready(self, cmd : TestUnitReadyCmd):
        self.info("Received test unit ready, returning no error (aka media inserted)")
        return None
    
    def handle_request_sense(self, cmd : RequestSenseData):
        self.info("Received request sense command")
        rsp = RequestSenseData(
            response_code = 0x70, # current, fixed response
            additional_sense_length = sizeof(RequestSenseData) - 8, # no additional data beyeond the fixed response
            sense_key = self.sense_key,
            additonal_sense_code = self.sense_code,
            additional_sense_code_qualifer = self.sense_qualifier,
        )

        # sincet hey read it, clear out any errors
        self.sense_key = SenseKeys.NO_SENSE
        self.sense_code = 0

        return rsp

    def handle_inquiry(self, cmd : InquiryCmd):
        self.info("Received inquiry command")
        if cmd.evpd != 0:
            self.error("Host is asking for an extended inquiry... don't know how to do that!")
            return
        
        rsp = InquiryData(
            rmb = 1, # removable
            version = 0x05, # SPC-3
            response_data_format = 0x02, # SPC-3 version of data,
            vendor_id = self.vendor_id.encode(),
            product_id = self.product_id.encode(),
            product_ver = self.product_ver.encode(),

            additional_length = 0x1f,
        )

        return rsp

    def handle_mode_sense(self, cmd : ModeSenseCmd):
        self.info("Received Mode Sense")
        return ModeSenseData(mode_data_length=3)

    def handle_read_capacity(self, cmd : ReadCapacityCmd):
        self.info("Received Read Capacity")

        if cmd.pmi != 0:
            raise MassStorageError("Do not know how to handle a read capacity with a PMI == 1")
        
        last_lba = self.image.capacity - 1 # LBAs start numbering at 0...

        if last_lba >= 0xffff_ffff:
            raise MassStorageError("Image too large, need to implement read capacity 16")
        
        return ReadCapacityData(
            returned_logical_block_address=last_lba,
            logical_block_length=self.image.block_size,
        )

    def handle_read_cmd(self, cmd : Read10Cmd):
        self.info("Reading block address = %s num_blocks = %s", cmd.logical_block_address, cmd.transfer_length)
        for callback in self.read_callbacks:
            data = callback(cmd.logical_block_address, cmd.transfer_length)
            if data != None:
                return data
        return self.image.read(cmd.logical_block_address, cmd.transfer_length)

    async def handle_write_cmd(self, cmd : Write10Cmd):
        self.info("Writing to block address = %s, num_blocks = %s", cmd.logical_block_address, cmd.transfer_length)

        data = await self.ep2_read(cmd.transfer_length * self.image.block_size)

        for callback in self.write_callbacks:
            callback(cmd.logical_block_address, data)

        if self.write_perms == WritePerms.ALLOW:
            self.image.write(cmd.logical_block_address, data)
        
        if self.write_perms == WritePerms.DENY:
            print("Here!")
            raise MassStorageError("Writes are denied", SenseKeys.DATA_PROTECT, 0x20, 0x02)
        
        # else we return normal to indicate success for allow or drop permisions
