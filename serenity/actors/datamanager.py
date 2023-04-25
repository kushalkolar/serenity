from queue import Empty
import logging
from typing import *

import numpy as np
import tifffile
import zmq

from improv.actor import Actor

from ..io import AcquisitionMetadata, TwoPhotonFrame

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ScanImageReceiver(Actor):
    """
    Receives frames and header from zmq and puts it in the queue as raw bytes.
    """
    def __init__(
            self,
            address: str = "tcp://0.0.0.0:9050",
            *args,
            **kwargs
    ):
        """
        Parameters
        ----------
        address: str, default ``"tcp://0.0.0.0:9050"``
            Address that zmq server will listen on for receiving data from scanimage

        """

        super().__init__(*args, **kwargs)

        # for receiving acquisition metadata
        self.context_acq = zmq.Context()
        self.socket = self.context_acq.socket(zmq.REP)
        self.socket.setsockopt(zmq.BACKLOG, 1_000)
        self.socket.bind(address)

        # received frame indices
        self.received_indices: List[int] = list()

    def setup(self):
        logger.info("ScanImageReceiver receiver starting")

        # TODO: Think about how to enter acquisition metadata
        # TODO: Some comes from scanimage such as fps

        # TODO: put acquisition metadata in store

        self.acquisition_metadata: AcquisitionMetadata = None

        logger.info("ScanImageReceiver receiver ready!")

    def _receive_bytes(self) -> List[bytes] | None:
        """
        Pulls bytes from the socket
        """

        try:
            b = self.socket.recv_multipart(zmq.NOBLOCK)
        except zmq.Again:
            pass
        else:
            return b

    def _reply_frame_received(self, index: int):
        self.socket.send(index)

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

        frame = TwoPhotonFrame.from_zmq_multipart(b, self.acquisition_metadata)
        self._reply_frame_received(frame.index)

        # in case a frame was received but the reply wasn't received on the other end
        if frame.index not in self.received_indices:
            self.q_out.put(frame.to_bytes())
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
        super().__init__(*args, **kwargs)
        self.acq_meta: AcquisitionMetadata = None
        self.writers: List[tifffile.TiffWriter] = list()

    def setup(self):
        # TODO: maybe do something here where we get the UUID and other info like params?
        # TODO: Also decide how we communicate information like dtype, buffer parsing etc.
        self.acq_meta: AcquisitionMetadata

        for channel in self.acq_meta.channels:
            color = channel.color
            self.writers.append(tifffile.TiffWriter(f"./{color}.tiff", bigtiff=True))

        # TODO: Get acquisition params etc. from store


        logger.info("Mesmerize Writer ready")

    def _get_frame(self) -> TwoPhotonFrame:
        """
        Gets frame from ScanImageReceiver
        """
        try:
            buff = self.q_in.get(timeout=0.05)  # queue connected to ScanImageReceiver
        except Empty:
            pass
        except:
            logger.error("Could not get frame!")
        else:
            return TwoPhotonFrame.from_bytes(buff, self.acq_meta)

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

        for writer, channel_data in zip(self.writers, frame.channels):
            writer.write(channel_data)
