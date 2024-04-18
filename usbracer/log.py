import ctypes
import enum

from .disks import DiskImage

class IOOp(enum.IntEnum):
    READ = 0
    WRITE = 1

class LogFlags(enum.IntFlag):
    NONE = 0
    INCLUDES_DATA = 1

class LogHeader(ctypes.Structure):
    _fields_ = [
        ("block_size", ctypes.c_uint32),
        ("capacity", ctypes.c_uint64),
        ("flags", ctypes.c_uint32)
    ]

class LogEntry(ctypes.Structure):
    _fields_ = [
        ("op", ctypes.c_ubyte),
        ("offset", ctypes.c_uint64),
        ("count", ctypes.c_uint32),
    ]

class IOLogger(DiskImage):
    '''
    Logs IO reads and writes. Log is a binary file with the following.

    Header:
    | Block Size | Capacity | Flags |

    Entries:
    | Op (Read or Write) | Offset (in blocks) | Count (in blocks) | Data (if flags.INCLUDES_DATA is set) |
    '''

    def __init__(self, path : str, include_data : bool, image : DiskImage):
        super().__init__(image.block_size, image.capacity)
        self.image = image
        self.log = open(path, "wb")
        self.include_data = include_data

        flags = LogFlags.NONE
        if self.include_data:
            flags |= LogFlags.INCLUDES_DATA

        hdr = LogHeader(block_size=self.image.block_size, capacity=self.image.capacity, flags=flags)
        self.log.write(hdr)
    
    def read(self, offset_block: int, num_blocks: int) -> bytes:
        data =  self.image.read(offset_block, num_blocks)
        entry = LogEntry(op=IOOp.READ, offset=offset_block, count=num_blocks)
        self.log.write(entry)
        if self.include_data:
            self.log.write(data)
        return data

    def write(self, offset_block: int, data: bytes):
        self.image.write(offset_block, data)
        entry = LogEntry(op=IOOp.WRITE, offset=offset_block, count=self.bytes_to_block(len(data)))
        self.log.write(entry)
        if self.include_data:
            self.log.write(data)

    def cleanup(self):
        self.log.close()
        self.image.cleanup()
        return super().cleanup()

class IOLogReader:

    def __init__(self, path : str):
        self.log = open(path, "rb")
        self.hdr = LogHeader()
        self.log.readinto(self.hdr)
        self.includes_data = self.hdr.flags & LogFlags.INCLUDES_DATA

        # just create one of these...
        self.entry = LogEntry()
    
    @property
    def block_size(self):
        return self.hdr.block_size
    
    @property
    def capacity(self):
        return self.hdr.capacity
    
    @property
    def flags(self):
        return LogFlags(self.hdr.flags)

    def entries(self):
        while True:
            if self.log.readinto(self.entry) == 0:
                break
            
            if self.includes_data:
                data = self.log.read(self.entry.count * self.hdr.block_size)
            else:
                data = b""
            
            yield IOOp(self.entry.op), self.entry.offset, self.entry.count, data
