from typing import *
from pathlib import Path
from time import time, sleep

import zmq


class ScanImageSender:
    def __init__(self, address: str, buffer_path: Path | str):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(address)

        self.buffer_path = Path(buffer_path)

        # frames that have been successfully received
        self.indices_received: List[int] = list()

        # frames that have been sent
        self.indices_sent: List[int] = list()

        self.current_index_read = 1
        self.current_failed_attempt: int = 0

    def send_loop(self):
        while True:
            data = self._read_frame_buffer(self.current_index_read)

            # if frame buffer not yet ready for this index
            if data is None:
                # sleep for 5ms and go back to the top of the loop
                sleep(0.005)
                continue

            self.socket.send(data)

            send_time = time()

            while True:
                now = time()
                try:
                    reply = self.socket.recv(zmq.NOBLOCK)
                    print(reply)
                # reply not yet received
                except zmq.Again:
                    # if we've waited longer than 10ms for a reply, send again
                    if now - send_time > 0.01:
                        self.current_failed_attempt += 1
                        break
                # reply received, increment to next frame
                else:
                    # send next frame
                    self.current_index_read += 1
                    self.current_failed_attempt = 0

    def _get_frame_buffer_path(self, index: int):
        return self.buffer_path.joinpath(f"{index}.bin")

    def _remove_from_from_buffer(self, index):
        frame_buffer_path = self._get_frame_buffer_path(index)
        frame_buffer_path.unlink()

    def _read_frame_buffer(self, index: int):
        frame_buffer_path = self._get_frame_buffer_path(index)
        try:
            with open(frame_buffer_path, "rb") as f:
                data = f.read()

        # if matlab is still writing the file or not yet written
        except (PermissionError, FileNotFoundError):
            return None
        else:
            return data
