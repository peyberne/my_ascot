"""
Orbit data IO module.

File: orbits.py
"""
import numpy as np
import h5py
import scipy.constants as constants

from a5py.ascot5io.ascot5data import AscotData
import a5py.marker.interpret as interpret
import a5py.marker as marker
import a5py.marker.plot as plot
from a5py.marker.alias import get as alias
from a5py.marker.endcond import Endcond

def read_hdf5(fn, qid):
    """
    Read orbit data from HDF5 file to dictionary.

    Args:
        fn : str <br>
            Full path to HDF5 file.
        qid : str <br>
            QID of the run whose orbit data is read.

    Returns:
        Dictionary storing the orbits that were read sorted by id and time.
    """

    with h5py.File(fn,"r") as f:
        orbits = f["/results/run-"+qid+"/orbits"]

        out = {}

        # Read data from file.
        for field in orbits:
            out[field]           = orbits[field][:]
            out[field + "_unit"] = orbits[field].attrs["unit"]

        # Find how many markers we have and their ids.
        N = (np.unique(orbits["id"][:])).size
        uniqueId = np.unique(orbits["id"][:])

        # Sort fields by id (major) and time (minor), both ascending.
        if N > 0:
            ind = np.lexsort((out["time"], out["id"]))
            for field in orbits:
                if field[-4:] != "unit":
                    out[field] = out[field][ind]

    return out


