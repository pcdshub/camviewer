from PyQt4 import QtCore
from PyQt4.QtGui import *
from PyQt4.QtCore import QTimer, Qt, QPoint, QPointF, QSize, QRectF, QObject

#
# This is projsize by viewheight
#
class ProjV(QWidget):
  def __init__(self, parent):
    QWidget.__init__(self, parent)
    gui = parent
    x = gui.parentWidget()
    while x != None:
      gui = x
      x = gui.parentWidget()
    self.gui = gui
    self.center = QPointF(self.width()/2, self.height()/2)         # screen
    self.negcenter = QPointF(-self.height()/2, -self.width()/2)     # screen
    self.font   = QFont("Times New Roman", 10, QFont.Bold)
    self.penProjMarker \
                = QPen(Qt.black, 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin)    

  def setImageSize(self, reset=True):
    self.center = QPointF(self.width()/2, self.height()/2)     # screen
    self.negcenter = QPointF(-self.height()/2, -self.width()/2) # screen

  def paintEvent(self, event):
    if not( 
      self.gui.ui.checkBoxProjLine1.isChecked() or self.gui.ui.checkBoxProjLine2.isChecked() or
      self.gui.ui.checkBoxProjLine3.isChecked() or self.gui.ui.checkBoxProjLine4.isChecked() or
      self.gui.ui.checkBoxProjRoi.isChecked() ):
      return
      
    painter = QPainter(self)        
    rectZoom  = self.gui.ui.display_image.arectZoom                               # image
    if self.gui.isportrait:
      painter.translate(self.center)    
      painter.scale(-1,1)
      painter.rotate(90)
      painter.translate(self.negcenter)
      rectProj = QRectF(rectZoom.x() + self.gui.xpad,
                        0,
                        self.height() / self.gui.zoom,
                        self.gui.imageProjX.height())                       # image
      rectImage = QRectF( 0, 0, self.height(), self.width())                # screen
      # Draw rectProj portion of image into rectImage
      painter.drawImage(rectImage, self.gui.imageProjX, rectProj)
    else:
      rectProj  = QRectF( 0,
                          rectZoom.y() + self.gui.ypad,
                          self.gui.imageProjY.width(),
                          self.height() / self.gui.zoom)                       # image
      rectImage = QRectF( 0, 0, self.width(), self.height())                   # screen
      painter.drawImage(rectImage, self.gui.imageProjY, rectProj)      

    #draw marker lines      
    rectZoom      = self.gui.ui.display_image.arectZoom      
    rectImage     = self.gui.ui.display_image.rectImage
    fZoomRatio    = self.gui.zoom
    lbProjChecked = [ self.gui.ui.checkBoxProjLine1.isChecked(), self.gui.ui.checkBoxProjLine2.isChecked(),      
      self.gui.ui.checkBoxProjLine3.isChecked(), self.gui.ui.checkBoxProjLine4.isChecked() ]    
    lPenProj      = self.gui.ui.display_image.lPenProj        
    for (iMarker, ptMarker) in enumerate(self.gui.ui.display_image.lMarker):
      markerImage = (ptMarker - rectZoom.topLeft()) * fZoomRatio + rectImage.topLeft()              
      if lbProjChecked[iMarker]:
        painter.setPen(lPenProj[iMarker])
        if self.gui.isportrait:
          painter.drawLine(markerImage.x(), 0, markerImage.x(), self.width()-1)
        else:
          painter.drawLine(0,markerImage.y(), self.width()-1, markerImage.y())        
      
    #draw projection marker lines      
    painter.setPen(self.penProjMarker)
    for (iMarker, ptMarker) in enumerate(self.gui.lProjMarker):
      projMarker = (ptMarker - rectZoom.topLeft()) * fZoomRatio + rectImage.topLeft()              
      if self.gui.isportrait:
        painter.drawLine(projMarker.x(), 0, projMarker.x(), self.width()-1)
      else:
        painter.drawLine(0,projMarker.y(), self.width()-1, projMarker.y())        
             
    #draw projection marker labels    
    painter.resetTransform()        
    painter.setFont(self.font)    
    for (iMarker, ptMarker) in enumerate(self.gui.lProjMarker):
      projMarker = (ptMarker - rectZoom.topLeft()) * fZoomRatio + rectImage.topLeft()              
      if self.gui.isportrait:
        painter.drawText( QPoint(0, projMarker.x() ), "%d" % (iMarker+1) )
      else:
        painter.drawText( QPoint(0, projMarker.y() ), "%d" % (iMarker+1) )
        
    #painter.resetTransform()    
    #painter.setFont (self.font)
    #painter.drawText( QPoint(0,20), "Test" )      
    
  def mousePressEvent(self, event):  
    if self.gui.isportrait:
      posx = event.y() 
      posy = self.width() - event.x()
    else:
      posx = event.x()
      posy = event.y()

    rectImage = self.gui.ui.display_image.rectImage
    rectZoom  = self.gui.ui.display_image.arectZoom
    imgx = ( posx - rectImage.x() ) * (rectZoom.width() / rectImage.width()) + rectZoom.x()
    imgy = ( posy - rectImage.y() ) * (rectZoom.height() / rectImage.height()) + rectZoom.y()
                      
    if self.gui.iProjMouseVmode >= 1 and self.gui.iProjMouseVmode <= 4:      
      if self.gui.isportrait:
        self.gui.lProjMarker[self.gui.iProjMouseVmode-1].setX(imgx)
      else:
        self.gui.lProjMarker[self.gui.iProjMouseVmode-1].setY(imgy)    
      self.gui.updateVmarkerText()
      
    self.update()      
    
  def mouseMoveEvent(self, event):
    if not ( event.buttons() & Qt.LeftButton ):
      return
      
    if self.gui.isportrait:
      posx = event.y() 
      posy = self.width() - event.x() 
    else:
      posx = event.x()
      posy = event.y()

    rectImage = self.gui.ui.display_image.rectImage
    rectZoom  = self.gui.ui.display_image.arectZoom
    imgx = ( posx - rectImage.x() ) * (rectZoom.width() / rectImage.width()) + rectZoom.x()
    imgy = ( posy - rectImage.y() ) * (rectZoom.height() / rectImage.height()) + rectZoom.y()

    if self.gui.iProjMouseVmode >= 1 and self.gui.iProjMouseVmode <= 4:      
      if self.gui.isportrait:
        self.gui.lProjMarker[self.gui.iProjMouseVmode-1].setX(imgx)
      else:
        self.gui.lProjMarker[self.gui.iProjMouseVmode-1].setY(imgy)    
      self.gui.updateVmarkerText()
      
    self.update()      
