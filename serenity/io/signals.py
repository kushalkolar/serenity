# can test both initialization and registration at same time
INIT_START_SIGNAL = b"initstart"

# start of an actual recording after initialization is complete
RECORD_START_SIGNAL = b"recordstart"

# resets states of all actors, use after either initialization or recording ended
ACQ_END_SIGNAL = b"acqend"

# TODO: have a visual alignment thing to visualize previous session means and current session live/rolling mean?