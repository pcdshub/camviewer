from PyQt4 import QtCore
from PyQt4.QtGui import *
from PyQt4.QtCore import QTimer, Qt, QPoint, QPointF, QSize, QRectF, QObject

# Comments are whether we are in image or screen coordinates.
class DisplayImage(QWidget):
  def __init__(self, parent):
    QWidget.__init__(self, parent)
    gui = parent
    x = gui.parentWidget()
    while x != None:
      gui = x
      x = gui.parentWidget()
    self.gui = gui
    self.hint         = QSize(self.gui.viewwidth, self.gui.viewheight)
    self.retry        = False
    self.pcnt         = 0
    size              = QSize(self.gui.x, self.gui.y)
    self.image        = QImage(size, QImage.Format_RGB32)
    self.image.fill(0)
    self.center       = QPointF(self.width()/2, self.height()/2)    # true screen
    self.negcenter    = QPointF(-self.height()/2, -self.width()/2)  # true screen
    self.rectZoom     = QRectF(0, 0, self.gui.x, self.gui.y)            # image
    self.arectZoom    = QRectF(0, 0, self.gui.x, self.gui.y)            # image
    self.rectRoi      = QRectF(self.rectZoom)                           # image
    self.paintevents  = 0
    self.xoff         = QPointF(20, 0)
    self.yoff         = QPointF(0, 20)
    self.setZoom()
    self.cursorPos    = QPointF(self.gui.x, self.gui.y)                 # image
    self.cursorMarker = QPointF(0,0)                                    # image
    self.setMouseTracking(True)
    self.rectImage = QRectF(0,0,size.width(),size.height())             # screen
    self.sWindowTitle = "Camera: None"

    # set marker data
    self.lMarker        = [ QPointF(-100, -100),                        # image
                            QPointF(self.gui.x + 100, -100),
                            QPointF(self.gui.x + 100, self.gui.y + 100),
                            QPointF(-100, self.gui.y + 100) ]
    self.lPenMarker     = [ QPen(QColor(0  ,128,255) , 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
                            QPen(QColor(255,0  ,0  ) , 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
                            QPen(QColor(0,  204,204) , 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
                            QPen(QColor(204,0  ,204) , 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin) ]
    self.lPenProj       = [ QPen(QColor(0  ,128,255) , 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin),
                            QPen(QColor(255,0  ,0  ) , 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin),
                            QPen(QColor(0,  204,204) , 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin),
                            QPen(QColor(204,0  ,204) , 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin) ]                          
    self.penMarkerBack= QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    self.penProjBack  = QPen(Qt.black, 1, Qt.DotLine  , Qt.RoundCap, Qt.RoundJoin)
    self.penRoi       = QPen(Qt.green, 1, Qt.DashLine , Qt.RoundCap, Qt.RoundJoin)
    self.penRoiBack   = QPen(Qt.black, 1, Qt.DashLine , Qt.RoundCap, Qt.RoundJoin)
    self.roiInvX      = False
    self.roiInvY      = False

  def contextMenuEvent(self, ev):
    ui = self.gui.ui
    # Fix up the menu!
    if self.gui.isportrait:
      ui.actionPortrait.setText("Switch to Landscape")
    else:
      ui.actionPortrait.setText("Switch to Portrait")
    if ui.showconf.isChecked():
      ui.actionShow_Configuration.setText("Hide Configuration")
    else:
      ui.actionShow_Configuration.setText("Show Configuration")
    if ui.showproj.isChecked():
      ui.actionShow_Projection.setText("Hide Projection")
    else:
      ui.actionShow_Projection.setText("Show Projection")
    action = ui.menuPopup.exec_(ev.globalPos())
    if action == ui.actionReset_ROI:
      self.gui.onRoiReset()
    elif action == ui.actionZoom_to_ROI:
      self.zoomToRoi()
    elif action == ui.actionPortrait:
      if self.gui.isportrait:
        self.gui.landscape()
      else:
        self.gui.portrait()
    elif action == ui.actionShow_Configuration:
      ui.showconf.setChecked(not ui.showconf.isChecked())
      self.gui.doShowConf()
    elif action == ui.actionShow_Projection:
      ui.showproj.setChecked(not ui.showproj.isChecked())
      self.gui.doShowProj()
    elif action == ui.actionSave_to_File:
      self.gui.onfileSave()

  def resizeEvent(self, ev):
    self.setZoom()

  def doResize(self, s=None):
    if s == None:
      s = self.size()
    self.hint = s
    self.updateGeometry()

  def sizeHint(self):
    return self.hint

  def pWidth(self):
    if self.gui.isportrait:
      return self.height()
    else:
      return self.width()

  def pHeight(self):
    if self.gui.isportrait:
      return self.width()
    else:
      return self.height()

  def setRectZoom(self, x, y, w, h):
    self.rectZoom = QRectF(x, y, w, h)
    self.setZoom()

  def setImageSize(self, reset=True):
    size              = QSize(self.gui.x, self.gui.y)
    self.image        = QImage(size, QImage.Format_RGB32)
    self.image.fill(0)
    self.center       = QPointF(self.gui.viewwidth/2, self.gui.viewheight/2)    # true screen
    self.negcenter    = QPointF(-self.gui.viewheight/2, -self.gui.viewwidth/2)  # true screen
    if reset:
      self.rectZoom     = QRectF(0, 0, self.gui.x, self.gui.y)
      self.rectRoi      = QRectF(self.rectZoom)
    self.setZoom()
    self.gui.updateRoiText()
    self.gui.updateMiscInfo()
    if reset:
      self.lMarker        = [ QPointF(-100, -100),                        # image
                              QPointF(self.gui.x + 100, -100),
                              QPointF(self.gui.x + 100, self.gui.y + 100),
                              QPointF(-100, self.gui.y + 100) ]
    
  def paintEvent(self, event):
    if self.gui.dispUpdates == 0:
      return
      
    painter = QPainter(self)
    #painter.setRenderHint(QPainter.Antialiasing)    
    
    self.paintevents += 1
    if self.gui.isportrait:
      painter.translate(self.center)
      painter.rotate(90)
      painter.translate(self.negcenter)
    
    fZoomedWidth    = self.gui.zoom * self.arectZoom.width ()
    fZoomedHeight   = self.gui.zoom * self.arectZoom.height()
    
    self.rectImage = QRectF( (self.pWidth()-fZoomedWidth)/2, (self.pHeight()-fZoomedHeight)/2,\
                             fZoomedWidth, fZoomedHeight)

    # Draw arectZoom portion of image into rectImage
    painter.drawImage(self.rectImage, self.image, self.arectZoom)
          
    painter.setOpacity(1)
    
    lbProjChecked = [ self.gui.ui.checkBoxProjLine1.isChecked(), self.gui.ui.checkBoxProjLine2.isChecked(),      
      self.gui.ui.checkBoxProjLine3.isChecked(), self.gui.ui.checkBoxProjLine4.isChecked() ]
    
    for (iMarker, ptMarker) in enumerate(self.lMarker):
      markerImage = (ptMarker - self.arectZoom.topLeft()) * self.gui.zoom + self.rectImage.topLeft() # screen
      
      painter.setPen(self.penMarkerBack)
      painter.drawLine(markerImage-self.xoff+QPointF(1,1), markerImage+self.xoff+QPointF(1,1))
      painter.drawLine(markerImage-self.yoff+QPointF(1,1), markerImage+self.yoff+QPointF(1,1))
      
      painter.setPen(self.lPenMarker[iMarker])              
      painter.drawLine(markerImage-self.xoff, markerImage+self.xoff)
      painter.drawLine(markerImage-self.yoff, markerImage+self.yoff)
    
      if lbProjChecked[iMarker]:
        painter.setPen(self.penProjBack)
        painter.drawLine(markerImage.x() + 1, 1, markerImage.x() + 1, self.pHeight())          
        painter.drawLine(1,markerImage.y()+1, self.pWidth(), markerImage.y()+1)
        painter.setPen(self.lPenProj[iMarker])
        painter.drawLine(markerImage.x(), 0, markerImage.x(), self.pHeight()-1)
        painter.drawLine(0,markerImage.y(), self.pWidth()-1, markerImage.y())
    
    roiTopLeft = (self.rectRoi.topLeft() - self.arectZoom.topLeft()) * self.gui.zoom + self.rectImage.topLeft() # image
    roiSize    = self.rectRoi.size() * self.gui.zoom
    painter.setPen(self.penRoiBack)
    painter.drawRect( QRectF( roiTopLeft + QPointF(1,1), roiSize ) )
    painter.setPen(self.penRoi)
    painter.drawRect( QRectF( roiTopLeft, roiSize ) )
    
  def mousePressEvent(self, event):  
    # OK, what's going on here?
    # arectZoom is coordinates in the image.
    # rectImage is coordinates on the screen.
    # posx is coordinates on the screen as well.
    if self.gui.isportrait:
      # Rotate 90 degrees!
      posx = event.y() 
      posy = self.width() - event.x()
    else:
      posx = event.x()
      posy = event.y()

    # rectImage is inside (xpos, ypos).  Convert to image coordinates.
    imgx = ( posx - self.rectImage.x() ) * \
        (self.arectZoom.width() / self.rectImage.width()) + self.arectZoom.x()
    imgy = ( posy - self.rectImage.y() ) * \
        (self.arectZoom.height() / self.rectImage.height()) + self.arectZoom.y()

    self.cursorPos      = QPointF(imgx,imgy)
    if self.gui.isportrait:
      self.cursorMarker = QPointF(self.gui.y - imgy, imgx)
    else:
      self.cursorMarker = QPointF(imgx, imgy)    
    
    if self.gui.iSpecialMouseMode == 0:
      self.lastMousePos = event.pos()
      return
          
    if self.gui.iSpecialMouseMode == 5:    
      self.roiInvX      = False
      self.roiInvY      = False    
      if event.buttons() & Qt.RightButton:
        self.rectRoi.setRight (imgx)
        self.rectRoi.setBottom(imgy)
      else:
        self.rectRoi.setX(imgx)
        self.rectRoi.setY(imgy)
        self.rectRoi.setRight (imgx+1)
        self.rectRoi.setBottom(imgy+1)
      self.gui.updateRoiText()
      self.gui.updateProj()
      if self.gui.cfg == None: self.gui.dumpConfig()
    elif self.gui.iSpecialMouseMode >= 1 and self.gui.iSpecialMouseMode <= 4:      
      self.lMarker[self.gui.iSpecialMouseMode-1].setX(imgx)
      self.lMarker[self.gui.iSpecialMouseMode-1].setY(imgy)
      self.gui.updateMarkerText(True, True, 1 << (self.gui.iSpecialMouseMode-1),
                                1 << (self.gui.iSpecialMouseMode-1))
      self.gui.updateProj()
      if self.gui.cfg == None: self.gui.dumpConfig()
    self.update()
    
  def mouseMoveEvent(self, event):
    if self.gui.isportrait:
      posx = event.y() 
      posy = self.width() - event.x() 
    else:
      posx = event.x()
      posy = event.y()

    imgx = ( posx - self.rectImage.x() ) * \
        (self.arectZoom.width() / self.rectImage.width()) + self.arectZoom.x()
    imgy = ( posy - self.rectImage.y() ) * \
        (self.arectZoom.height() / self.rectImage.height()) + self.arectZoom.y()

    self.cursorPos    = QPointF(imgx,imgy)
    if self.gui.isportrait:
      self.cursorMarker = QPointF(self.gui.y - imgy, imgx)
    else:
      self.cursorMarker = QPointF(imgx, imgy)    
    
    if self.gui.iSpecialMouseMode == 0:      
      if not ( event.buttons() & Qt.LeftButton ):
        return
      return self.moveImage(event)        
      
    if self.gui.iSpecialMouseMode <= 5 and not ( event.buttons() & Qt.LeftButton ):
      return
              
    if self.gui.iSpecialMouseMode == 5:
      if self.roiInvX:
        if imgx > self.rectRoi.right():
          self.roiInvX = False
      else:
        if imgx < self.rectRoi.left():
          self.roiInvX = True
          
      if self.roiInvX:
        self.rectRoi.setLeft  (imgx)
      else:
        self.rectRoi.setRight (imgx)
        
      if self.roiInvY:
        if imgy > self.rectRoi.bottom():
          self.roiInvY = False
      else:
        if imgy < self.rectRoi.top():
          self.roiInvY = True
          
      if self.roiInvY:
        self.rectRoi.setTop   (imgy)
      else:
        self.rectRoi.setBottom(imgy)
        
      self.gui.updateRoiText()
      self.gui.updateProj()
      if self.gui.cfg == None: self.gui.dumpConfig()
    elif self.gui.iSpecialMouseMode >= 1 and self.gui.iSpecialMouseMode <= 4:
      self.lMarker[self.gui.iSpecialMouseMode-1].setX(imgx)
      self.lMarker[self.gui.iSpecialMouseMode-1].setY(imgy)
      self.gui.updateMarkerText(True, True, 1 << (self.gui.iSpecialMouseMode-1),
                                1 << (self.gui.iSpecialMouseMode-1))
      self.gui.updateProj()
      if self.gui.cfg == None: self.gui.dumpConfig()
      
    self.update()      
    
  def mouseReleaseEvent(self, event):
    if self.gui.iSpecialMouseMode != 0:
      return self.mouseMoveEvent(event)            
    return self.moveImage(event)
    
  def wheelEvent(self, event):    
    if event.delta() < 0:
      fFactor = 1.5
    else:
      fFactor = 1/1.5
        
    zoomSize        = self.rectZoom.size() * fFactor
    
    if self.gui.isportrait:
      posx = event.y() 
      posy = self.width() - event.x() 
    else:
      posx = event.x()
      posy = event.y()
      
    shiftRatioX = ( posx - self.rectImage.x() ) / self.rectImage.width()
    shiftRatioY = ( posy - self.rectImage.y() ) / self.rectImage.height()
    imgx        = shiftRatioX * self.arectZoom.width () + self.arectZoom.x()
    imgy        = shiftRatioY * self.arectZoom.height() + self.arectZoom.y()
    
    pointNewTopLeft = QPointF( imgx - zoomSize.width() * shiftRatioX, imgy - zoomSize.height() * shiftRatioY )
    self.rectZoom   = QRectF( pointNewTopLeft, zoomSize )
    self.setZoom()
    self.gui.updateall()    
    if self.gui.cfg == None: self.gui.dumpConfig()
        
  def moveImage(self,event):  
    dx = ( event.x() - self.lastMousePos.x() ) * (self.arectZoom.width()  / self.rectImage.width())
    dy = ( event.y() - self.lastMousePos.y() ) * (self.arectZoom.height() / self.rectImage.height())
    self.lastMousePos = event.pos()
    
    if self.gui.isportrait:
      imgdx = dy
      imgdy = -dx
    else:
      imgdx = dx
      imgdy = dy
    
    self.rectZoom = QRectF( self.rectZoom.x() - imgdx, self.rectZoom.y() - imgdy,\
      self.rectZoom.width(), self.rectZoom.height() )
    self.setZoom()
    self.gui.updateall()           
    if self.gui.cfg == None: self.gui.dumpConfig()
          
  def zoomByFactor(self, fFactor):
    zoomSize        = self.arectZoom.size() / fFactor
    zoomCenterShift = QPointF( zoomSize.width(), zoomSize.height() ) * 0.5
    self.rectZoom   = QRectF( self.arectZoom.center() - zoomCenterShift, zoomSize )
    self.setZoom()
    self.gui.updateall()
    if self.gui.cfg == None: self.gui.dumpConfig()

  def zoomToRoi(self):
    self.rectZoom = QRectF(self.rectRoi)
    self.setZoom()
    self.gui.updateall()
    if self.gui.cfg == None: self.gui.dumpConfig()

  # This must be called after setting rectZoom so that arectZoom is correctly set!
  #
  # rectZoom is our *desired* zoom rectangle.
  # This routine "fixes" it to make it actually fit in the available space.
  def setZoom(self):
    if ( self.rectZoom.width() <= 0 ):
      self.rectZoom.setWidth(1)
    if ( self.rectZoom.height() <= 0 ):
      self.rectZoom.setHeight(1)

    self.arectZoom = QRectF(self.rectZoom)

    h = self.pHeight()
    w = self.pWidth()

    fWidthRatio   = w  / self.arectZoom.width()
    fHeightRatio  = h / self.arectZoom.height()
    
    if abs((fWidthRatio - fHeightRatio)/fWidthRatio) < 0.01:
      self.gui.zoom = w / self.arectZoom.width()
      return
      
    if fWidthRatio > fHeightRatio:
      fNewZoomWidth = self.arectZoom.width() * fWidthRatio / fHeightRatio
      fNewZoomX     = self.arectZoom.x() + ( self.arectZoom.width() - fNewZoomWidth ) * 0.5      
      self.arectZoom.setX    ( fNewZoomX )
      self.arectZoom.setWidth( fNewZoomWidth )
    else:
      fNewZoomHeight = self.arectZoom.height() * fHeightRatio / fWidthRatio
      fNewZoomY      = self.arectZoom.y() + ( self.arectZoom.height() - fNewZoomHeight ) * 0.5      
      self.arectZoom.setY     ( fNewZoomY )
      self.arectZoom.setHeight( fNewZoomHeight )
    self.gui.zoom = w / self.arectZoom.width()
        
  def zoomReset(self):
    self.zoomByFactor(self.rectZoom.width() / self.pWidth())
    
  def roiReset(self):
    self.rectRoi = QRectF(0, 0, self.gui.x, self.gui.y)
    self.gui.updateRoiText()
    self.update()
    if self.gui.cfg == None: self.gui.dumpConfig()

  def roiSet(self, x, y, w, h):
    self.rectRoi = QRectF(x, y, w, h)
    self.gui.updateRoiText()
    self.update()
    if self.gui.cfg == None: self.gui.dumpConfig()
    
