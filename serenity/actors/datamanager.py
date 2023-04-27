from typing import *
from queue import Empty
import logging
from collections import deque
from pathlib import Path
import traceback

import pandas as pd
from mesmerize_core import load_batch

import numpy as np
import tifffile
import zmq

from improv.actor import Actor

from serenity.io import AcquisitionMetadata, TwoPhotonFrame
from serenity.extensions import AcquisitionDataFrameExtensions, AcquisitionSeriesExtensions

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
        self.last_frame_index: int = -1

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
            try:
                self.acq_meta = AcquisitionMetadata.from_jsons(b, generate_uuid=True)

                # reply to socket
                # just send the first uid if using two channels, doesn't matter for matlab
                uids = self.acq_meta.uuids

                self.acq_ready = True
                # self downstream
                self.q_out.put(self.acq_meta.to_json())
            except Exception as e:
                self.socket.send_string(f"Failure in starting acquisition\n{e}\n{traceback.format_exc()}")
            else:
                self.socket.send_string("_".join(uids))
                logger.info(f"********** UUID in receiver ********\n{self.acq_meta.uuids}")
            finally:
                return

        # else, this is a frame, parse and send
        try:
            frame = TwoPhotonFrame.from_bytes(b, self.acq_meta, from_matlab=True)
        except Exception as e:
            # bad frame, request new one
            self.socket.send("bad frame".encode("utf-8"))
            logger.error(f"Bad frame after index: {self.last_frame_index}")
            return
        else:
            # good frame, reply frame index
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
            self.last_frame_index = frame.index
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

        # mesmerize batch dir for this acquisition
        self.acq_meta: AcquisitionMetadata = None
        self.writers: List[tifffile.TiffWriter] = None
        self.movie_paths: List[Path] = None
        self.header_paths: List[Path] = None

        self.dataframe: pd.DataFrame = None

    def setup(self):
        logger.info("Mesmerize Writer ready")

    def _get_bytes(self) -> bytes | None:
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

    def _reset(self):
        """
        Reset the state of this actor to get ready for next acquisition
        """
        self.acq_meta: AcquisitionMetadata = None
        self.writers: List[tifffile.TiffWriter] = None
        self.movie_paths: List[Path] = None
        self.header_paths: List[Path] = None

    def stop(self):
        for w in self.writers:
            w.close()

        return 0

    def _setup_new_acq(self, bytes_acq_meta):
        self.acq_meta = AcquisitionMetadata.from_jsons(bytes_acq_meta)

        logger.info(f"********** UUID in mesmerize writer ********\n{self.acq_meta.uuids}")

        # load mesmerize dataframe
        self.dataframe = load_batch(self.acq_meta.database, file_format="parquet")

        self.movie_paths, self.header_paths = self.dataframe.acq.add_item(acq_meta=self.acq_meta)

        self.writers = list()
        for i in range(len(self.acq_meta.channels)):
            self.writers.append(tifffile.TiffWriter(self.movie_paths[i], bigtiff=True))

    def runStep(self):
        """
        Writes data to a mesmerize database
        """
        b = self._get_bytes()

        if b is None:
            return

        # TODO: write header data to disk as well
        # set acq metadata
        if self.acq_meta is None:
            self._setup_new_acq(b)

            return

        frame = TwoPhotonFrame.from_bytes(b, self.acq_meta)

        for i, (writer, channel_data) in enumerate(zip(self.writers, frame.channels)):
            writer.write(channel_data)

            # append header of current frame to header file
            frame.append_header_file(self.header_paths[i], channel=i)
