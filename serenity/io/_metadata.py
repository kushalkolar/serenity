from uuid import UUID
from dataclasses import dataclass, asdict
import json
from typing import *

import numpy as np


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
    comments: str = None

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

        if "header_elements" in data.keys():
            _header_elements = data.pop("header_elements")
            header_elements: List[HeaderElement] = list()
            for he in _header_elements:
                header_elements.append(
                    HeaderElement(**he)
                )
            data["header_elements"] = tuple(header_elements)

        return cls(channels=tuple(channels), **data)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        d = self.to_dict()
        d["uid"] = str(d["uid"])

        return json.dumps(d)

    def to_disk(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f)
