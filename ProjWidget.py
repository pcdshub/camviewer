from PyQt5.QtGui import QImage, QTransform, QPainter
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtWidgets import QWidget
import param
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from lmfit.models import (
    GaussianModel,
    Model,
    update_param_vals,
    guess_from_peak,
    fwhm_expr,
    height_expr,
)
import numpy as np
import time
import json
import os
from datetime import datetime
import matplotlib.dates as mdates

# From lmfit.lineshapes, because it's not worth importing...
#
s2pi = np.sqrt(2 * np.pi)
# tiny had been numpy.finfo(numpy.float64).eps ~=2.2e16.
# here, we explicitly set it to 1.e-15 == numpy.finfo(numpy.float64).resolution
tiny = 1.0e-15


def gaussian_with_base(x, amplitude=1.0, center=0.0, sigma=1.0, base=0.0):
    return base + (
        (amplitude / (max(tiny, s2pi * sigma)))
        * np.exp(-((1.0 * x - center) ** 2) / max(tiny, (2 * sigma**2)))
    )


def sg4(x, amplitude=1.0, center=0.0, width=1.0):
    return amplitude * np.exp(-2.0 * ((x - center) ** 4 / max(tiny, width**4)))


def sg4_with_base(x, amplitude=1.0, center=0.0, width=1.0, base=0.0):
    return base + amplitude * np.exp(-2.0 * ((x - center) ** 4 / max(tiny, width**4)))


def sg6(x, amplitude=1.0, center=0.0, width=1.0):
    return amplitude * np.exp(-2.0 * ((x - center) ** 6 / max(tiny, width**6)))


def sg6_with_base(x, amplitude=1.0, center=0.0, width=1.0, base=0.0):
    return base + amplitude * np.exp(-2.0 * ((x - center) ** 6 / max(tiny, width**6)))


# A shameless copy from lmfit.
class GaussianModelWithBase(Model):
    r"""A model based on a Gaussian or normal distribution lineshape.

    The model has three Parameters: `amplitude`, `center`, and `sigma`.
    In addition, parameters `fwhm` and `height` are included as
    constraints to report full width at half maximum and maximum peak
    height, respectively.

    .. math::

        f(x; A, \mu, \sigma) = \frac{A}{\sigma\sqrt{2\pi}} e^{[{-{(x-\mu)^2}/{{2\sigma}^2}}]}

    where the parameter `amplitude` corresponds to :math:`A`, `center` to
    :math:`\mu`, and `sigma` to :math:`\sigma`. The full width at half
    maximum is :math:`2\sigma\sqrt{2\ln{2}}`, approximately
    :math:`2.3548\sigma`.

    For more information, see: https://en.wikipedia.org/wiki/Normal_distribution

    """

    fwhm_factor = 2 * np.sqrt(2 * np.log(2))
    height_factor = 1.0 / np.sqrt(2 * np.pi)

    def __init__(self, independent_vars=["x"], prefix="", nan_policy="raise", **kwargs):
        kwargs.update(
            {
                "prefix": prefix,
                "nan_policy": nan_policy,
                "independent_vars": independent_vars,
            }
        )
        super().__init__(gaussian_with_base, **kwargs)
        self._set_paramhints_prefix()

    def _set_paramhints_prefix(self):
        self.set_param_hint("sigma", min=0)
        self.set_param_hint("fwhm", expr=fwhm_expr(self))
        self.set_param_hint("height", expr=height_expr(self))

    def guess(self, data, x, negative=False, **kwargs):
        """Estimate initial model parameter values from data."""
        pars = guess_from_peak(self, data, x, negative)
        return update_param_vals(pars, self.prefix, **kwargs)


class SG4Model(Model):
    r"""A model based on a SuperGaussian model with p == 4.

    The model has three Parameters: `amplitude`, `center`, and `width`.
    In addition, parameters `fwhm` and `e2w` are also reported as
    constraints to report full width at half maximum and 1/e^2 width,
    respectively.

    .. math::

        f(x; A, c, w, p) = A*e^{-2((x-c)/w)^p}

    where `amplitude` is :math:`A`, `center` is :math:`c`, and `width`
    is :math:`w`. p is a constant 4.
    """

    def __init__(
        self, with_base, independent_vars=["x"], prefix="", nan_policy="raise", **kwargs
    ):
        kwargs.update(
            {
                "prefix": prefix,
                "nan_policy": nan_policy,
                "independent_vars": independent_vars,
            }
        )
        self.with_base = with_base
        if self.with_base:
            super().__init__(sg4_with_base, **kwargs)
        else:
            super().__init__(sg4, **kwargs)
        self._set_paramhints_prefix()

    def _set_paramhints_prefix(self):
        self.set_param_hint("width", min=0)
        self.set_param_hint("fwhm", expr="1.5345*width")
        self.set_param_hint("e2w", expr="2*width")

    def guess(self, data, x, negative=False, **kwargs):
        """Estimate initial model parameter values from data."""
        maxy, miny = max(data), min(data)
        maxx, minx = max(x), min(x)
        cen = x[np.argmax(data)]
        height = (maxy - miny) * 3.0
        sig = (maxx - minx) / 6.0
        if self.with_base:
            pars = self.make_params(amplitude=height, center=cen, width=sig, base=0)
        else:
            pars = self.make_params(amplitude=height, center=cen, width=sig)
        pars[f"{self.prefix}width"].set(min=0.0)
        return update_param_vals(pars, self.prefix, **kwargs)


class SG6Model(Model):
    r"""A model based on a SuperGaussian model with p == 6.

    The model has three Parameters: `amplitude`, `center`, and `width`.
    In addition, parameters `fwhm` and `e2w` are also reported as
    constraints to report full width at half maximum and 1/e^2 width,
    respectively.

    .. math::

        f(x; A, c, w, p) = A*e^{-2((x-c)/w)^p}

    where `amplitude` is :math:`A`, `center` is :math:`c`, and `width`
    is :math:`w`. p is a constant 6.
    """

    def __init__(
        self, with_base, independent_vars=["x"], prefix="", nan_policy="raise", **kwargs
    ):
        kwargs.update(
            {
                "prefix": prefix,
                "nan_policy": nan_policy,
                "independent_vars": independent_vars,
            }
        )
        self.with_base = with_base
        if self.with_base:
            super().__init__(sg6_with_base, **kwargs)
        else:
            super().__init__(sg6, **kwargs)
        self._set_paramhints_prefix()

    def _set_paramhints_prefix(self):
        self.set_param_hint("width", min=0)
        self.set_param_hint("fwhm", expr="1.6762*width")
        self.set_param_hint("e2w", expr="2*width")

    def guess(self, data, x, negative=False, **kwargs):
        """Estimate initial model parameter values from data."""
        maxy, miny = max(data), min(data)
        maxx, minx = max(x), min(x)
        cen = x[np.argmax(data)]
        height = (maxy - miny) * 3.0
        sig = (maxx - minx) / 6.0
        if self.with_base:
            pars = self.make_params(amplitude=height, center=cen, width=sig, base=0)
        else:
            pars = self.make_params(amplitude=height, center=cen, width=sig)
        pars[f"{self.prefix}width"].set(min=0.0)
        return update_param_vals(pars, self.prefix, **kwargs)


