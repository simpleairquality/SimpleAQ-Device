# SimpleAQ-Device

Generic firmware for a Raspberry Pi based SimpleAQ device.

# I Just Want to Image My Device

## Downloading an Image

First, you will have to select the image you want.
You can find an image by selecting [Actions](/actions) in this repository, then selecting a successful Build Image run.
Then, at the bottom of the page you will see Artifacts.
Click the artifact to download it.

## Writing the Image

You can unzip your image with
```bash
unzip your_downloaded_image_file.zip
```

Once you have the contained `.img` file, you can write it to your MicroSD card.
First, you will need to find the device corresponding to your MicroSD card.
```bash
sudo fdisk -l | grep MicroSD -B 1 -A 5
```

Now you will have a list of all MicroSD cards attached to your system, whether mounted or not.
The device name will look like `/dev/sdx`, where x is some letter.
It is **critical** that you select the correct device name, or you **will** cause unwanted data loss on your host system.

Next, we must ensure that the device is not mounted.
```bash
df -h | grep /dev/sdx
```
where `/dev/sdx/` is the device name for your MicroSD card will show whether your device is mounted.

For each mounted partition listed, unmount it with
```bash
sudo umount /dev/sdxy
```
where `x` is your device's letter that you found with `fdisk` and `y` may be a number.

It may be the case that your drive wasn't mounted at all.
In any event, if your device is mounted, the following step will not work.

Now we will write your image with
```bash
sudo dd bs=4M of=/dev/sdx if=your_image_file.img 
```
where `x` is your device's letter that you found with `fdisk` above.
This step may take a while.

You should now be able to mount the `ext4` Linux partition of your written image to inspect the written files.

## Manual Configuration

TODO:  How to manually configure the partition using the output from the frontend.
