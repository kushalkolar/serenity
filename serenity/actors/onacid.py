from queue import Empty
import logging

import numpy as np
import zmq

from scipy.sparse import csr_matrix
import tensorflow as tf
from time import time, sleep
import caiman as cm
from caiman.source_extraction import cnmf
from caiman.utils.nn_models import (fit_NL_model, create_LN_model, quantile_loss, rate_scheduler)

from improv.actor import Actor

from serenity.io import AcquisitionMetadata, TwoPhotonFrame
from serenity.io.signals import *
from serenity.extensions import AcquisitionDataFrameExtensions, AcquisitionSeriesExtensions
import tifffile

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


fr = 30.04                                                             # frame rate (Hz)
decay_time = 0.5                                                    # approximate length of transient event in seconds
gSig = (2, 2)                                                        # expected half size of neurons
p = 1                                                               # order of AR indicator dynamics
min_SNR = 1                                                         # minimum SNR for accepting new components
rval_thr = 0.90                                                     # correlation threshold for new component inclusion
ds_factor = 1                                                       # spatial downsampling factor (increases speed but may lose some fine structure)
gnb = 2                                                             # number of background components
gSig = tuple(np.ceil(np.array(gSig)/ds_factor).astype('int'))       # recompute gSig if downsampling is involved
mot_corr = True                                                     # flag for online motion correction
pw_rigid = False                                                    # flag for pw-rigid motion correction (slower but potentially more accurate)
max_shifts_online = np.ceil(10./ds_factor).astype('int')            # maximum allowed shift during motion correction
sniper_mode = True                                                  # flag using a CNN to detect new neurons (o/w space correlation is used)
init_batch = 200                                                    # number of frames for initialization (presumably from the first file)
expected_comps = 500                                                # maximum number of expected components used for memory pre-allocation (exaggerate here)
dist_shape_update = True                                            # flag for updating shapes in a distributed way
min_num_trial = 10                                                  # number of candidate components per frame
K = 2                                                               # initial number of components
epochs = 2                                                          # number of passes over the data
show_movie = False                                                  # show the movie with the results as the data gets processed

params_dict = {'fr': fr,
               'decay_time': decay_time,
               'gSig': gSig,
               'p': p,
               'min_SNR': min_SNR,
               'rval_thr': rval_thr,
               'ds_factor': ds_factor,
               'nb': gnb,
               'motion_correct': mot_corr,
               'init_batch': init_batch,
               'init_method': 'bare',
               'normalize': True,
               'expected_comps': expected_comps,
               'sniper_mode': sniper_mode,
               'dist_shape_update' : dist_shape_update,
               'min_num_trial': min_num_trial,
               'K': K,
               'epochs': epochs,
               'max_shifts_online': max_shifts_online,
               'pw_rigid': pw_rigid,
               'show_movie': show_movie}


class OnACIDActor(Actor):
    """
    Receives frame from zmq and puts it in the queue
    """
    def __init__(self, *args, channel_index: int, addr_mcorr_frames: str, **kwargs):
        """
        Parameters
        ----------
        channel_index: int
            channel to process in this OnACID actor

        addr_mcorr_frames: str
            address to publish mcorr frames
        args
        kwargs
        """
        super().__init__(*args, **kwargs)
        self.addr = addr_mcorr_frames
        self.channel_index: int = channel_index
        self.init_movie = None

    def setup(self):
        # setup ZMQ publisher
        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(self.addr)
        # TODO: setup file location for onacid estimates outputs
        # TODO: use zmq to get parameters for onacid
        # TODO: use zmq to get mesmerize dir and uuid info

        self.onacid_initialized: bool = False

        # whether onacid has been initialized or not yet
        # TODO: allow these to be settable via zmq
        self.init_batch = 1000  # number of frames to use for initialization
        self.frame_index = 0
        # TODO: these should be recieved from store
        dtype = "uint16"
        self.shape = (512, 512)
        self.fr = 15.5  # frame rate (Hz)
        self.dtype = getattr(np, dtype)

        self.init_movie = np.zeros((self.init_batch, *self.shape), dtype=self.dtype, order="C")

        self.acq_meta: AcquisitionMetadata = None

        logger.info("OnACID ready")

    def _reset(self):
        self.acq_meta: AcquisitionMetadata = None

    def _get_bytes(self) -> bytes | None:
        try:
            # TODO: this frame will just be raw bytes which contain a header of specific length
            # TODO: strip and parse header from each received frame
            buffer = self.q_in.get(timeout=0.005)
        except Empty:
            return None
        except:
            logger.error("Could not get frame!")
        else:
            return buffer

    def _initialize_onacid(self, array):
        self.init_movie = cm.movie(array)
        memmap_path = self.acq_meta.get_batch_item_path(self.channel_index).joinpath("init.mmap")
        fname_init = self.init_movie.save(str(memmap_path), order="C")

        params_dict["fnames"] = fname_init
        params_dict["init_batch"] = array.shape[0]

        self.cnmf_params = cnmf.params.CNMFParams(params_dict)
        self.cnmf_obj = cnmf.online_cnmf.OnACID(params=self.cnmf_params)

        self.cnmf_obj.initialize_online()

        # to be ready for next frame t arg thing
        self.frame_index = array.shape[0] + 1

        # onacid init complete
        self.onacid_initialized = True
        logger.info("OnACID Intialization Complete!")

    def runStep(self):
        """Receives data from queue, performs OnACID"""

        # get bytes from queue
        b = self._get_bytes()

        # no frames ready
        if b is None:
            return

        # bytes available but this is the first queued item, start initialization
        if self.acq_meta is None:
            self.acq_meta = AcquisitionMetadata.from_jsons(b)

            # read init array
            array = tifffile.imread(self.acq_meta.get_init_path(self.channel_index))
            self._initialize_onacid(array)
            return

        frame2p = TwoPhotonFrame.from_bytes(b, self.acq_meta)

        # TODO: figure out how to deal with dual channels
        frame = frame2p.channels[self.channel_index]

        mcorr = self.cnmf_obj.mc_next(self.frame_index, frame)

        # TODO: We probably also want to send more information to the viz frontend
        # TODO: such as frame index and other metadata that we already have
        # TODO: maybe we just constructe a TwoPhotonFrame object and send the bytes?
        # send mcorr frame for visualization
        # self.socket.send(mcorr)

        self.cnmf_obj.fit_next(self.frame_index, mcorr.ravel(order="F"))
        # TODO: keep esitmates in store or on disk or something and poll that for visualization udpates too

        self.frame_index += 1
