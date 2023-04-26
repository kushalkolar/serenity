from typing import *
from pathlib import Path
from time import time, sleep

import numpy as np
import zmq


class SerenityServer:
    def __init__(
            self,
            address_improv_server: str,
            address_matlab: str,
            buffer_path: Path | str
    ):
        # for sending data to improv actor
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(address_improv_server)

        # for receiving acq metadata from matlab
        self.context_matlab = zmq.Context()
        self.socket_matlab = self.context_matlab.socket(zmq.REP)
        self.socket_matlab.bind(address_matlab)

        # frame buffer on SSD
        self.buffer_path = Path(buffer_path)
        self.current_buffer_path: Path = None

        self.indices_received = None
        self.indices_sent = None
        self.current_index_read = None
        self.current_failed_attempt = None

        self.current_uid = None

        self.acq_ended = None
        self.last_frame_ix = None

    def close(self):
        self.socket_matlab.close()

    def start_acq(self, timeout: int = 30):
        """
        Receive acquisition metadata from matlab and get ready for acquisition.
        Blocks until acquisition metadata is received. Starts acquisition loop
        after metadata is received.

        Parameters
        ----------
        timeout: int, default ``30``
            timeout in seconds

        """
        # frames that have been successfully received
        self.indices_received: List[int] = list()

        # frames that have been sent
        self.indices_sent: List[int] = list()

        self.current_index_read = 1
        self.current_failed_attempt: int = 0

        t = time()
        while True:
            now = time()
            # check every second for acquisition metadata
            try:
                # receive acq metadata from matlab
                acq_meta_json = self.socket_matlab.recv(zmq.NOBLOCK)
            except zmq.Again:
                if (now - t) > timeout:
                    raise TimeoutError(
                        "Receiving acquisition metadata has timed out."
                    )
                sleep(1)
            else:
                break

        # send acquisition metadata to improv, should send uuid in reply
        self.socket.send(acq_meta_json)

        t = time()
        # wait for reply
        while True:
            now = time()
            try:
                # uuid from improv for this acquisition
                uid_reply = self.socket.recv_string(zmq.NOBLOCK, encoding="utf-8")
            except zmq.Again:
                if now - t > 5:
                    msg = "Failed to receive reply for acquisition metadata, try `start_acq()` again."
                    # reply to matlab with uuid
                    self.socket_matlab.send_string(msg)
                    raise TimeoutError(msg)

                sleep(0.5)
            else:
                self.socket_matlab.send_string(uid_reply)
                break

        # start frame sending loop
        self.current_uid = uid_reply
        self.current_buffer_path = self.buffer_path.joinpath(self.current_uid)

        self.acq_ended = False
        self.last_frame_ix = None
        self.send_loop()

    def _check_end_acq(self):
        try:
            frame_ix = self.socket_matlab.recv(zmq.NOBLOCK)
        except zmq.Again:
            pass
        else:
            self.last_frame_ix = np.frombuffer(frame_ix, offset=60, count=1, dtype=np.uint32).item()
            print(self.last_frame_ix)
            self.acq_ended = True

    def end_acq(self):
        # tell improv to end acq
        self.socket.send(b"end-acquisition")

        send_time = time()
        print("waiting for improv to acknowledge end of acquisition")
        while True:
            try:
                msg = self.socket.recv(zmq.NOBLOCK)
            except zmq.Again:
                if time() - send_time > 30:
                    msg = "Timeout exceeded in waiting for improv to acknowledge end of acquisition"
                    self.socket_matlab.send_string(msg)
                    raise TimeoutError(msg)
                sleep(1)
                break
            else:
                print(str(msg))
                # reply to matlab acq ended
                self.socket_matlab.send_string("serenity server and improv ended acquisition")
                break

    def send_loop(self):
        while True:
            # check if scanimage acq has ended
            self._check_end_acq()

            if self.acq_ended:
                if self.current_index_read > self.last_frame_ix:
                    self.end_acq()
                    break

            data = self._read_frame_buffer(self.current_index_read)

            # if frame buffer not yet ready for this index
            if data is None:
                # sleep for 5ms and go back to the top of the loop
                sleep(0.005)
                continue
                
            self.socket.send(data)
            print(f"sent frame: {self.current_index_read}")

            send_time = time()
            
            # reply wait loop
            while True:
                now = time()
                try:
                    reply = self.socket.recv(zmq.NOBLOCK)
                    print(f"received reply for: {np.frombuffer(reply, dtype=np.uint32)}")
                # reply not yet received
                except zmq.Again:
                    # if we've waited longer than 100ms for a reply, send again
                    if now - send_time > 1:
                        self.current_failed_attempt += 1
                        break
                # reply received, increment to next frame
                else:
                    # remove the replied frame from buffer
                    self._remove_from_from_buffer(self.current_index_read)
                    # increment to next frame
                    self.current_index_read += 1
                    self.current_failed_attempt = 0
                    break

    def _get_frame_buffer_path(self, index: int):
        return self.buffer_path.joinpath(self.current_uid, f"{index}.bin")

    def _remove_from_from_buffer(self, index):
        frame_buffer_path = self._get_frame_buffer_path(index)
        frame_buffer_path.unlink()

    def _read_frame_buffer(self, index: int):
        frame_buffer_path = self._get_frame_buffer_path(index)
        # frame not yet written
        if not frame_buffer_path.exists():
            return None

        try:
            with open(frame_buffer_path, "rb") as f:
                data = f.read()

        # if matlab is still writing the file or not yet written
        except (PermissionError, FileNotFoundError):
            return None
        else:
            return data
