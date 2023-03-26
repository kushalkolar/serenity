from uuid import UUID
from dataclasses import dataclass, asdict
import json
from typing import *

import numpy as np


@dataclass
class HeaderElement:
    name: str
    dtype: str

    @property
    def nbytes(self) -> int:
        return np.dtype(self.dtype).itemsize


@dataclass
class Channel:
    index: int
    name: str
    shape: Tuple[int, int]
    dtype: str
    indicator: str
    color: str
    genotype: str


@dataclass
class AcquisitionMetadata:
    """
    Acquisition metadata that pertains to an entire acquisition session

    Parameters
    ----------
    database: str
        name of mongodb or "batch path" that this acquisition belongs to

    uid: UUID
        identifier for this acquisition session, must be generated in ScanImageReceiver

    animal_id: str
        animal identifier

    channels: Tuple[Channel]
        recording channel data

    framerate: float
        framerate

    date: str
        "YYYYMMDD_HHMMSS", hours in 24 hour format

    # TODO: See which scanimage metadata is compatible, make sure no issues
    scanimage_meta: dict
        All other scanimage metadata

    header_elements: Tuple[HeaderElement]
        descriptions of the elements that make up the header in each frame
    """
    database: str
    uid: UUID
    animal_id: str
    channels: Tuple[Channel]
    framerate: float
    date: str
    scanimage_meta: dict = None

    # TODO: we could just use a yaml config or something for this long term
    # these are in order
    header_elements: Tuple[HeaderElement] = (
        HeaderElement("index", "uint32"),
        HeaderElement("trial_index", "uint32"),
        HeaderElement("trigger_state", "uint32"),
        HeaderElement("timestamp", "float32")
    )

    @property
    def nbytes_header(self) -> int:
        return sum(e.nbytes for e in self.header_elements)

    @classmethod
    def from_json(cls, json_str: bytes, uid: UUID = None):
        data = json.loads(json_str)
        if uid is not None:
            data["uid"] = uid

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict):
        _channels = data.pop("channels")

        channels = list()
        for ch in _channels:
            ch["shape"] = tuple(ch["shape"])
            channel_instance = Channel(**ch)
            channels.append(channel_instance)

        return cls(channels=tuple(channels), **data)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        d = self.to_dict()
        d["uid"] = str(d["uid"])

        return json.dumps(d)


@dataclass
class TwoPhotonFrame:
    """
    Data for a single two photon frame

    Parameters
    ----------
    acq_meta: AcquisitionMetadata
        acquisition metadata

    channels: Tuple[np.ndarray]
        tuple of arrays, one for each channel, ordered w.r.t AcquisitionMetadata

    index:
        frame index

    trial_index: np.uint32
        trial index

    trigger_state: np.uint32
        the state of the auxiliary trigger

    timestamp: np.float32
        timestamp in units of seconds
    """
    acq_meta: AcquisitionMetadata
    channels: List[np.ndarray]
    index: np.uint32
    trial_index: np.uint32
    trigger_state: np.uint32
    timestamp: np.float32

    @classmethod
    def from_bytes(
            cls,
            data: bytes,
            acq_meta: AcquisitionMetadata
    ):
        """
        Create ``TwoPhotonFrame`` using raw bytes received from the microscope.
        Parses header and channel data.

        Parameters
        ----------
        data: bytes
            raw bytes from the microscope containing the header and frame data

        acq_meta: AcquisitionMetadata
            acquisition metadata

        """

        header_parsed = dict()

        # parse header
        start_byte = 0
        for element in acq_meta.header_elements:
            # parse the header for this element
            header_parsed[element.name] = np.frombuffer(
                buffer=data,
                dtype=element.dtype,
                offset=start_byte,
                count=1  # this is the number of elements to get from the buffer, it is 1 since it is 1 header element
            )

            # jump to next header element
            start_byte = start_byte + element.nbytes

        # parse channels
        start_byte = acq_meta.nbytes_header
        channels: List[np.ndarray] = list()

        for channel in acq_meta.channels:
            # get number of bytes for this channel
            n_pixels = channel.shape[0] * channel.shape[1]

            # make frame data
            frame = np.frombuffer(
                buffer=data,
                offset=start_byte,  # providing offset and count is much faster than indexing
                count=n_pixels      # https://github.com/kushalkolar/serenity/issues/13
            ).reshape(channel.shape)

            channels.append(frame)

            # this is faster than calculating the bytes ourself
            start_byte += frame.nbytes

        return cls(acq_meta=acq_meta, channels=channels, **header_parsed)

    def to_bytes(self):
        b = bytearray()

        # this should be the fastest way to concatenate raw bytes
        for he in self.acq_meta.header_elements:
            b.extend(getattr(self, he.name).tobytes())

        for channel in self.channels:
            b.extend(channel)

        return b
