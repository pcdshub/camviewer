from PyQt4 import QtCore
from PyQt4.QtGui import *
from PyQt4.QtCore import QTimer, Qt, QPoint, QPointF, QSize, QRectF, QObject
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
    rectZoom  = self.gui.ui.display_image.arectZoom.oriented()            # image
    if self.is_x:
      if param.orientation & 2:
        xidx = param.y_fwd
      else:
        xidx = param.x_fwd
      screen_start = rectZoom.x()
      screen_width = rectZoom.width()
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
      view_width   = self.height()
      view_height  = self.width()
      proj = self.gui.py
      ymin = yminR
      ymax = ymaxR
    screen_end = screen_start + screen_width
    if abs(screen_width - view_width / param.zoom) > 1:
      self.image = None
      return   # This happens when things are adjusting.  Just skip for now.

    # 
    # OK, where are we?
    #
    # We want to create a plot that is view_width x view_height.
    # This covers the screen positions from screen_start to screen_start + screen_width - 1.
    # The actual range of data we have is from 0 to len(proj) - 1.
    # The plot range should be mn to mx.
    #
    fig = Figure(figsize=(view_width/100.0,view_height/100.0),dpi=100)
    canvas = FigureCanvas(fig)
    xmin = 0
    xmax = len(proj) - 1
    # What fits on the screen?
    if xmax < screen_start or xmin > screen_end: # Nothing!!
      canvas.draw()
      width, height = canvas.get_width_height()
      if self.is_x:
        self.image = QImage(canvas.buffer_rgba(0, 0), width, height, QImage.Format_ARGB32)
      else:
        self.image = QImage(canvas.buffer_rgba(0, 0), height, width, QImage.Format_ARGB32)
      self.update()
      return
    if xmin < screen_start:
      xmin = screen_start
    if xmax > screen_end:
      xmax = screen_end
    # Add our axis.
    # In both x and y cases, we need to scale to be the correct size.
    # The padding comes at opposite sides though... it's on the top for y!
    scale = (xmax - xmin) / float(screen_end - screen_start)
    if self.is_x:
      pad = 0 if screen_start >= 0 else -screen_start / float(screen_end - screen_start)
    else:
      pad = 0 if screen_end <= xmax else (screen_end - xmax) / float(screen_end - screen_start)
    ax = fig.add_axes([pad,0,scale,1])
    # Turn off borders and the axis labels.
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    # MCB - Add plotting, fitting etc. here!
    ax.plot(xidx, proj, 'g-')
    # MCB - End of plotting.

    # Crop the plot appropriately, and send it off to be displayed.
    ax.set_xlim([xmin, xmax])
    ax.set_ylim([ymin, ymax])
    canvas.draw()
    width, height = canvas.get_width_height()
    img = QImage(canvas.buffer_rgba(0, 0), width, height, QImage.Format_ARGB32)
    if self.is_x:
      self.image = img
    else:
      self.image = img.transformed(QMatrix().rotate(-90.0))
    self.update()

  def paintEvent(self, event):
    if self.image is None:
      return
    painter = QPainter(self)        
    rectImage = QRectF( 0, 0, self.width(), self.height())                # screen
    painter.drawImage(rectImage, self.image)
