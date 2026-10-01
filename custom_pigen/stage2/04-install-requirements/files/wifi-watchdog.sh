#!/bin/bash
# wifi-watchdog.sh
# Restores WiFi connectivity with escalating recovery, up to a reboot.
#
# Lessons from the Aug 2026 field outages (multi-day silences ended only
# by a power cycle):
#
# - Act on connectivity *outcome*, never on NetworkManager's view of the
#   device.  NM reported wlan0 "disconnected" throughout a 3-day outage
#   while autoconnect silently never recovered.
# - Weak-signal outdoor links blip constantly.  A single failed check
#   must do nothing; only a streak of failures may trigger recovery.
# - Never `nmcli connection down`: it marks the profile manually
#   deactivated, and if the following `up` fails, autoconnect stays
#   blocked forever.  `nmcli connection up` alone is always safe.
# - An `ip link` bounce does not clear brcmfmac firmware wedges
#   ("Scanning suppressed: status (4)" in dmesg); reloading the module
#   re-downloads the chip firmware and does.
# - A reboot is the software stand-in for the field power cycle.  It is
#   rate-limited, and health is judged by the *local* link only, so a
#   server-side outage can never cause fleet-wide reboot storms.

WIFI_CONN="Wifi"
AP_CONN="SimpleAQ-AP"
IFACE="wlan0"
AP_IFACE="ap0"

RUN_DIR="/run/wifi-watchdog"            # cleared on boot
FAIL_FILE="$RUN_DIR/consecutive_failures"
PERSIST_DIR="/var/lib/wifi-watchdog"    # survives reboots
REBOOT_STAMP="$PERSIST_DIR/last_reboot"
MIN_REBOOT_INTERVAL_SEC=21600           # at most one watchdog reboot per 6h

mkdir -p "$RUN_DIR" "$PERSIST_DIR"

# Only run if WiFi is configured with a real SSID.
SSID=$(nmcli -t -f 802-11-wireless.ssid connection show "$WIFI_CONN" 2>/dev/null | cut -d: -f2)
if [ -z "$SSID" ] || [ "$SSID" = "your_wifi_name" ]; then
    echo 0 > "$FAIL_FILE"
    exit 0
fi

recreate_ap_if_missing() {
    # Bouncing or reloading wlan0 destroys the virtual ap0 interface.
    # Recreate it so the configuration AP keeps working.
    if ! ip link show "$AP_IFACE" &>/dev/null; then
        logger -t wifi-watchdog "Recreating $AP_IFACE"
        iw dev "$IFACE" interface add "$AP_IFACE" type __ap 2>/dev/null || true
        ip link set "$AP_IFACE" up 2>/dev/null || true
        nmcli device set "$AP_IFACE" managed yes 2>/dev/null || true
        nmcli connection up "$AP_CONN" 2>/dev/null || true
    fi
}

link_is_healthy() {
    GATEWAY=$(ip route show dev "$IFACE" 2>/dev/null | awk '/default/ {print $3; exit}')
    [ -z "$GATEWAY" ] && return 1
    if ping -c 2 -W 5 -I "$IFACE" "$GATEWAY" &>/dev/null; then
        return 0
    fi
    # Some networks drop ICMP to the gateway; accept any external reply.
    if ping -c 2 -W 5 -I "$IFACE" 1.1.1.1 &>/dev/null; then
        return 0
    fi
    return 1
}

if link_is_healthy; then
    echo 0 > "$FAIL_FILE"
    exit 0
fi

FAILURES=0
if [ -f "$FAIL_FILE" ]; then
    FAILURES=$(cat "$FAIL_FILE" 2>/dev/null)
    [[ "$FAILURES" =~ ^[0-9]+$ ]] || FAILURES=0
fi
FAILURES=$((FAILURES + 1))
echo "$FAILURES" > "$FAIL_FILE"

logger -t wifi-watchdog "No connectivity on $IFACE (consecutive failure #$FAILURES)"

if [ "$FAILURES" -lt 3 ]; then
    # Could be a blip or an in-progress reconnect; give autoconnect time.
    exit 0
fi

if [ "$FAILURES" -ge 10 ]; then
    NOW=$(date +%s)
    LAST_REBOOT=0
    if [ -f "$REBOOT_STAMP" ]; then
        LAST_REBOOT=$(cat "$REBOOT_STAMP" 2>/dev/null)
        [[ "$LAST_REBOOT" =~ ^[0-9]+$ ]] || LAST_REBOOT=0
    fi
    if [ "$LAST_REBOOT" -gt "$NOW" ]; then
        # Clock moved backwards (stale boot clock); treat as recent and re-stamp.
        echo "$NOW" > "$REBOOT_STAMP"
        logger -t wifi-watchdog "Reboot stamp was in the future; re-stamped"
    elif [ $((NOW - LAST_REBOOT)) -ge "$MIN_REBOOT_INTERVAL_SEC" ]; then
        logger -t wifi-watchdog "Recovery exhausted after $FAILURES failures; rebooting"
        echo "$NOW" > "$REBOOT_STAMP"
        sync
        systemctl reboot
        exit 0
    else
        logger -t wifi-watchdog "Reboot suppressed (last one $((NOW - LAST_REBOOT))s ago)"
    fi
fi

if [ "$FAILURES" -lt 5 ]; then
    # Re-activation is safe whether or not NM thinks it is connected, and
    # also clears any lingering manual-deactivation autoconnect block.
    logger -t wifi-watchdog "Recovery: nmcli connection up $WIFI_CONN"
    nmcli --wait 30 connection up "$WIFI_CONN" 2>/dev/null || true

elif [ "$FAILURES" -lt 7 ]; then
    logger -t wifi-watchdog "Recovery: bouncing $IFACE"
    ip link set "$IFACE" down
    sleep 2
    ip link set "$IFACE" up
    sleep 5
    recreate_ap_if_missing
    nmcli --wait 30 connection up "$WIFI_CONN" 2>/dev/null || true

elif [ "$FAILURES" -lt 10 ] || [ $((FAILURES % 5)) -eq 0 ]; then
    # Reload the driver to re-download chip firmware.  This is what
    # actually clears a wedged brcmfmac ("Scanning suppressed" state).
    logger -t wifi-watchdog "Recovery: reloading brcmfmac"
    if timeout 60 modprobe -r brcmfmac 2>/dev/null; then
        sleep 2
        modprobe brcmfmac 2>/dev/null || true
        # Wait for the interface to come back.
        for _ in $(seq 1 15); do
            ip link show "$IFACE" &>/dev/null && break
            sleep 2
        done
        sleep 3
        recreate_ap_if_missing
        nmcli --wait 30 connection up "$WIFI_CONN" 2>/dev/null || true
    else
        logger -t wifi-watchdog "brcmfmac unload failed or hung; driver likely wedged beyond reload"
    fi
fi