class Orbits(AscotData):
    """
    Object representing orbit data.
    """

    def __init__(self, hdf5, runnode):
        """
        Initialize orbit object from given HDF5 file to given RunNode.
        """
        self._runnode = runnode
        super().__init__(hdf5)


    def read(self):
        """
        Read orbit data to dictionary.
        """
        return read_hdf5(self._file, self.get_qid())


    def __getitem__(self, key):
        """
        Return queried quantity.

        The quantity is returned as a single numpy array ordered by id and time.
        Internally, this method first sees if the quantity can be read directly
        from HDF5. If not, then it tries to see if it is present in endstate and
        can be copied from there (e.g. mass). If not, then quantity is evaluated
        by first determining if the stored orbit type is field line (has no
        charge), guiding center (has magnetic moment), or particle.

        Args:
            key : str <br>
                Name of the quantity (see alias.py for a complete list).
        Returns:
            The quantity in SI units ordered by id and time.
        """
        with self as h5:

            key  = alias(key)
            item = None

            # See if the field can be read directly and without conversions
            h5keys = list(h5.keys())
            h5keys_cleaned = [alias(x) for x in h5keys]
            for i in range(len(h5keys)):
                if h5keys_cleaned[i] == key:
                    item = h5[h5keys[i]][:]

                    # Unit conversions
                    if key == "charge":
                        f    = lambda x: interpret.charge_C(x)
                        item = np.array([f(x) for x in item]).ravel()
                    if key == "mu":
                        f    = lambda x: interpret.energy_J(x)
                        item = np.array([f(x) for x in item]).ravel()
                    if key == "phi":
                        item = item * np.pi/180
                    break

            # See if it is supposed to be read from inistate instead.
            if (item is None) and (key == "mass"):
                item = self._read_from_inistate("mass", h5)
                f    = lambda x: interpret.mass_kg(x)
                mass = np.array([f(x) for x in mass]).ravel()

            if (item is None) and ("mu" in h5keys):
                # HDF5 contains guiding center data
                mass = self._read_from_inistate("mass", h5)

                # Convert guiding-center quantities to SI units
                f      = lambda x: interpret.mass_kg(x)
                mass   = np.array([f(x) for x in mass]).ravel()
                f      = lambda x: interpret.charge_C(x)
                charge = np.array([f(x) for x in h5["charge"][:]]).ravel()
                f      = lambda x: interpret.energy_J(x)
                mu     = np.array([f(x) for x in h5["mu"][:]]).ravel()
                phi    = h5["phi"][:] * np.pi/180

                item = marker.eval_guidingcenter(
                    key, mass=mass, charge=charge,
                    R=h5["R"][:], phi=phi, z=h5["z"][:],
                    mu=mu, vpar=h5["vpar"][:],
                    theta=h5["theta"][:],
                    BR=h5["B_R"][:], Bphi=h5["B_phi"][:],
                    Bz=h5["B_z"][:])

            if (item is None) and ("charge" in h5keys):
                # HDF5 contains particle data
                mass = self._read_from_inistate("mass", h5)

                # Convert particle quantities to SI units
                f      = lambda x: interpret.mass_kg(x)
                mass   = np.array([f(x) for x in mass]).ravel()
                f      = lambda x: interpret.charge_C(x)
                charge = np.array([f(x) for x in h5["charge"][:]]).ravel()
                phi    = h5["phi"][:] * np.pi/180

                item = marker.eval_particle(
                    key, mass=mass, charge=charge,
                    R=h5["R"][:], phi=phi, z=h5["z"][:],
                    vR=h5["v_R"][:], vphi=h5["v_phi"][:], vz=h5["v_z"][:],
                    BR=h5["B_R"][:], Bphi=h5["B_phi"][:], Bz=h5["B_z"][:])

            if item is None:
                # HDF5 contains field line data

                # Convert particle quantities to SI units
                phi    = h5["phi"][:] * np.pi/180

                # All physical field-line quantities can be get like this.
                item = marker.eval_particle(key, R=h5["R"][:], phi=phi,
                                            z=h5["z"][:], BR=h5["B_R"][:],
                                            Bphi=h5["B_phi"][:],
                                            Bz=h5["B_z"][:])

            # Order by id and time
            ids  = h5["id"][:]
            time = h5["time"][:]
            idx  = np.lexsort((time, ids))

            return item[idx]


    def get(self, key, ids=None, endcond=None, SI=True):
        """
        Same as __getitem__ but with option to filter which points are returned.

        Args:
            key : str <br>
                Name of the quantity (see alias.py for a complete list).
            ids : int, array_like, optional <br>
                Id or a list of ids whose data points are returned.
            endcond : str, array_like, optional <br>
                Endcond or a list of endconds. Only data points of those markers
                whose simulation terminated with the given end conditions are
                returned.
        Returns:
            The quantity in SI units.
        """
        val = self[key]

        if endcond is not None:
            with self as h5:
                ec = self._read_from_endstate("endcond", h5)
                er = self._read_from_endstate("errormsg", h5)

            endcondlist = [Endcond(ec[i], er[i]) for i in range(ec.size)]

            idx = np.zeros(val.shape, dtype=bool)
            for i in range(idx.size):
                idx[i] = endcondlist[i] == endcond

            val = val[idx]

        if not SI:
            key = alias(key)

            if key in ["energy", "mu"]:
                f      = lambda x: interpret.energy_eV(x)
                val   = np.array([f(x) for x in val]).ravel()

            if key in ["phi", "phimod"]:
                val = val*180/np.pi

            if key in ["mass"]:
                f      = lambda x: interpret.mass_amu(x)
                val   = np.array([f(x) for x in val]).ravel()

            if key in ["charge"]:
                f      = lambda x: interpret.charge_e(x)
                val   = np.array([f(x) for x in val]).ravel()

        return val


    def plot(self, x=None, y=None, z=None, endcond=None, equal=False,
             log=False, axes=None):
        """
        Plot orbits as a continuous line.
        """
        ids = self.get("id", endcond=endcond)

        xc = np.linspace(0, ids.size, ids.size)
        if x is not None:
            xc = self.get(x, endcond=endcond, SI=False)

        yc = None
        if y is not None:
            yc = self.get(y, endcond=endcond, SI=False)

        zc = None
        if z is not None:
            zc = self.get(z, endcond=endcond, SI=False)

        if isinstance(log, tuple):
            if log[0]:
                xc = np.log10(np.absolute(xc))
            if log[1]:
                yc = np.log10(np.absolute(yc))
            if z is not None and log[2]:
                zc = np.log10(np.absolute(zc))
        elif log:
            xc = np.log10(np.absolute(xc))
            yc = np.log10(np.absolute(yc))
            if z is not None:
                zc = np.log10(np.absolute(zc))

        plot.plot_line(x=xc, y=yc, z=zc, ids=ids, equal=equal,
                       xlabel=x, ylabel=y, zlabel=z, axes=axes)


    def poincare(self, pncrids=None, subplots=False, **kwargs):
        """
        Make Poincare plot.

        Args:
            pncrids : int, array_like, optional <br>
                Id or list of ids for which poincare plot is constructed.
            subplots : bool, optional <br>
                Plot poincares in subplots insted of plotting them to axis or
                new figure.
            **kwargs : dict_like <br>
                All arguments accepted by plot().
        """
        pass


    def _read_from_inistate(self, key, h5):
        isval = self._runnode.inistate[key]
        isid  = self._runnode.inistate["id"]
        f     = lambda x: isval[isid == x]
        return np.array([f(x) for x in h5["id"][:]])

    def _read_from_endstate(self, key, h5):
        esval = self._runnode.endstate[key]
        esid  = self._runnode.endstate["id"]
        f     = lambda x: esval[esid == x]
        return np.array([f(x) for x in h5["id"][:]])
