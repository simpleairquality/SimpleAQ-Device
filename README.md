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

Be warned about the following pitfalls:
- If you later re-image your device and connect it again, you will receive a warning that the `ssh` key changed.
- I am unable to connect to the device via USB while connected to Ethernet on the same machine.  Wireless seems to be OK.
- Ubuntu will create a new Wired connection for each re-image of the device, as each new image is recognized as a different device.

## Manually Configuring Your Device To Connect to Wifi

## Manually Configuring Your Device To Write Data to InfluxDB

First, you'll need an instance of [InfluxDB](https://github.com/influxdata/influxdb) to write into!
If you need a temporary instance for testing purposes, you can create one using:
```bash
docker run -p 8086:8086 \
           -e DOCKER_INFLUXDB_INIT_USERNAME=influx_dev_user \
           -e DOCKER_INFLUXDB_INIT_PASSWORD=influx_not_secure \
           -e DOCKER_INFLUXDB_INIT_ORG=my_org \
           -e DOCKER_INFLUXDB_INIT_BUCKET=my_bucket \
           -e DOCKER_INFLUXDB_INIT_MODE=setup \
           -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=not_secure_admin_token \
           influxdb:latest
```

The InfluxDB instance will now be running on port 8086 on the host machine.
You will also need to find the IP address of the host machine so that the device can write into it.
One way to find the local IP address is using `ifconfig`.

In order to connect the device, you will need a valid org, bucket and token.
If you used the example above, you can use `my_org`, `my_bucket` and `not_secure_admin_token`.




