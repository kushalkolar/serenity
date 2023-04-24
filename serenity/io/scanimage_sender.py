from typing import *
import asyncio
from pathlib import Path
from time import time

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

        # {frame_ix: time}, frames which have been sent but not received
        self.indices_waiting: Dict[int, float] = dict()

        # frames which have been sent but lost
        self.missing_queue = list()

        self.current_index_read = 1

        self.reply_task = asyncio.create_task(self.reply_loop())
        self.send_task = asyncio.create_task(self.send_loop())

    async def send_loop(self):
        while True:
            ix = self.current_index_read

            self._send_frame(ix)
            self.indices_sent.append(ix)
            self.indices_waiting[ix] = time()
            self.current_index_read += 1

            # empty the missing queue
            for mix in self.missing_queue:
                self._send_frame(mix)
                # reset the time
                self.indices_waiting[mix] = time()

            # clear the missing queue, we assume that it is more likely to be received than lost
            # so if the frame is still missing after another send attempt we wait for it to be
            # re-added to the `missing_queue`
            self.missing_queue.clear()

            await asyncio.sleep(0.01)

    def _send_frame(self, index: int):
        data = self._read_frame_buffer(index)

        if data is None:
            return

        self.socket.send(data)

    async def reply_loop(self):
        while True:
            try:
                reply = self.socket.recv(zmq.NOBLOCK)
            except zmq.Again:
                pass
            else:
                index = int(reply.decode())
                self.remove_frame_from_buffer(index)

                # remove from missing queue
                # TODO: probably better to clear the missing queue from send_loop() and not here, but test it
                # if index in self.missing_queue:
                #     self.missing_queue.remove(index)

                self.indices_received.append(index)
            finally:
                self._check_for_missing_indices()
                await asyncio.sleep(0.01)

    def _check_for_missing_indices(self):
        finished = sorted(self.indices_received)

        # make sure finished is consecutive integers
        for i in range(len(self.indices_received) - 1):
            diff = finished[i] - finished[i + 1]

            # if non-consecutive, add all in-between indices to the missing queue
            if diff > 1:
                for j in range(i, i + diff):
                    # add to missing queue
                    self.missing_queue.append(j)

        # check for any frames that haven't been received for a long time
        now = time()
        for ix in self.indices_waiting.keys():
            delta = now - self.indices_waiting[ix]

            # frames that were sent > 1 second ago but still not confirmed as received
            if delta > 1:
                self.missing_queue.append(ix)

    def remove_frame_from_buffer(self, index: int):
        self.indices_waiting.pop(index)

    def _read_frame_buffer(self, index: int):
        try:
            with open(self.buffer_path.joinpath(f"{index}.bin"), "rb") as f:
                data = f.read()

        # if matlab is still writing the file
        except PermissionError:
            return None
        else:
            return data
