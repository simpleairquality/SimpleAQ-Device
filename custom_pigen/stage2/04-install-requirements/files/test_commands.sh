Let’s run the following command to create an access point with the name testpot and a password 12345678:

$ nmcli d wifi hotspot ifname wlan0 ssid testspot password 12345678
Device 'wlan0' successfully activated with '149d0e97-0958-46ff-a748-e71ccc21d0cd'.
Hint: "nmcli dev wifi show-password" shows the Wi-Fi name and password.
Copy
In this command, wifi is an argument that sets the connection name to hotspot. We use the ifname argument to select the interface we’ll be using while SSID specifies the name of the access point we’re creating. The SSID will be visible to devices connecting to it. Lastly, we use the password argument to create a password for the access point.

The NetworkManager will create a connection called hotspot if the command runs successfully. This access point will share the internet connection if the secondary interface has a network. So the devices connected to it will access the internet because the hosting device is connected to the internet (a shared connection is created between wlan0 and usb0).

Next, let’s view all the connections we have in the system:

$ nmcli con show
NAME                UUID                                  TYPE      DEVICE 
Hotspot             149d0e97-0958-46ff-a748-e71ccc21d0cd  wifi      wlan0  
Wired connection 1  7fb46fdc-3505-49f6-aeb7-edb17e26611c  ethernet  usb0   
lo                  3dcbbd88-d7f0-4426-b87c-9c7ab3ae0e37  loopback  lo 
Copy
From the snippet above, both wifi and ethernet are active. We’re using the ethernet to provide internet to the computer. If we lack a second interface, the hotspot we created won’t have internet access, but it can be used to share resources locally.

We can verify that the access point is up:

$ nmcli device wifi
IN-USE  BSSID              SSID        MODE   CHAN  RATE     
*       60:67:20:7A:A6:8C  testspot  Infra  11    0 Mbit/s 
Copy
Importantly, we’ll often use the term connection to refer to the full configuration specified for a specific device or interface. For example, if we create specific settings for eth0, we can refer to those settings as a connection

4. Creating the Access Point Sequentially
Alternatively, we can create a wireless access point sequentially running one command after another.


freestar
Let’s begin by running the following command to create the SSID for our hotspot on the wlan0 interface:

$ sudo nmcli connection add type wifi ifname wlan0 con-name testhotspot autoconnect yes ssid testhotspot 
Connection 'testhotspot' (23429383-f83f-4fbe-bbcc-9d64fcf5c7b9) successfully added.
Copy
Next, let’s add more properties to our connection:

$ sudo nmcli connection modify testhotspot 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
Copy
Then, we must configure WPA2-PSK security for our access point:

$ sudo nmcli connection modify testhotspot wifi-sec.key-mgmt wpa-psk
$ sudo nmcli connection modify testhotspot wifi-sec.psk 12345678

Lastly, let’s activate the access point we’ve created:

$ sudo nmcli connection up testhotspot
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/7)
Copy
We must note that for the access point to start automatically on boot, we must enable ‘autoconnect‘:

$ sudo nmcli connection modify testhotspot connection.autoconnect yes
Copy
To turn it down, we run:

$ sudo nmcli connection down testhotspot
Connection 'testhotspot' successfully deactivated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/7)
Copy
We can also view the active connection on our system:

$ nmcli con show --active
NAME                UUID                                  TYPE      DEVICE 
testhotspot         23429383-f83f-4fbe-bbcc-9d64fcf5c7b9  wifi      wlan0  
Wired connection 1  7fb46fdc-3505-49f6-aeb7-edb17e26611c  ethernet  usb0   
lo                  3dcbbd88-d7f0-4426-b87c-9c7ab3ae0e37  loopback  lo 
Copy
We can see that testhotspot is the connection we’ve created while Wired connection 1 is the secondary interface (usb0) which provides our system with an internet connection.


