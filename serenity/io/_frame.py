from dataclasses import dataclass
from typing import *
from pathlib import Path

import h5py
import numpy as np

from ._metadata import AcquisitionMetadata


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
            data: bytes | bytearray,
            acq_meta: AcquisitionMetadata,
            from_matlab: bool = False
    ):
        """
        Create ``TwoPhotonFrame`` using raw bytes. Parses header and channel data.

        Benchmarked to 10µs

        Parameters
        ----------
        data: bytes
            raw bytes containing the header and frame data

        acq_meta: AcquisitionMetadata
            acquisition metadata, required to parse the header

        from_matlab: bool
            if these bytes are from matlab,
            compensates for the additional bytes that matlab adds to each header element

        """

        header_parsed = dict()

        # parse header
        start_byte = 0

        if from_matlab:
            # since matlab adds 60 bits of something as a header to each header element
            # only the last 4 bytes are our actual header element value
            start_byte += 60

        for element in acq_meta.header_elements:
            # parse the header for this element
            header_parsed[element.name] = np.frombuffer(
                buffer=data,
                dtype=element.dtype,
                offset=start_byte,
                count=1  # this is the number of elements to get from the buffer, it is 1 since it is 1 header element
            )

            # jump to next header element
            start_byte += element.nbytes

            # add the 60 bits for matlab weirdness
            if from_matlab:
                start_byte += 60

        # parse channels
        if not from_matlab:
            start_byte = acq_meta.nbytes_header

        channels: List[np.ndarray] = list()

        for channel in acq_meta.channels:
            # make frame data
            frame = np.frombuffer(
                buffer=data,
                dtype=channel.dtype,
                offset=start_byte,  # providing offset and count is much faster than indexing
                count=channel.size  # https://github.com/kushalkolar/serenity/issues/13
            ).reshape(channel.shape)

            channels.append(frame)

            # this is faster than calculating the bytes ourself
            start_byte += frame.nbytes

        return cls(acq_meta=acq_meta, channels=channels, **header_parsed)

    @classmethod
    def from_zmq_multipart(cls, data: List[bytes], acq_meta):
        """
        Parse zmq multipart message sent from SerenityClient on matlab.

        Benchmarked to 15µs.

        Parameters
        ----------
        data: list of bytes
            list of bytes, each element corresponds to a header element, and
             the last or last 2 elements are the channel array data

        acq_meta: AcquisitionMetadata
            acquisition metadata, required to parse the header

        """
        header_parsed = dict()

        for element in acq_meta.header_elements:
            # parse the header for this element
            buffer = data.pop(0)
            header_parsed[element.name] = np.frombuffer(
                buffer=buffer,
                dtype=element.dtype,
                offset=len(buffer) - element.nbytes,
                count=1  # this is the number of elements to get from the buffer, it is 1 since it is 1 header element
            )

        # parse channels
        channels: List[np.ndarray] = list()
        for channel in acq_meta.channels:
            # bytes for this channel
            buffer = data.pop(0)

            frame = np.frombuffer(
                buffer=buffer,
                dtype=channel.dtype,
                offset=len(buffer) - channel.nbytes,
                count=channel.size
            ).reshape(channel.shape)

            channels.append(frame)

        return cls(acq_meta=acq_meta, channels=channels, **header_parsed)

    def to_bytes(self) -> bytearray:
        """
        serialize to bytearray.

        benchmarked to 20µs
        """
        b = bytearray()

        # this should be the fastest way to concatenate raw bytes
        for he in self.acq_meta.header_elements:
            b.extend(getattr(self, he.name).tobytes())

        for channel in self.channels:
            b.extend(channel)

        return b

    def append_header_file(self, path: Path | str):
        """
        Append header information from this frame to the header file at the given path
        """
        path = Path(path)
        if not path.exists():
            raise FileExistsError(f"header does not exist at given location: {path}")

        with h5py.File(path, "r+") as f:
            if not f.attrs["uid"] == str(self.acq_meta.uid):
                raise ValueError(
                    "acquisition uid of the given header file does not "
                    "match the acquisition uid of the current frame"
                )
            for header_element in self.acq_meta.header_elements:
                val = getattr(self, header_element.name)
                # since it will be an array of size 1
                f[header_element.name][self.index] = val.item()

    def __eq__(self, other):
        """
        Just checks equality of channel array data
        """
        for i in range(len(self.channels)):
            if not (self.channels[i] == other.channels[i]).all():
                return False

        return True
