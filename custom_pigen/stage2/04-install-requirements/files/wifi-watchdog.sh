#!/bin/bash
# wifi-watchdog.sh
# Detects WiFi driver hangs and performs escalating recovery.
#
# The Broadcom brcmf driver can get stuck in a
# brcmf_netdev_wait_pend8021x timeout state, leaving WiFi unusable
# even though NetworkManager believes it is connected.
#
# This script only intervenes when NetworkManager reports wlan0 as
# "connected" but traffic cannot actually flow (i.e., the driver is
# wedged). Normal disconnects (out of range, AP rebooted, etc.) are
# left to NetworkManager's autoconnect, which handles them fine.

WIFI_CONN="Wifi"
AP_CONN="SimpleAQ-AP"
IFACE="wlan0"
AP_IFACE="ap0"
STATE_FILE="/tmp/wifi-watchdog-failures"

# Only run if WiFi is configured with a real SSID.
SSID=$(nmcli -t -f 802-11-wireless.ssid connection show "$WIFI_CONN" 2>/dev/null | cut -d: -f2)
if [ -z "$SSID" ] || [ "$SSID" = "your_wifi_name" ]; then
    exit 0
fi

# Check NetworkManager's view of the device state.
# We only care about the case where NM thinks wlan0 is connected
# but it actually isn't working. If NM knows it's disconnected,
# autoconnect will handle reconnection — no intervention needed.
NM_STATE=$(nmcli -t -f GENERAL.STATE device show "$IFACE" 2>/dev/null | cut -d: -f2 | xargs)
case "$NM_STATE" in
    100*)
        # "100 (connected)" — NM thinks we're connected.
        # Verify by pinging the gateway.
        ;;
    *)
        # NM knows it's disconnected/connecting/unavailable/etc.
        # Let autoconnect handle it.
        rm -f "$STATE_FILE"
        exit 0
        ;;
esac

# NM says connected. Check if traffic actually flows.
GATEWAY=$(ip route show dev "$IFACE" 2>/dev/null | awk '/default/ {print $3; exit}')

if [ -n "$GATEWAY" ]; then
    if ping -c 2 -W 5 -I "$IFACE" "$GATEWAY" &>/dev/null; then
        # Everything is actually fine.
        rm -f "$STATE_FILE"
        exit 0
    fi
fi

# NM says connected, but we can't reach the gateway (or have none).
# The driver is likely wedged. Track consecutive failures.
FAILURES=0
if [ -f "$STATE_FILE" ]; then
    FAILURES=$(cat "$STATE_FILE" 2>/dev/null)
    if ! [[ "$FAILURES" =~ ^[0-9]+$ ]]; then
        FAILURES=0
    fi
fi
FAILURES=$((FAILURES + 1))
echo "$FAILURES" > "$STATE_FILE"

logger -t wifi-watchdog "NM reports connected but gateway unreachable (consecutive failure #$FAILURES)"

if [ "$FAILURES" -le 1 ]; then
    # Soft: ask NetworkManager to cycle the connection.
    logger -t wifi-watchdog "Soft recovery: reconnecting $WIFI_CONN"
    nmcli connection down "$WIFI_CONN" 2>/dev/null || true
    sleep 1
    nmcli connection up "$WIFI_CONN" 2>/dev/null || true

elif [ "$FAILURES" -le 2 ]; then
    # Medium: disconnect and reconnect the device entirely.
    logger -t wifi-watchdog "Medium recovery: device disconnect/connect $IFACE"
    nmcli device disconnect "$IFACE" 2>/dev/null || true
    sleep 2
    nmcli device connect "$IFACE" 2>/dev/null || true

else
    # Hard: bounce the interface to reset driver state.
    # This is the fix for brcmf_netdev_wait_pend8021x hangs.
    logger -t wifi-watchdog "Hard recovery: bouncing $IFACE"
    ip link set "$IFACE" down
    sleep 2
    ip link set "$IFACE" up
    sleep 5

    # Bouncing wlan0 destroys the virtual ap0 interface.
    # Recreate it so the configuration AP keeps working.
    if ! ip link show "$AP_IFACE" &>/dev/null; then
        logger -t wifi-watchdog "Recreating $AP_IFACE"
        iw dev "$IFACE" interface add "$AP_IFACE" type __ap 2>/dev/null || true
        ip link set "$AP_IFACE" up 2>/dev/null || true
        nmcli device set "$AP_IFACE" managed yes 2>/dev/null || true
        nmcli connection up "$AP_CONN" 2>/dev/null || true
    fi

    nmcli connection up "$WIFI_CONN" 2>/dev/null || true

    # Reset counter to cycle through escalation again.
    echo "0" > "$STATE_FILE"
fi
