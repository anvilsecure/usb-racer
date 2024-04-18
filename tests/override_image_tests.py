import unittest
import io

from usbracer.disks import DiskOverrideImage, MemoryDiskImage, DiskImage, FileReadOverride

# the following only work for disks with 255 or less blocks

def read_callback(disk : DiskImage, offset : int, num_blocks : int) -> bytes:
    return offset.to_bytes(1) * (disk.block_size * num_blocks)

def expand(disk : DiskImage, pattern : bytes) -> bytes:
    datas = []
    for b in pattern:
        datas.append(b.to_bytes(1) * disk.block_size)
    return b"".join(datas)

class TestDiskOverrideImage(unittest.TestCase):

    def test_single_page(self):
        mem_disk = MemoryDiskImage(512, 20)
        disk = DiskOverrideImage(mem_disk, read_overrides = [
            (3, read_callback) 
        ])

        self.assertEqual(expand(disk, b"\x03"), disk.read(3, 1))
        self.assertEqual(expand(disk, b"\x00\x03"), disk.read(2,2))
        self.assertEqual(expand(disk, b"\x03\x00"), disk.read(3,2))
        self.assertEqual(expand(disk, b"\x00\x03\x00"), disk.read(2,3))
    
    def test_ranged_pages(self):
        mem_disk = MemoryDiskImage(512, 20)
        disk = DiskOverrideImage(mem_disk, read_overrides = [
            ((3,4), read_callback) 
        ])

        self.assertEqual(expand(disk, b"\x03"), disk.read(3, 1))
        self.assertEqual(expand(disk, b"\x03\x03"), disk.read(3, 2))
        self.assertEqual(expand(disk, b"\x00\x03"), disk.read(2,2))
        self.assertEqual(expand(disk, b"\x04\x00"), disk.read(4,2)) # started reading at offset 4
        self.assertEqual(expand(disk, b"\x00\x03\x03\x00"), disk.read(2,4))
    

    def test_ranged_pages_ext(self):
        mem_disk = MemoryDiskImage(512, 20)
        disk = DiskOverrideImage(mem_disk, read_overrides = [
            ((3,6), read_callback) 
        ])

        self.assertEqual(expand(disk, b"\x03"), disk.read(3, 1))
        self.assertEqual(expand(disk, b"\x03"*2), disk.read(3, 2))
        self.assertEqual(expand(disk, b"\x03"*3), disk.read(3, 3))
        self.assertEqual(expand(disk, b"\x03"*4), disk.read(3, 4))
        self.assertEqual(expand(disk, b"\x00\x03"), disk.read(2,2))
        self.assertEqual(expand(disk, b"\x06\x00"), disk.read(6,2)) # started reading at offset 4
        self.assertEqual(expand(disk, b"\x00\x03\x03\x03\x03\x00"), disk.read(2,6))

    def test_multi_single_page(self):
        mem_disk = MemoryDiskImage(512, 20)
        disk = DiskOverrideImage(mem_disk, read_overrides = [
            (3, read_callback),
            (4, read_callback) 
        ])

        self.assertEqual(expand(disk, b"\x03"), disk.read(3, 1))
        self.assertEqual(expand(disk, b"\x03\x04"), disk.read(3, 2))
        self.assertEqual(expand(disk, b"\x00\x03"), disk.read(2,2))
        self.assertEqual(expand(disk, b"\x04\x00"), disk.read(4,2))
        self.assertEqual(expand(disk, b"\x00\x03\x04\x00"), disk.read(2,4))
    
    def test_multi_single_page_gap(self):
        mem_disk = MemoryDiskImage(512, 20)
        disk = DiskOverrideImage(mem_disk, read_overrides = [
            (3, read_callback),
            (5, read_callback) 
        ])

        self.assertEqual(expand(disk, b"\x03"), disk.read(3, 1))
        self.assertEqual(expand(disk, b"\x03\x00"), disk.read(3, 2))
        self.assertEqual(expand(disk, b"\x03\x00\x05"), disk.read(3, 3))
        self.assertEqual(expand(disk, b"\x00\x03\x00\x05\x00"), disk.read(2,5))
    
    def test_mixed_pages(self):
        mem_disk = MemoryDiskImage(512, 20)
        disk = DiskOverrideImage(mem_disk, read_overrides = [
            (3, read_callback),
            ((5,7), read_callback) 
        ])

        self.assertEqual(expand(disk, b"\x03"), disk.read(3, 1))
        self.assertEqual(expand(disk, b"\x03\x00"), disk.read(3, 2))
        self.assertEqual(expand(disk, b"\x03\x00\x05"), disk.read(3, 3))
        self.assertEqual(expand(disk, b"\x03\x00\x05\x05"), disk.read(3, 4))
        self.assertEqual(expand(disk, b"\x03\x00\x05\x05\x05"), disk.read(3, 5))
        self.assertEqual(expand(disk, b"\x03\x00\x05\x05\x05\x00"), disk.read(3, 6))

        self.assertEqual(expand(disk, b"\x00\x03\x00\x05\x05\x05\x00"), disk.read(2,7))
    
    def test_filereaderoverride(self):
        mem_disk = MemoryDiskImage(512, 20)
        override = FileReadOverride(io.BytesIO(b"A"*1026), 512, 3)
        
        disk = DiskOverrideImage(mem_disk, read_overrides = [
            (override.override_key, override)
        ])

        self.assertEqual(b"A"*512, disk.read(3, 1))
        self.assertEqual(b"A"*512, disk.read(4, 1))
        self.assertEqual(b"A"*1024, disk.read(3, 2))
        self.assertEqual(b"AA" + b"\x00" * 510, disk.read(5, 1))
        self.assertEqual(expand(disk, b"\x00AA") + b"AA" + b"\x00" * 510, disk.read(2,4))



if __name__ == "__main__":
    unittest.main()
        
