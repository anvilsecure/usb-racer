import os
import mmap
import bitarray

class DiskError(Exception):
    pass

class DiskImage:

    def __init__(self, block_size : int, capacity : int):
        self.block_size = block_size
        self.capacity = capacity
    
    @property
    def capacity_bytes(self):
        return self.capacity * self.block_size
    
    def bytes_to_block(self, byte_count):
        return (byte_count + self.block_size - 1) // self.block_size

    def read(self, offset_block : int, num_blocks : int) -> bytes:
        raise NotImplemented()

    def write(self, offset_block : int, data : bytes):
        raise NotImplemented()
    
    def cleanup(self):
        return
    
class FileDiskImage(DiskImage):

    def __init__(self, path : str, block_size : int, new_size : int = 0):
        try:
            self.image = open(path, "rb+")
        except FileNotFoundError:
            if new_size != 0:
                self.image = open(path, "wb+")
                self.image.truncate(new_size)
            else:
                raise

        self.image_size = os.fstat(self.image.fileno()).st_size
        super().__init__(block_size, self.image_size // block_size)

    def read(self, offset_block : int, num_blocks : int) -> bytes:
        self.image.seek(offset_block * self.block_size, os.SEEK_SET)
        return self.image.read(num_blocks * self.block_size)

    def write(self, offset_block : int, data : bytes):
        self.image.seek(offset_block * self.block_size, os.SEEK_SET)
        self.image.write(data)
    
    def cleanup(self):
        self.image.close()


class MMapDiskImage(FileDiskImage):

    def __init__(self, path : str, block_size : int, new_size : int = 0):
        super().__init__(path, block_size, new_size)
        self.image_file = self.image
        self.image = mmap.mmap(self.image_file.fileno(), 0)
    
    def cleanup(self):
        self.image.flush()
        self.image.close()
        self.image_file.close()

class COWDiskImage(DiskImage):

    METADATA_EXT = ".metadata"

    def __init__(self, path : str, block_size : int, write_path : str):
        self.read_disk = MMapDiskImage(path, block_size)
        self.write_disk = MMapDiskImage(write_path, block_size, new_size=self.read_disk.image_size)
        self.metadata_file = open(write_path + COWDiskImage.METADATA_EXT, "ab+")
        self.metadata_file.truncate((self.read_disk.capacity + 7) // 8)
        self.metadata_map = mmap.mmap(self.metadata_file.fileno(), 0)
        self.metadata = bitarray.bitarray(buffer=self.metadata_map, endian='little')

        super().__init__(block_size, self.read_disk.capacity)
    
    def read(self, offset_block: int, num_blocks: int) -> bytes:
        # quick out check
        if not self.metadata[offset_block:offset_block + num_blocks].any():
            return self.read_disk.read(offset_block, num_blocks)
        else:
            reads = []
            end_block = offset_block + num_blocks
            while num_blocks > 0:
                if self.metadata[offset_block] == 1:
                    value = 0
                    src = self.write_disk
                else:
                    value = 1
                    src = self.read_disk
                tmp_end = self.metadata.find(value, offset_block, end_block)
                if tmp_end == -1:
                    tmp_end = end_block
                tmp_count = tmp_end - offset_block
                reads.append(src.read(offset_block, tmp_count))
                offset_block += tmp_count
                num_blocks -= tmp_count
        return b"".join(reads)
    
    def write(self, offset_block: int, data: bytes):
        self.write_disk.write(offset_block, data)
        self.metadata[offset_block:offset_block + self.bytes_to_block(len(data))] = 1
    
    def cleanup(self):
        self.read_disk.cleanup()
        self.write_disk.cleanup()
        self.metadata_map.flush()
        self.metadata_map.close()
        self.metadata_file.close()
