#!/usr/bin/env python3
"""WiFi scan HTTP server. Runs on the Pi. Exposes /scan and /health."""
import json
import os
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

IFACE = os.environ.get("HEATMAP_IFACE", "wlan0")
PORT = int(os.environ.get("HEATMAP_PORT", "8080"))
SSID_FILTER = os.environ.get("HEATMAP_SSID", "eduroam")


def scan_iw():
    out = subprocess.run(
        ["sudo", "-n", "iw", "dev", IFACE, "scan"],
        capture_output=True, text=True, timeout=20,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "iw scan failed")
    return parse_iw(out.stdout)


def parse_iw(text):
    results = []
    current = {}

    def flush():
        if current.get("ssid") == SSID_FILTER and "bssid" in current:
            results.append({
                "bssid": current["bssid"],
                "ssid": current["ssid"],
                "rssi_dbm": current.get("rssi_dbm"),
                "freq_mhz": current.get("freq_mhz"),
            })

    for line in text.splitlines():
        m = re.match(r"BSS ([0-9a-f:]{17})", line)
        if m:
            flush()
            current = {"bssid": m.group(1)}
            continue
        m = re.match(r"\s*signal:\s*(-?\d+(?:\.\d+)?)\s*dBm", line)
        if m:
            current["rssi_dbm"] = float(m.group(1))
            continue
        m = re.match(r"\s*freq:\s*(\d+)", line)
        if m:
            current["freq_mhz"] = int(m.group(1))
            continue
        m = re.match(r"\s*SSID:\s*(.*)", line)
        if m:
            current["ssid"] = m.group(1)
            continue
    flush()
    return results


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/scan":
            try:
                aps = scan_iw()
                self._json(200, {"ts": time.time(), "iface": IFACE,
                                 "ssid_filter": SSID_FILTER, "aps": aps})
            except Exception as e:
                self._json(500, {"error": str(e)})
        elif self.path == "/health":
            self._json(200, {"ok": True, "iface": IFACE, "ssid_filter": SSID_FILTER})
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")


if __name__ == "__main__":
    print(f"scanner listening on :{PORT} (iface={IFACE}, ssid={SSID_FILTER!r})")
    HTTPServer(("", PORT), Handler).serve_forever()
