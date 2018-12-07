"""
Non-axisymmetric tokamak magnetic field HDF5 IO

File: E_3D.py
"""
import numpy as np
import h5py
import random
import datetime

from . ascot5file import add_group

def write_hdf5(fn, Rmin, Rmax, nR, zmin, zmax, nz, phimin, phimax, nphi,
               E_R, E_phi, E_z):
    """
    Write 3D electric field input in HDF5 file for trilinear interpolation.

    TODO Not compatible with new HDF5 format.

    Parameters
    ----------

    fn : str
        Full path to the HDF5 file.
    Rlim, Rmax, phimin, phimax, zmin, zmax : real
        Edges of the uniform Rphiz-grid.
    nR, nphi, nz : int
        Number of Rphiz-grid points.
    E_R, E_phi, E_z : real R x phi x z numpy array
        Electric field components in Rphiz-grid.

    Notes
    -------

    Rphiz coordinates form a right-handed cylindrical coordinates.
    phi is in degrees and is considered as a periodic coordinate.
    phimin is where the period begins and phimax is the last data point,
    i.e. not the end of period. E.g if you have a n = 2 symmetric system
    with nphi = 180 deg and phimin = 0 deg, then phimax should be 179 deg.

    """

    parent = "efield"
    group    = "E_3D"

    # Create a group for this input.
    with h5py.File(fn, "a") as f:
        path = add_group(f, parent, group)

        # Transpose grids
        E_R = np.transpose(E_R,(1,0,2))
        E_phi = np.transpose(E_phi,(1,0,2))
        E_z = np.transpose(E_z,(1,0,2))

        # TODO Check that inputs are consistent.

        # Actual data.
        f.create_dataset(path + "/R_min", (1,), data=Rmin, dtype="f8")
        f.create_dataset(path + "/R_max", (1,), data=Rmax, dtype="f8")
        f.create_dataset(path + "/n_R", (1,),   data=nR, dtype="i8")

        f.create_dataset(path + "/phi_min", (1,), data=phimin, dtype="f8")
        f.create_dataset(path + "/phi_max", (1,), data=phimax, dtype="f8")
        f.create_dataset(path + "/n_phi", (1,),   data=nphi, dtype="i8")

        f.create_dataset(path + "/z_min", (1,), data=zmin, dtype="f8")
        f.create_dataset(path + "/z_max", (1,), data=zmax, dtype="f8")
        f.create_dataset(path + "/n_z", (1,),   data=nz, dtype="i8")

        f.create_dataset(path + "/E_R",   data=E_R,   dtype="f8")
        f.create_dataset(path + "/E_phi", data=E_phi, dtype="f8")
        f.create_dataset(path + "/E_z",   data=E_z,   dtype="f8")


def read_hdf5(fn,qid):
    """
    Read 3D electric field input from HDF5 file.

    Parameters
    ----------

    fn : str
        Full path to the HDF5 file.
    qid : str
        qid of the bfield to be read.


    Returns
    -------

    Dictionary containing magnetic field data.
    """

    path = "efield" + "/E_3D-" + qid

    with h5py.File(fn,"r") as f:
        out = {}

        # Metadata.
        out["qid"] = qid
        out["date"] = f[path].attrs["date"]
        out["description"] = f[path].attrs["description"]

        # Actual data.
        out["R_min"] = f[path]["R_min"][:]
        out["R_max"] = f[path]["R_max"][:]
        out["n_R"]   = f[path]["n_R"][:]

        out["phi_min"] = f[path]["phi_min"][:]
        out["phi_max"] = f[path]["phi_max"][:]
        out["n_phi"]   = f[path]["n_phi"][:]

        out["z_min"] = f[path]["z_min"][:]
        out["z_max"] = f[path]["z_max"][:]
        out["n_z"]   = f[path]["n_z"][:]

        out["E_R"]   = f[path]["E_R"][:]
        out["E_phi"] = f[path]["E_phi"][:]
        out["E_z"]   = f[path]["E_z"][:]

    return out
