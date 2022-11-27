#!/usr/bin/env python3
# Copyright 2022 Martin Burri <info@burrima.ch>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import copy
import datetime
import json
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time

"""
See https://github.com/burrima/sonarlint-ls-wrapper for documentation.

Terminology used in this script
  * raw data: raw bytes on the line (stdin or socket) - binary encoded
  * message: binary string containing a JSON object which can be understood
    by the parties
  * object: message binary-decoded and parsed from JSON into a python object
"""

LOGFILE = None  # e.g. "/tmp/sonarlint-ls-wrapper.log"
PORT = random.randrange(5000, 65535)
SONARLINT_PATH = (
    "<path-to-sonarlint-jars>")  # TODO: provide correct path
SONARLINT_START_CMD = (
    f"{SONARLINT_PATH}/jre/17.0.4.1-linux-x86_64.tar/bin/java"
    f" -jar {SONARLINT_PATH}/server/sonarlint-ls.jar"
    f" {PORT} -analyzers"
    f" {SONARLINT_PATH}/analyzers/sonarjava.jar"
    f" {SONARLINT_PATH}/analyzers/sonarjs.jar"
    f" {SONARLINT_PATH}/analyzers/sonarphp.jar"
    f" {SONARLINT_PATH}/analyzers/sonarpython.jar"
    f" {SONARLINT_PATH}/analyzers/sonarhtml.jar"
    f" {SONARLINT_PATH}/analyzers/sonarxml.jar"
    f" {SONARLINT_PATH}/analyzers/sonarcfamily.jar"
    f" -extraAnalyzers {SONARLINT_PATH}/analyzers/sonarsecrets.jar")
BUFSIZE = 4096
VERSION = "0.1.0"


def print_log(message, overwrite=False):
    """
    Prints a given message to the log file.

    @param message [string] or [binary string] with the message to be logged
    @param overwrite [boolean] overwrite existing file if true
    """
    if LOGFILE is None:
        return
    mode = "w" if overwrite else "a"
    with open(LOGFILE, mode) as f:
        f.write(f"{datetime.datetime.now()}: {message}\n")


def find_messages_in_raw_data(raw_data):
    """
    Scan the given raw data for messages and extract them.

    Returns a tuple (messages, remainer) containing a list of found messages
    and the remaining data.

    @param raw_data [binary string] raw data received from client or server
    @return tuple ([binary string] messages, [binary string] remainer)
    """
    messages = []
    remainer = raw_data

    try:
        while True:
            body_start_index = remainer.find(b'\r\n\r\n', 0, 40)
            if body_start_index <= 0:
                break
            body_start_index += 4  # ignore the newlines

            length = int(re.match(br"Content-Length: (\d+)", remainer)[1])

            remainer_start_index = body_start_index + length
            if len(remainer) < remainer_start_index:
                break  # not enough data yet

            body = remainer[body_start_index:remainer_start_index]
            remainer = remainer[remainer_start_index:]
            messages.append(body)
    except Exception as e:
        print_log(e)
        raise

    print_log(f"{len(messages)} messages found")

    return (messages, remainer)


def message_to_raw_data(message):
    """
    Convert a message to raw data (including Content-Length specifier).

    @param message [binary string] to be converted
    @return [binary string] raw data to be sent out
    """
    return (f"Content-Length: {len(message)}\r\n\r\n").encode() + message


def message_to_object(message):
    """
    Convert a (JSON) message to a (python) object.

    @param message [binary string] to be converted
    @return [object] decoded and parsed from JSON
    """
    return json.loads(message.decode())


def object_to_message(obj):
    """
    Convert a python object to (JSON) binary-encoded message.

    @param obj [object] to be converted
    @return [binary string] JSON encoded message
    """
    return json.dumps(obj).encode()


