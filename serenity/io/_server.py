from typing import *
from pathlib import Path
from time import time, sleep

import numpy as np
import zmq
from IPython.display import clear_output

# can test both initialization and registration at same time
INIT_START_SIGNAL = b"initstart"

# start of an actual recording after initialization is complete
RECORD_START_SIGNAL = b"recordstart"

# resets states of all actors, use after either initialization or recording ended
ACQ_END_SIGNAL = b"acqend"

# TODO: have a visual alignment thing to visualize previous session means and current session live/rolling mean?


class SerenityServer:
    def __init__(
            self,
            address_improv_server: str,
            address_matlab: str,
            buffer_path: Path | str
    ):
        # for sending data to improv actor
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.REQ_RELAXED, 1)
        self.socket.connect(address_improv_server)

        # for receiving acq metadata from matlab
        self.context_matlab = zmq.Context()
        self.socket_matlab = self.context_matlab.socket(zmq.REP)
        self.socket_matlab.setsockopt(zmq.LINGER, 0)
        self.socket_matlab.bind(address_matlab)

        # frame buffer on SSD
        self.buffer_path = Path(buffer_path)
        self.current_buffer_path: Path = None

        self.indices_received = None
        self.indices_sent = None
        self.current_index_read = None
        self.current_failed_attempt = None
        self.retries: int = 0
        self.lingering_files = list()

        self.current_uid = None

        self.acq_ended = None
        self._abort = False
        self.last_frame_ix = None
        
        # "init" or "record"
        self.state: str = None

    def close(self):
        self.socket_matlab.close()

    def start_acq(self, timeout: int = 30):
        """
        Receive acquisition metadata from matlab and get ready for acquisition.
        Blocks until acquisition metadata is received. Starts acquisition loop
        after metadata is received.

        Parameters
        ----------
        timeout: int, default ``30``
            timeout in seconds

        """
        # frames that have been successfully received
        self.indices_received: List[int] = list()

        # frames that have been sent
        self.indices_sent: List[int] = list()

        self.current_index_read = 1
        self.current_failed_attempt: int = 0

        t = time()
        while True:
            print("waiting to receive metadata from matlab")
            now = time()
            # check every second for acquisition metadata
            try:
                # receive acq metadata from matlab
                acq_meta_json = self.socket_matlab.recv(zmq.NOBLOCK)
            except zmq.Again:
                if (now - t) > timeout:
                    raise TimeoutError(
                        "Receiving acquisition metadata has timed out."
                    )
                sleep(1)
            else:
                break
        
        # send acquisition metadata to improv, should send uuid in reply
        self.socket.send(acq_meta_json)
        
        t = time()
        # wait for reply
        while True:
            now = time()
            try:
                # uuid from improv for this acquisition
                uid_reply = self.socket.recv_string(zmq.NOBLOCK, encoding="utf-8")
            except zmq.Again:
                if now - t > 5:
                    msg = "Failed to receive reply for acquisition metadata, try `start_acq()` again."
                    # reply to matlab with uuid
                    self.socket_matlab.send_string(msg)
                    raise TimeoutError(msg)

                sleep(0.5)
            else:
                self.socket_matlab.send_string(uid_reply)
                break

        # make frame buffer using uuid for this item
        self.current_uid = uid_reply
        self.current_buffer_path = self.buffer_path.joinpath(self.current_uid)

        self.acq_ended = False
        self.last_frame_ix = None
        
        # start frame sending loop
        # start with initialization
        self.state = "init"
        print("ready for initialization")
        self.send_loop()

    def _check_end_acq(self):
        try:
            frame_ix = self.socket_matlab.recv(zmq.NOBLOCK)
        except zmq.Again:
            pass
        else:
            if frame_ix == b"abort":
                # abort acq
                self.abort()
                return
            self.last_frame_ix = np.frombuffer(frame_ix, offset=60, count=1, dtype=np.uint32).item()
            print(self.last_frame_ix)
            self.acq_ended = True

    def end_acq(self):
        # tell improv to end acq
        self.socket.send(ACQ_END_SIGNAL)

        send_time = time()
        print("waiting for improv to acknowledge end of acquisition")
        while True:
            now = time()
            try:
                msg = self.socket.recv(zmq.NOBLOCK)
            except zmq.Again:
                if now - send_time > 30:
                    msg = "Timeout exceeded in waiting for improv to acknowledge end of acquisition"
                    self.socket_matlab.send_string(msg)
                    raise TimeoutError(msg)
                sleep(1)
            else:
                print(f"improv says: {str(msg)}")
                # reply to matlab acq ended
                self.socket_matlab.send_string("serenity server and improv ended acquisition")
                break
                
    def abort(self):
        # if abort signal received from matlab
        self.acq_ended = True
        self._abort = True
    
    def reset(self):
        self.current_buffer_path: Path = None

        self.indices_received = None
        self.indices_sent = None
        self.current_index_read = None
        self.current_failed_attempt = None
        self.retries: int = 0
        self.lingering_files = list()

        self.current_uid = None

        self.acq_ended = None
        self._abort = False
        self.last_frame_ix = None
        
    def _check_init(self):
        # polls matlab to check if initialization frames are all acquired
        try:
            response = self.socket_matlab.recv(zmq.NOBLOCK)
        except zmq.Again:
            pass
        else:
            if response == b"initacquired":
                # tell improv server init is done
                self.socket.send(b"initacquired")
                return True
        
        return False
        
    def send_loop(self):
        while True:
            if self.current_index_read % 50 == 0:
                clear_output()
                print(
                    f"frame sent: {self.current_index_read}\n"
                    f"retries: {self.retries}\n"
                    f"frame received: {self.current_index_read - 1}"
                )
                
            # check if init is done
            if self.state == "init":
                if self._check_init():
                    # wait for OnACID to finish initialization
                    while True:
                        try:
                            reply = self.socket.recv(zmq.NOBLOCK)
                        except zmq.Again:
                            pass
                        else:
                            # return to send_loop()
                            if reply == b"initrunnning":
                                print("improv received initialization frames, wait for initialization to complete before recording")
                                # required else socket_matlab.recv() deadlocks
                                self.socket_matlab.send(b"improvereceivedinit")
                                break
                            else:
                                raise RuntimeError(f"failed to start initialization: {reply}")
            
            # check if scanimage acq has ended
            self._check_end_acq()

            if self.acq_ended:
                if self._abort:
                    print("Acquisition aborted")
                    self.end_acq()
                    self.reset()
                    break
                
                # reply has been received for last frame, end
                if self.current_index_read > self.last_frame_ix:
                    if self.state == "init":
                        # initialization is finished, start recording real data
                        self.socket.send(b"recordstart")
                        self.state = "record"
                    else:
                        self.end_acq()
                        self.reset()
                    break
            
            # read data from disk frame buffer
            data = self._read_frame_buffer(self.current_index_read)

            # if frame buffer not yet ready for this index
            if data is None:
                # sleep for 2ms and go back to the top of the loop
                sleep(0.002)
                continue
                
            self.socket.send(data)

            send_time = time()
            
            # reply wait loop
            while True:
                now = time()
                try:
                    reply = self.socket.recv(zmq.NOBLOCK)
                # reply not yet received
                except zmq.Again:
                    # if we've waited longer than 20ms for a reply, send again
                    if now - send_time > 0.03:
                        self.current_failed_attempt += 1
                        break
                # reply received, increment to next frame
                else:
                    # bad frame
                    if reply.decode("utf-8") == "bad frame":
                        self.current_failed_attempt +=1
                        self.retries += 1
                        break
                    # remove the replied frame from buffer
                    try:
                        self._remove_from_from_buffer(self.current_index_read)
                    except:
                        self.lingering_files.append(self.current_index_read)
                    # increment to next frame
                    self.current_index_read += 1
                    self.current_failed_attempt = 0
                    break
                    
        self.reset()

    def _get_frame_buffer_path(self, index: int):
        return self.buffer_path.joinpath(self.current_uid, f"{index}.bin")

    def _remove_from_from_buffer(self, index):
        frame_buffer_path = self._get_frame_buffer_path(index)
        frame_buffer_path.unlink()

    def _read_frame_buffer(self, index: int):
        frame_buffer_path = self._get_frame_buffer_path(index)
        # frame not yet written
        if not frame_buffer_path.exists():
            return None

        try:
            with open(frame_buffer_path, "rb") as f:
                data = f.read()

        # if matlab is still writing the file or not yet written
        except (PermissionError, FileNotFoundError):
            return None
        else:
            return data
