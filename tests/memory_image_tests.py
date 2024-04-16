import unittest

from mass.disks import MemoryDiskImage, DiskImage

# the following only work for disks with 255 or less blocks

def read_callback(disk : DiskImage, offset : int, num_blocks : int) -> bytes:
    return offset.to_bytes(1) * (disk.block_size * num_blocks)

def expand(disk : DiskImage, pattern : bytes) -> bytes:
    datas = []
    for b in pattern:
        datas.append(b.to_bytes(1) * disk.block_size)
    return b"".join(datas)

class TestMemoryImage(unittest.TestCase):

    def test_single_page(self):
        disk = MemoryDiskImage(512, 20)

        disk.write(3, b"\x03"*512)

        self.assertEqual(expand(disk, b"\x03"), disk.read(3, 1))
        self.assertEqual(expand(disk, b"\x00\x03"), disk.read(2,2))
        self.assertEqual(expand(disk, b"\x03\x00"), disk.read(3,2))
        self.assertEqual(expand(disk, b"\x00\x03\x00"), disk.read(2,3))


    def test_multi_page(self):
        disk = MemoryDiskImage(512, 20)

        disk.write(3, b"\x03"*512*3)

        self.assertEqual(expand(disk, b"\x03"), disk.read(3, 1))
        self.assertEqual(expand(disk, b"\x00\x03"), disk.read(2,2))
        self.assertEqual(expand(disk, b"\x03\x03"), disk.read(3,2))
        self.assertEqual(expand(disk, b"\x03\x03\x03"), disk.read(3,3))
        self.assertEqual(expand(disk, b"\x00\x03\x03\x03\x00"), disk.read(2,5))

if __name__ == "__main__":
    unittest.main()
        