class VimSocket(threading.Thread):

    def __init__(self):
        super().__init__()
        self.sonarlintSocket = None

    def registerSonarlintSocket(self, socket):
        self.sonarlintSocket = socket

    def run(self):
        os.set_blocking(sys.stdin.fileno(), False)
        try:
            while self.sonarlintSocket is None\
                  or not self.sonarlintSocket.isConnected():
                time.sleep(0.1)
            remainer = b''
            while True:
                data = sys.stdin.buffer.read(BUFSIZE)
                if data is None:
                    time.sleep(0.1)
                    continue
                print_log(f"RX<-CL: {data}")
                remainer += data
                messages, remainer = find_messages_in_raw_data(remainer)
                for message in messages:
                    self.handleRxMessage(message)
        except Exception as e:
            print_log(str(e))
            print_log("Stdio Handler terminated")
            if self.sonarlintSocket is not None:
                self.sonarlintSocket.shutdown()
            raise

    def handleRxMessage(self, message):
        obj = message_to_object(message)
        if 'method' in obj:
            if obj['method'] == 'initialize':
                # FIX #1: add clientInfo into initialize message:
                obj['params']['clientInfo'] = {
                    'name': 'Vim', 'version': '8.2'
                }
                # FIX #2: extend init capabilities with 'window' options:
                obj['params']['capabilities']['window'] = {
                    'workDoneProgress': False
                }
            # FIX #3a: store config provided by Vim:
            elif obj['method'] == 'workspace/didChangeConfiguration':
                config = copy.deepcopy(obj['params']['settings'])
                print_log(f"Found config: {config}")
                if self.sonarlintSocket is not None:
                    self.sonarlintSocket.setSonarConfig(config)

        message = object_to_message(obj)

        if self.sonarlintSocket is not None:
            self.sonarlintSocket.send(message_to_raw_data(message))

    def send(self, message):
        data = message_to_raw_data(message)
        print_log(f"TX->CL: {data}")
        sys.stdout.buffer.write(data)
        sys.stdout.flush()


class SonarlintSocket(threading.Thread):

    def __init__(self, address):
        super().__init__()
        self.address = address
        self.conn = None
        self.diagnostics = None
        self.isRunning = True
        self.sonarConfig = None
        self.vimSocket = None

    def registerVimSocket(self, socket):
        self.vimSocket = socket

    def setSonarConfig(self, config):
        self.sonarConfig = config

    def run(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(self.address)
                s.listen(1)
                conn, addr = s.accept()
                self.conn = conn
                with conn:
                    print_log("Client connected")
                    remainer = b''
                    while self.isRunning:
                        data = conn.recv(BUFSIZE)
                        if not data:
                            break
                        print_log(f"RX<-LS: {data}")
                        remainer += data
                        messages, remainer =\
                            find_messages_in_raw_data(remainer)
                        for message in messages:
                            self.handleRxMessage(message)
        except Exception as e:
            print_log(str(e))
            raise

    def handleRxMessage(self, message):
        obj = message_to_object(message)
        if 'method' in obj:
            # FIX #3b: send config to sonarlint when it is requested:
            if obj['method'] == 'workspace/configuration':
                cfg = copy.deepcopy(self.sonarConfig['settings']['sonarlint'])
                new_object = {
                    'jsonrpc': '2.0',
                    'id': obj['id'],
                    'result': [cfg]
                }
                message = object_to_message(new_object)
                self.send(message_to_raw_data(message))
                return
            # FIX #4: reply with True to proprietary isOpenInEditor request:
            elif obj['method'] == 'sonarlint/isOpenInEditor':
                new_object = {
                    'jsonrpc': '2.0',
                    'id': obj['id'],
                    'result': True
                }
                message = object_to_message(new_object)
                self.send(message_to_raw_data(message))
                return
            # FIX #5: replay with False to proprietary isIgnoredByScm request:
            elif obj['method'] == 'sonarlint/isIgnoredByScm':
                new_object = {
                    'jsonrpc': '2.0',
                    'id': obj['id'],
                    'result': False
                }
                message = object_to_message(new_object)
                self.send(message_to_raw_data(message))
                return
            # FIX #6a: continuously store diagnostics received by sonarlint:
            elif obj['method'] == 'textDocument/publishDiagnostics':
                self.diagnostics = copy.deepcopy(obj)
                return
            # FIX #6b: send latest diagnostics to Vim once done:
            elif obj['method'] == 'window/logMessage':
                if 'Found' in obj['params']['message']:
                    message = object_to_message(self.diagnostics)
                    if self.vimSocket is not None:
                        self.vimSocket.send(message)

        message = object_to_message(obj)
        if self.vimSocket is not None:
            self.vimSocket.send(message)

    def isConnected(self):
        return (self.conn is not None)

    def send(self, data):
        print_log(f"TX->LS: {data}")
        self.conn.sendall(data)

    def shutdown(self):
        self.isRunning = False


if __name__ == "__main__":
    print_log(f"Started version {VERSION}...", overwrite=True)

    sonarlintSocket = SonarlintSocket(("localhost", PORT))
    sonarlintSocket.start()

    vimSocket = VimSocket()
    vimSocket.daemon = True
    vimSocket.start()

    vimSocket.registerSonarlintSocket(sonarlintSocket)
    sonarlintSocket.registerVimSocket(vimSocket)

    subprocess.call(SONARLINT_START_CMD.split(" "))

    sonarlintSocket.join()
    vimSocket.join()

    print_log("Stopped.")
