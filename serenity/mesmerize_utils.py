import mesmerize_core


# additional columns that we use
ADD_COLUMNS = [
    "animal_id",
    "framerate",
    "date",
    "channel_index",
    "channel_name",
    "channel_color",
    "channel_genotype",
    "channel_indicator"
]


def load_batch(path, file_format="hdf"):
    """thin wrapper around mesmerize_core.load_batch"""
    return mesmerize_core.load_batch(path, file_format=file_format)


def create_batch(path, file_format="hdf"):
    return mesmerize_core.create_batch(path, file_format=file_format, add_columns=ADD_COLUMNS)
