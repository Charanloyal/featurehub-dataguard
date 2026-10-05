#!/usr/bin/env python3
"""
Resilient Tunnel Runner for Public Live Demo
Spawns and automatically monitors/restarts localtunnel connections for the Unified Dashboard and Public API.
"""

import subprocess
import sys
import time
import os

def run_tunnel(port: int, subdomain: str):
    print(f"[*] Starting localtunnel on port {port} with subdomain '{subdomain}'...")
    while True:
        try:
            # Run localtunnel
            proc = subprocess.Popen(
                ["npx", "-y", "localtunnel", "--port", str(port), "--subdomain", subdomain],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            for line in proc.stdout:
                line_clean = line.strip()
                if line_clean:
                    print(f"[{subdomain}:{port}] {line_clean}")
            proc.wait()
            print(f"[-] Tunnel for port {port} exited with code {proc.returncode}. Reconnecting in 3s...")
        except Exception as e:
            print(f"[!] Error in tunnel {port}: {e}. Reconnecting in 3s...")
        time.sleep(3)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/tunnel_runner.py <port> <subdomain>")
        sys.exit(1)
    port = int(sys.argv[1])
    subdomain = sys.argv[2]
    run_tunnel(port, subdomain)
