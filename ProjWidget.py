from PyQt5.QtGui import QImage, QTransform, QPainter
from PyQt5.QtCore import QRectF
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

    @property
    def lineout_cbs(self):
        """
        Load these later instead of in init in case they aren't created yet
        """
        self.lineout_cbs = [
            self.gui.ui.checkBoxM1Lineout,
            self.gui.ui.checkBoxM2Lineout,
            self.gui.ui.checkBoxM3Lineout,
            self.gui.ui.checkBoxM4Lineout,
        ]

    def set_x(self):
        self.is_x = True

    def set_y(self):
        self.is_x = False

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
        if self.is_x:
            self.gui.ui.lineEditFWHMx.setText(self.gui.displayFormat % (fwhm))
            self.gui.ui.lineEdite2x.setText(self.gui.displayFormat % (e2w))
        else:
            self.gui.ui.lineEditFWHMy.setText(self.gui.displayFormat % (fwhm))
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
        if abs(screen_width - view_width / param.zoom) > 10:
            self.image = None
            return (
                ymin,
                ymax,
            )  # This happens when things are adjusting.  Just skip for now.
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
        fig = Figure(figsize=(view_width / 100.0, view_height / 100.0), dpi=100)
        canvas = FigureCanvas(fig)
        fig.patch.set_facecolor("0.75")  # Qt5 defaults to white!!
        # We want to display beteen roi_start and roi_end.  What fits though?
        if (
            roi_end < screen_start or screen_end < roi_start or roi_start == roi_end
        ):  # Nothing!!
            canvas.draw()
            width, height = canvas.get_width_height()
            if self.is_x:
                self.image = QImage(
                    canvas.buffer_rgba(), width, height, QImage.Format_RGBA8888
                )
            else:
                self.image = QImage(
                    canvas.buffer_rgba(), height, width, QImage.Format_RGBA8888
                )
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
        ax = fig.add_axes([pad, 0, scale, 1])
        # Turn off borders and the axis labels.
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        idx = np.logical_and(xidx >= xmin, xidx <= xmax)
        x = xidx[idx]
        y = proj[idx]

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
            (ymin, ymax) = self.plotFit(
                ax, self.is_x, x, self.yplot, xmin, xmax, ymin, ymax
            )

        # MCB - End of plotting.

        # Crop the plot appropriately, and send it off to be displayed.
        ax.set_xlim([xmin, xmax])
        ax.set_ylim([ymin, ymax])
        canvas.draw()
        width, height = canvas.get_width_height()
        img = QImage(canvas.buffer_rgba(), width, height, QImage.Format_RGBA8888)
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
        w = self.width()
        h = self.height()
        rectImage = QRectF(0, 0, w, h)  # screen
        painter.drawImage(rectImage, self.image)
