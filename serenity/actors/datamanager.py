from typing import *
from queue import Empty
import logging
from collections import deque
from uuid import uuid4

import numpy as np
import tifffile
import zmq

from improv.actor import Actor

from serenity.io import AcquisitionMetadata, TwoPhotonFrame

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ScanImageReceiver(Actor):
    """
    Receives frames and header from zmq and puts it in the queue as raw bytes.
    """
    def __init__(
            self,
            *args,
            address: str = None,
            **kwargs
    ):
        """
        Parameters
        ----------
        address: str, default ``"tcp://0.0.0.0:9050"``
            Address that zmq server will listen on for receiving data from scanimage

        """
        if address is None:
            raise("Must specify address in improv graphic config yaml")

        self.address = address

        # super(ScanImageReceiver, self).__init__(name="ScanImageReceiver")
        super().__init__(*args, **kwargs)

    def setup(self):
        # for receiving acquisition metadata
        self.context_acq = zmq.Context()
        self.socket = self.context_acq.socket(zmq.REP)
        # self.socket.setsockopt(zmq.REQ, 1)
        self.socket.setsockopt(zmq.BACKLOG, 1_000)
        self.socket.setsockopt(zmq.LINGER, 10)  # 10ms
        self.socket.bind(self.address)

        # received frame indices
        self.received_indices: List[int] = list()

        # increment trial_index whenever we get a [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
        # this is the rising edge of the trigger
        self.n_frames_trial_index_increment = 5
        n = self.n_frames_trial_index_increment
        self.previous_trigger_states = deque([0] * (2 * n), maxlen=10)
        self._trial_index_increment_match = deque([0] * n + [1] * n)

        self.current_trial_index = 0

        self.current_uid = None

        self.acq_ready: bool = False
        self.acq_meta = None

        logger.info("ScanImageReceiver receiver ready!")

    def stop(self):
        self.socket.close()

    def _receive_bytes(self) -> bytes | None:
        """
        receive bytes from the socket
        """

        try:
            b = self.socket.recv(zmq.NOBLOCK)
        except zmq.Again:
            return None
        else:
            return b

    def _reply_frame_received(self, index: int):
        self.socket.send(str(index).encode("utf-8"))

    def runStep(self):
        """
        Receives data from zmq socket, puts it in the queue.

        We assume that actors which utilize this array will parse
        the header and frame themselves from raw bytes.
        """

        # TODO: make sure we don't have a memory leak here
        b = self._receive_bytes()

        if b is None:
            return

        # we expect that this is json encoded acq metadata
        if not self.acq_ready:
            uid = uuid4()
            self.acq_meta = AcquisitionMetadata.from_json(b, uid)

            # reply to socket
            self.socket.send_string(str(uid))

            self.current_uid = uid
            self.acq_ready = True
            # self downstream
            self.q_out.put(self.acq_meta.to_json())
            return

        # else, this is a frame, parse and send
        try:
            frame = TwoPhotonFrame.from_bytes(b, self.acq_meta, from_matlab=True)
        except Exception as e:
            # bad frame, request new one
            self.socket.send("bad frame".encode("utf-8"))
            logger.error(f"Bad frame after index: {self.current_trial_index}")
            return
        else:
            # goo frame, reply frame index
            self._reply_frame_received(frame.index)

        # this is a new frame
        if frame.index not in self.received_indices:
            # determine trial index
            self.previous_trigger_states.append(frame.trigger_state)
            # check for rising edge of trigger
            if self.previous_trigger_states == self._trial_index_increment_match:
                self.current_trial_index += 1

            # MUST be numpy array, else to_bytes doesn't work!
            frame.trial_index = np.array([self.current_trial_index], dtype=np.uint32)
            self.q_out.put(frame.to_bytes())
        # in case a frame was received but the reply wasn't received on the other end
        else:
            # send reply again
            self._reply_frame_received(frame.index)


class MesmerizeWriter(Actor):
    """
    Writes data to mesmerize database
    """

    def __init__(
            self,
            *args,
            **kwargs
    ):
        """

        Parameters
        ----------
        addr_acq_meta: str
            zmq address to receive acquisition metadata
        """
        # super(MesmerizeWriter, self).__init__(*args, name="MesmerizeWriter", **kwargs)
        super().__init__(*args, **kwargs)

        self.acq_meta: AcquisitionMetadata = None
        self.writers: List[tifffile.TiffWriter] = None

    def setup(self):
        logger.info("Mesmerize Writer ready")

    def _get_frame(self) -> bytes | None:
        """
        Gets frame from ScanImageReceiver
        """
        try:
            b = self.q_in.get(timeout=0.05)  # queue connected to ScanImageReceiver
        except Empty:
            return None
        except:
            logger.error("Could not get frame!")
            return None
        else:
            return b

    def stop(self):
        for w in self.writers:
            w.close()

        return 0

    def runStep(self):
        """
        Writes data to a mesmerize database
        """
        frame = self._get_frame()

        if frame is None:
            return

        # set acq metadata
        if self.acq_meta is None:
            self.acq_meta = AcquisitionMetadata.from_json(frame)
            self.acq_meta.to_disk(f"/data/kushal/improv-testing/{self.acq_meta.uid}.json")
            self.writers = list()
            for channel in self.acq_meta.channels:
                color = channel.color
                self.writers.append(tifffile.TiffWriter(f"/data/kushal/improv-testing/{color}.tiff", bigtiff=True))

            return

        frame = TwoPhotonFrame.from_bytes(frame, self.acq_meta)

        for writer, channel_data in zip(self.writers, frame.channels):
            writer.write(channel_data)