#
# If is_x, this is viewwidth by projsize, otherwise it is projsize by viewheight!
#
class ProjWidget(QWidget):
    def resizeEvent(self, event):
        # Do not call makeImage here; it requires arguments.
        self.update()
        super().resizeEvent(event)

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        gui = parent
        x = gui.parentWidget()
        while x is not None:
            gui = x
            x = gui.parentWidget()
        self.gui = gui
        self.hint = self.size()
        self.is_x = True
        self.image = None
        # Fit history: separate lists for x and y fits: list of (timestamp, fwhm_value)
        self.fit_history_x = []
        self.fit_history_y = []
        # Center history: (timestamp, center_value)
        self.center_history_x = []
        self.center_history_y = []
        # Amplitude history: (timestamp, amplitude_value)
        self.ampl_history_x = []
        self.ampl_history_y = []
        # When true, makeImage will render a small time-series plot of FWHM
        self._show_history = False
        # When true, only draw the history subplot (do not show projection/lineout)
        self._show_only_history = False
        # Recording flag: when False, do not append new fits
        self._recording = True
        # Maximum number of history entries to retain
        self.max_history = 1000
        # When True, the widget will not compute its own fits and will
        # instead rely on externally provided FWHM values appended via
        # `append_fwhm`. This is used by the Plot-against-PV dialog so the
        # main window can compute fits once and share results.
        self._use_external_fits = False
        # Y axis control for history plot: when True, auto-scale; when False
        # use `self.y_limits_*` if set to a tuple (ymin, ymax).
        self.y_auto_fwhm = True
        self.y_limits_fwhm = None
        self.y_auto_center = True
        self.y_limits_center = None
        self.y_auto_center_x = True
        self.y_limits_center_x = None
        self.y_auto_center_y = True
        self.y_limits_center_y = None
        self.y_auto_amplitude = True
        self.y_limits_amplitude = None
        # Subplot visibility flags
        self._show_fwhm_subplot = True
        self._show_center_subplot = True
        self._show_amplitude_subplot = True
        # Split center subplot into separate X and Y plots
        self._split_center_xy = False
        # PV plotting mode: when True, use PV value for X-axis instead of time
        self._use_pv_for_x = False
        self._pv_name = ""
        # PV history: store (pv_value, fwhm/center/amplitude) pairs
        self.pv_history_fwhm_x = []
        self.pv_history_fwhm_y = []
        self.pv_history_center_x = []
        self.pv_history_center_y = []
        self.pv_history_ampl_x = []
        self.pv_history_ampl_y = []

    @property
    def lineout_cbs(self):
        """
        Load these later instead of in init in case they aren't created yet
        """
        return [
            self.gui.ui.checkBoxM1Lineout,
            self.gui.ui.checkBoxM2Lineout,
            self.gui.ui.checkBoxM3Lineout,
            self.gui.ui.checkBoxM4Lineout,
        ]

    def set_x(self):
        self.is_x = True

    def set_y(self):
        self.is_x = False

    def set_show_history(self, flag: bool):
        """Enable or disable the small FWHM vs time subplot for this widget."""
        self._show_history = bool(flag)

    def set_show_only_history(self, flag: bool):
        """When True, only render the history plot (no projection or lineout)."""
        self._show_only_history = bool(flag)

    def set_recording(self, enabled: bool):
        """Enable or disable recording new fit results into history."""
        self._recording = bool(enabled)

    def set_max_history(self, n: int):
        """Set maximum number of history entries to retain (positive integer)."""
        try:
            n = int(n)
            if n < 1:
                n = 1
            self.max_history = n
            # Trim existing histories to the new cap
            if len(self.fit_history_x) > self.max_history:
                self.fit_history_x = self.fit_history_x[-self.max_history:]
            if len(self.fit_history_y) > self.max_history:
                self.fit_history_y = self.fit_history_y[-self.max_history:]
            if len(self.center_history_x) > self.max_history:
                self.center_history_x = self.center_history_x[-self.max_history:]
            if len(self.center_history_y) > self.max_history:
                self.center_history_y = self.center_history_y[-self.max_history:]
            if len(self.ampl_history_x) > self.max_history:
                self.ampl_history_x = self.ampl_history_x[-self.max_history:]
            if len(self.ampl_history_y) > self.max_history:
                self.ampl_history_y = self.ampl_history_y[-self.max_history:]
        except Exception:
            pass

    def set_use_external_fits(self, flag: bool):
        """When True, the widget will not perform local fitting and will
        rely on externally supplied FWHM values via `append_fwhm`.
        """
        try:
            self._use_external_fits = bool(flag)
        except Exception:
            pass

    def set_y_auto(self, flag: bool, subplot: str = "fwhm"):
        """Enable or disable automatic Y scaling for the specified subplot.
        
        Parameters
        ----------
        flag : bool
            True to enable auto-scaling, False to use fixed limits.
        subplot : str
            Which subplot to control: 'fwhm', 'center', 'center_x', 'center_y', or 'amplitude'.
        """
        try:
            subplot = subplot.lower()
            if subplot == "fwhm":
                self.y_auto_fwhm = bool(flag)
                if self.y_auto_fwhm:
                    self.y_limits_fwhm = None
            elif subplot == "center":
                self.y_auto_center = bool(flag)
                if self.y_auto_center:
                    self.y_limits_center = None
            elif subplot == "center_x":
                self.y_auto_center_x = bool(flag)
                if self.y_auto_center_x:
                    self.y_limits_center_x = None
            elif subplot == "center_y":
                self.y_auto_center_y = bool(flag)
                if self.y_auto_center_y:
                    self.y_limits_center_y = None
            elif subplot == "amplitude":
                self.y_auto_amplitude = bool(flag)
                if self.y_auto_amplitude:
                    self.y_limits_amplitude = None
        except Exception:
            pass

    def set_y_limits(self, ymin: float, ymax: float, subplot: str = "fwhm"):
        """Set fixed Y limits for the specified subplot.

        Parameters
        ----------
        ymin : float
            Minimum Y value.
        ymax : float
            Maximum Y value.
        subplot : str
            Which subplot to control: 'fwhm', 'center', 'center_x', 'center_y', or 'amplitude'.
        """
        try:
            yminf = float(ymin)
            ymaxf = float(ymax)
            if yminf >= ymaxf:
                return
            subplot = subplot.lower()
            if subplot == "fwhm":
                self.y_limits_fwhm = (yminf, ymaxf)
                self.y_auto_fwhm = False
            elif subplot == "center":
                self.y_limits_center = (yminf, ymaxf)
                self.y_auto_center = False
            elif subplot == "center_x":
                self.y_limits_center_x = (yminf, ymaxf)
                self.y_auto_center_x = False
            elif subplot == "center_y":
                self.y_limits_center_y = (yminf, ymaxf)
                self.y_auto_center_y = False
            elif subplot == "amplitude":
                self.y_limits_amplitude = (yminf, ymaxf)
                self.y_auto_amplitude = False
        except Exception:
            pass

    def clear_y_limits(self, subplot: str = "fwhm"):
        """Clear any fixed Y limits and enable auto-scaling for the specified subplot.
        
        Parameters
        ----------
        subplot : str
            Which subplot to control: 'fwhm', 'center', 'center_x', 'center_y', or 'amplitude'.
        """
        subplot = subplot.lower()
        if subplot == "fwhm":
            self.y_limits_fwhm = None
            self.y_auto_fwhm = True
        elif subplot == "center":
            self.y_limits_center = None
            self.y_auto_center = True
        elif subplot == "center_x":
            self.y_limits_center_x = None
            self.y_auto_center_x = True
        elif subplot == "center_y":
            self.y_limits_center_y = None
            self.y_auto_center_y = True
        elif subplot == "amplitude":
            self.y_limits_amplitude = None
            self.y_auto_amplitude = True

    def set_show_fwhm_subplot(self, flag: bool):
        """Enable or disable the FWHM subplot."""
        self._show_fwhm_subplot = bool(flag)

    def set_show_center_subplot(self, flag: bool):
        """Enable or disable the center subplot."""
        self._show_center_subplot = bool(flag)

    def set_show_amplitude_subplot(self, flag: bool):
        """Enable or disable the amplitude subplot."""
        self._show_amplitude_subplot = bool(flag)

    def set_split_center_xy(self, flag: bool):
        """Enable or disable splitting center into separate X and Y subplots."""
        self._split_center_xy = bool(flag)

    def set_use_pv_for_x(self, flag: bool, pv_name: str = ""):
        """Enable or disable PV mode for X-axis.
        
        Parameters
        ----------
        flag : bool
            True to use PV values for X-axis, False to use timestamps.
        pv_name : str
            EPICS PV name to read for X-axis values.
        """
        self._use_pv_for_x = bool(flag)
        if pv_name:
            self._pv_name = str(pv_name)

    def append_pv_data(self, is_x: bool, pv_value: float, fwhm: float, center: float = None, amplitude: float = None):
        """Append fit data with PV value instead of timestamp.
        
        Parameters
        ----------
        is_x : bool
            True for X projection, False for Y.
        pv_value : float
            PV value for X-axis.
        fwhm : float
            FWHM value.
        center : float, optional
            Center position.
        amplitude : float, optional
            Amplitude value.
        """
        try:
            if is_x:
                self.pv_history_fwhm_x.append((float(pv_value), float(fwhm)))
                if len(self.pv_history_fwhm_x) > self.max_history:
                    self.pv_history_fwhm_x = self.pv_history_fwhm_x[-self.max_history:]
                if center is not None:
                    self.pv_history_center_x.append((float(pv_value), float(center)))
                    if len(self.pv_history_center_x) > self.max_history:
                        self.pv_history_center_x = self.pv_history_center_x[-self.max_history:]
                if amplitude is not None:
                    self.pv_history_ampl_x.append((float(pv_value), float(amplitude)))
                    if len(self.pv_history_ampl_x) > self.max_history:
                        self.pv_history_ampl_x = self.pv_history_ampl_x[-self.max_history:]
            else:
                self.pv_history_fwhm_y.append((float(pv_value), float(fwhm)))
                if len(self.pv_history_fwhm_y) > self.max_history:
                    self.pv_history_fwhm_y = self.pv_history_fwhm_y[-self.max_history:]
                if center is not None:
                    self.pv_history_center_y.append((float(pv_value), float(center)))
                    if len(self.pv_history_center_y) > self.max_history:
                        self.pv_history_center_y = self.pv_history_center_y[-self.max_history:]
                if amplitude is not None:
                    self.pv_history_ampl_y.append((float(pv_value), float(amplitude)))
                    if len(self.pv_history_ampl_y) > self.max_history:
                        self.pv_history_ampl_y = self.pv_history_ampl_y[-self.max_history:]
        except Exception:
            pass

    def append_fwhm(self, is_x: bool, ts: float, fwhm: float, center: float = None, amplitude: float = None):
        """Append an externally-computed FWHM, center, and amplitude value into the widget's
        history list.

        Parameters
        ----------
        is_x : bool
            True for the X (horizontal) FWHM, False for Y (vertical).
        ts : float
            Unix timestamp (seconds) for the measurement.
        fwhm : float
            The FWHM value to append.
        center : float, optional
            The center position of the fit.
        amplitude : float, optional
            The amplitude of the fit.
        """
        try:
            if is_x:
                self.fit_history_x.append((ts, float(fwhm)))
                if len(self.fit_history_x) > self.max_history:
                    self.fit_history_x = self.fit_history_x[-self.max_history:]
                if center is not None:
                    self.center_history_x.append((ts, float(center)))
                    if len(self.center_history_x) > self.max_history:
                        self.center_history_x = self.center_history_x[-self.max_history:]
                if amplitude is not None:
                    self.ampl_history_x.append((ts, float(amplitude)))
                    if len(self.ampl_history_x) > self.max_history:
                        self.ampl_history_x = self.ampl_history_x[-self.max_history:]
            else:
                self.fit_history_y.append((ts, float(fwhm)))
                if len(self.fit_history_y) > self.max_history:
                    self.fit_history_y = self.fit_history_y[-self.max_history:]
                if center is not None:
                    self.center_history_y.append((ts, float(center)))
                    if len(self.center_history_y) > self.max_history:
                        self.center_history_y = self.center_history_y[-self.max_history:]
                if amplitude is not None:
                    self.ampl_history_y.append((ts, float(amplitude)))
                    if len(self.ampl_history_y) > self.max_history:
                        self.ampl_history_y = self.ampl_history_y[-self.max_history:]
        except Exception:
            pass

    def clear_history(self):
        """Clear stored fit histories for both X and Y."""
        self.fit_history_x = []
        self.fit_history_y = []
        self.center_history_x = []
        self.center_history_y = []
        self.ampl_history_x = []
        self.ampl_history_y = []
        self.pv_history_fwhm_x = []
        self.pv_history_fwhm_y = []
        self.pv_history_center_x = []
        self.pv_history_center_y = []
        self.pv_history_ampl_x = []
        self.pv_history_ampl_y = []

    def save_history(self, path=None):
        """Save history to JSON file. If path is None, use default in home dir."""
        try:
            if path is None:
                path = os.path.expanduser("~/.camviewer_plotpv_history.json")
            data = {
                "x": self.fit_history_x,
                "y": self.fit_history_y,
                "center_x": self.center_history_x,
                "center_y": self.center_history_y,
                "ampl_x": self.ampl_history_x,
                "ampl_y": self.ampl_history_y,
            }
            with open(path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def load_history(self, path=None, cap=None):
        """Load history from JSON file and append to current history.

        If `cap` is None, use `self.max_history`.
        """
        try:
            if cap is None:
                cap = self.max_history
            if path is None:
                path = os.path.expanduser("~/.camviewer_plotpv_history.json")
            if not os.path.exists(path):
                return
            with open(path, "r") as f:
                data = json.load(f)
            lx = data.get("x", [])
            ly = data.get("y", [])
            # Extend existing histories and cap length
            self.fit_history_x = (self.fit_history_x + lx)[-cap:]
            self.fit_history_y = (self.fit_history_y + ly)[-cap:]
        except Exception:
            pass

    def toggle_pause(self):
        """Toggle the recording pause state and return new state."""
        self._recording = not self._recording
        return self._recording

    def doResize(self, s=None):
        if s is None:
            s = self.size()
        self.hint = s
        self.updateGeometry()
        self.resize(s)

    def sizeHint(self):
        return self.hint

    def plotFit(self, ax, is_x, x, y, xmin, xmax, ymin, ymax):
        if self.gui.ui.radioGaussian.isChecked():
            if self.gui.ui.checkBoxConstant.isChecked():
                mod = GaussianModelWithBase()
            else:
                mod = GaussianModel()
            mod.set_param_hint("e2w", expr="1.699*fwhm")
        elif self.gui.ui.radioSG4.isChecked():
            mod = SG4Model(self.gui.ui.checkBoxConstant.isChecked())
        elif self.gui.ui.radioSG6.isChecked():
            mod = SG6Model(self.gui.ui.checkBoxConstant.isChecked())
        else:
            return  # Not sure how we manage to check nothing here?!?
        pars = mod.guess(y, x=x)
        out = mod.fit(y, pars, x=x)
        ax.plot(x, out.best_fit, "k-")
        t = min(out.best_fit)
        if t < ymin:
            ymin = t
        t = max(out.best_fit)
        if t > ymax:
            ymax = t
        # What do we have here?
        #     out.params['amplitude'].value is the amplitude.
        #     out.params['center'].value is the mean if is_x, and
        #         self.gui.image.shape[1] - 1 - out.params['center'].value otherwise.
        #     out.params['sigma'].value is the std deviation if Gaussian.
        #     out.params['width'].value is the width if Super Gaussian.
        #     out.params['fwhm'].value is the FWHM.
        #     out.params['e2w'].value is the 1/e^2 width.
        # All need to be scaled by self.gui.calib!
        fwhm = self.gui.calib * out.params["fwhm"].value
        e2w = self.gui.calib * out.params["e2w"].value
        center = self.gui.calib * out.params["center"].value
        amplitude = out.params["amplitude"].value
        # Record fit into this widget's history (timestamp in seconds)
        try:
            if self._recording:
                ts = time.time()
                if self.is_x:
                    self.fit_history_x.append((ts, float(fwhm)))
                    if len(self.fit_history_x) > self.max_history:
                        self.fit_history_x = self.fit_history_x[-self.max_history:]
                    self.center_history_x.append((ts, float(center)))
                    if len(self.center_history_x) > self.max_history:
                        self.center_history_x = self.center_history_x[-self.max_history:]
                    self.ampl_history_x.append((ts, float(amplitude)))
                    if len(self.ampl_history_x) > self.max_history:
                        self.ampl_history_x = self.ampl_history_x[-self.max_history:]
                else:
                    self.fit_history_y.append((ts, float(fwhm)))
                    if len(self.fit_history_y) > self.max_history:
                        self.fit_history_y = self.fit_history_y[-self.max_history:]
                    self.center_history_y.append((ts, float(center)))
                    if len(self.center_history_y) > self.max_history:
                        self.center_history_y = self.center_history_y[-self.max_history:]
                    self.ampl_history_y.append((ts, float(amplitude)))
                    if len(self.ampl_history_y) > self.max_history:
                        self.ampl_history_y = self.ampl_history_y[-self.max_history:]
        except Exception:
            pass
        if self.is_x:
            self.gui.ui.lineEditFWHMx.setText(self.gui.displayFormat % (fwhm))
            print("FWHMx:", fwhm)
            self.gui.ui.lineEdite2x.setText(self.gui.displayFormat % (e2w))
        else:
            self.gui.ui.lineEditFWHMy.setText(self.gui.displayFormat % (fwhm))
            print("FWHMy:", fwhm)
            self.gui.ui.lineEdite2y.setText(self.gui.displayFormat % (e2w))
        return (ymin, ymax)

    def plotLineout(
        self, ax, is_x, size, x, idx, xmin, xmax, ymin, ymax, marker, color
    ):
        if is_x:
            i = int(marker.y())
            if i < 0 or i >= size:
                return (ymin, ymax)
            y = self.gui.image[i, idx]
        else:
            i = int(marker.x())
            if i < 0 or i >= size:
                return (ymin, ymax)
            y = self.gui.image[idx, i]
        t = min(y)
        if t < ymin:
            ymin = t
        t = max(y)
        if t > ymax:
            ymax = t  
        ax.plot(x, y, "-", color=color)
        self.yplot = y
        return (ymin, ymax)

    # Make the image to display.  This should match the view size.
    def makeImage(self, xminR, xmaxR, yminR, ymaxR):
        if not self.isVisible():
            print("ProjWidget.makeImage: widget not visible yet")
            return (0, 100)
        rectZoom = self.gui.ui.display_image.arectZoom.oriented()  # image
        rectRoi = self.gui.ui.display_image.rectRoi.oriented()  # image
        if self.is_x:
            if param.orientation & 2:
                xidx = param.y_fwd
            else:
                xidx = param.x_fwd
            screen_start = rectZoom.x()
            screen_width = rectZoom.width()
            roi_start = rectRoi.x()
            roi_width = rectRoi.width()
            view_width = self.width()
            view_height = self.height()
            linelim = self.gui.image.shape[0]
            proj = self.gui.px
            ymin = xminR
            ymax = xmaxR
        else:
            if param.orientation & 2:
                xidx = param.x_rev
            else:
                xidx = param.y_rev
            screen_start = rectZoom.y()
            screen_width = rectZoom.height()
            roi_start = rectRoi.y()
            roi_width = rectRoi.height()
            view_width = self.height()
            view_height = self.width()
            linelim = self.gui.image.shape[1]
            proj = self.gui.py
            ymin = yminR
            ymax = ymaxR
        screen_end = screen_start + screen_width - 1
        roi_end = roi_start + roi_width - 1
        # Why 10?  Well... it's still small, and expecially when blown up, things
        # seem to be larger than this.  I'd like to believe that 1 would be OK though.
        # Allow some tolerance for layout timing differences. If the measured
        # screen_width differs substantially from the expected width derived
        # from the widget view width and current zoom, adjust to the expected
        # value rather than bailing out entirely. This avoids leaving the
        # Plot-PV window empty when layout hasn't stabilized yet.
        expected_width = view_width / max(1e-6, param.zoom)
        tol = max(10, 0.15 * expected_width)
        if abs(screen_width - expected_width) > tol:
            # Size mismatch between measured screen width and expected width.
            # This can happen during layout/resize timing races. Do not
            # bombard stdout with messages; proceed using the measured
            # screen_width (arectZoom) as the source of truth.
            pass
        # Figure out where the plot should be.
        if roi_start < 0:
            roi_start = 0
        if roi_end > len(proj) - 1:
            roi_end = len(proj) - 1
        roi_width = roi_end - roi_start + 1
        #
        # OK, where are we?
        #
        # We want to create a plot fits into view_width x view_height.
        # This covers the screen positions from screen_start to screen_end.
        # We have data from roi_start to roi_end.
        # The plot range should be mn to mx.
        #
        # Always render at widget's current pixel size and devicePixelRatio
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        target_px_w = max(1, int(self.width() * dpr))
        target_px_h = max(1, int(self.height() * dpr))
        fig = Figure(figsize=(target_px_w / 100.0, target_px_h / 100.0), dpi=100)
        canvas = FigureCanvas(fig)
        # Make the figure background transparent so the widget background
        # shows through instead of a white panel.
        try:
            fig.patch.set_alpha(0.0)
            fig.patch.set_facecolor("none")
        except Exception:
            try:
                fig.patch.set_facecolor("0.75")
            except Exception:
                pass
        # We want to display beteen roi_start and roi_end.  What fits though?
        if (
            roi_end < screen_start or screen_end < roi_start or roi_start == roi_end
        ):  # Nothing!!
            print(
                "ProjWidget.makeImage: empty projection window or ROI out of view",
                "roi_start=", roi_start,
                "roi_end=", roi_end,
                "screen_start=", screen_start,
                "screen_end=", screen_end,
            )
            canvas.draw()
            width, height = canvas.get_width_height()
            if self.is_x:
                img = QImage(canvas.buffer_rgba(), width, height, QImage.Format_RGBA8888)
            else:
                img = QImage(canvas.buffer_rgba(), height, width, QImage.Format_RGBA8888)
            try:
                img.setDevicePixelRatio(dpr)
            except Exception:
                pass
            self.image = img
            self.update()
            return (ymin, ymax)
        # Cut a little off the ends if needed, scale and pad appropriately.
        if xidx[0] < xidx[1]:
            xmin = screen_start if screen_start > roi_start else roi_start
            xmax = screen_end if screen_end < roi_end else roi_end
            scale = (xmax - xmin) / float(screen_width)
            pad = (
                0
                if screen_start >= xmin
                else (xmin - screen_start) / float(screen_width)
            )
        else:
            xmin = len(proj) - 1 - (screen_end if screen_end < roi_end else roi_end)
            xmax = (
                len(proj)
                - 1
                - (screen_start if screen_start > roi_start else roi_start)
            )
            scale = (xmax - xmin) / float(screen_width)
            pad = (
                0
                if screen_end <= roi_end
                else (screen_end - roi_end) / float(screen_width)
            )
        # If requested, reserve a small area at the bottom for the fit-history plot
        # Show history area if enabled and any history exists (either X or Y)
        hist_exists = (len(self.fit_history_x) + len(self.fit_history_y)) > 0
        hist_ratio = 0.25 if (self._show_history and hist_exists) else 0.0
        ax = fig.add_axes([pad, hist_ratio, scale, 1 - hist_ratio])
        try:
            ax.set_facecolor("none")
        except Exception:
            pass
        # Turn off borders and the axis labels for the projection axes.
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        idx = np.logical_and(xidx >= xmin, xidx <= xmax)
        x = xidx[idx]
        y = proj[idx]

        # If we're in history-only mode, compute fits (to populate history)
        # but do not draw the projection/lineout. Instead draw only the
        # history subplot occupying the full canvas.
        if self._show_only_history:
            # Possibly compute a fit so plotFit appends to history
            yplot = None
            if self.gui.ui.checkBoxProjRoi.isChecked():
                yplot = y
            if self.gui.ui.checkBoxFits.isChecked() and yplot is not None:
                # If external fits are enabled, do not perform a local fit here;
                # the main window is responsible for computing and supplying
                # FWHM values via `append_fwhm`.
                if not getattr(self, "_use_external_fits", False):
                    try:
                        # Use a temporary axes to compute the fit without affecting
                        # the main figure. plotFit appends to history and updates UI fields.
                        fig_tmp = Figure()
                        ax_tmp = fig_tmp.add_subplot(111)
                        try:
                            (ymin, ymax) = self.plotFit(
                                ax_tmp, self.is_x, x, yplot, xmin, xmax, ymin, ymax
                            )
                        except Exception:
                            pass
                    except Exception:
                        pass

            # Now render only the history on the main figure canvas
            # Draw up to three subplots: FWHM, center, amplitude
            try:
                # Check which histories have data and are enabled
                # Consider both time-based and PV-based histories
                if self._use_pv_for_x:
                    hist_exists = (len(self.pv_history_fwhm_x) + len(self.pv_history_fwhm_y)) > 0 and self._show_fwhm_subplot
                    center_exists = (len(self.pv_history_center_x) + len(self.pv_history_center_y)) > 0 and self._show_center_subplot
                    center_x_exists = len(self.pv_history_center_x) > 0 and self._show_center_subplot
                    center_y_exists = len(self.pv_history_center_y) > 0 and self._show_center_subplot
                    ampl_exists = (len(self.pv_history_ampl_x) + len(self.pv_history_ampl_y)) > 0 and self._show_amplitude_subplot
                else:
                    hist_exists = (len(self.fit_history_x) + len(self.fit_history_y)) > 0 and self._show_fwhm_subplot
                    center_exists = (len(self.center_history_x) + len(self.center_history_y)) > 0 and self._show_center_subplot
                    center_x_exists = len(self.center_history_x) > 0 and self._show_center_subplot
                    center_y_exists = len(self.center_history_y) > 0 and self._show_center_subplot
                    ampl_exists = (len(self.ampl_history_x) + len(self.ampl_history_y)) > 0 and self._show_amplitude_subplot
                
                # Calculate number of subplots based on split_center_xy setting
                if self._split_center_xy and center_exists:
                    n_subplots = sum([hist_exists, center_x_exists, center_y_exists, ampl_exists])
                else:
                    n_subplots = sum([hist_exists, center_exists, ampl_exists])
                if n_subplots == 0:
                    # No data, skip plotting
                    pass
                else:
                    # Dynamically size subplots based on how many are shown
                    total_height = 0.88  # available height (0.08 bottom margin + 0.88 plot area)
                    individual_height = (total_height - 0.04 * (n_subplots - 1)) / n_subplots  # small gap between subplots
                    subplot_idx = 0
                    
                    # FWHM subplot (top)
                    if hist_exists:
                        bottom = 0.08 + (n_subplots - 1 - subplot_idx) * (individual_height + 0.04)
                        ax_hist = fig.add_axes([0.08, bottom, 0.85, individual_height])
                        try:
                            ax_hist.set_facecolor("none")
                        except Exception:
                            pass
                        # Use PV data if PV mode is enabled, otherwise use time data
                        if self._use_pv_for_x:
                            tx = [pv for (pv, v) in self.pv_history_fwhm_x]
                            vx = [v for (pv, v) in self.pv_history_fwhm_x]
                            ty = [pv for (pv, v) in self.pv_history_fwhm_y]
                            vy = [v for (pv, v) in self.pv_history_fwhm_y]
                        else:
                            tx = [datetime.fromtimestamp(t) for (t, v) in self.fit_history_x]
                            vx = [v for (t, v) in self.fit_history_x]
                            ty = [datetime.fromtimestamp(t) for (t, v) in self.fit_history_y]
                            vy = [v for (t, v) in self.fit_history_y]
                        if len(tx) > 0:
                            ax_hist.plot(tx, vx, "-o", markersize=3, label="FWHM X", color="#1f77b4")
                        if len(ty) > 0:
                            ax_hist.plot(ty, vy, "-o", markersize=3, label="FWHM Y", color="#ff7f0e")
                        ax_hist.set_ylabel("FWHM", fontsize=9)
                        ax_hist.spines["top"].set_visible(False)
                        ax_hist.spines["right"].set_visible(False)
                        if not self._use_pv_for_x:
                            ax_hist.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                        else:
                            ax_hist.set_xlabel(self._pv_name if self._pv_name else "PV Value", fontsize=8)
                        for lbl in ax_hist.get_xticklabels():
                            lbl.set_rotation(25)
                            lbl.set_fontsize(8)
                        ax_hist.tick_params(axis="y", labelsize=8)
                        # Apply Y limits if set
                        if self.y_limits_fwhm is not None and not self.y_auto_fwhm:
                            ax_hist.set_ylim(self.y_limits_fwhm)
                        handles, labels = ax_hist.get_legend_handles_labels()
                        if labels:
                            ax_hist.legend(loc="upper right", fontsize="small", frameon=False)
                        subplot_idx += 1
                    
                    # Center subplot (middle)
                    if center_exists:
                        if self._split_center_xy:
                            # Plot Center X and Center Y on separate subplots
                            if center_x_exists:
                                bottom = 0.08 + (n_subplots - 1 - subplot_idx) * (individual_height + 0.04)
                                ax_center_x = fig.add_axes([0.08, bottom, 0.85, individual_height])
                                try:
                                    ax_center_x.set_facecolor("none")
                                except Exception:
                                    pass
                                # Use PV data if PV mode is enabled, otherwise use time data
                                if self._use_pv_for_x:
                                    tx = [pv for (pv, v) in self.pv_history_center_x]
                                    cx = [v for (pv, v) in self.pv_history_center_x]
                                else:
                                    tx = [datetime.fromtimestamp(t) for (t, v) in self.center_history_x]
                                    cx = [v for (t, v) in self.center_history_x]
                                ax_center_x.plot(tx, cx, "-o", markersize=3, label="Center X", color="#2ca02c")
                                ax_center_x.set_ylabel("Center X", fontsize=9)
                                ax_center_x.spines["top"].set_visible(False)
                                ax_center_x.spines["right"].set_visible(False)
                                if not self._use_pv_for_x:
                                    ax_center_x.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                                else:
                                    ax_center_x.set_xlabel(self._pv_name if self._pv_name else "PV Value", fontsize=8)
                                for lbl in ax_center_x.get_xticklabels():
                                    lbl.set_rotation(25)
                                    lbl.set_fontsize(8)
                                ax_center_x.tick_params(axis="y", labelsize=8)
                                # Apply Y limits if set
                                if self.y_limits_center_x is not None and not self.y_auto_center_x:
                                    ax_center_x.set_ylim(self.y_limits_center_x)
                                handles, labels = ax_center_x.get_legend_handles_labels()
                                if labels:
                                    ax_center_x.legend(loc="upper right", fontsize="small", frameon=False)
                                subplot_idx += 1
                            
                            if center_y_exists:
                                bottom = 0.08 + (n_subplots - 1 - subplot_idx) * (individual_height + 0.04)
                                ax_center_y = fig.add_axes([0.08, bottom, 0.85, individual_height])
                                try:
                                    ax_center_y.set_facecolor("none")
                                except Exception:
                                    pass
                                # Use PV data if PV mode is enabled, otherwise use time data
                                if self._use_pv_for_x:
                                    ty = [pv for (pv, v) in self.pv_history_center_y]
                                    cy = [v for (pv, v) in self.pv_history_center_y]
                                else:
                                    ty = [datetime.fromtimestamp(t) for (t, v) in self.center_history_y]
                                    cy = [v for (t, v) in self.center_history_y]
                                ax_center_y.plot(ty, cy, "-o", markersize=3, label="Center Y", color="#d62728")
                                ax_center_y.set_ylabel("Center Y", fontsize=9)
                                ax_center_y.spines["top"].set_visible(False)
                                ax_center_y.spines["right"].set_visible(False)
                                if not self._use_pv_for_x:
                                    ax_center_y.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                                else:
                                    ax_center_y.set_xlabel(self._pv_name if self._pv_name else "PV Value", fontsize=8)
                                for lbl in ax_center_y.get_xticklabels():
                                    lbl.set_rotation(25)
                                    lbl.set_fontsize(8)
                                ax_center_y.tick_params(axis="y", labelsize=8)
                                # Apply Y limits if set
                                if self.y_limits_center_y is not None and not self.y_auto_center_y:
                                    ax_center_y.set_ylim(self.y_limits_center_y)
                                handles, labels = ax_center_y.get_legend_handles_labels()
                                if labels:
                                    ax_center_y.legend(loc="upper right", fontsize="small", frameon=False)
                                subplot_idx += 1
                        else:
                            # Combined Center subplot (original behavior)
                            bottom = 0.08 + (n_subplots - 1 - subplot_idx) * (individual_height + 0.04)
                            ax_center = fig.add_axes([0.08, bottom, 0.85, individual_height])
                            try:
                                ax_center.set_facecolor("none")
                            except Exception:
                                pass
                            # Use PV data if PV mode is enabled, otherwise use time data
                            if self._use_pv_for_x:
                                tx = [pv for (pv, v) in self.pv_history_center_x]
                                cx = [v for (pv, v) in self.pv_history_center_x]
                                ty = [pv for (pv, v) in self.pv_history_center_y]
                                cy = [v for (pv, v) in self.pv_history_center_y]
                            else:
                                tx = [datetime.fromtimestamp(t) for (t, v) in self.center_history_x]
                                cx = [v for (t, v) in self.center_history_x]
                                ty = [datetime.fromtimestamp(t) for (t, v) in self.center_history_y]
                                cy = [v for (t, v) in self.center_history_y]
                            if len(tx) > 0:
                                ax_center.plot(tx, cx, "-o", markersize=3, label="Center X", color="#2ca02c")
                            if len(ty) > 0:
                                ax_center.plot(ty, cy, "-o", markersize=3, label="Center Y", color="#d62728")
                            ax_center.set_ylabel("Center", fontsize=9)
                            ax_center.spines["top"].set_visible(False)
                            ax_center.spines["right"].set_visible(False)
                            if not self._use_pv_for_x:
                                ax_center.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                            else:
                                ax_center.set_xlabel(self._pv_name if self._pv_name else "PV Value", fontsize=8)
                            for lbl in ax_center.get_xticklabels():
                                lbl.set_rotation(25)
                                lbl.set_fontsize(8)
                            ax_center.tick_params(axis="y", labelsize=8)
                            # Apply Y limits if set
                            if self.y_limits_center is not None and not self.y_auto_center:
                                ax_center.set_ylim(self.y_limits_center)
                            handles, labels = ax_center.get_legend_handles_labels()
                            if labels:
                                ax_center.legend(loc="upper right", fontsize="small", frameon=False)
                            subplot_idx += 1
                    
                    # Amplitude subplot (bottom)
                    if ampl_exists:
                        bottom = 0.08 + (n_subplots - 1 - subplot_idx) * (individual_height + 0.04)
                        ax_ampl = fig.add_axes([0.08, bottom, 0.85, individual_height])
                        try:
                            ax_ampl.set_facecolor("none")
                        except Exception:
                            pass
                        # Use PV data if PV mode is enabled, otherwise use time data
                        if self._use_pv_for_x:
                            tx = [pv for (pv, v) in self.pv_history_ampl_x]
                            ax_vals = [v for (pv, v) in self.pv_history_ampl_x]
                            ty = [pv for (pv, v) in self.pv_history_ampl_y]
                            ay = [v for (pv, v) in self.pv_history_ampl_y]
                        else:
                            tx = [datetime.fromtimestamp(t) for (t, v) in self.ampl_history_x]
                            ax_vals = [v for (t, v) in self.ampl_history_x]
                            ty = [datetime.fromtimestamp(t) for (t, v) in self.ampl_history_y]
                            ay = [v for (t, v) in self.ampl_history_y]
                        if len(tx) > 0:
                            ax_ampl.plot(tx, ax_vals, "-o", markersize=3, label="Amplitude X", color="#9467bd")
                        if len(ty) > 0:
                            ax_ampl.plot(ty, ay, "-o", markersize=3, label="Amplitude Y", color="#8c564b")
                        ax_ampl.set_ylabel("Amplitude", fontsize=9)
                        ax_ampl.spines["top"].set_visible(False)
                        ax_ampl.spines["right"].set_visible(False)
                        if not self._use_pv_for_x:
                            ax_ampl.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                        else:
                            ax_ampl.set_xlabel(self._pv_name if self._pv_name else "PV Value", fontsize=8)
                        for lbl in ax_ampl.get_xticklabels():
                            lbl.set_rotation(25)
                            lbl.set_fontsize(8)
                        ax_ampl.tick_params(axis="y", labelsize=8)
                        # Apply Y limits if set
                        if self.y_limits_amplitude is not None and not self.y_auto_amplitude:
                            ax_ampl.set_ylim(self.y_limits_amplitude)
                        handles, labels = ax_ampl.get_legend_handles_labels()
                        if labels:
                            ax_ampl.legend(loc="upper right", fontsize="small", frameon=False)
                        subplot_idx += 1
            except Exception:
                pass

            canvas.draw()
            width, height = canvas.get_width_height()
            img = QImage(canvas.buffer_rgba(), width, height, QImage.Format_RGBA8888)
            try:
                img.setDevicePixelRatio(dpr)
            except Exception:
                pass
            # For history-only mode, do not rotate the image; present it as-is
            self.image = img
            self.update()
            return (ymin, ymax)

        # MCB - The past, as they say, is prologue.  So what do we have here?
        #     ax   - A matplotlib Axes.
        #     x    - A np array of pixel coordinates, in the oriented frame.
        #     y    - A np array of projection sums, in the oriented frame.
        #     self.gui.image - A np array containing the most recent full image, oriented.
        #     xmin, xmax, ymin, ymax - The limits of the plot.
        #
        # At this point, we should plot whatever we want to plot and fit whatever
        # we want to fit.

        self.yplot = None
        for (ii, cb) in enumerate(self.lineout_cbs):
            if cb.isChecked():
                (ymin, ymax) = self.plotLineout(
                    ax,
                    self.is_x,
                    linelim,
                    x,
                    idx,
                    xmin,
                    xmax,
                    ymin,
                    ymax,
                    self.gui.ui.display_image.lMarker[ii].oriented(),
                    self.gui.ui.display_image.lPenColor[ii],
                )
        if self.gui.ui.checkBoxProjRoi.isChecked():
            ax.plot(x, y, "g-")
            self.yplot = y
        if self.gui.ui.checkBoxFits.isChecked() and self.yplot is not None:
            if not getattr(self, "_use_external_fits", False):
                (ymin, ymax) = self.plotFit(
                    ax, self.is_x, x, self.yplot, xmin, xmax, ymin, ymax
                )
            else:
                # External-fit mode: do not recompute fits here.
                pass

        # If we have history enabled, draw it in a small subplot beneath the projection
        if hist_ratio > 0.0:
            try:
                # plot both X and Y histories (if present) with different colors
                hx = self.fit_history_x
                hy = self.fit_history_y
                if len(hx) == 0 and len(hy) == 0:
                    # nothing to draw
                    pass
                else:
                    # Reserve a little left/right margin so labels don't clip.
                    ax_hist = fig.add_axes([pad, 0, scale, hist_ratio])
                    try:
                        ax_hist.set_facecolor("none")
                    except Exception:
                        pass
                    try:
                        # nudge the axis into a slightly inset position so
                        # the x tick labels have room.
                        left = max(pad + 0.02, 0.02)
                        width = max(scale - 0.04, 0.1)
                        bottom = 0.02
                        height = max(hist_ratio - 0.02, 0.05)
                        ax_hist.set_position([left, bottom, width, height])
                    except Exception:
                        pass
                    # Convert timestamps to datetimes
                    tx = [datetime.fromtimestamp(t) for (t, v) in hx]
                    vx = [v for (t, v) in hx]
                    ty = [datetime.fromtimestamp(t) for (t, v) in hy]
                    vy = [v for (t, v) in hy]
                    # Choose colors
                    try:
                        ax_hist.plot(tx, vx, "-o", markersize=3, label="FWHM X", color="#1f77b4")
                    except Exception:
                        pass
                    try:
                        ax_hist.plot(ty, vy, "-o", markersize=3, label="FWHM Y", color="#ff7f0e")
                    except Exception:
                        pass
                    ax_hist.set_ylabel("FWHM")
                    # minimal styling: turn off top/right spines
                    ax_hist.spines["top"].set_visible(False)
                    ax_hist.spines["right"].set_visible(False)
                    # format x-axis with human-readable times
                    ax_hist.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                    # tighten y-limits a little based on both series
                    try:
                        if self.y_limits is not None and not self.y_auto:
                            ymin_h, ymax_h = self.y_limits
                            ax_hist.set_ylim([ymin_h, ymax_h])
                        else:
                            all_vals = []
                            if len(vx) > 0:
                                all_vals.extend(vx)
                            if len(vy) > 0:
                                all_vals.extend(vy)
                            if len(all_vals) > 0:
                                ymin_h = min(all_vals)
                                ymax_h = max(all_vals)
                                if ymin_h == ymax_h:
                                    ymin_h -= 0.5
                                    ymax_h += 0.5
                                ax_hist.set_ylim([ymin_h, ymax_h])
                    except Exception:
                        pass
                    # rotate labels slightly and reduce font size for small windows
                    for lbl in ax_hist.get_xticklabels():
                        lbl.set_rotation(25)
                        try:
                            lbl.set_fontsize(8)
                        except Exception:
                            pass
                    try:
                        ax_hist.tick_params(axis="y", labelsize=8)
                    except Exception:
                        pass
                    # legend
                    try:
                        handles, labels = ax_hist.get_legend_handles_labels()
                        if labels:
                            ax_hist.legend(
                                loc="upper left",
                                fontsize="small",
                                frameon=False,
                                bbox_to_anchor=(1.0, 1.0),
                            )
                    except Exception:
                        pass
            except Exception:
                pass

        # MCB - End of plotting.

        # Crop the plot appropriately, and send it off to be displayed.
        ax.set_xlim([xmin, xmax])
        ax.set_ylim([ymin, ymax])
        canvas.draw()
        width, height = canvas.get_width_height()
        img = QImage(canvas.buffer_rgba(), width, height, QImage.Format_RGBA8888)
        try:
            img.setDevicePixelRatio(dpr)
        except Exception:
            pass
        try:
            if self.is_x:
                img2 = img
            else:
                img2 = img.transformed(QTransform().rotate(-90))
            self.image = img2
        except Exception:
            if self.is_x:
                self.image = img
            else:
                self.image = img.transformed(QTransform().rotate(-90))
        self.update()
        return (ymin, ymax)

    def paintEvent(self, event):
        if self.image is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if self.image:
            painter.drawImage(self.rect(), self.image)
        else:
            painter.fillRect(self.rect(), Qt.white)
        painter.end()
