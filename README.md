# Description 

This tool emulates USB disk drives and allows easy swapping out of data blocks. We built this tool to exploit [Time-of-check/Time-of-use](https://en.wikipedia.org/wiki/Time-of-check_to_time-of-use) (TOCTOU) issues when embedded devices accessed data on USB drives.

# Requirements

We use Linux's [FunctionFS](https://docs.kernel.org/usb/functionfs.html) to implement a user space USB device interface and `libcomposite` in conjunction with [ConfigFS](https://www.kernel.org/doc/Documentation/filesystems/configfs/configfs.txt) to configure and setup the USB device. In many cases these should already be included with your Linux Kernel.

A Linux device capable of doing USB-OTG. We used a [Raspberry PI 4](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/) with the following added to the `/boot/config.txt` file to enable OTG:

```
dtoverlay=dwc2
```

# Install

1. Clone from Github:

```shell
git clone https://github.com/anvilsecure/usb-racer.git
```

2. Install with pip:

```shell
cd usb-racer
pip install .
```

# Usage

## Basic Mass Storage Device

The `usbracer-storage` implements a basic mass storage device backed by a disk image, with some options.

```
usage: usbracer-storage [-h] [--block-size BLOCK_SIZE] [--write WRITE] [--cow COW] [--log LOG] [--log-data] [--debug-level DEBUG_LEVEL] image

positional arguments:
  image                 Path to disk image

options:
  -h, --help            show this help message and exit
  --block-size BLOCK_SIZE
  --write WRITE
  --cow COW             Path to copy on write file (creates/expects a .metadata file next to it)
  --log LOG             Log IO operations to file
  --log-data            Include data within the log file
  --debug-level DEBUG_LEVEL
```

Running `usbracer-storage` with just a path to a disk image and block size will present a basic mass storage device to the host. It is pretty slow, so you are better off using the standard mass storage gadget than this if all you want is a mass storage device. The fun is with the options!

```
> usbracer-storage --block-size 512 /path/to/disk.img
```

### Write Protect/Drops

The `--write` option lets you control if writes are allowed and has the following options:

 - **ALLOW** - Allows writes (the default).
 - **DENY** - Returns an error when writing.
 - **DROP** - Silently discards writes.

### Copy on Write (COW)

A primitive `--cow /path/to/cow-location` option exists where another image, the same size as the original, is used to store writes. A simple bitmap is used to keep track of which blocks are in the COW image and which ones are still in the original image. Any reads will source from the COW image first.

### Logging

The `--log /path/to/log-file` can be used to log any read/writes to disk. This is a binary log and the `usbracer-log-dump` can be used to display the operations. Adding a `--log-data` option will include the data from the reads and the writes within the log, otherwise only the operation, offset, and block counts are retained.

```
> usbracer-log-dump ~/disk.log 
Block Size=512, Capacity=20481, Flags=INCLUDES_DATA
Op: READ Offset: 0 Count: 1
00000000  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
*
000001b0  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 fe  |................|
000001c0  ff ff ee fe ff ff 01 00  00 00 00 50 00 00 00 00  |...........P....|
000001d0  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
*
000001f0  00 00 00 00 00 00 00 00  00 00 00 00 00 00 55 aa  |..............U.|
00000200
Op: READ Offset: 1 Count: 1
00000000  45 46 49 20 50 41 52 54  00 00 01 00 5c 00 00 00  |EFI PART....\...|
00000010  13 0d c5 9f 00 00 00 00  01 00 00 00 00 00 00 00  |................|
00000020  00 50 00 00 00 00 00 00  22 00 00 00 00 00 00 00  |.P......".......|
00000030  df 4f 00 00 00 00 00 00  36 1a fb b8 45 3b 4a 40  |.O......6...E;J@|
00000040  99 ec 17 f0 93 8f 6a 90  02 00 00 00 00 00 00 00  |......j.........|
00000050  80 00 00 00 80 00 00 00  93 7c e7 57 00 00 00 00  |.........|.W....|
00000060  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
*
00000200
Op: READ Offset: 2 Count: 32
00000000  ef 57 34 7c 00 00 aa 11  aa 11 00 30 65 43 ec ac  |.W4|.......0eC..|
00000010  04 8b 9b 08 df d0 4c 4f  97 c7 04 ec 9b 07 5b ac  |......LO......[.|
00000020  28 00 00 00 00 00 00 00  df 4f 00 00 00 00 00 00  |(........O......|
00000030  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
*
00004000
```

## TOCTOU Tool

The `usbracer` script can be used to exploit Time of Check/Time of Use style issues. It is launched with two images and can switch between the two while running.

```
usage: usbracer [-h] (--toggle-image TOGGLE_IMAGE | --offset-override OFFSET_OVERRIDE OFFSET_OVERRIDE) [--block-size BLOCK_SIZE]
                               [--toggle-delay TOGGLE_DELAY] [--toggle-read-block TOGGLE_READ_BLOCK] [--debug-level DEBUG_LEVEL]
                               disk

positional arguments:
  disk                  Path to disk image

options:
  -h, --help            show this help message and exit
  --block-size BLOCK_SIZE
  --toggle-delay TOGGLE_DELAY
                        Automatically toggles the disks after a delay (in seconds)
  --toggle-read-block TOGGLE_READ_BLOCK
                        Toggle disks after a read on a specific block
  --debug-level DEBUG_LEVEL

Second Image:
  --toggle-image TOGGLE_IMAGE
                        A full image to toggle between
  --offset-override OFFSET_OVERRIDE OFFSET_OVERRIDE
                        The next two arguments are used as an offset and a path, can be specified multipule times
```

We built this tool because we had a device that would *secure* boot from a USB drive and then did something like this:

```shell
#!/bin/sh

ROOT_IMG="..."

openssl dgst -sha256 -verify ${SIGNING_KEY} -signature "${ROOT_IMG}.sig" ${ROOT_IMG}
if [ $? -ne 0 ]
then
    logger -p Error "Invalid signature on root filesystem."
    exit -1
fi
mount ${ROOT_IMG} /new_root
#...
```

We used the `--toggle-read-block` option on the last block of the root disk image and swapped the image right after the verification step and before the mount! (Yes, you should be using [dm-verity](https://docs.kernel.org/admin-guide/device-mapper/verity.html)).

The `--toggle-image` and `--offset-override` are used to specify the alternative data. With the `--toggle-image` option the entire disk is swapped. This is basic and simple. The original disk would contain the untouched and valid data, the second disk can contain anything you want. Simple but can result in more disk corruption as writes can be redirected and any updates to the disk before the toggle will be lost.

The `--offset-override` option consumes two arguments, an offset and then a path to a file (`--offset-override 425 ~/malicious_data.bin`. The file will override the data at that offset. This allows you to more selectively target a file within the disk without having to swap the whole disk. This allows the system to write normally with persistent writes and is more reliable and less susceptible to disk corruption. The argument can be specified multiple times to override multiple locations with new data. Only reads are overridden, any writes are made to the original disk.

More sophisticated scenarios are possible and can be [scripted](#scripts) up. 

### Disk Caching

A constant nemesis in performing these style of attacks is disk caching. Your OS is going to cache disk reads, especially small files. Swapping the backing image isn't going to do anything if your target never reads from the drive again. You will have to come up with strategy to handle disk caching.

Sometimes it doesn't matter, in the above example if you have a multi gigabyte root file system and your target only has 512 MB of RAM, it isn't going to cache the whole image and the swap is fairly straight forward.

Other times you will need to become more creative. For example, if your target has a webpage for firmware updates, upload large files and exercise disk IO. If your actual target block isn't accessed too frequently it may get evicted out the disk cache. Pretty much just exercises the target and force it to consume resources to evict entries out of the cache.

For testing purposes you can force purging of disk caches:

* **Linux** - `blockdev --flushbufs /dev/sda` or `echo 3 > /proc/sys/vm/drop_cache`. The `blockdev` calls an IOCTL to flush disk caches, but it doesn't work on all devices. The `/proc/sys/vm/drop_cache` should work system wide.
* **macOS** - The `purge` command clears caches to approximate initial boot conditions.
* **Windows** - The `RAMMap` tool from [SysInternals](https://learn.microsoft.com/en-us/sysinternals/downloads/rammap) can be used to empty caches.

## Scripts

To be successful you may need to script up an attack. Take a look at the [examples](/examples) and the pre-built [tools](/usbracer/tools). There are five steps to setup the device:

1. Create a `Gadget` and specify the vendor/product ids, and some description strings:

```python
gadget = Gadget(VENDOR_ID, PRODUCT_ID, manufacture="Anvil", product="My Device")
```

2. Create and add a configuration (used to hold a set of functions):

```python
config = gadget.add_configuration(Configuration(gadget, "Config-1"))
```

3. Create a disk image:

```python
disk = MMapDiskImage(args.image, args.block_size)
```

3. Create and add functions to the configuration. In this case the `MassStorage` function:

```python
func = config.add_function(MassStorage(
    config, 
    disk, 
    vendor_id="Anvil", 
    product_id="Random Data", 
    product_ver="0.1"))
```

4. Start the run loop:

```python
asyncio.run(gadget.run())
```

### Other types of USB Devices

Have other USB devices you want to spoof/emulate? The `usbracer.gadget.FFSFunction` class can be subclassed to implement other USB devices. Just swap out the `MassStorage` object in step #3. Take a look at the `MassStorage` class to see how to setup the descriptors and open the EP devices.