"""Module for verifying that ASCOT5 can model the physics it claims.

Implemented tests:

  - elementary: verify that ASCOT5 reproduces correct gyromotion and drifts
    in a simple electromagnetic field.
  - orbitfollowing: verify the conservation properties of orbit-integrators.
  - gctransform: verify the guiding center transformation implementation.
  - ccoll: verify the Coulomb collision operator.
  - classical: verify that ASCOT5 reproduces classical transport correctly.
  - neoclassical: verify that ASCOT5 reproduces the neoclassical transport
    correctly
  - boozer: verify Boozer coordinate transformation.
  - mhd: verify inclusion of MHD modes.
  - atomic: verify implementation of ionization and neutralization reactions.
"""
import copy
import unyt
import subprocess
import warnings
import numpy as np
import matplotlib.pyplot as plt

from matplotlib.gridspec import GridSpec

from a5py import Ascot, physlib
from a5py.routines import plotting as a5plt
from a5py.ascot5io.options import Opt
from a5py.ascot5io.marker import Marker
from a5py.ascot5io.bfield import B_2DS

class PhysTest():

    tag_elementary_gyro    = "TESTELEMENTARYGYRO"
    tag_elementary_exbgo   = "TESTELEMENTARYEXBGO"
    tag_elementary_exbgc   = "TESTELEMENTARYEXBGC"
    tag_elementary_gradbgo = "TESTELEMENTARYGRADBGO"
    tag_elementary_gradbgc = "TESTELEMENTARYGRADBGC"
    tag_orbfol_go          = "TESTORBFOLGO"
    tag_orbfol_gcf         = "TESTORBFOLGCF"
    tag_orbfol_gca         = "TESTORBFOLGCA"
    tag_gctransform_go     = "TESTGCTRANSFORMGO"
    tag_gctransform_gc     = "TESTGCTRANSFORMGC"
    tag_gctransform_go2gc  = "TESTGCTRANSFORMGO2GC"
    tag_gctransform_zeroth = "TESTGCTRANSFORMZEROTH"
    tag_gctransform_first  = "TESTGCTRANSFORMFIRST"
    tag_ccoll_thermalgo    = "TESTCCOLLTHERMALGO"
    tag_ccoll_thermalgcf   = "TESTCCOLLTHERMALGCF"
    tag_ccoll_thermalgca   = "TESTCCOLLTHERMALGCA"
    tag_ccoll_slowinggo    = "TESTCCOLLSLOWINGGO"
    tag_ccoll_slowinggcf   = "TESTCCOLLSLOWINGGCF"
    tag_ccoll_slowinggca   = "TESTCCOLLSLOWINGGCA"
    tag_classical_go       = "TESTCLASSGO"
    tag_classical_gcf      = "TESTCLASSGCF"
    tag_classical_gca      = "TESTCLASSGCA"
    tag_neoclassical_go    = "TESTNEOCLASSGO"
    tag_neoclassical_gcf   = "TESTNEOCLASSGCF"
    tag_neoclassical_gca   = "TESTNEOCLASSGCA"
    tag_boozer             = "TESTBOOZER"
    tag_mhd_go             = "TESTMHDGO"
    tag_mhd_gcf            = "TESTMHDGCF"
    tag_mhd_gca            = "TESTMHDGCA"
    tag_atomic_cx          = "TESTATOMICCX"
    tag_atomic_ionz        = "TESTATOMICIONZ"

    def __init__(self, fn="testascot.h5"):
        try:
            self.ascot = Ascot(fn)
        except FileNotFoundError:
            self.ascot = Ascot(fn, create=True)
            init = self.ascot.data.create_input
            init("opt")
            init("gc")
            init("B_TC")
            init("E_TC")
            init("wall_2D")
            init("plasma_1D")
            init("N0_1D")
            init("Boozer")
            init("MHD_STAT")
            init("asigma_loc")

    def execute(self, init=True, run=True, check=True, tests=None):
        """Execute test(s).

        Parameters
        ----------
        """
        if tests is None:
            tests = ["elementary", "orbitfollowing", "gctransform", "ccoll",
                     "classical", "neoclassical", "boozer", "mhd", "atomic"]
        elif isinstance(tests, str):
            tests = [tests]

        for test in tests:
            if init:
                getattr(self, "init_" + test)()
                print("Test %s initialized" % test)
            if run:
                getattr(self, "run_" + test)()
                print("Test %s simulation complete" % test)
            if check:
                a5plt.setpaperstyle()
                getattr(self, "check_" + test)()
                print("Test %s check finished" % test)

    def init_elementary(self):
        """Initialize data for the elementary test.

        This test covers elementary results such as the gyromotion and drifts by
        verifying that ASCOT5 reproduces:

        1. correct gyroradius and gyrofrequency in an uniform magnetic field.
        2. correct E X B drift in uniform electromagnetic field.
        3. correct gradB drift in a magnetic field with constant gradient.

        Test 1 is done with GO mode and 2 and 3 with both GO and GC modes,
        latter using the fixed step scheme. Tests are done in Cartesian
        electromagnetic field (B_TC and E_TC) and without collisions.
        The test particles are an energetic electron and a positron so
        the tests also verify that ASCOT5 is valid in the relativistic regime.
        """
        if hasattr(self.ascot.data.options, PhysTest.tag_elementary_gyro):
            warnings.warn("Inputs already present: Test elementary")
            return
        init = self.ascot.data.create_input

        # Options
        opt = Opt.get_default()
        opt.update({
            "SIM_MODE" : 1, "FIXEDSTEP_USE_USERDEFINED" : 1,
            "FIXEDSTEP_USERDEFINED" : 1e-11, "ENDCOND_SIMTIMELIM" : 1,
            "ENDCOND_LIM_SIMTIME" : 2e-9, "ENABLE_ORBIT_FOLLOWING" : 1,
            "ENABLE_ORBITWRITE" : 1, "ORBITWRITE_MODE" : 1,
            "ORBITWRITE_INTERVAL" : 1e-11, "ORBITWRITE_NPOINT" : 202
        })
        init("opt", **opt, desc=PhysTest.tag_elementary_gyro)
        opt.update({
            "FIXEDSTEP_USERDEFINED" : 1e-10, "ENDCOND_LIM_SIMTIME" : 1e-7,
            "ORBITWRITE_NPOINT" : 10002
        })
        init("opt", **opt, desc=PhysTest.tag_elementary_exbgo)
        init("opt", **opt, desc=PhysTest.tag_elementary_gradbgo)
        opt.update({
            "SIM_MODE" : 2, "FIXEDSTEP_USERDEFINED" : 1e-9,
            "ORBITWRITE_INTERVAL" : 1e-9, "ORBITWRITE_NPOINT" : 102
        })
        init("opt", **opt, desc=PhysTest.tag_elementary_exbgc)
        init("opt", **opt, desc=PhysTest.tag_elementary_gradbgc)

        # Magnetic field
        d = {"bxyz" : np.array([5, 0, 0]),
             "jacobian" : np.array([0,0,0,0,0,0,0,0,0]),
             "rhoval" : 1.5}
        init("B_TC", **d, desc=PhysTest.tag_elementary_gyro)
        init("B_TC", **d, desc=PhysTest.tag_elementary_exbgo)
        init("B_TC", **d, desc=PhysTest.tag_elementary_exbgc)

        d.update({"jacobian" : np.array([0,0,0.1,0,0,0,0,0,0])})
        init("B_TC", **d, desc=PhysTest.tag_elementary_gradbgo)
        init("B_TC", **d, desc=PhysTest.tag_elementary_gradbgc)

        # Electric field
        d = {"exyz" : np.array([0, 0, 0])}
        init("E_TC", **d, desc=PhysTest.tag_elementary_gyro)
        init("E_TC", **d, desc=PhysTest.tag_elementary_gradbgo)
        init("E_TC", **d, desc=PhysTest.tag_elementary_gradbgc)

        d.update({"exyz" : np.array([0, 1e6, 0])})
        init("E_TC", **d, desc=PhysTest.tag_elementary_exbgo)
        init("E_TC", **d, desc=PhysTest.tag_elementary_exbgc)

        # Marker input is an electron and positron
        mrk = Marker.generate("gc", n=2, species="electron")
        mrk["charge"]    = np.array([1, -1])
        mrk["r"][:]      = 5
        mrk["phi"][:]    = 90
        mrk["z"][:]      = 0
        mrk["zeta"][:]   = 0
        mrk["energy"][:] = 100e6
        mrk["pitch"][:]  = 0.5

        for tag in [PhysTest.tag_elementary_gyro,
                    PhysTest.tag_elementary_exbgo,
                    PhysTest.tag_elementary_exbgc,
                    PhysTest.tag_elementary_gradbgo,
                    PhysTest.tag_elementary_gradbgc]:
            init("gc", **mrk, desc=tag)

    def run_elementary(self):
        """Run elementary test.
        """
        if hasattr(self.ascot.data, PhysTest.tag_elementary_gyro):
            warnings.warn("Results already present: Test elementary")
            return
        for tag in [PhysTest.tag_elementary_gyro,
                    PhysTest.tag_elementary_exbgo,
                    PhysTest.tag_elementary_exbgc,
                    PhysTest.tag_elementary_gradbgo,
                    PhysTest.tag_elementary_gradbgc]:
            self._activateinputs(tag)
            self._runascot(tag)

    def check_elementary(self):
        """Verify and plot elementary test results.

        Returns
        -------
        passed : bool
            True if the test passed.
        """
        run_gyro    = self.ascot.data[PhysTest.tag_elementary_gyro]
        run_exbgo   = self.ascot.data[PhysTest.tag_elementary_exbgo]
        run_exbgc   = self.ascot.data[PhysTest.tag_elementary_exbgc]
        run_gradbgo = self.ascot.data[PhysTest.tag_elementary_gradbgo]
        run_gradbgc = self.ascot.data[PhysTest.tag_elementary_gradbgc]

        # Initialize plots
        fig = a5plt.figuredoublecolumn()
        gs = GridSpec(2, 3, figure=fig)
        h1a = fig.add_subplot(gs[0,0])
        h2a = fig.add_subplot(gs[0,1])
        h2b = fig.add_subplot(gs[1,1])
        h3a = fig.add_subplot(gs[0,2])
        h3b = fig.add_subplot(gs[1,2])

        h1a.set_title("Gyro-motion")
        h2a.set_title("ExB drift")
        h3a.set_title("Grad-B drift")

        h1a.set_ylabel("z [m]")
        h1a.set_xlabel("y [m]")

        h1a.set_aspect("equal", adjustable="box")
        h2a.set_aspect("equal", adjustable="box")
        h2b.set_aspect("equal", adjustable="box")
        h3a.set_aspect("equal", adjustable="box")
        h3b.set_aspect("equal", adjustable="box")

        def plotarrow(ax, ini, end, txt):
            """Plot line with an arrow
            """
            ax.annotate("", xytext=ini, xy=end,
                        arrowprops={"arrowstyle":"->", "color":"black"})
            ax.plot([ini[0], end[0]], [ini[1], end[1]], color="black")
            ax.annotate(txt, ini + .005)

        ## Gyro test ##
        m, q, pitch, ekin, x0, y0 = \
            run_gyro.getstate("mass", "charge", "pitch", "ekin", "y", "z")
        x, y, time = run_gyro.getorbit("y", "z", "time", ids=1)

        # Analytical values
        bnorm = np.sqrt(np.sum(run_gyro.bfield.read()["bxyz"]**2)) * unyt.T
        larmorrad_ana = physlib.gyrolength(m, q, ekin, pitch, bnorm).to("m")
        gyrofreq_ana  = physlib.gyrofrequency(m, q, ekin, bnorm).to("rad/s")

        # Numerical values
        larmorrad_go = np.mean( np.sqrt( (x - x0[0])**2 + (y - y0[0])**2 ) )
        gyrofreq_go  = np.sum( np.sqrt( np.diff(x)**2 + np.diff(y)**2 ) ) \
            * unyt.rad / (larmorrad_go * time[-1])

        # Plot
        orbx = x - x0[0]
        orby = y - y0[0]

        anax   = larmorrad_ana[0] * np.sin(np.linspace(0, 2*np.pi, 360))
        anay   = larmorrad_ana[0] * np.cos(np.linspace(0, 2*np.pi, 360))
        fangle = np.arctan2(orby[0], orbx[0]) * unyt.rad \
            + gyrofreq_ana[0] * time[-1]
        fx = larmorrad_ana[0] * np.cos(-fangle) # Minus sign because this we are
        fy = larmorrad_ana[0] * np.sin(-fangle) # in LHS coordinate system.

        h1a.plot(orbx, orby, linewidth=3)
        h1a.plot(anax, anay, linestyle="--", color="black", alpha=0.7)
        h1a.scatter(orbx[-1], orby[-1], marker="o", color="C0", zorder=3)
        h1a.scatter(fx, fy, marker="x", color="black", zorder=4)

        ## E x B drift
        yi_go            = run_exbgo.getstate("z", state="ini")
        yf_go, deltat_go = run_exbgo.getstate("z", "mileage", state="end")
        x_go1, y_go1     = run_exbgo.getorbit("y", "z", ids=1)
        x_go2, y_go2     = run_exbgo.getorbit("y", "z", ids=2)

        yi_gc            = run_exbgc.getstate("z", state="ini")
        yf_gc, deltat_gc = run_exbgc.getstate("z", "mileage", state="end")
        x_gc1, y_gc1     = run_exbgc.getorbit("y", "z", ids=1)
        x_gc2, y_gc2     = run_exbgc.getorbit("y", "z", ids=2)

        # Analytical values
        bvec  = run_exbgo.bfield.read()["bxyz"].ravel()
        evec  = run_exbgo.efield.read()["exyz"].ravel()
        v_ExB = np.cross(evec, bvec) / np.inner(bvec, bvec) * unyt.m / unyt.s
        time  = run_exbgo.options.read()["ENDCOND_LIM_SIMTIME"] * unyt.s

        # Numerical values
        vgo_ExB = (yf_go - yi_go) / deltat_go
        vgc_ExB = (yf_gc - yi_gc) / deltat_gc

        # Plot
        h2a.plot(x_go1, y_go1)
        h2b.plot(x_go2, y_go2)
        h2a.plot(x_gc1, y_gc1)
        h2b.plot(x_gc2, y_gc2)

        ini = np.array([x_gc1[0].v + .01, y_gc1[0].v])
        end = np.array([x_gc1[0].v + .01, (y_gc1[0] + v_ExB[2]*deltat_gc[1]).v])
        plotarrow(h2a, ini, end, r"$e^+$")
        ini = np.array([x_gc2[0].v + .01, y_gc2[0].v])
        end = np.array([x_gc2[0].v + .01, (y_gc2[0] + v_ExB[2]*deltat_gc[0]).v])
        plotarrow(h2b, ini, end, r"$e^-$")

        ## gradB drift
        pitch, ekin, q, m = run_gradbgo.getstate(
            "pitch", "ekin", "charge", "mass", ids=1)
        xi_go            = run_gradbgo.getstate("y", state="ini")
        xf_go, deltat_go = run_gradbgo.getstate("y", "mileage", state="end")
        x_go1, y_go1     = run_gradbgo.getorbit("y", "z", ids=1)
        x_go2, y_go2     = run_gradbgo.getorbit("y", "z", ids=2)

        xi_gc            = run_gradbgc.getstate("y", state="ini")
        xf_gc, deltat_gc = run_gradbgc.getstate("y", "mileage", state="end")
        x_gc1, y_gc1     = run_gradbgc.getorbit("y", "z", ids=1)
        x_gc2, y_gc2     = run_gradbgc.getorbit("y", "z", ids=2)

        # Analytical values
        gamma   = physlib.gamma_energy(m, ekin)
        vnorm   = physlib.vnorm_gamma(gamma)
        bvec    = run_gradbgo.bfield.read()["bxyz"].ravel()
        gradb   = run_gradbgo.bfield.read()["jacobian"][0,:]
        bnorm   = np.sqrt(np.sum(bvec**2)) * unyt.T
        v_gradb = gamma * m * ( (1.0 - pitch**2) * vnorm**2 / ( q * bnorm ) ) \
            * 0.5 * np.cross(bvec, gradb) / bnorm**2 * unyt.T**2 / unyt.m
        v_gradb.convert_to_units("m/s")
        time    = run_gradbgo.options.read()["ENDCOND_LIM_SIMTIME"] * unyt.s

        # Numerical values
        vgo_gradb = (xf_go - xi_go) / deltat_go
        vgc_gradb = (xf_gc - xi_gc) / deltat_gc

        # Plot
        h3a.plot(x_go1, y_go1)
        h3b.plot(x_go2, y_go2)
        h3a.plot(x_gc1, y_gc1)
        h3b.plot(x_gc2, y_gc2)

        ini = np.array([x_gc1[0].v, y_gc1[0].v + .01])
        end = np.array([x_gc1[0] + v_gradb[1]*deltat_gc[0], y_gc1[0].v + .01])
        plotarrow(h3a, ini, end, r"$e^+$")
        ini = np.array([x_gc2[0].v, y_gc2[0] + .01])
        end = np.array([x_gc2[0] - v_gradb[1]*deltat_gc[0], y_gc2[0].v + .01])
        plotarrow(h3b, ini, end, r"$e^-$")

        print("Test elementary:")
        passed = True

        print("  Gyroradius %e, Gyrofrequency %e (gyro-orbit)" \
              % (larmorrad_go, gyrofreq_go))
        err = np.abs(larmorrad_go - larmorrad_ana[0]) / larmorrad_ana[0]
        if err > 5e-8: print("Error: %e (FAILED)" % err); passed = False

        print("  Gyroradius %e, Gyrofrequency %e (expected)" \
              % (larmorrad_ana[0], gyrofreq_ana[0]))
        err = np.abs(gyrofreq_go - gyrofreq_ana[0]) / gyrofreq_ana[0]
        if err > 5e-4: print("Error: %e (FAILED)" % err); passed = False

        print("  ExB drift for positrons %e electrons %e (gyro-orbit)" \
              % (vgo_ExB[0], vgo_ExB[1]) )
        print("  ExB drift for positrons %e electrons %e (guiding center)" \
              % (vgc_ExB[0], vgc_ExB[1]) )
        print("  ExB drift for positrons %e electrons %e (expected)" \
              % (v_ExB[2], v_ExB[2]) )
        err = np.amax([np.abs( ( vgo_ExB[0] - v_ExB[2] ) / v_ExB[2] ),
                       np.abs( ( vgo_ExB[1] - v_ExB[2] ) / v_ExB[2] ),
                       np.abs( ( vgc_ExB[0] - v_ExB[2] ) / v_ExB[2] ),
                       np.abs( ( vgc_ExB[1] - v_ExB[2] ) / v_ExB[2] )])
        if err > 5e-5: print("Error: %e (FAILED)" % err); passed = False

        print("  Grad-B drift for positrons %e electrons %e (gyro-orbit)" \
              % (vgo_gradb[0], vgo_gradb[1]) )
        print("  Grad-B drift for positrons %e electrons %e (guiding center)" \
              % (vgc_gradb[0], vgc_gradb[1]) )
        print("  Grad-B drift for positrons %e electrons %e (expected)" \
              % (v_gradb[1], -v_gradb[1]) )
        err = np.amax([np.abs( ( vgo_gradb[0] - v_gradb[1] ) / v_gradb[1] ),
                       np.abs( ( vgo_gradb[1] + v_gradb[1] ) / v_gradb[1] ),
                       np.abs( ( vgc_gradb[0] - v_gradb[1] ) / v_gradb[1] ),
                       np.abs( ( vgc_gradb[1] + v_gradb[1] ) / v_gradb[1] )])
        if err > 1e-3: print("Error: %e (FAILED)" % err); passed = False

        return passed

    def init_orbitfollowing(self):
        """Initialize data for the  test.
        """
        if hasattr(self.ascot.data.options, PhysTest.tag_orbfol_go):
            warnings.warn("Inputs already present: Test orbit-following")
            return
        init = self.ascot.data.create_input

        # Options
        opt = Opt.get_default()
        opt.update({
            "SIM_MODE" : 1, "FIXEDSTEP_USE_USERDEFINED" : 1,
            "FIXEDSTEP_USERDEFINED" : 1e-12, "ENDCOND_SIMTIMELIM" : 1,
            "ENDCOND_LIM_SIMTIME" : 5e-6, "ENABLE_ORBIT_FOLLOWING" : 1,
            "ENABLE_ORBITWRITE" : 1, "ORBITWRITE_MODE" : 1,
            "ORBITWRITE_INTERVAL" : 1e-10, "ORBITWRITE_NPOINT" : 50002
        })
        init("opt", **opt, desc=PhysTest.tag_orbfol_go)
        opt.update({
            "SIM_MODE" : 2, "FIXEDSTEP_USERDEFINED" : 1e-12,
            "ENABLE_ADAPTIVE" : 0,
            "ORBITWRITE_INTERVAL" : 1e-8, "ORBITWRITE_NPOINT" : 502
        })
        init("opt", **opt, desc=PhysTest.tag_orbfol_gcf)
        opt.update({
            "ENABLE_ADAPTIVE" : 1, "ADAPTIVE_MAX_DRHO" : 0.1,
            "ADAPTIVE_MAX_DPHI" : 10, "ADAPTIVE_TOL_ORBIT" : 1e-10,
            "FIXEDSTEP_USERDEFINED" : 1e-8
        })
        init("opt", **opt, desc=PhysTest.tag_orbfol_gca)

        # Magnetic field is just some tokamak
        init("bfield_analytical_iter_circular", desc=PhysTest.tag_orbfol_go)
        init("bfield_analytical_iter_circular", desc=PhysTest.tag_orbfol_gcf)
        init("bfield_analytical_iter_circular", desc=PhysTest.tag_orbfol_gca)

        # Marker input is a trapped positron and a passing electron
        mrk = Marker.generate("gc", n=2, species="electron")
        mrk["charge"]    = np.array([1, -1])
        mrk["r"][:]      = 7.6
        mrk["phi"][:]    = 90
        mrk["z"][:]      = 0
        mrk["zeta"][:]   = 2
        mrk["energy"][:] = 10e6
        mrk["pitch"]     = np.array([0.4, 0.9])
        for tag in [PhysTest.tag_orbfol_go, PhysTest.tag_orbfol_gcf,
                    PhysTest.tag_orbfol_gca]:
            init("gc", **mrk, desc=tag)

    def run_orbitfollowing(self):
        """Run orbit-following test.
        """
        if hasattr(self.ascot.data, PhysTest.tag_orbfol_go):
            warnings.warn("Results already present: Test orbit-following")
            return
        for tag in [PhysTest.tag_orbfol_go, PhysTest.tag_orbfol_gcf,
                    PhysTest.tag_orbfol_gca]:
            self._activateinputs(tag)
            self._runascot(tag)

    def check_orbitfollowing(self):
        """Check test.
        """
        run_go  = self.ascot.data[PhysTest.tag_orbfol_go]
        run_gcf = self.ascot.data[PhysTest.tag_orbfol_gcf]
        run_gca = self.ascot.data[PhysTest.tag_orbfol_gca]

        # Initialize plots
        fig = a5plt.figuredoublecolumn(3/2)
        gs = GridSpec(3, 4, figure=fig)
        h1a = fig.add_subplot(gs[0,0])
        h2a = fig.add_subplot(gs[1,0])
        h3a = fig.add_subplot(gs[2,0])
        h4a = fig.add_subplot(gs[:,1])
        h1b = fig.add_subplot(gs[0,2])
        h2b = fig.add_subplot(gs[1,2])
        h3b = fig.add_subplot(gs[2,2])
        h4b = fig.add_subplot(gs[:,3])

        h4a.set_aspect("equal", adjustable="box")
        h4b.set_aspect("equal", adjustable="box")

        h1a.set_xlim(0, 5)
        h2a.set_xlim(0, 5)
        h3a.set_xlim(0, 5)
        h1b.set_xlim(0, 5)
        h2b.set_xlim(0, 5)
        h3b.set_xlim(0, 5)

        h4a.set_xlim(5, 8)
        h4a.set_ylim(-2, 2)
        h4b.set_xlim(5, 8)
        h4b.set_ylim(-2, 2)

        h1a.set_xticklabels([])
        h2a.set_xticklabels([])
        h1b.set_xticklabels([])
        h2b.set_xticklabels([])

        h4a.set_yticklabels([])
        h4b.set_xlabel("R [m]")
        h4b.set_ylabel("z [m]")
        h4b.yaxis.set_label_position("right")
        h4b.yaxis.tick_right()

        h1a.set_ylabel(r"$(E-E_0)/E_0$")
        h2a.set_ylabel(r"$(\mu-\mu_0)/\mu_0$")
        h3a.set_ylabel(r"$(P-P_0)/P_0$")

        h3a.set_xlabel("Time [µs]")
        h3b.set_xlabel("Time [µs]")

        def plotreldiff(ax1, ax2, ax3, t, q1, q2, q3, **kwargs):
            """Plot relative diffenrence of given quantities on given axes.
            """
            ax1.plot(t, ( q1 - q1[0] ) / q1[0], **kwargs)
            ax2.plot(t, ( q2 - q2[0] ) / q2[0], **kwargs)
            ax3.plot(t, ( q3 - q3[0] ) / q3[0], **kwargs)

        def fails(t, q, eps, qnt, otype, mode):
            """Check if the change in time of a given quantity is below given
            tolerance
            """
            err = np.polyfit(t, (q - q[0]) / q[0], 1)[0]
            msg = "Rate of change in %6s (%s/%11s): %e Tolerance: %e" \
                % (qnt, otype, mode, err, eps)
            if err > eps:
                msg += " (FAILED)"
                print(msg)
                return False
            print(msg)
            return True

        # Numerical values
        self.ascot.input_init(run=run_go.get_qid(), bfield=True)
        tgo1, ego1, mugo1, pgo1, rgo1, zgo1 = run_go.getorbit(
            "mileage", "ekin", "mu", "ptor", "r", "z", ids=1)
        tgo2, ego2, mugo2, pgo2, rgo2, zgo2 = run_go.getorbit(
            "mileage", "ekin", "mu", "ptor", "r", "z", ids=2)
        tgcf1, egcf1, mugcf1, pgcf1, rgcf1, zgcf1 = run_gcf.getorbit(
            "mileage", "ekin", "mu", "ptor", "r", "z", ids=1)
        tgcf2, egcf2, mugcf2, pgcf2, rgcf2, zgcf2 = run_gcf.getorbit(
            "mileage", "ekin", "mu", "ptor", "r", "z", ids=2)
        tgca1, egca1, mugca1, pgca1, rgca1, zgca1 = run_gca.getorbit(
            "mileage", "ekin", "mu", "ptor", "r", "z", ids=1)
        tgca2, egca2, mugca2, pgca2, rgca2, zgca2 = run_gca.getorbit(
            "mileage", "ekin", "mu", "ptor", "r", "z", ids=2)
        self.ascot.input_free()

        # Plot
        plotreldiff(h1a, h2a, h3a, tgo1.to("µs"),  ego1,  mugo1,  pgo1,
                    color="C0")
        plotreldiff(h1b, h2b, h3b, tgo2.to("µs"),  ego2,  mugo2,  pgo2,
                    color="C0")
        plotreldiff(h1a, h2a, h3a, tgcf1.to("µs"), egcf1, mugcf1, pgcf1,
                    color="C1")
        plotreldiff(h1b, h2b, h3b, tgcf2.to("µs"), egcf2, mugcf2, pgcf2,
                    color="C1")
        plotreldiff(h1a, h2a, h3a, tgca1.to("µs"), egca1, mugca1, pgca1,
                    color="C2")
        plotreldiff(h1b, h2b, h3b, tgca2.to("µs"), egca2, mugca2, pgca2,
                    color="C2")

        h4a.plot(rgo1,  zgo1,  color="C0")
        h4a.plot(rgcf1, zgcf1, color="C1")
        h4a.plot(rgca1, zgca1, color="C2")
        h4b.plot(rgo2,  zgo2,  color="C0")
        h4b.plot(rgcf2, zgcf2, color="C1")
        h4b.plot(rgca2, zgca2, color="C2")

        print("Test orbit-following:")
        passed = True

        otype1 = "passing"; otype2 = "trapped"
        simmode1 = "gyro-orbit"; simmode2 = "fixed GC"; simmode3 = "adaptive GC"
        if fails(tgo1,  ego1,   5e-6, "energy", otype1, simmode1):passed = False
        if fails(tgo2,  ego2,   5e-6, "energy", otype2, simmode1):passed = False
        if fails(tgcf1, egcf1,  5e-3, "energy", otype1, simmode2):passed = False
        if fails(tgcf2, egcf2,  5e-5, "energy", otype2, simmode2):passed = False
        if fails(tgca1, egca1,  5e-3, "energy", otype1, simmode3):passed = False
        if fails(tgca2, egca2,  5e-5, "energy", otype2, simmode3):passed = False
        if fails(tgo1,  mugo1,  2e2,  "mu",     otype1, simmode1):passed = False
        if fails(tgo2,  mugo2,  1e-1, "mu",     otype2, simmode1):passed = False
        if fails(tgcf1, mugcf1, 1e-9, "mu",     otype1, simmode2):passed = False
        if fails(tgcf2, mugcf2, 1e-9, "mu",     otype2, simmode2):passed = False
        if fails(tgca1, mugca1, 1e-9, "mu",     otype1, simmode3):passed = False
        if fails(tgca2, mugca2, 1e-9, "mu",     otype2, simmode3):passed = False
        if fails(tgo1,  pgo1,   5e-3, "Ptor",   otype1, simmode1):passed = False
        if fails(tgo2,  pgo2,   5e-5, "Ptor",   otype2, simmode1):passed = False
        if fails(tgcf1, pgcf1,  5e-2, "Ptor",   otype1, simmode2):passed = False
        if fails(tgcf2, pgcf2,  5e-2, "Ptor",   otype2, simmode2):passed = False
        if fails(tgca1, pgca1,  5e-2, "Ptor",   otype1, simmode3):passed = False
        if fails(tgca2, pgca2,  5e-2, "Ptor",   otype2, simmode3):passed = False

        return passed

    def init_gctransform(self):
        """Initialize data for the guiding-center transformation test.
        """
        if hasattr(self.ascot.data.options, PhysTest.tag_gctransform_go):
            warnings.warn("Inputs already present: Test GC transform")
            return
        init = self.ascot.data.create_input

        # Options
        opt = Opt.get_default()
        opt.update({
            "SIM_MODE" : 2, "FIXEDSTEP_USE_USERDEFINED" : 1,
            "FIXEDSTEP_USERDEFINED" : 1e-10, "ENDCOND_SIMTIMELIM" : 1,
            "ENDCOND_LIM_SIMTIME" : 3e-5, "ENABLE_ORBIT_FOLLOWING" : 1,
            "ENABLE_ORBITWRITE" : 1, "ORBITWRITE_MODE" : 1,
            "ORBITWRITE_INTERVAL" : 4e-10, "ORBITWRITE_NPOINT" : 75002
        })
        init("opt", **opt, desc=PhysTest.tag_gctransform_gc)
        init("opt", **opt, desc=PhysTest.tag_gctransform_first)
        opt.update({"DISABLE_FIRSTORDER_GCTRANS" : 1})
        init("opt", **opt, desc=PhysTest.tag_gctransform_zeroth)

        opt.update({"DISABLE_FIRSTORDER_GCTRANS" : 0, "SIM_MODE" : 1 })
        init("opt", **opt, desc=PhysTest.tag_gctransform_go)
        opt.update({"RECORD_MODE" : 1 })
        init("opt", **opt, desc=PhysTest.tag_gctransform_go2gc)

        # Magnetic field is just some tokamak
        init("bfield_analytical_iter_circular",
             desc=PhysTest.tag_gctransform_go)
        init("bfield_analytical_iter_circular",
             desc=PhysTest.tag_gctransform_gc)
        init("bfield_analytical_iter_circular",
             desc=PhysTest.tag_gctransform_go2gc)
        init("bfield_analytical_iter_circular",
             desc=PhysTest.tag_gctransform_zeroth)
        init("bfield_analytical_iter_circular",
             desc=PhysTest.tag_gctransform_first)

        # Use single alpha particle in tests
        mrk = Marker.generate("gc", n=1, species="alpha")
        mrk["r"][:]      = 7.6
        mrk["phi"][:]    = 90
        mrk["z"][:]      = 0
        mrk["zeta"][:]   = 2
        mrk["energy"][:] = 3.5e6
        mrk["pitch"][:]  = 0.4
        init("gc", **mrk, desc=PhysTest.tag_gctransform_go)
        init("gc", **mrk, desc=PhysTest.tag_gctransform_gc)
        init("gc", **mrk, desc=PhysTest.tag_gctransform_go2gc)

    def run_gctransform(self):
        """Run GC transform test.
        """
        init = self.ascot.data.create_input
        if hasattr(self.ascot.data, PhysTest.tag_gctransform_go):
            warnings.warn("Results already present: Test GC transform")
            return
        for tag in [PhysTest.tag_gctransform_go, PhysTest.tag_gctransform_gc,
                    PhysTest.tag_gctransform_go2gc]:
            self._activateinputs(tag)
            self._runascot(tag)

        # Create new marker input from results
        nrep = 10
        mrk = Marker.generate("prt", n=nrep, species="alpha")
        run = self.ascot.data[PhysTest.tag_gctransform_go]

        # Pick initial coordinates along the orbit trajectory
        dt   = 20
        idx = np.s_[:nrep*dt:dt]
        time, r, phi, z, vr, vphi, vz = \
            run.getorbit("time", "r", "phi", "z", "vr", "vphi", "vz")
        mrk.update({
            "time" : time[idx], "r" : r[idx], "phi" : phi[idx], "z" : z[idx],
            "vr" : vr[idx], "vphi" : vphi[idx], "vz" : vz[idx]
        })
        init("prt", **mrk, desc=PhysTest.tag_gctransform_zeroth)
        init("prt", **mrk, desc=PhysTest.tag_gctransform_first)

        for tag in [PhysTest.tag_gctransform_zeroth,
                    PhysTest.tag_gctransform_first]:
            self._activateinputs(tag)
            self._runascot(tag)

    def check_gctransform(self):
        """Check test.
        """
        run_go     = self.ascot.data[PhysTest.tag_gctransform_go]
        run_gc     = self.ascot.data[PhysTest.tag_gctransform_gc]
        run_go2gc  = self.ascot.data[PhysTest.tag_gctransform_go2gc]
        run_zeroth = self.ascot.data[PhysTest.tag_gctransform_zeroth]
        run_first  = self.ascot.data[PhysTest.tag_gctransform_first]

        # Initialize plots
        fig = a5plt.figuredoublecolumn(3/2)
        gs  = GridSpec(3, 3, figure=fig)
        h1a = fig.add_subplot(gs[0,0])
        h1b = fig.add_subplot(gs[1,0])
        h1c = fig.add_subplot(gs[2,0])
        h2  = fig.add_subplot(gs[:,1])
        h3  = fig.add_subplot(gs[:,2])

        h1a.set_xlim(0, 30)
        h1b.set_xlim(0, 30)
        h1c.set_xlim(0, 30)
        h1a.set_xticklabels([])
        h1b.set_xticklabels([])

        h2.set_xlim(6.2, 6.7)
        h2.set_ylim(1.0, 1.6)
        h2.set_aspect("equal", adjustable="box")
        h3.set_xlim(6.2, 6.7)
        h3.set_ylim(1.0, 1.6)
        h3.set_aspect("equal", adjustable="box")
        h3.set_yticklabels([])

        h1c.set_xlabel("Time [µs]")
        h1a.set_ylabel(r"$(E-E_0)/E_0$")
        h1b.set_ylabel(r"$(\mu-\mu_0)/\mu_0$")
        h1c.set_ylabel(r"$(P-P_0)/P_0$")
        h2.set_xlabel("R [m]")
        h2.set_ylabel("z [m]")

        # Get data and plot
        self.ascot.input_init(run=run_go.get_qid(), bfield=True)
        rgo, zgo, tgo, ego, mugo, pgo = run_go.getorbit(
            "r", "z", "mileage", "ekin", "mu", "ptor")
        rgc, zgc, tgc, egc, mugc, pgc = run_gc.getorbit(
            "r", "z", "mileage", "ekin", "mu", "ptor")
        rgo2gc, zgo2gc, tgo2gc, ego2gc, mugo2gc, pgo2gc = run_go2gc.getorbit(
            "r", "z", "mileage", "ekin", "mu", "ptor")
        self.ascot.input_free()

        h1a.plot(tgo.to("µs"), mugo)
        h1a.plot(tgo2gc.to("µs"), mugo2gc)
        h1a.plot(tgc.to("µs"), mugc)

        h1b.plot(tgo.to("µs"), ego)
        h1b.plot(tgo2gc.to("µs"), ego2gc)
        h1b.plot(tgc.to("µs"), egc)

        h1c.plot(tgo.to("µs"), pgo)
        h1c.plot(tgo2gc.to("µs"), pgo2gc)
        h1c.plot(tgc.to("µs"), pgc)

        h2.plot(rgo, zgo)
        h2.plot(rgo2gc, zgo2gc)
        h2.plot(rgc, zgc)

        nrep = run_zeroth.getstate("ids").size
        for i in range(nrep):
            r, z = run_zeroth.getorbit("r", "z", ids=i)
            h3.plot(r, z, color="C1")
        for i in range(nrep):
            r, z = run_first.getorbit("r", "z", ids=i)
            h3.plot(r.v+0.01, z, color="C2")
        h3.plot(rgo2gc, zgo2gc, color="black")

        # Verify results by interpolating the orbits at fixed intervals and then
        # calculating sum-of-squares of the difference between go and gc and
        # go2gc and gc. The latter should be smaller if the guiding center
        # transformation works.
        t = np.linspace(0, 1e-6, 1000)
        mugo    = np.interp(t, tgo,    mugo)
        mugc    = np.interp(t, tgc,    mugc)
        mugo2gc = np.interp(t, tgo2gc, mugo2gc)
        ego    = np.interp(t, tgo,    ego)
        egc    = np.interp(t, tgc,    egc)
        ego2gc = np.interp(t, tgo2gc, ego2gc)
        pgo    = np.interp(t, tgo,    pgo)
        pgc    = np.interp(t, tgc,    pgc)
        pgo2gc = np.interp(t, tgo2gc, pgo2gc)

        err1 = np.sum( (mugo    - mugc)**2 )
        err2 = np.sum( (mugo2gc - mugc)**2 )
        print(err2/err1)
        err1 = np.sum( (ego    - egc)**2 )
        err2 = np.sum( (ego2gc - egc)**2 )
        print(err2/err1)
        err1 = np.sum( (pgo    - pgc)**2 )
        err2 = np.sum( (pgo2gc - pgc)**2 )
        print(err2/err1)

    def init_ccoll(self):
        """Initialize data for the Coulomb collision test.
        """
        if hasattr(self.ascot.data.options, PhysTest.tag_ccoll_thermalgo):
            warnings.warn("Inputs already present: Test Coulomb collision")
            return
        init = self.ascot.data.create_input

        # Options
        opt = Opt.get_default()
        opt.update({
            "ENDCOND_SIMTIMELIM" : 1, "ENDCOND_LIM_SIMTIME" : 2e-2,
            "ENABLE_ORBIT_FOLLOWING" : 1, "ENABLE_COULOMB_COLLISIONS" : 1,
            "ENABLE_DIST_5D" : 1,
            "DIST_MIN_R" : 4, "DIST_MAX_R" : 10, "DIST_NBIN_R" : 1,
            "DIST_MIN_PHI" : 0, "DIST_MAX_PHI" : 360, "DIST_NBIN_PHI" : 1,
            "DIST_MIN_Z" : -5, "DIST_MAX_Z" : 5, "DIST_NBIN_Z" : 1,
            "DIST_MIN_TIME" : 0, "DIST_MAX_TIME" : 2e-2, "DIST_NBIN_TIME" : 2,
            "DIST_MIN_PPA" : -2.5e-21, "DIST_MAX_PPA" : 2.5e-21,
            "DIST_NBIN_PPA" : 140, "DIST_MIN_PPE" : 0, "DIST_MAX_PPE" : 2.5e-21,
            "DIST_NBIN_PPE" : 80
        })

        opt.update({"SIM_MODE" : 1, "FIXEDSTEP_USE_USERDEFINED" : 1,
                    "FIXEDSTEP_USERDEFINED" : 1e-8})
        init("opt", **opt, desc=PhysTest.tag_ccoll_thermalgo)
        opt.update({"SIM_MODE" : 2, "FIXEDSTEP_USE_USERDEFINED" : 1,
                    "FIXEDSTEP_USERDEFINED" : 2e-8})
        init("opt", **opt, desc=PhysTest.tag_ccoll_thermalgcf)
        opt.update({"ENABLE_ADAPTIVE" : 1, "ADAPTIVE_TOL_ORBIT" : 1e-6,
                    "ADAPTIVE_TOL_CCOL" : 1e-2, "ADAPTIVE_MAX_DRHO" : 0.1,
                    "ADAPTIVE_MAX_DPHI" : 10, "FIXEDSTEP_USERDEFINED" : 1e-8})
        init("opt", **opt, desc=PhysTest.tag_ccoll_thermalgca)

        opt = Opt.get_default()
        opt.update({
            "ENDCOND_ENERGYLIM" : 1, "ENDCOND_MIN_ENERGY" : 50e3,
            "ENDCOND_MIN_THERMAL" : 0, "ENABLE_ORBIT_FOLLOWING" : 1,
            "ENABLE_COULOMB_COLLISIONS" : 1, "ENABLE_DIST_5D" : 1,
            "DIST_MIN_R" : 4, "DIST_MAX_R" : 10, "DIST_NBIN_R" : 1,
            "DIST_MIN_PHI" : 0, "DIST_MAX_PHI" : 360, "DIST_NBIN_PHI" : 1,
            "DIST_MIN_Z" : -5, "DIST_MAX_Z" : 5, "DIST_NBIN_Z" : 1,
            "DIST_MIN_TIME" : 0, "DIST_MAX_TIME" : 2e-2, "DIST_NBIN_TIME" : 2,
            "DIST_MIN_PPA" : -1.3e-19, "DIST_MAX_PPA" : 1.3e-19,
            "DIST_NBIN_PPA" : 200, "DIST_MIN_PPE" : 0, "DIST_MAX_PPE" : 1.3e-19,
            "DIST_NBIN_PPE" : 100
        })

        opt.update({"SIM_MODE" : 1, "FIXEDSTEP_USE_USERDEFINED" : 1,
                    "FIXEDSTEP_USERDEFINED" : 2e-9})
        init("opt", **opt, desc=PhysTest.tag_ccoll_slowinggo)
        opt.update({"SIM_MODE" : 2, "FIXEDSTEP_USE_USERDEFINED" : 1,
                    "FIXEDSTEP_USERDEFINED" : 3e-8})
        init("opt", **opt, desc=PhysTest.tag_ccoll_slowinggcf)
        opt.update({"ENABLE_ADAPTIVE" : 1, "ADAPTIVE_TOL_ORBIT" : 1e-6,
                    "ADAPTIVE_TOL_CCOL" : 1e-2, "ADAPTIVE_MAX_DRHO" : 0.1,
                    "ADAPTIVE_MAX_DPHI" : 10, "FIXEDSTEP_USERDEFINED" : 1e-8})
        init("opt", **opt, desc=PhysTest.tag_ccoll_slowinggca)

        # Magnetic field is just some tokamak and plasma is uniform
        for tag in [PhysTest.tag_ccoll_thermalgo, PhysTest.tag_ccoll_thermalgcf,
                    PhysTest.tag_ccoll_thermalgca, PhysTest.tag_ccoll_slowinggo,
                    PhysTest.tag_ccoll_slowinggcf, PhysTest.tag_ccoll_slowinggca
                    ]:
            init("bfield_analytical_iter_circular", desc=tag)
            init("plasma_flat", density=1e20, temperature=1e3, desc=tag)

        mrk = Marker.generate("gc", n=20, species="proton")
        pol = 2 * np.pi * np.random.rand(mrk["n"],)
        mrk["r"][:]      = 6.2 + 0.8 * np.cos(pol)
        mrk["phi"][:]    = 90
        mrk["z"][:]      = 0.8 * np.sin(pol)
        mrk["zeta"][:]   = 2 * np.pi * np.random.rand(mrk["n"],)
        mrk["energy"][:] = 1.e3
        mrk["pitch"][:]  = 0.5
        init("gc", **mrk, desc=PhysTest.tag_ccoll_thermalgo)
        init("gc", **mrk, desc=PhysTest.tag_ccoll_thermalgcf)
        init("gc", **mrk, desc=PhysTest.tag_ccoll_thermalgca)

        mrk = Marker.generate("gc", n=200, species="alpha")
        pol = 2 * np.pi * np.random.rand(mrk["n"],)
        mrk["r"][:]      = 6.2 + 0.8 * np.cos(pol)
        mrk["phi"][:]    = 90
        mrk["z"][:]      = 0.8 * np.sin(pol)
        mrk["zeta"][:]   = 2 * np.pi * np.random.rand(mrk["n"],)
        mrk["energy"][:] = 3.5e6
        mrk["pitch"][:]  = 1.0 - 2.0 * np.random.rand(mrk["n"],)
        init("gc", **mrk, desc=PhysTest.tag_ccoll_slowinggo)
        init("gc", **mrk, desc=PhysTest.tag_ccoll_slowinggcf)
        init("gc", **mrk, desc=PhysTest.tag_ccoll_slowinggca)

    def run_ccoll(self):
        """Run Coulmb collision test.
        """
        if hasattr(self.ascot.data, PhysTest.tag_ccoll_thermalgo):
            warnings.warn("Results already present: Test Coulomb collision")
            return
        for tag in [PhysTest.tag_ccoll_thermalgo, PhysTest.tag_ccoll_thermalgcf,
                    PhysTest.tag_ccoll_thermalgca, PhysTest.tag_ccoll_slowinggo,
                    PhysTest.tag_ccoll_slowinggcf, PhysTest.tag_ccoll_slowinggca
                    ]:
            self._activateinputs(tag)
            self._runascot(tag)

    def check_ccoll(self):
        """Check Coulomb collision test.
        """
        run_tgo  = self.ascot.data[PhysTest.tag_ccoll_thermalgo]
        run_tgcf = self.ascot.data[PhysTest.tag_ccoll_thermalgcf]
        run_tgca = self.ascot.data[PhysTest.tag_ccoll_thermalgca]
        run_sgo  = self.ascot.data[PhysTest.tag_ccoll_slowinggo]
        run_sgcf = self.ascot.data[PhysTest.tag_ccoll_slowinggcf]
        run_sgca = self.ascot.data[PhysTest.tag_ccoll_slowinggca]

        fig = a5plt.figuredoublecolumn()
        gs = GridSpec(2, 2, figure=fig)
        h1 = fig.add_subplot(gs[0,0])
        h2 = fig.add_subplot(gs[0,1])
        h3 = fig.add_subplot(gs[1,0])
        h4 = fig.add_subplot(gs[1,1])

        # Analytical results
        alphaZ = 2
        clog   = 16
        vth    = np.sqrt(2*Te*e / m_e)
        vcrit  = vth * np.power( (3.0*np.sqrt(np.pi)/4.0) * (m_e / m_p) , 1/3.0)
        Ecrit  = 0.5 * m_a * vcrit * vcrit / e
        ts     = 3 * np.sqrt( np.power(2*np.pi * Te * e, 3) / m_e ) * eps_0 * eps_0 \
            * m_a /( alphaZ * alphaZ * np.power(e, 4) * ne * clog)

        heaviside = np.logical_and(SLOWING["Egrid"] <= Esd,
                                   SLOWING["Egrid"] >= 50*Te)

        THERMAL["analytical"]  = 2 * np.sqrt(THERMAL["Egrid"]/np.pi) \
            * np.power(Te,-3.0/2) \
            * np.exp(-THERMAL["Egrid"]/Te)
        THERMAL["analytical"] *= (simtime_th/2)
        SLOWING["analytical"] = heaviside * ts \
            / ( ( 1 + np.power(Ecrit/SLOWING["Egrid"], 3.0/2) )\
                * 2 * SLOWING["Egrid"] )

        # ts is slowing down rate which gives the slowing down time as
        # t_sd = ts*log(v_0 / v_th) = 0.5*ts*log(E_0/E_th)
        slowingdowntime = 0.5*ts*np.log(Esd/(50*Te))

        for run in [run_tgo, run_tgcf, run_tgca]:
            dist = run.getdist("5d", exi=True)
            edist = dist.integrate(
                r=np.s_[:], phi=np.s_[:], z=np.s_[:], time=np.s_[:],
                charge=np.s_[:], pitch=np.s_[:], copy=True)
            xdist = dist.integrate(
                r=np.s_[:], phi=np.s_[:], z=np.s_[:], time=np.s_[:],
                charge=np.s_[:], ekin=np.s_[:], copy=True)
            run.plotdist(edist, axes=h1)
            run.plotdist(xdist, axes=h2)

        for run in [run_sgo, run_sgcf, run_sgca]:
            dist = run.getdist("5d", exi=True)
            edist = dist.integrate(
                r=np.s_[:], phi=np.s_[:], z=np.s_[:], time=np.s_[:],
                charge=np.s_[:], pitch=np.s_[:], copy=True)
            xdist = dist.integrate(
                r=np.s_[:], phi=np.s_[:], z=np.s_[:], time=np.s_[:],
                charge=np.s_[:], ekin=np.s_[:], copy=True)
            run.plotdist(edist, axes=h3)
            run.plotdist(xdist, axes=h4)

        plt.show()

    def init_classical(self):
        """Initialize data for the classical transport test.
        """
        if hasattr(self.ascot.data.options,
                   PhysTest.tag_classical_go + "0"):
            warnings.warn("Inputs already present: Test classical transport")
            return
        init = self.ascot.data.create_input

        # Options
        optgo = Opt.get_default()
        optgo.update({
            "SIM_MODE" : 1, "FIXEDSTEP_USE_USERDEFINED" : 1,
            "FIXEDSTEP_USERDEFINED" : 1e-10, "ENDCOND_SIMTIMELIM" : 1,
            "ENDCOND_LIM_SIMTIME" : 5e-6, "ENABLE_ORBIT_FOLLOWING" : 1,
            "ENABLE_COULOMB_COLLISIONS" : 1
        })
        optgcf = copy.deepcopy(optgo)
        optgcf.update({
            "SIM_MODE" : 2, "FIXEDSTEP_USERDEFINED" : 1e-9
        })
        optgca = copy.deepcopy(optgcf)
        optgca.update({
            "ENABLE_ADAPTIVE" : 1, "ADAPTIVE_MAX_DRHO" : 0.1,
            "ADAPTIVE_TOL_ORBIT" : 1e-8, "ADAPTIVE_TOL_CCOL" : 1e-1,
            "ADAPTIVE_MAX_DPHI" : 10, "FIXEDSTEP_USERDEFINED" : 1e-8
        })

        # Marker input consists of protons
        mrk = Marker.generate("gc", n=200, species="proton")
        mrk["r"][:]      = 5.0
        mrk["phi"][:]    = 0.0
        mrk["z"][:]      = 0.0
        mrk["energy"][:] = 1e3
        mrk["pitch"][:]  = 1.0 - 2.0 * np.random.rand(mrk["n"],)
        mrk["zeta"][:]   = 2 * np.pi * np.random.rand(mrk["n"],)

        # Plasma consisting of electrons only to avoid proton-proton collisions
        pls = init("plasma_flat", density=1e22, temperature=1e3, dryrun=True)
        pls["idensity"][:] = 1

        for i in range(6):
            init("opt", **optgo,  desc=PhysTest.tag_classical_go  + str(i))
            init("opt", **optgcf, desc=PhysTest.tag_classical_gcf + str(i))
            init("opt", **optgca, desc=PhysTest.tag_classical_gca + str(i))
            for tag in [PhysTest.tag_classical_go, PhysTest.tag_classical_gcf,
                        PhysTest.tag_classical_gca]:
                # Transport is scanned as a function of magnetic field strength
                d = {"bxyz" : np.array([1, 0, 0]), "rhoval" : 0.5,
                     "jacobian" : np.array([0,0,0,0,0,0,0,0,0])}
                d["bxyz"][0] = 1.0 + i * (10.0 - 1.0) / 5
                init("B_TC", **d, desc=tag + str(i))
                init("gc", **mrk, desc=tag + str(i))
                init("plasma_1D", **pls, desc=tag + str(i))

    def run_classical(self):
        """Run classical transport test.
        """
        if hasattr(self.ascot.data, PhysTest.tag_classical_go):
            warnings.warn("Results already present: Test classical transport")
            return
        for tag in [PhysTest.tag_classical_go, PhysTest.tag_classical_gcf,
                    PhysTest.tag_classical_gca]:
            i = 0
            while tag + str(i) in self.ascot.data.bfield.ls(show=False):
                self._activateinputs(tag+str(i))
                self._runascot(tag+str(i))
                i += 1

    def check_classical(self):
        """Check classical transport test.
        """
        nscan = 0
        while PhysTest.tag_classical_go + str(nscan) in \
              self.ascot.data.bfield.ls(show=False):
            nscan += 1

        # Initialize plots
        fig = a5plt.figuredoublecolumn(3/2)
        ax = fig.add_subplot(1,1,1)

        # Numerical values
        ndim = 2 # Diffusion happens on 2D plane
        bnorm = np.zeros((nscan,)) * unyt.T
        Dgo   = np.zeros((nscan,)) * unyt.m**2 / unyt.s
        Dgcf  = np.zeros((nscan,)) * unyt.m**2 / unyt.s
        Dgca  = np.zeros((nscan,)) * unyt.m**2 / unyt.s
        for i in range(nscan):
            run_go  = self.ascot.data[PhysTest.tag_classical_go  + str(i)]
            run_gcf = self.ascot.data[PhysTest.tag_classical_gcf + str(i)]
            run_gca = self.ascot.data[PhysTest.tag_classical_gca + str(i)]

            yi, zi, ti = run_go.getstate("y", "z", "mileage", state="ini")
            yf, zf, tf = run_go.getstate("y", "z", "mileage", state="end")
            Dgo[i] = np.mean( ( (yi - yf)**2 + (zi - zf)**2 ) / (tf - ti) ) \
                / (2*ndim)
            yi, zi, ti = run_gcf.getstate("y", "z", "mileage", state="ini")
            yf, zf, tf = run_gcf.getstate("y", "z", "mileage", state="end")
            Dgcf[i] = np.mean( ( (yi - yf)**2 + (zi - zf)**2 ) / (tf - ti) ) \
                / (2*ndim)
            yi, zi, ti = run_gca.getstate("y", "z", "mileage", state="ini")
            yf, zf, tf = run_gca.getstate("y", "z", "mileage", state="end")
            Dgca[i] = np.mean( ( (yi - yf)**2 + (zi - zf)**2 ) / (tf - ti) ) \
                / (2*ndim)

            bnorm[i] = np.sqrt(np.sum(run_go.bfield.read()["bxyz"]**2))

        # Analytical
        clog = 13.4
        ekin = run_go.getstate("ekin")[0]
        self.ascot.input_init(run=run_go.get_qid(), bfield=True, plasma=True)
        ne, Te = self.ascot.input_eval(6.2, 0, 0, 0, "ne", "te")
        self.ascot.input_free()
        #collfreq = ( (unyt.me / unyt.mp) * ( np.sqrt(2 / np.pi) / 3 )
        #             * ( unyt.e**2 / ( 4 * np.pi * unyt.eps_0 ) )**2 * ne * clog
        #             * 4 * np.pi / np.sqrt( unyt.me * (Te)**3 ) ).to("1/s")
        collfreq = physlib.collfreq_ie(unyt.mp, unyt.e, ne, Te, clog)
        rhog = physlib.gyrolength(unyt.mp, 1*unyt.e, ekin, 0.0, bnorm).to("m")
        Dana = collfreq * rhog**2 / 2

        # Plotting
        ax.scatter(1/bnorm**2, Dgo)
        ax.scatter(1/bnorm**2, Dgcf)
        ax.scatter(1/bnorm**2, Dgca)
        ax.plot(1/bnorm**2, Dana, color="black")

    def init_neoclassical(self):
        """Initialize data for the neoclassical transport test.
        """
        if hasattr(self.ascot.data.options, PhysTest.tag_neoclassical_go):
            warnings.warn("Inputs already present: Test neoclass. transport")
            return
        init = self.ascot.data.create_input

        # Ion densities to be scanned
        ni = np.power( 10, np.linspace(17.5, 22.0, 20) )

        # Options (some parameters are changed between the scans)
        optgo = Opt.get_default()
        optgo.update({
            "SIM_MODE" : 1, "FIXEDSTEP_USE_USERDEFINED" : 1,
            "FIXEDSTEP_USERDEFINED" : 3e-10, "ENDCOND_SIMTIMELIM" : 1,
            "ENABLE_ORBIT_FOLLOWING" : 1, "ENABLE_COULOMB_COLLISIONS" : 1
        })
        optgcf = copy.deepcopy(optgo)
        optgcf.update({
            "SIM_MODE" : 2
        })
        optgca = copy.deepcopy(optgcf)
        optgca.update({
            "ENABLE_ADAPTIVE" : 1, "ADAPTIVE_MAX_DRHO" : 0.1,
            "ADAPTIVE_TOL_ORBIT" : 1e-8, "ADAPTIVE_TOL_CCOL" : 1e-1,
            "ADAPTIVE_MAX_DPHI" : 10, "FIXEDSTEP_USERDEFINED" : 1e-10
        })

        # Marker input consists of electrons
        mrk = Marker.generate("gc", n=100, species="electron")
        mrk["r"][:]      = 7.2
        mrk["phi"][:]    = 0.0
        mrk["z"][:]      = 0.0
        mrk["energy"][:] = 1e3
        mrk["pitch"][:]  = 1.0 - 2.0 * np.random.rand(mrk["n"],)
        mrk["zeta"][:]   = 2 * np.pi * np.random.rand(mrk["n"],)

        # Plasma consisting of protons only to avoid e-e collisions
        pls = init("plasma_flat", temperature=1e3, dryrun=True)
        pls["edensity"][:] = 1

        for i in range(ni.size):

            # Adjust simulation time and time step as the density changes
            # (otherwise simulations with low density would take very long)
            simtime = np.maximum( 5e-4, 4e-2 / ( ni[i-1] / ni[0] ) )
            optgo.update({
                "ENDCOND_LIM_SIMTIME" : simtime,
                "FIXEDSTEP_USERDEFINED" :
                np.minimum( 2e-9, 3e-10 / ( ni[i-1] / ni[-1] ) )
            })
            optgcf.update({
                "ENDCOND_LIM_SIMTIME" : simtime,
                "FIXEDSTEP_USERDEFINED" :
                np.minimum( 2e-8, 5e-10 / ( ni[i-1] / ni[-1] ) )
            })
            optgca.update({
                "ENDCOND_LIM_SIMTIME" : simtime
            })
            init("opt", **optgo,  desc=PhysTest.tag_neoclassical_go  + str(i))
            init("opt", **optgcf, desc=PhysTest.tag_neoclassical_gcf + str(i))
            init("opt", **optgca, desc=PhysTest.tag_neoclassical_gca + str(i))

            pls["idensity"][:] = ni[i]
            for tag in [PhysTest.tag_neoclassical_go,
                        PhysTest.tag_neoclassical_gcf,
                        PhysTest.tag_neoclassical_gca]:
                init("gc", **mrk, desc=tag + str(i))
                init("plasma_1D", **pls, desc=tag + str(i))
                init("bfield_analytical_iter_circular", desc=tag + str(i))

    def run_neoclassical(self):
        """Run neoclassical transport test.
        """
        if hasattr(self.ascot.data, PhysTest.tag_neoclassical_go):
            warnings.warn("Results already present: Test neoclass. transport")
            return
        for tag in [PhysTest.tag_neoclassical_go, PhysTest.tag_neoclassical_gcf,
                    PhysTest.tag_neoclassical_gca]:
            i = 0
            while tag + str(i) in self.ascot.data.bfield.ls(show=False):
                print(i)
                self._activateinputs(tag+str(i))
                self._runascot(tag+str(i))
                i += 1

    def check_neoclassical(self):
        """Check neoclassical transport test.
        """
        nscan = 0
        items = self.ascot.data.bfield.ls(show=False)
        while PhysTest.tag_neoclassical_go + str(nscan) in items:
            nscan += 1
            print(nscan)

        # Evaluate Ti and R_omp(rho) as these are needed
        run_go = self.ascot.data[PhysTest.tag_neoclassical_go  + "0"]
        self.ascot.input_init(run=run_go.get_qid(), bfield=True, plasma=True)
        Ti         = self.ascot.input_eval(6.2, 0, 0, 0, "ti1")
        rhoomp     = np.linspace(0, 1, 100)
        romp, zomp = self.ascot.input_rhotheta2rz(rhoomp, 0, 0, 0)
        self.ascot.input_free()

        # Initialize plots
        fig = a5plt.figuredoublecolumn(3/2)
        ax = fig.add_subplot(1,1,1)
        ax.set_xscale("log")
        ax.set_yscale("log")

        # Numerical values
        ni    = np.zeros((nscan,)) / unyt.m**3
        Dgo   = np.zeros((nscan,)) * unyt.m**2 / unyt.s
        Dgcf  = np.zeros((nscan,)) * unyt.m**2 / unyt.s
        Dgca  = np.zeros((nscan,)) * unyt.m**2 / unyt.s
        for i in range(nscan):
            run_go  = self.ascot.data[PhysTest.tag_neoclassical_go  + str(i)]
            run_gcf = self.ascot.data[PhysTest.tag_neoclassical_gcf + str(i)]
            run_gca = self.ascot.data[PhysTest.tag_neoclassical_gca + str(i)]

            ri, ti = run_go.getstate("rho", "mileage", state="ini")
            rf, tf = run_go.getstate("rho", "mileage", state="end")
            ri = np.interp(ri, rhoomp, romp) * unyt.m
            rf = np.interp(rf, rhoomp, romp) * unyt.m
            Dgo[i] = 0.5 * np.mean( (rf - ri)**2 / (tf - ti) )

            ri, ti = run_gcf.getstate("rho", "mileage", state="ini")
            rf, tf = run_gcf.getstate("rho", "mileage", state="end")
            ri = np.interp(ri, rhoomp, romp) * unyt.m
            rf = np.interp(rf, rhoomp, romp) * unyt.m
            Dgcf[i] = 0.5 * np.mean( (rf - ri)**2 / (tf - ti) )

            ri, ti = run_gca.getstate("rho", "mileage", state="ini")
            rf, tf = run_gca.getstate("rho", "mileage", state="end")
            ri = np.interp(ri, rhoomp, romp) * unyt.m
            rf = np.interp(rf, rhoomp, romp) * unyt.m
            Dgca[i] = 0.5 * np.mean( (rf - ri)**2 / (tf - ti) )

            ni[i] = run_go.plasma.read()["idensity"][0, 0]

        r0    = run_go.getstate("r")[0]
        axisr = run_go.bfield.read()["raxis"][0] * unyt.m
        eps   = (r0 - axisr) / axisr
        qfac  = 1.7 # Safety factor at r0 was verified numerically
        bnorm = run_go.bfield.read()["bphi0"][0] * unyt.T

        ekin   = run_go.getstate("ekin")[0]
        omegat = physlib.bouncefrequency(unyt.me, ekin, r0, axisr, qfac)
        rhog   = physlib.gyrolength(unyt.me, 1*unyt.e, ekin, 0.0, bnorm).to("m")

        clog     = 15
        density  = np.power( 10, np.linspace(np.log10(ni[0]) - 1,
                                             np.log10(ni[-1]) + 1, 50) ) / unyt.m**3
        collfreq = physlib.collfreq_ie(unyt.mp, unyt.e, density, Ti, clog) \
            * ( unyt.mp / unyt.me )
        veff = collfreq / omegat
        # Add intermediate values needed for plotting a continuous curve
        veff = np.append(veff, [1, np.power(eps, 3.0/2.0)])
        veff.sort()

        Dps = qfac**2 * veff * omegat * rhog**2 / 2
        Dp  = 0.5 * qfac**2 * omegat * rhog**2 * np.ones(veff.shape)
        Db  = np.power(eps, -3.0/2.0) * Dps

        # x coordinate for plotting the numerical coefficients
        collfreq = physlib.collfreq_ie(unyt.mp, unyt.e, ni, Ti, clog) \
            * ( unyt.mp / unyt.me )
        veff_x = collfreq / omegat

        ax.plot(veff, Dps, color="black")
        ax.plot(veff, Dp, color="black")
        ax.plot(veff, Db, color="black")
        ax.scatter(veff_x, Dgo, marker="*")
        ax.scatter(veff_x, Dgcf, marker="o")
        ax.scatter(veff_x, Dgca, marker="^")
        print(Dgo)
        print(Dgcf)
        print(Dgca)
        plt.show()

    def init_boozer(self):
        """Initialize data for the Boozer transformation test.
        """
        if hasattr(self.ascot.data.options, PhysTest.tag_boozer):
            warnings.warn("Inputs already present: Test Boozer transformation")
            return
        init = self.ascot.data.create_input

        # Options
        opt = Opt.get_default()
        opt.update({
            "SIM_MODE" : 4, "ENDCOND_SIMTIMELIM" : 1,
            "ENDCOND_MAX_MILEAGE" : 1e2/3e8, "ENABLE_ORBIT_FOLLOWING" : 1,
            "ENABLE_ORBITWRITE" : 1, "ORBITWRITE_MODE" : 1,
            "ORBITWRITE_INTERVAL" : 1e-1/3e8, "ORBITWRITE_NPOINT" : 10002
        })

        # Use field line markers
        mrk = Marker.generate("fl", n=1)
        mrk["r"][:]      = 8.0
        mrk["phi"][:]    = 0
        mrk["z"][:]      = 0
        mrk["pitch"][:]  = 1.0

        # Magnetic field is just some tokamak with Boozer data
        b = init("bfield_analytical_iter_circular", dryrun=True)
        b.update({"rmin" : 4, "rmax" : 8.5, "nr" : 120, "zmin" : -4,
                  "zmax" : 4, "nz" : 200})

        bphi = [5.3, -5.3, 5.3, -5.3]
        psimult = [200, 200, -200, -200]
        for i in range(4):
            b.update({"bphi0" : bphi[i], "psimult" : psimult[i]})
            out = B_2DS.convert_B_GS(**b)
            qid = init("B_2DS", **out, desc=PhysTest.tag_boozer+str(i))
            qid = self.ascot.data.bfield[qid].get_qid()
            self.ascot.input_init(bfield=qid)
            qid = init("boozer_tokamak", desc=PhysTest.tag_boozer+str(i))
            self.ascot.input_free(bfield=True)

            init("fl", **mrk, desc=PhysTest.tag_boozer+str(i))
            init("opt", **opt, desc=PhysTest.tag_boozer+str(i))

        # This perturbation is used only in the post-processing
        mhd = {"nmode" : 1, "nmodes" : np.array([2]), "mmodes" : np.array([3]),
               "amplitude" : np.array([1.0]), "omega" : np.array([1.0]),
               "phase" : np.array([0.0]), "nrho" : 100, "rhomin" : 0.0,
               "rhomax" : 1.0}
        rhogrid = np.linspace(mhd["rhomin"], mhd["rhomax"], mhd["nrho"])
        alpha   = np.exp( -(rhogrid-0.85)**2/0.1 )
        phi     = alpha*0
        mhd["phi"]   = np.tile(phi, (mhd["nmode"],1)).T
        mhd["alpha"] = np.tile(alpha, (mhd["nmode"],1)).T
        init("MHD_STAT", **mhd, desc=PhysTest.tag_boozer+"0")

    def run_boozer(self):
        """Run Boozer transformation test.
        """
        if hasattr(self.ascot.data, PhysTest.tag_boozer):
            warnings.warn("Results already present: Test Boozer transformation")
            return
        for i in range(4):
            self._activateinputs(PhysTest.tag_boozer + str(i))
            self._runascot(PhysTest.tag_boozer + str(i))

    def check_boozer(self):
        """Check Boozer transformation test.
        """
        run1 = self.ascot.data[PhysTest.tag_boozer+"0"]
        run2 = self.ascot.data[PhysTest.tag_boozer+"1"]
        run3 = self.ascot.data[PhysTest.tag_boozer+"2"]
        run4 = self.ascot.data[PhysTest.tag_boozer+"3"]

        # Initialize plots
        fig = a5plt.figuredoublecolumn(3/2)
        ax1 = fig.add_subplot(3,2,1)
        ax2 = fig.add_subplot(3,2,3)
        ax3 = fig.add_subplot(3,2,5)
        ax4 = fig.add_subplot(3,2,2)
        ax5 = fig.add_subplot(3,2,4)

        ax3.set_xlabel("Boozer theta [rad]")
        ax1.set_ylabel("Error in Bpol [T]")
        ax2.set_ylabel("Error in Bphi [T]")
        ax3.set_ylabel("Jacobian")
        ax4.set_ylabel("q")
        ax5.set_ylabel("q")
        ax5.set_xlabel("Orbit parameter s")

        colors = ["C0", "C1", "C2", "C3"]
        for i, run in enumerate([run1, run2, run3, run4]):
            self.ascot.input_init(run=run.get_qid(), bfield=True, boozer=True,
                                  mhd=True)
            r, phi, z, t, pol = run.getorbit("r", "phi", "z", "time", "theta")
            theta, zeta, alpha, jacb2 = self.ascot.input_eval(
                r, phi, z, t, "theta", "zeta", "alphaeig", "bjacxb2")

            # Results are plotted as a function of poloidal angle so find the
            # "discontinuity" points at 0/2pi.
            idx = np.nonzero(np.abs(np.diff(theta)) > np.pi)[0]
            theta = theta.v
            zeta  = zeta.v

            # Numerical safety factor has some noise so evaluate the average
            dz = np.diff(zeta)
            dz[dz > np.pi]  = dz[dz > np.pi]  - 2*np.pi
            dz[dz < -np.pi] = dz[dz < -np.pi] + 2*np.pi
            dt = np.diff(theta)
            dt[dt > np.pi]  = dt[dt > np.pi]  - 2*np.pi
            dt[dt < -np.pi] = dt[dt < -np.pi] + 2*np.pi
            qfac = dz/dt

            # Evaluate gradients and field components so we can compare those
            a, b, c = self.ascot.input_eval(
                r, phi, z, t, "dpsidr (bzr)", "dpsidphi (bzr)", "dpsidz (bzr)")
            gradpsi = np.array([a, b/r, c]).T
            a, b, c = self.ascot.input_eval(
                r, phi, z, t, "dthetadr", "dthetadphi", "dthetadz")
            gradtheta = np.array([a, b/r, c]).T
            a, b, c = self.ascot.input_eval(
                r, phi, z, t, "dzetadr", "dzetadphi", "dzetadz")
            gradzeta = np.array([a, b/r, c]).T

            br, bphi, bz = self.ascot.input_eval(
                r, phi, z, t, "br", "bphi", "bz")
            self.ascot.input_free()

            # Magnetic field vector from Boozer coordinates
            veca = np.cross(gradpsi, gradtheta)
            vecb = np.cross(gradzeta, gradpsi)
            bvec = -veca*np.mean(qfac) - vecb

            idx = np.nonzero(np.abs(np.diff(theta)) > np.pi)[0]
            dbpol = np.sqrt((bvec[:,0] - br.v)**2 + (bvec[:,2] - bz.v)**2)
            dbphi = bvec[:,1] - bphi.v
            bnorm = br**2 + bz**2 + bphi**2

            j0 = 1
            for j in idx[1:]:
                ax1.plot(theta[j0:j], dbpol[j0:j], color=colors[i])
                ax2.plot(theta[j0:j], dbphi[j0:j], color=colors[i])
                ax3.plot(theta[j0:j], jacb2[j0:j], color=colors[i])
                j0 = j
            if qfac[0] > 0:
                ax4.plot(qfac, color=colors[i])
            else:
                ax5.plot(qfac, color=colors[i])

    def init_mhd(self):
        """Initialize data for the MHD test.
        """
        if hasattr(self.ascot.data.options, PhysTest.tag_mhd_go):
            warnings.warn("Inputs already present: Test MHD")
            return
        init = self.ascot.data.create_input

        # Options
        opt = Opt.get_default()
        opt.update({
            "SIM_MODE" : 1, "FIXEDSTEP_USE_USERDEFINED" : 1,
            "FIXEDSTEP_USERDEFINED" : 1e-11, "ENDCOND_SIMTIMELIM" : 1,
            "ENDCOND_LIM_SIMTIME" : 1e-3, "ENABLE_ORBIT_FOLLOWING" : 1,
            "ENABLE_MHD" : 1, "ENABLE_ORBITWRITE" : 1, "ORBITWRITE_MODE" : 1,
            "ORBITWRITE_INTERVAL" : 1e-7, "ORBITWRITE_NPOINT" : 10000
        })
        init("opt", **opt, desc=PhysTest.tag_mhd_go)
        opt.update({
            "SIM_MODE" : 2, "FIXEDSTEP_USERDEFINED" : 1e-10
        })
        init("opt", **opt, desc=PhysTest.tag_mhd_gcf)
        opt.update({
            "ENABLE_ADAPTIVE" : 1, "FIXEDSTEP_USERDEFINED" : 1e-11,
            "ADAPTIVE_TOL_ORBIT" : 1e-10, "ADAPTIVE_MAX_DRHO" : 0.1,
            "ADAPTIVE_MAX_DPHI" : 10
        })
        init("opt", **opt, desc=PhysTest.tag_mhd_gca)

        # Use field line markers
        mrk = Marker.generate("gc", n=2, species="electron")
        mrk["r"][:]      = np.array([7.0, 8.0])
        mrk["phi"][:]    = 0
        mrk["z"][:]      = 0
        mrk["pitch"][:]  = np.array([0.4, 0.9])
        mrk["energy"][:] = 1e6

        # ITER-like field with boozer data and field line markers
        for tag in [PhysTest.tag_mhd_go, PhysTest.tag_mhd_gcf,
                    PhysTest.tag_mhd_gca]:
            qid = init("bfield_analytical_iter_circular", splines=True,
                       desc=tag)
            init("gc", **mrk, desc=tag)

        qid = self.ascot.data.bfield[qid].get_qid()
        self.ascot.input_init(bfield=qid)
        bzr = init("boozer_tokamak", dryrun=True)
        self.ascot.input_free(bfield=True)
        for tag in [PhysTest.tag_mhd_go, PhysTest.tag_mhd_gcf,
                    PhysTest.tag_mhd_gca]:
            init("Boozer", **bzr, desc=tag)

    def run_mhd(self):
        """Run MHD test.
        """
        if hasattr(self.ascot.data, PhysTest.tag_mhd_go):
            warnings.warn("Results already present: Test MHD")
            return
        for tag in [PhysTest.tag_mhd_go, PhysTest.tag_mhd_gcf,
                    PhysTest.tag_mhd_gca]:
            self._activateinputs(tag)
            self._runascot(tag)

    def check_mhd(self):
        """Check MHD test.
        """
        run_go  = self.ascot.data[PhysTest.tag_mhd_go]
        run_gcf = self.ascot.data[PhysTest.tag_mhd_gcf]
        run_gca = self.ascot.data[PhysTest.tag_mhd_gca]

    def init_atomic(self):
        """Initialize data for the atomic reaction test.
        """
        if hasattr(self.ascot.data.options, PhysTest.tag_atomic_cx):
            warnings.warn("Inputs already present: Test atomic reaction")
            return
        init = self.ascot.data.create_input

        # Options
        opt = Opt.get_default()
        opt.update({
            "SIM_MODE" : 1, "FIXEDSTEP_USE_USERDEFINED" : 1,
            "ENDCOND_SIMTIMELIM" : 1, "ENDCOND_LIM_SIMTIME" : 1e-3, # 1e-3
            "ENABLE_ORBIT_FOLLOWING" : 1, "ENABLE_ATOMIC" : 1
        })
        opt.update({
            "FIXEDSTEP_USERDEFINED" : 1e-9, "ENDCOND_NEUTRALIZED" : 1
        })
        init("opt", **opt, desc=PhysTest.tag_atomic_ionz)
        opt.update({
            "FIXEDSTEP_USERDEFINED" : 1e-9, "ENDCOND_NEUTRALIZED" : 0,#1e-13
            "ENDCOND_IONIZED" : 1
        })
        init("opt", **opt, desc=PhysTest.tag_atomic_cx)

        mrk = Marker.generate("gc", n=100, species="deuterium")
        mrk["r"][:]      = 7.0
        mrk["phi"][:]    = 0.0
        mrk["z"][:]      = 0.0
        mrk["zeta"][:]   = 2 * np.pi * np.random.rand(mrk["n"],)
        mrk["energy"][:] = 1e5
        mrk["pitch"][:]  = 1.0 - 2.0 * np.random.rand(mrk["n"],)
        init("gc", **mrk, desc=PhysTest.tag_atomic_cx)

        mrk = Marker.generate("gc", n=100, species="deuterium")
        mrk["charge"][:] = 0
        mrk["r"][:]      = 7.0
        mrk["phi"][:]    = 0.0
        mrk["z"][:]      = 0.0
        mrk["zeta"][:]   = 1.0 - 2.0 * np.random.rand(mrk["n"],)
        mrk["energy"][:] = 1e5
        mrk["pitch"][:]  = 2 * np.pi * np.random.rand(mrk["n"],)
        init("gc", **mrk, desc=PhysTest.tag_atomic_ionz)

        for tag in [PhysTest.tag_atomic_cx, PhysTest.tag_atomic_ionz]:
            # Some tokamak magnetic field
            init("bfield_analytical_iter_circular", desc=tag)

            # Plasma and neutral data
            init("plasma_flat", anum=2, znum=1, mass=2.0135532,
                 density=1e20, temperature=1e3, desc=tag)
            init("neutral_flat", anum=2, znum=1, density=1e16, temperature=1e3,
                 desc=tag)

            # ADAS data
            init("import_adas", desc=tag)

    def run_atomic(self):
        """Run atomic reaction test.
        """
        if hasattr(self.ascot.data, PhysTest.tag_atomic_cx):
            warnings.warn("Results already present: Test atomic reaction")
            return
        for tag in [PhysTest.tag_atomic_cx, PhysTest.tag_atomic_ionz]:
            self._activateinputs(tag)
            self._runascot(tag)

    def check_atomic(self):
        """Check atomic reaction test.
        """
        run_cx   = self.ascot.data[PhysTest.tag_atomic_cx]
        run_ionz = self.ascot.data[PhysTest.tag_atomic_ionz]

    def _activateinputs(self, tag):
        data = self.ascot.data
        tag0 = tag if hasattr(data.bfield, tag) else "DUMMY"
        data.bfield[tag0].activate()
        tag0 = tag if hasattr(data.efield, tag) else "DUMMY"
        data.efield[tag0].activate()
        tag0 = tag if hasattr(data.wall, tag) else "DUMMY"
        data.wall[tag0].activate()
        tag0 = tag if hasattr(data.plasma, tag) else "DUMMY"
        data.plasma[tag0].activate()
        tag0 = tag if hasattr(data.neutral, tag) else "DUMMY"
        data.neutral[tag0].activate()
        tag0 = tag if hasattr(data.boozer, tag) else "DUMMY"
        data.boozer[tag0].activate()
        tag0 = tag if hasattr(data.mhd, tag) else "DUMMY"
        data.mhd[tag0].activate()
        tag0 = tag if hasattr(data.asigma, tag) else "DUMMY"
        data.asigma[tag0].activate()
        tag0 = tag if hasattr(data.options, tag) else "DUMMY"
        data.options[tag0].activate()
        tag0 = tag if hasattr(data.marker, tag) else "DUMMY"
        data.marker[tag0].activate()

    def _runascot(self, test):
        subprocess.call(["./ascot5_main", "--in=testascot.h5", "--d="+test],
                        stdout=subprocess.DEVNULL)
        self.ascot = Ascot(self.ascot.file_getpath())

if __name__ == '__main__':
    test = PhysTest()
    test.execute(init=True, run=True, check=True, tests=["boozer"])
    plt.show()
