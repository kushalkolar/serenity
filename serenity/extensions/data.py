from typing import *
from pathlib import Path
import logging

import numpy as np
import pandas as pd
import h5py
import tifffile

from mesmerize_core.batch_utils import PathsDataFrameExtension, PathsSeriesExtension

from ..io import AcquisitionMetadata, TwoPhotonFrame

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@pd.api.extensions.register_series_accessor("acq")
class AcquisitionSeriesExtensions:
    def __init__(self, series: pd.Series):
        self._series = series

    def get_item_dir(self) -> Path:
        return self._series.paths.get_batch_path().parent.joinpath(self.uuid)

    @property
    def uuid(self) -> str:
        return self._series["uuid"]

    # TODO: make mesmerize cache decorator more easily accessible so I can use it here
    def get_meta(self) -> AcquisitionMetadata:
        """
        Get the acquisition metadata

        Returns
        -------
        AcquisitionMetadata
            acquisition metadata object
        """
        # "batch_path/uuid/uuid.json"
        path = self.get_item_dir().joinpath(f"{self.uuid}.json")
        return AcquisitionMetadata.from_json(path)

    def get_header(self) -> Dict[str, np.ndarray]:
        path = self.get_item_dir().joinpath(f"{self.uuid}.header")

        with h5py.File(path, "r") as f:
            header = dict.fromkeys(f.keys())
            for k in header.keys():
                # should be fine to just return the entire array for each header element
                # even if there are 10 header elements and 100,000 frames that is only
                # 100,000 * 10 * 4 bytes = 4 megabytes
                header[k] = f[k][()]

        return header


@pd.api.extensions.register_dataframe_accessor("acq")
class AcquisitionDataFrameExtensions:
    def __init__(self, dataframe: pd.DataFrame):
        self._dataframe = dataframe

    def add_item(self, acq_meta: AcquisitionMetadata) -> Tuple[List[Path], List[Path]]:
        """
        Add an item to start acquisition

        Parameters
        ----------
        acq_meta: AcquisitionMetadata

        Returns
        -------
        Tuple[List[Path], List[Path]]
            ([input_movie_paths], [header_paths])
        """
        batch_dir: Path = self._dataframe.paths.get_batch_path().parent

        # input movie paths are returned, order corresponds to channel order
        input_movie_paths = list()
        # also returns paths to headers so they can be appended
        header_paths = list()

        logger.info(f"********** UUID in add_item ********\n{acq_meta.uuids}")

        for i in range(len(acq_meta.channels)):
            channel = acq_meta.channels[i]
            uid = acq_meta.uuids[i]

            # make dir for this item only
            item_path = batch_dir.joinpath(uid)
            item_path.mkdir()

            # full path to input movie
            input_movie_path = item_path.joinpath("raw.tiff")
            input_movie_paths.append(input_movie_path)
            # path relative to batch_dir
            relative_input_movie_path = self._dataframe.paths.split(input_movie_path)[1]

            s = pd.Series(
                {
                    "uuid": uid,
                    "input_movie_path": str(relative_input_movie_path),
                    "algo": "onacid",
                    "animal_id": acq_meta.animal_id,
                    "framerate": acq_meta.framerate,
                    "date": acq_meta.date,
                    "comments": acq_meta.comments,
                    "channel_index": channel.index,
                    "channel_name": channel.name,
                    "channel_colors": channel.color,
                    "channel_genotype": channel.genotype,
                    "channel_indicator": channel.indicator,
                }
            )

            logger.info(uid)
            logger.info(str(s))

            # write metadata to disk
            acq_meta.to_disk(item_path.joinpath(f"{uid}.json"))

            # create header file that is ready to go
            header_path = item_path.joinpath(f"{uid}.header")
            acq_meta.create_header_file(header_path, channel=i)
            header_paths.append(header_path)

            # Add the Series to the DataFrame
            self._dataframe.loc[self._dataframe.index.size] = s

            # Save DataFrame to disk
            self._dataframe.to_parquet(self._dataframe.paths.get_batch_path())

        return input_movie_paths, header_paths
