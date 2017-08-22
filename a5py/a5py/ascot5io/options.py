"""
Options IO.
"""
import h5py
import numpy as np
from . ascot5group import replacegroup, setgrouptype, setmetadata

def write_hdf5(fn,options):
    """
    Write options.

    Unlike most other "write" functions, this one takes dictionary
    as an argument. The dictionary should have exactly the same format
    as given by the "read" function in this module.

    TODO not compatible with new format

    Parameters
    ----------
    fn : str
        Full path to HDF5 file.
    options : dictionary
        Options to be written in dictionary format.
    """

    group = "options"
    path = "options/"
        
    f = h5py.File(fn, "a")

    replacegroup(f, path)
    setmetadata(f[path])
    
    # TODO Check that inputs are consistent.

    # Actual data.
    for opt in options:
        f.create_dataset(path + opt, data=options[opt])
    
    f.close()


def read_hdf5(fn):
    """
    Read options from HDF5 file.

    TODO Not compatible with new HDF5 format.

    Parameters
    ----------

    fn : str
        Full path to the HDF5 file.

    Returns
    -------

    Dictionary containing options.
    """
    
    path = "options"

    f = h5py.File(fn,"r")

    out = {}

    # Metadata.
    out["qid"]  = f[path].attrs["qid"]
    out["date"] = f[path].attrs["date"]

    # Actual data.
    for opt in f[path]:
        out[opt] = f[path][opt][:]

    f.close()

    return out
