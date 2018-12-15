from PyQt4 import QtCore
from PyQt4.QtGui import *
from PyQt4.QtCore import QTimer, Qt, QPoint, QPointF, QSize, QRectF, QObject
import param

#
# This is viewwidth by projsize!
#
class ProjH(QWidget):
  def __init__(self, parent):
    QWidget.__init__(self, parent)
    gui = parent
    x = gui.parentWidget()
    while x != None:
      gui = x
      x = gui.parentWidget()
    self.gui = gui
    self.hint = self.size()

  def doResize(self, s=None):
    if s == None:
      s = self.size()
    self.hint = s
    self.updateGeometry()
    self.resize(s)

  def sizeHint(self):
    return self.hint

  def paintEvent(self, event):
    if not self.gui.ui.checkBoxProjRoi.isChecked():
      return
            
    painter = QPainter(self)        
    rectZoom  = self.gui.ui.display_image.arectZoom.oriented()            # image
    rectProj = QRectF(rectZoom.x() + param.xpad_oriented(),
                      0,
                      self.width() / param.zoom,
                      self.gui.imageProjX.height())                       # image
    rectImage = QRectF( 0, 0, self.width(), self.height())                # screen
    # Draw rectProj portion of image into rectImage on the screen
    painter.drawImage(rectImage, self.gui.imageProjX, rectProj)   
