#!/usr/bin/env python3
"""Interactive collector. Prompts for (floor, x, y), scans via Pi, appends CSV."""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.request

CSV_FIELDS = [
    "timestamp", "floor", "x", "y",
    "bssid", "ssid", "rssi_dbm", "freq_mhz", "channel",
]


def freq_to_channel(mhz):
    if mhz is None:
        return None
    if mhz == 2484:
        return 14
    if 2412 <= mhz <= 2472:
        return 1 + (mhz - 2412) // 5
    if 5180 <= mhz <= 5885:
        return (mhz - 5000) // 5
    if 5955 <= mhz <= 7115:
        return (mhz - 5950) // 5
    return None


def scan(pi_url, timeout=25):
    req = urllib.request.Request(f"{pi_url.rstrip('/')}/scan")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def append_rows(path, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)


def ask(label, prev):
    suffix = f" [{prev}]" if prev is not None else ""
    val = input(f"{label}{suffix}: ").strip()
    if val.lower() in ("q", "quit", "exit"):
        return None, True
    if val == "":
        return prev, False
    return val, False


def prompt_position(last):
    quit_flag = False
    for key in ("floor", "x", "y"):
        val, quit_flag = ask(key, last.get(key))
        if quit_flag:
            return None
        if val is None:
            print(f"  {key} is required")
            return prompt_position(last)
        last[key] = val
    return last["floor"], last["x"], last["y"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pi", required=True, help="e.g. http://192.168.50.10:8080")
    ap.add_argument("--out", default="scans.csv")
    ap.add_argument("--repeat", type=int, default=1,
                    help="number of scans to average per position (default 1)")
    args = ap.parse_args()

    last = {}
    print(f"appending to {args.out}. press Ctrl+C or type 'q' to quit.")
    while True:
        try:
            pos = prompt_position(last)
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if pos is None:
            break
        floor, x, y = pos

        all_rows = []
        for i in range(args.repeat):
            tag = f"({i+1}/{args.repeat}) " if args.repeat > 1 else ""
            print(f"  {tag}scanning...", end=" ", flush=True)
            try:
                payload = scan(args.pi)
            except Exception as e:
                print(f"FAILED: {e}")
                continue
            ts_iso = dt.datetime.fromtimestamp(payload.get("ts", time.time())).isoformat()
            aps = payload.get("aps", [])
            print(f"{len(aps)} BSSID(s)")
            if not aps:
                all_rows.append({
                    "timestamp": ts_iso, "floor": floor, "x": x, "y": y,
                    "bssid": None, "ssid": None,
                    "rssi_dbm": None, "freq_mhz": None, "channel": None,
                })
            else:
                for a in aps:
                    all_rows.append({
                        "timestamp": ts_iso,
                        "floor": floor, "x": x, "y": y,
                        "bssid": a.get("bssid"),
                        "ssid": a.get("ssid"),
                        "rssi_dbm": a.get("rssi_dbm"),
                        "freq_mhz": a.get("freq_mhz"),
                        "channel": freq_to_channel(a.get("freq_mhz")),
                    })

        if all_rows:
            append_rows(args.out, all_rows)
            seen = [r["rssi_dbm"] for r in all_rows if r["rssi_dbm"] is not None]
            if seen:
                print(f"  saved {len(all_rows)} rows. strongest {max(seen):.1f} dBm")
            else:
                print(f"  saved {len(all_rows)} row(s) marking no signal")


if __name__ == "__main__":
    main()
