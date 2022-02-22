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

NOTE:  Environment variables live in `/etc/environment/` in 

# Dev Quickstart

## First Time

You can install needed dependencies in `virtualenv` with:
```bash
virtualenv venv -p python3
source venv/bin/activate
pip install -r requirements.txt
```

When you return to your work later, you can simply use:
```bash
source venv/bin/activate
```
## SSH Into your SimpleAQ Device For Testing

Our build process automatically creates Raspbian images appropriate for both a production environment and for development.
In order to SSH into your SimpleAQ device, you will need to select a development image labeled INSECURE-DEBUG.
These devices use the default username `pi` and the default password `raspberry` and would be compromised immediately if placed on the public internet.

After imaging your device with the desired INSECURE-DEBUG image, you will need to connect your device to your PC using the **data/peripherals** USB port.
On a Raspberry Pi Zero W, this is the USB port closest to the center of the device.
You may need to wait a minute for the device to boot.

On Windows or Mac, you should now be able to connect to the device using
```
ssh pi@raspberrypi.local
```
using the default password `raspberry`.

On Ubuntu, while the device appears in the networking menu as "Ethernet Network (Netchip Linux-USB Gadget)", it may be necessary to first mark the connection as "Link-Local" only in `nm-connection-editor`:
1. Run `nm-connection-editor` from the Host OS.
2. Select the appropriate "Wired connection #" under Ethernet, then click the gear. (The device name will be something like enxbed891078ed1)
3. Select "IPv4 Settings", then Method: "Link-Local Only".
4. Run `ssh pi@raspberrypi.local`, using the default password `raspberry`.
