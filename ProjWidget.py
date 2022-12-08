from PyQt5 import QtCore
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTimer, Qt, QPoint, QPointF, QSize, QRectF, QObject
import param
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

#
# If is_x, this is viewwidth by projsize, otherwise it is projsize by viewheight!
#
class ProjWidget(QWidget):
  def __init__(self, parent):
    QWidget.__init__(self, parent)
    gui = parent
    x = gui.parentWidget()
    while x != None:
      gui = x
      x = gui.parentWidget()
    self.gui = gui
    self.hint = self.size()
    self.is_x = True
    self.image = None

  def set_x(self):
    self.is_x = True

  def set_y(self):
    self.is_x = False

  def doResize(self, s=None):
    if s == None:
      s = self.size()
    self.hint = s
    self.updateGeometry()
    self.resize(s)

  def sizeHint(self):
    return self.hint

  # Make the image to display.  This should match the view size.
  def makeImage(self, xminR, xmaxR, yminR, ymaxR):
    if not self.isVisible():
      return
    rectZoom  = self.gui.ui.display_image.arectZoom.oriented()          # image
    rectRoi   = self.gui.ui.display_image.rectRoi.oriented()            # image
    if self.is_x:
      if param.orientation & 2:
        xidx = param.y_fwd
      else:
        xidx = param.x_fwd
      screen_start = rectZoom.x()
      screen_width = rectZoom.width()
      roi_start    = rectRoi.x()
      roi_width    = rectRoi.width()
      view_width   = self.width()
      view_height  = self.height()
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
      roi_start    = rectRoi.y()
      roi_width    = rectRoi.height()
      view_width   = self.height()
      view_height  = self.width()
      proj = self.gui.py
      ymin = yminR
      ymax = ymaxR
    screen_end = screen_start + screen_width - 1
    roi_end    = roi_start + roi_width - 1
    if abs(screen_width - view_width / param.zoom) > 1:
      self.image = None
      return   # This happens when things are adjusting.  Just skip for now.
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
    fig = Figure(figsize=(view_width/100.0,view_height/100.0),dpi=100)
    canvas = FigureCanvas(fig)
    fig.patch.set_facecolor('0.75')   # Qt5 defaults to white!!
    # We want to display beteen roi_start and roi_end.  What fits though?
    if roi_end < screen_start or screen_end < roi_start or roi_start == roi_end: # Nothing!!
      canvas.draw()
      width, height = canvas.get_width_height()
      if self.is_x:
        self.image = QImage(canvas.buffer_rgba(), width, height, QImage.Format_RGBA8888)
      else:
        self.image = QImage(canvas.buffer_rgba(), height, width, QImage.Format_RGBA8888)
      self.update()
      return
    # Cut a little off the ends if needed, scale and pad appropriately.
    if xidx[0] < xidx[-1]:
      xmin = screen_start if screen_start > roi_start else roi_start
      xmax = screen_end if screen_end < roi_end else roi_end
      scale = (xmax - xmin) / float(screen_width)
      pad = 0 if screen_start >= xmin else (xmin - screen_start) / float(screen_width)
    else:
      xmin = len(proj) - 1 - (screen_end if screen_end < roi_end else roi_end)
      xmax = len(proj) - 1 - (screen_start if screen_start > roi_start else roi_start)
      scale = (xmax - xmin) / float(screen_width)
      pad = 0 if screen_end <= roi_end else (screen_end - roi_end) / float(screen_width)
    ax = fig.add_axes([pad,0,scale,1])
    # Turn off borders and the axis labels.
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    x = xidx[proj != 0]
    y = proj[proj != 0]

    # MCB - The past, as they say, is prologue.  So what do we have here?
    #     ax   - A matplotlib Axes.
    #     x    - A np array of pixel coordinates, in the oriented frame.
    #     y    - A np array of projection sums, in the oriented frame.
    #     self.gui.image - A np array containing the most recent full image, oriented.
    #     xmin, xmax, ymin, ymax - The limits of the plot.
    #
    # At this point, we should plot whatever we want to plot and fit whatever
    # we want to fit.

    ax.plot(x, y, 'g-')

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

  def paintEvent(self, event):
    if self.image is None:
      return
    painter = QPainter(self)
    w = self.width()
    h = self.height()
    rectImage = QRectF(0, 0, w, h)            # screen
    painter.drawImage(rectImage, self.image)
