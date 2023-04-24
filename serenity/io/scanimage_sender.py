from typing import *
import asyncio
from pathlib import Path

import zmq


class ScanImageSender:
    def __init__(self, address: str, buffer_path: Path | str):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(address)

        self.buffer_path = Path(buffer_path)

        self.indices_finished: List[int] = list()
        self.current_index_read = 1

    async def send_frame(self, index):
        data = self.read_si_binary(index)

        self.socket.send(data)
        # wait for reply
        # self.socket.recv()

    async def receive_reply(self):
        pass

    def remove_frame_from_buffer(self, index: int):
        pass

    def read_si_binary(self, index: int):
        with open(self.buffer_path.joinpath(f"{index}.bin"), "rb") as f:
            data = f.read()

        return data
