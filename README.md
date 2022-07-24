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

## The Flask HostAP Configuration Tool

You can run this locally to test it out.
```bash
cp example.env .env
source .env
flask run
```

## Manually Configuring Your Device To Connect to Wifi

You can configure Wifi on your device without using `ssh`.
First, insert the imaged MicroSD card into a standard card reader, then edit `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf` in the root filesystem "rootfs".
At the end of the file, add:

```
network={
    ssid="Your Wireless Network ID Here!"
    psk="Your Wireless Network Password Here!"
}
```

Note that if you are concerned about the security of storing your key in plain-text, you can run:
```bash
wpa_passphrase YourWirelessNetworkID YourWirelessNetworkPassword
```
and get a hash that you can use in the PSK field instead.

## SSH Into your SimpleAQ Device For Testing

Our build process automatically creates Raspbian images appropriate for both a production environment and for development.
In order to SSH into your SimpleAQ device, you will need to select a development image labeled INSECURE-DEBUG.
These devices use the default username `pi` and the default password `simpleaq` and would be compromised immediately if placed on the public internet.

Note that since our transition to `systemd-networkd` based networking, **link-local connections through your device's data/peripherals USB port are no longer supported.**
You have two options to connect to your device.

1.  If you have configured wifi in the step above, you may use your router to find the `simpleaq` device's IP address on your network, then connect with e.g., `ssh pi@192.168.1.xxx`.
2.  If your device's wifi is not configured, you can connect through the device's `hostap` network by connecting to wireless at `SimpleAQ-xxxx`.   Then, connect with `ssh pi@192.168.4.1`.
3.  You can connect a keyboard to the device's data/peripheral port and a monitor to the device's HDMI pirt.

Our devices automatically switch between `hostap` and `wlan` modes based on whether `wlan` is working.  
Therefore, if you have a correctly configured and working `wlan` connection, `ssh` into your `hostap` connection will not work.
A service will periodically retry the `wlan` connection, but in doing so it will briefly take down the `hostap`.

## Manually Configuring Your Device To Write Data to InfluxDB

### Create a Temporary InfluxDB Instance For Testing

First, you'll need an instance of [InfluxDB](https://github.com/influxdata/influxdb) to write into!
If you already have one, you can skip this step.

If you need a temporary instance for testing purposes, you can create one using:
```bash
docker run -p 8086:8086 \
           -e DOCKER_INFLUXDB_INIT_USERNAME=influx_dev_user \
           -e DOCKER_INFLUXDB_INIT_PASSWORD=influx_not_secure \
           -e DOCKER_INFLUXDB_INIT_ORG=my_org \
           -e DOCKER_INFLUXDB_INIT_BUCKET=my_bucket \
           -e DOCKER_INFLUXDB_INIT_MODE=setup \
           -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=not_secure_admin_token \
           --network host \
           influxdb:latest
```

The InfluxDB instance will now be running on port 8086 on the host machine.
You will also need to find the IP address of the host machine so that the device can write into it.
One way to find the local IP address is using `ifconfig`.
It may be helpful to confirm that you can connect to http://HOST.IP.ADDRESS.HERE:8086 from a web browser on a machine on the same network as your device.
If InfluxDB is set up properly and accessible, you will see a login page for InfluxDB.

### Configuring Your Device

#### Using the HostAP network

When you boot your SimpleAQ image, it should start a HostAP network with a name like SimpleAQ-xxxx, and a default password of SimpleAQ.
If you connect to the HostAP network with any device, navigate to [http://192.168.4.1](http://192.168.4.1) or [http://simpleaq.setup](http://simpleaq.setup) in a web browser.
On this page, you will be able to change relevant settings.
When the device is reporting data to a backend server expected, this HostAP network will not appear.

#### Manually

In order to connect the device to the backend, you will need a valid org, bucket and token.
If you used the example above, you can use "my\_org", "my\_bucket" and "not\_secure\_admin\_token".

You do not need `ssh` to configure your device.
First, put your imaged MicroSD card into a card reader.
Edit `/etc/environment` in the root filesystem "rootfs".
If you're following the example above, the relevant fields would then be:
```
influx_org=my_org
influx_bucket=my_bucket
influx_token=not_secure_admin_token
influx_server=http://HOST.IP.ADDRESS.HERE:8086
```

If everything is configured correctly and the device has network connectivity, your device should be auto-configured on boot and automatically start sending readings to InfluxDB.

# Troubleshooting

## Boot

`bootlogd` is installed in our images.
Therefore, if booting fails for any reason, you can insert the MicroSD card into a standard reader, then check the root file system "rootfs" for boot errors using

```bash
sed 's/\^\[/\o33/g;s/\[1G\[/\[27G\[/' var/log/boot
```

## Service

If there is an issue with the service, you can `ssh` into the device using the instructions above, then run

```bash
sudo service simpleaq status
```

to explore the issue.
