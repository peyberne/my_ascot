"""
Contains definition of WallFrame class.

File: wallframe.py
"""
import tkinter
import tkinter.ttk as ttk

import numpy as np

from .plotframe import PlotFrame
from .components import NumEntry

class WallFrame(PlotFrame):
    """
    A frame for plotting wall inputs.
    """

    def __init__(self, gui, wall):
        """
        Initialize and show default plot.
        """

        super().__init__(gui)
        self._gui  = gui
        self._wall = wall

        panel = self.get_sidepanel()
        self.phi_entry = NumEntry(panel, labeltext="phi [deg]:", defval=0)
        self.phi_entry.grid(row=0, column=0)

        plotbutton = tkinter.Button(panel, text="Plot", command=self._plot)
        plotbutton.grid(row=1, column=0, sticky="WE")

        self._plot()


    def _plot(self, *args):
        """
        Read control states and plot.
        """
        phi  = self.phi_entry.getval() * np.pi / 180

        fig  = self.get_fig()
        axes = fig.add_subplot(1,1,1)
        self._wall.plotRz(axes=axes, phi=phi)

        self.draw()
