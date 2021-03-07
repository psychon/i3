#!/usr/bin/python3

import select
import socket
import sys
import time


class Listener:
    def __init__(self, listen_port, target_port, delay):
        self.fd = socket.create_server(("127.0.0.1", listen_port))
        self.fd.settimeout(0)
        self.target_port = target_port
        self.delay = delay

    def register_fds(self, rlist, wlist):
        rlist.append(self.fd.fileno())

    def process(self, readable, writable):
        if self.fd.fileno() in readable:
            client, addr = self.fd.accept()
            print(f"Incoming connection from {addr}")

            server = socket.create_connection(("127.0.0.1", self.target_port))

            client.settimeout(0)
            server.settimeout(0)

            return [Forwarder(client, server, self.delay), Forwarder(server, client, self.delay)]


class Forwarder:
    def __init__(self, read, write, delay):
        self.read = read
        self.write = write
        self.delay = delay
        self.pending_data = []

    def register_fds(self, rlist, wlist):
        rlist.append(self.read.fileno())
        if self.pending_data:
            timeout = self.pending_data[0][0] - time.time()
            if timeout <= 0:
                wlist.append(self.write.fileno())
            else:
                return timeout

    def process(self, readable, writable):
        if self.write.fileno() in writable:
            delay, data = self.pending_data[0]
            try:
                sent = self.write.send(data)
            except OSError as e:
                print("Error during socket.recv():")
                print(e)
                try:
                    self.write.shutdown(socket.SHUT_RD)
                except OSError as e:
                    print("Error during socket.shutdown(RD):")
                    print(e)
                return True
            data = data[sent:]
            if data:
                self.pending_data[0] = (delay, data)
            else:
                self.pending_data.pop(0)

        if self.read.fileno() in readable:
            try:
                data = self.read.recv(4096)
            except OSError as e:
                print("Error during socket.recv():")
                print(e)
                self.shutdown_write()
                return True
            self.pending_data.append((time.time() + self.delay, data))
            if not data:
                self.shutdown_write()
                return True

    def shutdown_write(self):
        try:
            self.write.shutdown(socket.SHUT_WR)
        except OSError as e:
            print("Error during socket.shutdown(WR):")
            print(e)


def main(listen_port, target_port, delay):
    sockets = [Listener(listen_port, target_port, delay)]
    while True:
        rlist, wlist = [], []
        timeout = None
        for sock in sockets:
            t = sock.register_fds(rlist, wlist)
            if t and (timeout is None or t < timeout):
                timeout = t

        readable, writeable, _ = select.select(rlist, wlist, [], timeout)
        new_sockets = []
        for sock in sockets:
            new_socks = sock.process(readable, writeable)
            if new_socks is None:
                new_sockets.append(sock)
            elif isinstance(new_socks, list):
                new_sockets.append(sock)
                new_sockets += new_socks
            elif isinstance(new_socks, bool) and new_socks:
                # Socket is not added to new_sockets
                pass
            else:
                print(new_socks)
                error()

        sockets = new_sockets


if __name__ == "__main__":
    print("This program is a TCP proxy which adds a delay to the connection")
    print(f"Usage: {sys.argv[0]} [port to listen on] [port on localhost to connect to] [delay in seconds]")
    print("Note that the round-trip delay will be twice the given delay.")
    main(int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]))
