"""
Lightweight Standalone Redis RESP Protocol Server over TCP Socket (Port 6379)
Provides real TCP network socket communication for Redis clients when Docker Desktop is offline.
"""

import socket
import threading
from typing import Dict

class RedisRespServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 6379):
        self.host = host
        self.port = port
        self.store: Dict[str, bytes] = {}
        self.running = False
        self.server_socket = None

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(128)
            self.running = True
            print(f"Redis RESP Server running on tcp://{self.host}:{self.port}")
            
            thread = threading.Thread(target=self._accept_loop, daemon=True)
            thread.start()
        except Exception as e:
            print(f"Redis RESP Server failed to bind on {self.port}: {e}")

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, _ = self.server_socket.accept()
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except Exception:
                break

    def _handle_client(self, sock: socket.socket):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        buffer = b""
        while self.running:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                buffer += data
                while b"\r\n" in buffer:
                    lines = buffer.split(b"\r\n")
                    if not lines[0].startswith(b"*"):
                        # Handle inline PING
                        if b"PING" in lines[0].upper():
                            sock.sendall(b"+PONG\r\n")
                        buffer = b""
                        break
                    
                    try:
                        num_args = int(lines[0][1:])
                        needed_lines = 1 + num_args * 2
                        if len(lines) < needed_lines:
                            break # Wait for full payload
                        
                        args = []
                        for idx in range(2, needed_lines, 2):
                            args.append(lines[idx].decode('utf-8', errors='ignore'))
                        
                        consumed_bytes = len(b"\r\n".join(lines[:needed_lines]) + b"\r\n")
                        buffer = buffer[consumed_bytes:]
                        
                        cmd = args[0].upper() if args else ""
                        if cmd == "PING":
                            sock.sendall(b"+PONG\r\n")
                        elif cmd == "GET":
                            key = args[1]
                            val = self.store.get(key)
                            if val is None:
                                sock.sendall(b"$-1\r\n")
                            else:
                                sock.sendall(f"${len(val)}\r\n".encode('utf-8') + val + b"\r\n")
                        elif cmd == "SET":
                            key = args[1]
                            val = args[2].encode('utf-8')
                            self.store[key] = val
                            sock.sendall(b"+OK\r\n")
                        elif cmd in ["CLIENT", "INFO", "COMMAND", "HELLO"]:
                            if cmd == "HELLO":
                                # Return RESP2 hello map
                                resp = b"%2\r\n$5\r\nserver\r\n$5\r\nredis\r\n$7\r\nversion\r\n$5\r\n7.2.0\r\n"
                                sock.sendall(resp)
                            else:
                                sock.sendall(b"+OK\r\n")
                        else:
                            sock.sendall(b"+OK\r\n")
                    except Exception:
                        buffer = b""
                        break
            except Exception:
                break
        sock.close()

if __name__ == "__main__":
    server = RedisRespServer()
    server.start()
    import time
    while True:
        time.sleep(1)
