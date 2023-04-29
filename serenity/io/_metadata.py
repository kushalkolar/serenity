from uuid import UUID, uuid4
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import *

import numpy as np
import h5py


@dataclass
class HeaderElement:
    """Dataclass for a single header element"""
    name: str
    dtype: str

    @property
    def nbytes(self) -> int:
        return np.dtype(self.dtype).itemsize


@dataclass
class Channel:
    """Channel metadata"""
    index: int
    name: str
    shape: Tuple[int, int]
    dtype: str
    indicator: str
    color: str
    genotype: str

    @property
    def size(self) -> int:
        return self.shape[0] * self.shape[1]

    @property
    def nbytes(self) -> int:
        return np.dtype(self.dtype).itemsize * self.size


@dataclass
class AcquisitionMetadata:
    """
    Acquisition metadata that pertains to an entire acquisition session.

    Parameters
    ----------
    database: str
        batch parquet file that this acquisition belongs to

    uuid: UUID
        identifier for this acquisition session, must be generated in ScanImageReceiver

    animal_id: str
        animal identifier

    channels: Tuple[Channel]
        recording channel data

    framerate: float
        framerate

    date: str
        "YYYYMMDD_HHMMSS", hours in 24 hour format

    sub_session: int
        subsession number for this acquisition

    # TODO: See which scanimage metadata is compatible, make sure no issues
    scanimage_meta: dict
        All other scanimage metadata

    header_elements: Tuple[HeaderElement]
        descriptions of the elements that make up the header in each frame
    """
    database: str
    uuids: Tuple[UUID]
    animal_id: str
    channels: Tuple[Channel]
    framerate: float
    date: str
    sub_session: int
    scanimage_meta: dict = None
    comments: str = None

    # TODO: we could just use a yaml config or something for this long term
    # these are in order
    header_elements: Tuple[HeaderElement] = (
        HeaderElement("index", "uint32"),
        HeaderElement("sub_index", "uint32"),
        HeaderElement("sub_session", "uint32"),  # corresponds to one table-round sub-session
        HeaderElement("trial_index", "uint32"),
        HeaderElement("trigger_state", "uint32"),
        HeaderElement("timestamp", "float32")
    )

    @property
    def nbytes_header(self) -> int:
        return sum(e.nbytes for e in self.header_elements)

    @property
    def n_frames_init(self) -> int:
        """number of frames set for this acquisition + 100"""
        return self.scanimage_meta["hStackManager"]["framesPerSlice"] + 100

    def get_batch_item_path(self, channel_index: int) -> Path:
        """path to the batch item dir that corresponds to the given channel data"""
        return Path(self.database).parent.joinpath(self.uuids[channel_index])

    def get_init_path(self, channel_index: int) -> Path:
        return self.get_batch_item_path(channel_index).joinpath("init.tiff")

    @classmethod
    def from_jsons(cls, json_str: bytes, generate_uuid: bool = False):
        """
        Load from json formatted bytes

        Parameters
        ----------
        json_str: bytes
            jsone formatted bytes

        generate_uuid: bool, default False
            generate UUID, this is ONLY used when creating the
            metadata for a new acquisition from scanimage

        """
        data = json.loads(json_str)

        return cls.from_dict(data, generate_uuid=generate_uuid)

    @classmethod
    def from_json(cls, path: Path | str):
        """load from json file on disk"""
        d = json.load(open(path, "r"))

        return cls.from_dict(d)

    @classmethod
    def from_dict(cls, data: dict, generate_uuid: bool = False):
        _channels = data.pop("channels")

        channels = list()
        for ch in _channels:
            ch["shape"] = tuple(ch["shape"])
            channel_instance = Channel(**ch)
            channels.append(channel_instance)

        # sort them so they are in order in case they were sent out of order
        # they need to be sorted so we can assume uuids[i] always corresponds to channels[i]
        # likewise for frame data
        channel_indices = [ch.index for ch in channels]
        channels_sorted = list()

        for i in range(len(channel_indices)):
            # get the unsorted position of channel_i
            unsorted_ix = channel_indices.index(i)
            # append at sorted position i
            channels_sorted.append(channels[unsorted_ix])

        if generate_uuid:
            # when receiving brand new acq metadata from scanimage
            uids = list()
            for i in range(len(channels)):
                uid = str(uuid4())
                uids.append(uid)
            data["uuids"] = tuple(uids)

        if "header_elements" in data.keys():
            _header_elements = data.pop("header_elements")
            header_elements: List[HeaderElement] = list()
            for he in _header_elements:
                header_elements.append(
                    HeaderElement(**he)
                )
            data["header_elements"] = tuple(header_elements)

        return cls(channels=tuple(channels_sorted), **data)

    def create_header_file(self, path: Path | str, channel: int):
        """
        Create header file at given path, used to store frame headers for every frame
        """
        path = Path(path)
        if path.exists():
            raise FileExistsError(f"header file already exists at given location: {path}")

        # set upper limit of 3 hours at 30Hz
        max_n_frames = 3 * 60 * 60 * 30

        with h5py.File(path, "w") as f:
            # store uid
            f.attrs["uuid"] = str(self.uuids[channel])

            # create dataset for each header element which will be stored as 1D array
            for header_element in self.header_elements:
                f.create_dataset(header_element.name, shape=(max_n_frames,), dtype=header_element.dtype)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        d = self.to_dict()

        return json.dumps(d)

    def to_disk(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
