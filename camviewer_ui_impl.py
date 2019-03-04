# NOTES:
# OK, New regime: all of the rotation is handled by the false coloring processor for the image PV.
# So, now this processor is given an orientation, and everything is automatically rotated with
# x going right and y going down, (0,0) in the upper left corner.  The Rect and Point classes in
# the param module automatically deal with absolute image coordinates as well as rotated ones.
#
# So, we only have to deal with true screen coordinates and how the oriented image is mapped to
# this.
#
from camviewer_ui import Ui_MainWindow
from psp.Pv import Pv
#from xtcrdr import xtcrdr
from dialogs import advdialog
from dialogs import markerdialog
from dialogs import specificdialog
from dialogs import dropletdialog
from dialogs import xtcrdrdialog
from dialogs import timeoutdialog
from dialogs import forcedialog

import pycaqtimage
import pyca
import sys
import math
import os
import re
import time
import tempfile
import Image
import functools

from PyQt4 import QtCore, uic
from PyQt4.QtGui import *
from PyQt4.QtCore import QTime, QTimer, Qt, QPoint, QPointF, QSize, QRectF, QObject

import DisplayImage
import ProjV
import ProjH
import param

#
# Utility functions to put/get Pv values.
#
def caput(pvname,value,timeout=1.0):
  try:
    pv = Pv(pvname)
    pv.connect(timeout)
    pv.get(ctrl=False, timeout=timeout)
    pv.put(value, timeout)
    pv.disconnect()
  except pyca.pyexc, e:
    print 'pyca exception: %s' %(e)
  except pyca.caexc, e:
    print 'channel access exception: %s' %(e)

def caget(pvname,timeout=1.0):
  try:
    pv = Pv(pvname)
    pv.connect(timeout)
    pv.get(ctrl=False, timeout=timeout)
    v = pv.value
    pv.disconnect()
    return v
  except pyca.pyexc, e:
    print 'pyca exception: %s' %(e)
    return None
  except pyca.caexc, e:
    print 'channel access exception: %s' %(e)
    return None

#
# A configuration object class.
#
class cfginfo():
  def __init__(self):
    self.dict = {}
  
  def read(self, name):
    try:
      cfg = open(name).readlines()
      for line in cfg:
        line = line.lstrip()
        token = line.split()
        if len(token) == 2:
          self.dict[token[0]] = token[1]
        else:
          self.dict[token[0]] = token[1:]
      return True
    except:
      return False
  
  def add(self, attr, val):
    self.dict[attr] = val
  
  def __getattr__(self, name):
    if self.dict.has_key(name):
      return self.dict[name]
    else:
      raise AttributeError

class FilterObject(QObject):
  def __init__(self, app, main):
    QObject.__init__(self, main)
    self.app = app
    self.clip = app.clipboard()
    self.main = main
    self.app.installEventFilter(self)
    sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    sizePolicy.setHorizontalStretch(0)
    sizePolicy.setVerticalStretch(0)
    self.renderlabel = QLabel()
    self.renderlabel.setSizePolicy(sizePolicy)
    self.renderlabel.setMinimumSize(QtCore.QSize(0, 20))
    self.renderlabel.setMaximumSize(QtCore.QSize(16777215, 100))
    self.last = QtCore.QPoint(0,0)

  def eventFilter(self, obj, event):
    if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.MidButton:
      p = event.globalPos()
      w = self.app.widgetAt(p)
      if w == obj and self.last != p:
        self.last = p
        try:
          t = w.writepvname
        except:
          t = None
        if t == None:
          try:
            t = w.readpvname
          except:
            t = None
        if t == None:
          return False
        self.clip.setText(t, QClipboard.Selection)
        mimeData = QtCore.QMimeData()
        mimeData.setText(t)
        self.renderlabel.setText(t)
        self.renderlabel.adjustSize()
        pixmap = QPixmap(self.renderlabel.size())
        self.renderlabel.render(pixmap)
        drag = QDrag(self.main)
        drag.setMimeData(mimeData)
        drag.setPixmap(pixmap)
        drag.exec_(QtCore.Qt.CopyAction)
    return False

SINGLE_FRAME   = 0
REMOTE_AVERAGE = 1
LOCAL_AVERAGE  = 2

class GraphicUserInterface(QMainWindow):

#  def __init__(self, app, cwd, instrument, cameraIndex, cameraPv, ...)
  def __init__(self, app, cwd, instrument, camera, cameraPv,
               cameraListFilename, cfgdir, activedir, rate, idle, options):
    QMainWindow.__init__(self)
    self.app = app
    self.cwd = cwd
    self.rcnt = 0
    self.resizing = False
    self.startResize()
    self.cfgdir = cfgdir
    self.cfg = None
    self.activedir = activedir
    self.fixname = False
    self.instrument = instrument
    self.description = "%s:%d" % (os.uname()[1], os.getpid())
    self.options = options

    if self.options.pos != None:
      try:
        p = self.options.pos.split(',')
        p = QPoint(int(p[0]), int(p[1]))
        self.move(p)
      except:
        pass

    # View parameters
    self.viewwidth  = 640    # Size of our viewing area.
    self.viewheight = 640    # Size of our viewing area.
    self.projsize   = 300    # Size of our projection window.
    self.minwidth   = 450
    self.minheight  = 450
    self.minproj    = 250

    # Default to VGA!
    param.setImageSize(640, 480)
    self.isColor = False
    self.bits = 10
    self.maxcolor = 1023
    self.lastUpdateTime  = time.time()
    self.dispUpdates     = 0
    self.lastDispUpdates = 0
    self.dataUpdates     = 0
    self.lastDataUpdates = 0
    self.average         = 1
    param.orientation    = param.ORIENT0
    self.connected       = False
    self.cameraBase      = ""
    self.camera          = None
    self.camtype         = None
    self.notify          = None
    self.haveNewImage    = False
    self.lastGetDone     = True
    self.wantNewImage    = True
    self.lensPv          = None
    self.putlensPv       = None
    self.nordPv          = None
    self.count           = None
    self.rowPv           = None
    self.colPv           = None
    self.scale           = 1
    self.shiftPv         = None
    self.iocRoiXPv       = None
    self.iocRoiYPv       = None
    self.iocRoiHPv       = None
    self.iocRoiWPv       = None
    self.params1Pv        = None
    self.params2Pv        = None
    self.fLensPrevValue  = -1
    self.fLensValue      = 0
    self.avgState        = SINGLE_FRAME
    self.index           = 0
    self.averageCur      = 0
    self.iRangeMin       = 0
    self.iRangeMax       = 1023
    self.camactions      = []
    self.lastwidth       = 0
    self.useglobmarks    = False
    self.useglobmarks2   = False
    self.globmarkpvs     = []
    self.globmarkpvs2    = []
    self.pulnixmodes     = [":SetAsyncShutter", ":SetManualShutter", ":SetDirectShutter"]
    self.lastimagetime   = [0, 0]
    self.simtype = None
    self.xtcrdr = None
    self.xtcdir = os.getenv("HOME")
    self.xtclocs = []
    self.xtcidx  = 0
    self.dispspec = 0
    self.otherpvs = []

    self.markhash = []
    for i in range(131072):
      self.markhash.append(8*[0])

    self.itime        = 10*[0.]
    self.idispUpdates = 10*[0]
    self.idataUpdates = 10*[0]
    
    self.rfshTimer   = QTimer();
    self.imageTimer  = QTimer();
    self.discoTimer  = QTimer();

    self.ui         = Ui_MainWindow()
    self.ui.setupUi(self)
    self.RPSpacer = QSpacerItem(20, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
    self.ui.RightPanel.addItem(self.RPSpacer)

    self.ui.xmark = [self.ui.Disp_Xmark1, self.ui.Disp_Xmark2, self.ui.Disp_Xmark3, self.ui.Disp_Xmark4]
    self.ui.ymark = [self.ui.Disp_Ymark1, self.ui.Disp_Ymark2, self.ui.Disp_Ymark3, self.ui.Disp_Ymark4]
    self.ui.pBM   = [self.ui.pushButtonMarker1, self.ui.pushButtonMarker2,
                     self.ui.pushButtonMarker3, self.ui.pushButtonMarker4,
                     self.ui.pushButtonRoiSet]
    self.ui.actM  = [self.ui.actionM1, self.ui.actionM2,
                     self.ui.actionM3, self.ui.actionM4,
                     self.ui.actionROI]
    self.advdialog = advdialog(self)
    self.advdialog.hide()
    
    self.markerdialog = markerdialog(self)
    self.markerdialog.xmark = [self.markerdialog.ui.Disp_Xmark1, self.markerdialog.ui.Disp_Xmark2,
                               self.markerdialog.ui.Disp_Xmark3, self.markerdialog.ui.Disp_Xmark4]
    self.markerdialog.ymark = [self.markerdialog.ui.Disp_Ymark1, self.markerdialog.ui.Disp_Ymark2,
                               self.markerdialog.ui.Disp_Ymark3, self.markerdialog.ui.Disp_Ymark4]
    self.markerdialog.pBM   = [self.markerdialog.ui.pushButtonMarker1,
                               self.markerdialog.ui.pushButtonMarker2,
                               self.markerdialog.ui.pushButtonMarker3,
                               self.markerdialog.ui.pushButtonMarker4,
                               None]
    self.markerdialog.hide()
    
    self.specificdialog = specificdialog(self)
    self.specificdialog.hide()
    
    self.dropletdialog = dropletdialog(self)
    self.dropletdialog.hide()
    
    self.xtcrdrdialog = xtcrdrdialog(self)
    self.xtcrdrdialog.hide()
    self.xtcdirinit()
    
    self.timeoutdialog = timeoutdialog(self, idle)
    self.timeoutdialog.hide()

    self.forcedialog = None
    self.haveforce = False
    self.lastforceid = ""

    # Not sure how to do this in designer, so we put it in the main window.
    # Move it to the status bar!
    self.ui.statusbar.addWidget(self.ui.labelMarkerInfo)

    # This is our popup menu, which we just put into the menubar for convenience.
    # Take it out!
    self.ui.menuBar.removeAction(self.ui.menuPopup.menuAction())
    
    # Turn off the stuff we don't care about!
    self.ui.labelLens.setVisible(False)
    self.ui.horizontalSliderLens.setVisible(False)
    self.ui.lineEditLens.setVisible(False)
    self.ui.groupBoxIOC.setVisible(False)
    self.ui.rem_avg.setVisible(False)
    self.ui.remote_average.setVisible(False)
    self.ui.menuDroplet.menuAction().setVisible(False)
    self.ui.groupBoxDrop.setVisible(False)

    # Resize the main window!
    self.ui.display_image.setImageSize(False)
    
    self.iScaleIndex = 0
    self.connect(self.ui.comboBoxScale,  QtCore.SIGNAL("currentIndexChanged(int)"), self.onComboBoxScaleIndexChanged)
    
    self.cameraListFilename  = cameraListFilename
      
    self.imageBuffer = pycaqtimage.pyCreateImageBuffer(self.ui.display_image.image, param.orientation)

    self.updateRoiText()
    self.updateMarkerText(True, True, 0, 15)

    sizeProjX       = QSize(self.viewwidth, self.projsize)
    self.ui.projH.doResize(sizeProjX)

    sizeProjY       = QSize(self.projsize, self.viewheight)
    self.ui.projV.doResize(sizeProjY)

    self.ui.display_image.doResize(QSize(self.viewwidth, self.viewheight))

    sizeProjX       = QSize(param.maxd, self.projsize)
    self.imageProjX = QImage(sizeProjX, QImage.Format_RGB32) # image

    sizeProjY       = QSize(self.projsize, param.maxd)
    self.imageProjY = QImage(sizeProjY, QImage.Format_RGB32) # image
    
    self.updateCameraCombo()
    
    self.connect(self.ui.checkBoxProjRoi,   QtCore.SIGNAL("stateChanged(int)"), self.onCheckProjUpdate)        
    self.connect(self.ui.checkBoxProjAutoRange, QtCore.SIGNAL("stateChanged(int)"), self.onCheckProjUpdate)
    
    self.connect(self.ui.horizontalSliderRangeMin , QtCore.SIGNAL("valueChanged(int)"), self.onSliderRangeMinChanged )
    self.connect(self.ui.horizontalSliderRangeMax, QtCore.SIGNAL("valueChanged(int)"), self.onSliderRangeMaxChanged)
    self.connect(self.ui.lineEditRangeMin , QtCore.SIGNAL("returnPressed()"), self.onRangeMinTextEnter )
    self.connect(self.ui.lineEditRangeMax, QtCore.SIGNAL("returnPressed()"), self.onRangeMaxTextEnter)    

    self.connect(self.ui.horizontalSliderLens , QtCore.SIGNAL("sliderReleased()"), self.onSliderLensReleased )
    self.connect(self.ui.horizontalSliderLens , QtCore.SIGNAL("valueChanged(int)"), self.onSliderLensChanged )
    self.connect(self.ui.lineEditLens , QtCore.SIGNAL("returnPressed()"), self.onLensEnter )

    self.connect(self.ui.singleframe, QtCore.SIGNAL("toggled(bool)"), self.onCheckDisplayUpdate)
    self.connect(self.ui.grayScale,   QtCore.SIGNAL("stateChanged(int)"), self.onCheckGrayUpdate)
    self.connect(self.ui.rem_avg,     QtCore.SIGNAL("toggled(bool)"), self.onCheckDisplayUpdate)
    self.connect(self.ui.local_avg,   QtCore.SIGNAL("toggled(bool)"), self.onCheckDisplayUpdate)
    self.connect(self.ui.remote_average, QtCore.SIGNAL("returnPressed()"), self.onRemAvgEnter )
    
    self.connect(self.ui.comboBoxColor, QtCore.SIGNAL("currentIndexChanged(int)"), self.onComboBoxColorIndexChanged)
    self.hot() # default option

    for i in range(4):
      self.connect(self.ui.xmark[i], QtCore.SIGNAL("returnPressed()"),
                   functools.partial(self.onMarkerTextEnter, i))
      self.connect(self.ui.ymark[i], QtCore.SIGNAL("returnPressed()"),
                   functools.partial(self.onMarkerTextEnter, i))
 
      self.connect(self.markerdialog.xmark[i], QtCore.SIGNAL("returnPressed()"),
                   functools.partial(self.onMarkerDialogEnter, i))
      self.connect(self.markerdialog.ymark[i], QtCore.SIGNAL("returnPressed()"),
                   functools.partial(self.onMarkerDialogEnter, i))

    self.connect(self.ui.Disp_RoiX, QtCore.SIGNAL("returnPressed()"), self.onRoiTextEnter)
    self.connect(self.ui.Disp_RoiY, QtCore.SIGNAL("returnPressed()"), self.onRoiTextEnter)
    self.connect(self.ui.Disp_RoiW, QtCore.SIGNAL("returnPressed()"), self.onRoiTextEnter)
    self.connect(self.ui.Disp_RoiH, QtCore.SIGNAL("returnPressed()"), self.onRoiTextEnter)
    
    #
    # Special Mouse Mode:
    #   1-4: Marker 1-4, 5: ROI
    self.iSpecialMouseMode = 0

    for i in range(4):
      self.connect(self.ui.pBM[i], QtCore.SIGNAL("clicked(bool)"),
                   functools.partial(self.onMarkerSet, i))
      self.connect(self.markerdialog.pBM[i], QtCore.SIGNAL("clicked(bool)"),
                   functools.partial(self.onMarkerDialogSet, i))
      self.connect(self.ui.actM[i], QtCore.SIGNAL("triggered()"),
                   functools.partial(self.onMarkerTrig, i))

    self.connect(self.ui.pushButtonRoiSet  , QtCore.SIGNAL("clicked(bool)"), self.onRoiSet)
    self.connect(self.ui.pushButtonRoiReset, QtCore.SIGNAL("clicked()"), self.onRoiReset)

    self.connect(self.ui.actionMS      , QtCore.SIGNAL("triggered()"), self.onMarkerSettingsTrig)
    self.connect(self.ui.actionROI     , QtCore.SIGNAL("triggered()"), self.onRoiTrig)
    self.connect(self.ui.actionResetROI, QtCore.SIGNAL("triggered()"), self.onRoiReset)
    self.connect(self.ui.actionResetMarkers, QtCore.SIGNAL("triggered()"), self.onMarkerReset)

    self.connect(self.ui.pushButtonZoomRoi  , QtCore.SIGNAL("clicked()"), self.onZoomRoi)
    self.connect(self.ui.pushButtonZoomIn   , QtCore.SIGNAL("clicked()"), self.onZoomIn)
    self.connect(self.ui.pushButtonZoomOut  , QtCore.SIGNAL("clicked()"), self.onZoomOut)
    self.connect(self.ui.pushButtonZoomReset, QtCore.SIGNAL("clicked()"), self.onZoomReset)

    self.connect(self.ui.actionZoomROI  , QtCore.SIGNAL("triggered()"), self.onZoomRoi)
    self.connect(self.ui.actionZoomIn   , QtCore.SIGNAL("triggered()"), self.onZoomIn)
    self.connect(self.ui.actionZoomOut  , QtCore.SIGNAL("triggered()"), self.onZoomOut)
    self.connect(self.ui.actionZoomReset, QtCore.SIGNAL("triggered()"), self.onZoomReset)

    self.connect(self.ui.actionReconnect, QtCore.SIGNAL("triggered()"), self.onReconnect)
    self.connect(self.ui.actionForce    , QtCore.SIGNAL("triggered()"), self.onForceDisco)
    
    self.connect(self.rfshTimer, QtCore.SIGNAL("timeout()"), self.UpdateRate)
    self.rfshTimer.start(1000)

    self.connect(self.imageTimer, QtCore.SIGNAL("timeout()"), self.wantImage)
    self.imageTimer.start(1000.0 / rate)

    self.connect(self.discoTimer, QtCore.SIGNAL("timeout()"), self.do_disco)

    self.connect(self.ui.average  , QtCore.SIGNAL("returnPressed()"), self.onAverageSet)
    self.connect(self.ui.orient0,    QtCore.SIGNAL("triggered()"), 
                 lambda : self.setOrientation(param.ORIENT0))
    self.connect(self.ui.orient90,   QtCore.SIGNAL("triggered()"),
                 lambda : self.setOrientation(param.ORIENT90))
    self.connect(self.ui.orient180,  QtCore.SIGNAL("triggered()"),
                 lambda : self.setOrientation(param.ORIENT180))
    self.connect(self.ui.orient270,  QtCore.SIGNAL("triggered()"),
                 lambda : self.setOrientation(param.ORIENT270))
    self.connect(self.ui.orient0F,   QtCore.SIGNAL("triggered()"),
                 lambda : self.setOrientation(param.ORIENT0F))
    self.connect(self.ui.orient90F,  QtCore.SIGNAL("triggered()"),
                 lambda : self.setOrientation(param.ORIENT90F))
    self.connect(self.ui.orient180F, QtCore.SIGNAL("triggered()"),
                 lambda : self.setOrientation(param.ORIENT180F))
    self.connect(self.ui.orient270F, QtCore.SIGNAL("triggered()"),
                 lambda : self.setOrientation(param.ORIENT270F))
    self.setOrientation(param.ORIENT0) # default to use unrotated
    
    self.connect(self.ui.FileSave, QtCore.SIGNAL("triggered()"), self.onfileSave)    
    self.connect(self.ui.PostElog, QtCore.SIGNAL("triggered()"), self.onPostElog)    
    
    self.event = QObject()
    self.connect(self.event, QtCore.SIGNAL("onImageUpdate"), self.onImageUpdate)
    self.connect(self.event, QtCore.SIGNAL("onMiscUpdate"), self.onMiscUpdate)
    self.connect(self.event, QtCore.SIGNAL("onAvgUpdate"), self.onAvgUpdate)
    self.connect(self.event, QtCore.SIGNAL("onSizeUpdate"), self.onSizeUpdate)
    self.connect(self.event, QtCore.SIGNAL("onIOCUpdate"), self.onIOCUpdate)
    self.connect(self.event, QtCore.SIGNAL("onCross1Update"),
                 lambda : self.onCrossUpdate(0))
    self.connect(self.event, QtCore.SIGNAL("onCross2Update"),
                 lambda : self.onCrossUpdate(1))
    self.connect(self.event, QtCore.SIGNAL("onCross3Update"),
                 lambda : self.onCrossUpdate(2))
    self.connect(self.event, QtCore.SIGNAL("onCross4Update"),
                 lambda : self.onCrossUpdate(3))
    self.connect(self.event, QtCore.SIGNAL("onParam1Update"), self.onParam1Update)
    self.connect(self.event, QtCore.SIGNAL("onParam2Update"), self.onParam2Update)
    self.connect(self.event, QtCore.SIGNAL("onTimeoutExpiry"), self.onTimeoutExpiry)

    self.connect(self.ui.showconf,   QtCore.SIGNAL("triggered()"), self.doShowConf)
    self.connect(self.ui.showproj,   QtCore.SIGNAL("triggered()"), self.doShowProj)
    self.connect(self.ui.showmarker,   QtCore.SIGNAL("triggered()"), self.doShowMarker)
    self.connect(self.ui.showexpert, QtCore.SIGNAL("triggered()"), self.onExpertMode)
    self.connect(self.ui.showspecific, QtCore.SIGNAL("triggered()"), self.doShowSpecific)
    self.connect(self.ui.actionGlobalMarkers, QtCore.SIGNAL("triggered()"), self.onGlobMarks)
    self.connect(self.advdialog.ui.showevr, QtCore.SIGNAL("clicked()"), self.onOpenEvr)
    self.onExpertMode()

    self.connect(self.advdialog.ui.buttonBox, QtCore.SIGNAL("clicked(QAbstractButton *)"), self.onAdvanced)
    self.connect(self.specificdialog.ui.buttonBox, QtCore.SIGNAL("clicked(QAbstractButton *)"), self.onSpecific)
    self.connect(self.dropletdialog.ui.buttonBox, QtCore.SIGNAL("clicked(QAbstractButton *)"), self.onDroplet)

    self.connect(self.specificdialog.ui.cameramodeG, QtCore.SIGNAL("currentIndexChanged(int)"),
                 lambda n: self.comboWriteCallback(self.specificdialog.ui.cameramodeG, n))
    self.connect(self.specificdialog.ui.cameramodeP, QtCore.SIGNAL("currentIndexChanged(int)"),
                 lambda n: self.comboWriteCallback(self.specificdialog.ui.cameramodeP, n))
    self.connect(self.specificdialog.ui.cameramodeO, QtCore.SIGNAL("currentIndexChanged(int)"),
                 lambda n: self.comboWriteCallback(self.specificdialog.ui.cameramodeO, n))

    self.connect(self.specificdialog.ui.gainG,  QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineFloatWriteCallback(self.specificdialog.ui.gainG))
    self.connect(self.specificdialog.ui.gainAP, QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineIntWriteCallback(self.specificdialog.ui.gainAP))
    self.connect(self.specificdialog.ui.gainBP, QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineIntWriteCallback(self.specificdialog.ui.gainBP))
    self.connect(self.specificdialog.ui.gainO , QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineFloatWriteCallback(self.specificdialog.ui.gainO))
    self.connect(self.specificdialog.ui.gainU,  QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineIntWriteCallback(self.specificdialog.ui.gainU))

    self.connect(self.specificdialog.ui.timeG,  QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineFloatWriteCallback(self.specificdialog.ui.timeG))
    self.connect(self.specificdialog.ui.timeO,  QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineIntWriteCallback(self.specificdialog.ui.timeO))

    self.connect(self.specificdialog.ui.periodG,  QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineFloatWriteCallback(self.specificdialog.ui.periodG))
    self.connect(self.specificdialog.ui.periodO,  QtCore.SIGNAL("returnPressed()"),
                 lambda : self.lineIntWriteCallback(self.specificdialog.ui.periodO))

    self.connect(self.specificdialog.ui.timeP, QtCore.SIGNAL("currentIndexChanged(int)"),
                 lambda n: self.comboWriteCallback(self.specificdialog.ui.timeP, n))
    self.connect(self.specificdialog.ui.timeU, QtCore.SIGNAL("currentIndexChanged(int)"),
                 lambda n: self.comboWriteCallback(self.specificdialog.ui.timeU, n))

    self.connect(self.specificdialog.ui.runButtonG, QtCore.SIGNAL("clicked()"),
                 lambda : self.buttonWriteCallback(self.specificdialog.ui.runButtonG))

    self.connect(self.ui.IOC_RoiX,    QtCore.SIGNAL("returnPressed()"), self.onIOCROIX)
    self.connect(self.ui.IOC_RoiY,    QtCore.SIGNAL("returnPressed()"), self.onIOCROIY)
    self.connect(self.ui.IOC_RoiW,    QtCore.SIGNAL("returnPressed()"), self.onIOCROIW)
    self.connect(self.ui.IOC_RoiH,    QtCore.SIGNAL("returnPressed()"), self.onIOCROIH)
    self.connect(self.ui.shiftText,   QtCore.SIGNAL("returnPressed()"), self.onShiftText)
    self.connect(self.ui.shiftSlider, QtCore.SIGNAL("valueChanged(int)"), self.onShiftSliderChanged )
    self.connect(self.ui.shiftSlider, QtCore.SIGNAL("sliderReleased()"),  self.onShiftSliderReleased)

    # Droplet stuff!
    self.connect(self.ui.setROI,          QtCore.SIGNAL("clicked()"), self.onDropRoiSet)
    self.connect(self.ui.fetchROI,        QtCore.SIGNAL("clicked()"), self.onDropRoiFetch)
    self.connect(self.ui.actionFetchROI1, QtCore.SIGNAL("triggered()"), self.onFetchROI1)
    self.connect(self.ui.actionFetchROI2, QtCore.SIGNAL("triggered()"), self.onFetchROI2)
    self.connect(self.ui.actionSetROI1,   QtCore.SIGNAL("triggered()"), self.onSetROI1)
    self.connect(self.ui.actionSetROI2,   QtCore.SIGNAL("triggered()"), self.onSetROI2)
    self.connect(self.ui.actionShowDrop,  QtCore.SIGNAL("triggered()"), self.onShowDropAction)
    self.connect(self.ui.showdrops,       QtCore.SIGNAL("stateChanged(int)"), self.onShowDrops)
    self.connect(self.ui.param1_0,        QtCore.SIGNAL("returnPressed()"), self.onParam1_0)
    self.connect(self.ui.param1_1,        QtCore.SIGNAL("returnPressed()"), self.onParam1_1)
    self.connect(self.ui.param2_0,        QtCore.SIGNAL("returnPressed()"), self.onParam2_0)
    self.connect(self.ui.param2_1,        QtCore.SIGNAL("returnPressed()"), self.onParam2_1)
    self.connect(self.ui.actionAdjustDrop,QtCore.SIGNAL("triggered()"), self.doShowDroplet)
    self.connect(self.ui.ROI1,            QtCore.SIGNAL("toggled(bool)"), self.onDebugROI1)
    self.connect(self.ui.ROI2,            QtCore.SIGNAL("toggled(bool)"), self.onDebugROI2)
    self.connect(self.ui.dropDebug,       QtCore.SIGNAL("toggled(bool)"), self.onDropDebug)
    
    # set camera pv and start display
    self.connect(self.ui.menuCameras, QtCore.SIGNAL("triggered(QAction *)"), self.onCameraMenuSelect)
    self.connect(self.ui.comboBoxCamera, QtCore.SIGNAL("currentIndexChanged(int)"), self.onCameraSelect)

    self.connect(self.xtcrdrdialog.ui.dirselect,  QtCore.SIGNAL("clicked()"), self.onXtcrdrDir)
    self.connect(self.xtcrdrdialog.ui.openButton, QtCore.SIGNAL("clicked()"), self.onXtcrdrOpen)
    self.connect(self.xtcrdrdialog.ui.prevButton, QtCore.SIGNAL("clicked()"), self.onXtcrdrPrev)
    self.connect(self.xtcrdrdialog.ui.nextButton, QtCore.SIGNAL("clicked()"), self.onXtcrdrNext)
    self.connect(self.xtcrdrdialog.ui.skipButton, QtCore.SIGNAL("clicked()"), self.onXtcrdrSkip)
    self.connect(self.xtcrdrdialog.ui.backButton, QtCore.SIGNAL("clicked()"), self.onXtcrdrBack)

    # Sigh, we might change this if taking a one-liner!
    camera = options.camera
    if camera != None:
      try:
        cameraIndex = int(camera)
      except:
        # OK, I suppose it's a name!  Default to 0, then look for it!
        cameraIndex = 0
        for i in range(len(self.lCameraDesc)):
          if self.lCameraDesc[i].find(camera) >= 0:
            cameraIndex = i
            break
        
    if cameraPv != None:
      try:
        idx = self.lCameraList.index(cameraPv)
        print "Camera PV %s --> index %d" % (cameraPv, idx)
        cameraIndex = idx
      except:
        # Can't find an exact match.  Strip off the end, and look for the same base.
        m=re.search("(.*):([^:]*)$", cameraPv)
        if m == None:
          print "Cannot find camera PV %s!" % cameraPv
        else:
          try:
            pvname = m.group(1)
            pvnamelen = len(pvname)
            idx = -1
            for i in range(len(self.lCameraList)):
              if self.lCameraList[i][:pvnamelen] == pvname:
                idx = i
                break
            if idx < -1:
              raise Exception, "No match"
            print "Camera PV %s --> index %d" % (cameraPv, idx)
            cameraIndex = idx
          except:
            print "Cannot find camera PV %s!" % cameraPv

    try:
      self.ui.comboBoxCamera.setCurrentIndex(-1)
      if cameraIndex < 0 or cameraIndex >= len(self.lCameraList):
        print "Invalid camera index %d" % cameraIndex
        cameraIndex = 0
      self.ui.comboBoxCamera.setCurrentIndex(int(cameraIndex))
    except: pass
    self.finishResize()
    self.efilter = FilterObject(self.app, self)

  def closeEvent(self, event):
    if (self.cameraBase != ""):
      self.activeClear()
    if self.haveforce and self.forcedialog != None:
      self.forcedialog.close()
    self.timeoutdialog.close()
    self.advdialog.close()
    self.markerdialog.close()
    self.specificdialog.close()
    self.dropletdialog.close()
    self.xtcrdrdialog.close()
    if self.cfg == None:
      self.dumpConfig()
    QMainWindow.closeEvent(self, event)

#
# OK, what is going on here?
#
# When we want to do something that could cause a resize, we:
#     - Call startResize(), which sets the size contraint to fixed and resizing to True.
#     - Do the resize/hide/show/whatever.  The DisplayImage has its sizeHint() set to our view size.
#     - Call finishResize().  If we are totally done with any enclosed operation, we call adjustSize()
#       to force the window to recalculate/relayout.
#
# When the resize actually happens, we get a resize event, but this seems to be before most things
# have settled down.  So we do a singleShot(0) timer to get a callback when everything is done.
#
#
#

  def startResize(self):
    if self.rcnt == 0:
      self.layout().setSizeConstraint(QLayout.SetFixedSize)
      self.resizing = True
    self.rcnt += 1

  def finishResize(self):
    self.rcnt -= 1
    if self.rcnt == 0:
      self.adjustSize()

  def resizeEvent(self, ev):
    QtCore.QTimer.singleShot(0, self.completeResize)

  def completeResize(self):
    self.layout().setSizeConstraint(QLayout.SetDefaultConstraint)
    self.setMaximumSize(QtCore.QSize(16777215, 16777215))
    di = self.ui.display_image
    dis = di.size()
    if dis != di.hint:
      if not self.resizing:
        # We must really be resizing the window!
        self.changeSize(dis.width(), dis.height(), self.projsize, True, False)
        self.ui.display_image.hint = dis
        return
      else:
        # See if we are limited by the right panel height or info width?
        rps = self.ui.RightPanel.geometry()
        info  = self.ui.info.geometry()
        lph = info.height() + self.viewheight
        if self.ui.showproj.isChecked():
          lph += self.ui.projH.geometry().height()
        spc = self.RPSpacer.geometry().height()
        hlim = rps.height() - spc
        if rps.width() > 0 and lph < hlim:
          # Yeah, the right panel is keeping us from shrinking the window.
          hlim -= info.height()
          self.startResize()
          self.changeSize(self.viewwidth, hlim, self.projsize, True)
          self.finishResize()
        elif abs(self.viewheight - dis.height()) <= 3:
          # We're just off by a little bit!  Nudge the window into place!
          newsize = QSize(self.width(), self.height() - (dis.height() - self.viewheight))
          QtCore.QTimer.singleShot(0, lambda: self.resize(newsize))
        else:
          # We're just wrong.  Who knows why?  Just retry.
          QtCore.QTimer.singleShot(0, self.delayedRetry)
    else:
      # We're good!
      self.resizing = False 

  def delayedRetry(self):
    # Try the resize again...
    self.startResize()
    self.layout().invalidate()
    self.ui.display_image.updateGeometry()
    self.finishResize()

  def setImageSize(self, newx, newy, reset=True):
    if (newx == 0 or newy == 0):
      return
    param.setImageSize(newx, newy)
    self.ui.display_image.setImageSize(reset)
    self.imageBuffer = pycaqtimage.pyCreateImageBuffer(self.ui.display_image.image, param.orientation)
    if self.camera != None:
      if self.isColor:
        self.camera.processor  = pycaqtimage.pyCreateColorImagePvCallbackFunc(self.imageBuffer)
#        self.ui.grayScale.setVisible(True)
      else:
        self.camera.processor  = pycaqtimage.pyCreateImagePvCallbackFunc(self.imageBuffer)
#        self.ui.grayScale.setVisible(False)
      pycaqtimage.pySetImageBufferGray(self.imageBuffer, self.ui.grayScale.isChecked())
    sizeProjX       = QSize(param.maxd, self.projsize)
    self.imageProjX = QImage(sizeProjX, QImage.Format_RGB32) # image
    sizeProjY       = QSize(self.projsize, param.maxd)
    self.imageProjY = QImage(sizeProjY, QImage.Format_RGB32) # image

  def doShowProj(self):
    v = self.ui.showproj.isChecked()
    self.startResize()
    self.ui.projH.setVisible(v)
    self.ui.projV.setVisible(v)
    self.ui.projectionFrame.setVisible(v)
    self.finishResize()
    if self.cfg == None:
      # print "done doShowProj"
      self.dumpConfig()

  def doShowMarker(self):
    v = self.ui.showmarker.isChecked()
    self.startResize()
    self.ui.groupBoxMarker.setVisible(v)
    self.ui.RightPanel.invalidate()
    self.finishResize()
    if self.cfg == None:
      # print "done doShowMarker"
      self.dumpConfig()

  def doShowConf(self):
    v = self.ui.showconf.isChecked()
    self.startResize()
    self.ui.groupBoxAverage.setVisible(v)
    self.ui.groupBoxCamera.setVisible(v)
    self.ui.groupBoxColor.setVisible(v)
    self.ui.groupBoxZoom.setVisible(v)
    self.ui.groupBoxROI.setVisible(v)
    self.ui.RightPanel.invalidate()
    if self.lType[self.index] == "IC":
      self.ui.groupBoxIOC.setVisible(v)
      self.ui.shiftWidget.setVisible(v and self.shiftPv != None)
    else:
      self.ui.groupBoxIOC.setVisible(False)
    self.finishResize()
    if self.cfg == None:
      # print "done doShowConf"
      self.dumpConfig()

  def onDropDebug(self, newval):
    if newval:
      if self.ui.ROI1.isChecked():
        self.onDebugROI1(True)
      else:
        self.onDebugROI2(True)
    else:
      # Back to the main image.
      if self.avgState == SINGLE_FRAME:
        self.connectCamera(self.cameraBase + ":LIVE_IMAGE_FULL", self.index)
        if self.isColor:
          pycaqtimage.pySetImageBufferGray(self.imageBuffer, self.ui.grayScale.isChecked())
      elif self.avgState == REMOTE_AVERAGE:
        self.connectCamera(self.cameraBase + ":AVG_IMAGE", self.index)
      elif self.avgState == LOCAL_AVERAGE:
        self.connectCamera(self.cameraBase + ":LIVE_IMAGE_FULL", self.index)
      self.onAverageSet()

  def onDebugROI1(self, newval):
    if newval and self.ui.dropDebug.isChecked():
      # Start debugging BG_IMAGE1
      caput(self.cameraBase + ":BG_IMAGE1.PROC", 1)
      self.connectCamera(self.cameraBase + ":BG_IMAGE1", self.index, self.cameraBase + ":LIVE_IMAGE_FULL")

  def onDebugROI2(self, newval):
    if newval and self.ui.dropDebug.isChecked():
      # Start debugging BG_IMAGE2
      caput(self.cameraBase + ":BG_IMAGE2.PROC", 1)
      self.connectCamera(self.cameraBase + ":BG_IMAGE2", self.index, self.cameraBase + ":LIVE_IMAGE_FULL")

  def onDropRoiSet(self):
    if self.ui.ROI1.isChecked():
      self.onSetROI1()
    if self.ui.ROI2.isChecked():
      self.onSetROI2()
    pass

  def onDropRoiFetch(self):
    if self.ui.ROI1.isChecked():
      self.onFetchROI1()
    if self.ui.ROI2.isChecked():
      self.onFetchROI2()
    pass

  def onFetchROI1(self):
    x = caget(self.cameraBase + ":ROI_X1")
    y = caget(self.cameraBase + ":ROI_Y1")
    w = caget(self.cameraBase + ":ROI_WIDTH1")
    h = caget(self.cameraBase + ":ROI_HEIGHT1")
    x -= w/2
    y -= h/2
    self.ui.display_image.roiSet(x, y, w, h)

  def onFetchROI2(self):
    x = caget(self.cameraBase + ":ROI_X2")
    y = caget(self.cameraBase + ":ROI_Y2")
    w = caget(self.cameraBase + ":ROI_WIDTH2")
    h = caget(self.cameraBase + ":ROI_HEIGHT2")
    x -= w/2
    y -= h/2
    self.ui.display_image.roiSet(x, y, w, h)

  def getROI(self):
    roi = self.ui.display_image.rectRoi.abs()
    x = roi.left()
    y = roi.top()
    w = roi.width()
    h = roi.height()
    return (int(x + w/2 + 0.5), int(y + h/2 + 0.5), int(w), int(h))

  def onSetROI1(self):
    box = self.getROI()
    caput(self.cameraBase + ":ROI_X1", box[0])
    caput(self.cameraBase + ":ROI_Y1", box[1])
    caput(self.cameraBase + ":ROI_WIDTH1", box[2])
    caput(self.cameraBase + ":ROI_HEIGHT1", box[3])

  def onSetROI2(self):
    box = self.getROI()
    caput(self.cameraBase + ":ROI_X2", box[0])
    caput(self.cameraBase + ":ROI_Y2", box[1])
    caput(self.cameraBase + ":ROI_WIDTH2", box[2])
    caput(self.cameraBase + ":ROI_HEIGHT2", box[3])

  def onGlobMarks(self):
    self.setUseGlobalMarkers(self.ui.actionGlobalMarkers.isChecked())
    
  def setUseGlobalMarkers(self, ugm):
    if ugm != self.useglobmarks: # If something has changed...
      if ugm:
        self.useglobmarks = self.connectMarkerPVs()
        if self.useglobmarks:
          self.onCrossUpdate(0)
          self.onCrossUpdate(1)
      else:
        self.useglobmarks = self.disconnectMarkerPVs()
      if self.cfg == None:
        self.dumpConfig()

  def setUseGlobalMarkers2(self, ugm):
    if ugm != self.useglobmarks2: # If something has changed...
      if ugm:
        self.useglobmarks2 = self.connectMarkerPVs2()
        if self.useglobmarks2:
          self.onCrossUpdate(2)
          self.onCrossUpdate(3)
      else:
        self.useglobmarks2 = self.disconnectMarkerPVs2()
      self.ui.showdrops.setChecked(self.useglobmarks2)
      self.ui.actionShowDrop.setChecked(self.useglobmarks2)
      if self.cfg == None:
        self.dumpConfig()

  def onShowDropAction(self):
    self.setUseGlobalMarkers2(self.ui.actionShowDrop.isChecked())

  def onShowDrops(self, newval):
    self.setUseGlobalMarkers2(newval != 0)

  def onParam1_0(self):
    try:
      v = float(self.ui.param1_0.text())
      l = list(self.params1Pv.value)
      l[0] = v
      self.params1Pv.put(tuple(l))
      pyca.flush_io()
    except:
      self.ui.param1_0.setText("%g" % self.params1Pv.value[0])
      self.dropletdialog.ui.param1_0.setText("%g" % self.params1Pv.value[0])

  def onParam1_1(self):
    try:
      v = float(self.ui.param1_1.text())
      l = list(self.params1Pv.value)
      l[1] = v
      self.params1Pv.put(tuple(l))
      pyca.flush_io()
    except:
      self.ui.param1_1.setText("%g" % self.params1Pv.value[1])
      self.dropletdialog.ui.param1_1.setText("%g" % self.params1Pv.value[1])

  def onParam2_0(self):
    try:
      v = float(self.ui.param2_0.text())
      l = list(self.params2Pv.value)
      l[0] = v
      self.params2Pv.put(tuple(l))
      pyca.flush_io()
    except:
      self.ui.param2_0.setText("%g" % self.params2Pv.value[0])
      self.dropletdialog.ui.param2_0.setText("%g" % self.params2Pv.value[0])

  def onParam2_1(self):
    try:
      v = float(self.ui.param2_1.text())
      l = list(self.params2Pv.value)
      l[1] = v
      self.params2Pv.put(tuple(l))
      pyca.flush_io()
    except:
      self.ui.param2_1.setText("%g" % self.params2Pv.value[1])
      self.dropletdialog.ui.param2_1.setText("%g" % self.params2Pv.value[1])

  def onParam1Update(self):
    self.ui.param1_0.setText("%g" % self.params1Pv.value[0])
    self.dropletdialog.ui.param1_0.setText("%g" % self.params1Pv.value[0])
    self.ui.param1_1.setText("%g" % self.params1Pv.value[1])
    self.dropletdialog.ui.param1_1.setText("%g" % self.params1Pv.value[1])

  def onParam2Update(self):
    self.ui.param2_0.setText("%g" % self.params2Pv.value[0])
    self.dropletdialog.ui.param2_0.setText("%g" % self.params2Pv.value[0])
    self.ui.param2_1.setText("%g" % self.params2Pv.value[1])
    self.dropletdialog.ui.param2_1.setText("%g" % self.params2Pv.value[1])

  def param1Callback(self, exception=None):           
    if exception is None:
      self.event.emit(QtCore.SIGNAL("onParam1Update"))
    else:
      print "noise1Callback(): %-30s " % (self.name), exception

  def param2Callback(self, exception=None):           
    if exception is None:
      self.event.emit(QtCore.SIGNAL("onParam2Update"))
    else:
      print "noise2Callback(): %-30s " % (self.name), exception

  def onMarkerTextEnter(self, n):
    self.ui.display_image.lMarker[n].setRel(float(self.ui.xmark[n].text()), 
                                            float(self.ui.ymark[n].text()))
    if n <= 1:
      self.updateMarkerText(False, True, 1 << n, 1 << n)
    else:
      self.updateMarkerText(False, True, 0, 1 << n)
    self.updateMarkerValue()
    self.updateall()
    if self.cfg == None: self.dumpConfig()

  def onMarkerDialogEnter(self, n):
    self.ui.display_image.lMarker[n].setRel(float(self.markerdialog.xmark[n].text()),
                                            float(self.markerdialog.ymark[n].text()))
    if n <= 1:
      self.updateMarkerText(False, True, 1 << n, 1 << n)
    else:
      self.updateMarkerText(False, True, 0, 1 << n)
    self.updateMarkerValue()
    self.updateall()
    if self.cfg == None: self.dumpConfig()
     
  def updateMarkerText(self, do_main=True, do_dialog=True, pvmask=0, change=15):
    if do_main:
      for i in range(4):
        if change & (1 << i):
          pt = self.ui.display_image.lMarker[i].oriented()
          self.ui.xmark[i].setText("%.0f" % pt.x())
          self.ui.ymark[i].setText("%.0f" % pt.y())
    if do_dialog:
      for i in range(4):
        if change & (1 << i):
          pt = self.ui.display_image.lMarker[i].oriented()
          self.markerdialog.xmark[i].setText("%.0f" % pt.x())
          self.markerdialog.ymark[i].setText("%.0f" % pt.y())
    if self.useglobmarks:
      for i in range(2):
        if pvmask & (1 << i):
          pt = self.ui.display_image.lMarker[i].abs()
          newx = int(pt.x())
          newy = int(pt.y())
          self.globmarkpvs[2*i+0].put(newx)
          self.globmarkpvs[2*i+1].put(newy)
    self.updateMarkerValue()
    
  def updateMarkerValue(self):          
    lValue = pycaqtimage.pyGetPixelValue(self.imageBuffer, self.ui.display_image.cursorPos.abs(), 
                                         self.ui.display_image.lMarker[0].abs(),
                                         self.ui.display_image.lMarker[1].abs(),
                                         self.ui.display_image.lMarker[2].abs(),
                                         self.ui.display_image.lMarker[3].abs())
    self.averageCur = lValue[5]
    sMarkerInfoText = ""
    if lValue[0] >= 0:
      pt = self.ui.display_image.cursorPos.oriented()
      sMarkerInfoText += "(%d,%d): %-4d " % (pt.x(), pt.y(), lValue[0])
    for iMarker in range(4):
      if lValue[iMarker+1] >= 0:
        pt = self.ui.display_image.lMarker[iMarker].oriented()
        sMarkerInfoText += "%d:(%d,%d): %-4d " % (1+iMarker, pt.x(), pt.y(), lValue[iMarker+1])    
    # Sigh.  This is the longest label... if it is too long, the window will resize.
    # This would be bad, because the display_image minimum size is small... so we
    # need to protect it a bit until things stabilize.
    self.ui.labelMarkerInfo.setText(sMarkerInfoText)

  def updateall(self):
    self.updateProj()
    self.updateMiscInfo()
    self.ui.display_image.update()
        
  def onCheckProjUpdate(self):
    self.updateall()
    if self.cfg == None: self.dumpConfig()

  def onCheckGrayUpdate(self, newval):
    pycaqtimage.pySetImageBufferGray(self.imageBuffer, newval)
    if self.cfg == None: self.dumpConfig()

  def onCheckDisplayUpdate(self, newval):
    if not newval:
      return         # Only do this for the checked one!
    if self.ui.singleframe.isChecked():
      if self.avgState != SINGLE_FRAME:
        if self.avgState == REMOTE_AVERAGE:
          self.connectCamera(self.cameraBase + ":LIVE_IMAGE_FULL", self.index)
        self.avgState = SINGLE_FRAME
      if self.isColor:
        pycaqtimage.pySetImageBufferGray(self.imageBuffer, self.ui.grayScale.isChecked())
    elif self.ui.rem_avg.isChecked():
      if self.avgState != REMOTE_AVERAGE:
        self.connectCamera(self.cameraBase + ":AVG_IMAGE", self.index)
        self.avgState = REMOTE_AVERAGE
    elif self.ui.local_avg.isChecked():
      if self.avgState != LOCAL_AVERAGE:
        if self.avgState == REMOTE_AVERAGE:
          self.connectCamera(self.cameraBase + ":LIVE_IMAGE_FULL", self.index)
        self.avgState = LOCAL_AVERAGE
    self.onAverageSet()
            
  def clearSpecialMouseMode(self, keepMode, bNewCheckedState):
    for i in range(1, 6):
      if keepMode != i:
        self.ui.pBM[i-1].setChecked(False)
        if self.markerdialog.pBM[i-1] != None:
          self.markerdialog.pBM[i-1].setChecked(False)  
        self.ui.actM[i-1].setChecked(False)  
    if bNewCheckedState:
      self.iSpecialMouseMode = keepMode
    else:
      self.iSpecialMouseMode = 0
      
  def onMarkerSet(self, n, bChecked):
    self.clearSpecialMouseMode(n+1, bChecked)
    self.ui.actM[n].setChecked(bChecked)
    self.markerdialog.pBM[n].setChecked(bChecked)
    self.ui.display_image.update()
      
  def onMarkerDialogSet(self, n, bChecked):
    self.clearSpecialMouseMode(n+1, bChecked)
    self.ui.actM[n].setChecked(bChecked)
    self.ui.pBM[n].setChecked(bChecked)
    self.ui.display_image.update()
    
  def onRoiSet(self, bChecked):
    self.clearSpecialMouseMode(5, bChecked)
    self.ui.actionROI.setChecked(bChecked)
    self.ui.display_image.update()
       
  def onMarkerSettingsTrig(self):
    self.markerdialog.show()
      
  def onMarkerTrig(self, n):
    bChecked = self.ui.actM[n].isChecked()
    self.clearSpecialMouseMode(n+1, bChecked)
    self.ui.pBM[n].setChecked(bChecked)
    self.markerdialog.pBM[n].setChecked(bChecked)
    self.ui.display_image.update()

  def onMarkerReset(self):
    self.ui.display_image.lMarker = [ param.Point(-100, -100),
                                      param.Point(param.x + 100, -100),
                                      param.Point(param.x + 100, param.y + 100),
                                      param.Point(-100, param.y + 100) ]
    self.updateMarkerText(True, True, 3, 15)
    self.updateall()
    if self.cfg == None: self.dumpConfig()
    
  def onRoiTrig(self):
    bChecked = self.ui.actionROI.isChecked()
    self.clearSpecialMouseMode(5, bChecked)
    self.ui.pushButtonRoiSet.setChecked(bChecked)
    self.ui.display_image.update()

  def onRoiReset(self):
    self.clearSpecialMouseMode(0, False)
    self.ui.display_image.roiReset()
    
  def onRoiTextEnter(self):
    self.ui.display_image.rectRoi = param.Rect(float(self.ui.Disp_RoiX.text()), 
                                               float(self.ui.Disp_RoiY.text()),
                                               float(self.ui.Disp_RoiW.text()), 
                                               float(self.ui.Disp_RoiH.text()),
                                               rel=True)        
    self.updateRoiText()
    self.updateall()
    if self.cfg == None: self.dumpConfig()
          
  def updateRoiText(self):
    rct = self.ui.display_image.rectRoi.oriented()
    self.ui.Disp_RoiX.setText("%.0f" % rct.x())
    self.ui.Disp_RoiY.setText("%.0f" % rct.y())
    self.ui.Disp_RoiW.setText("%.0f" % rct.width() )
    self.ui.Disp_RoiH.setText("%.0f" % rct.height())
      
  def onZoomRoi(self):
    self.ui.display_image.zoomToRoi()

  def onZoomIn(self):
    self.ui.display_image.zoomByFactor(2.0)

  def onZoomOut(self):
    self.ui.display_image.zoomByFactor(0.5)

  def onZoomReset(self):
    self.ui.display_image.zoomReset()
        
  def hsv(self):
    self.colorMap = "hsv"
    self.setColorMap()

  def hot(self):
    self.colorMap = "hot"
    self.setColorMap()

  def jet(self):
    self.colorMap = "jet"
    self.setColorMap()

  def cool(self):
    self.colorMap = "cool"
    self.setColorMap()

  def gray(self):
    self.colorMap = "gray"    
    self.setColorMap()
    
  def setColorMap(self):
    if self.colorMap != "gray":
      fnColorMap = self.cwd + "/" + self.colorMap + ".txt"
      pycaqtimage.pydspl_setup_color_map(fnColorMap, self.iRangeMin, self.iRangeMax, self.iScaleIndex)
    else:
      pycaqtimage.pydspl_setup_gray(self.iRangeMin, self.iRangeMax, self.iScaleIndex)
    # If the image isn't frozen, this isn't really necessary.  But it bothers me when it *is*
    # frozen!
    pycaqtimage.pyRecolorImageBuffer(self.imageBuffer)
    self.ui.display_image.update()
    if self.cfg == None: self.dumpConfig()
      
  def onComboBoxScaleIndexChanged(self, iNewIndex):
    self.iScaleIndex = iNewIndex    
    self.setColorMap()
      
  def onComboBoxColorIndexChanged(self, iNewIndex):
    self.colorMap = str(self.ui.comboBoxColor.currentText()).lower()
    self.setColorMap()

  def clear(self):
    self.ui.label_dispRate.setText("-")
    self.ui.label_connected.setText("NO")
    if self.camera is not None:
      try:
        self.camera.disconnect()
      except:
        pass
      self.camera = None
    if self.notify is not None:
      try:
        self.notify.disconnect()
      except:
        pass
      self.notify = None
    if self.lensPv is not None:
      try:
        self.lensPv.disconnect()
      except:
        pass
      self.lensPv = None
    if self.putlensPv is not None:
      try:
        self.putlensPv.disconnect()
      except:
        pass
      self.putlensPv = None
    for pv in self.otherpvs:
      try:
        pv.disconnect()
      except:
        pass
    self.otherpvs = []

  def shutdown(self):
    self.clear()
    self.rfshTimer.stop()
    self.imageTimer.stop()
    #print "shutdown"

  def onfileSave(self):
    try:
      fileName = str(QFileDialog.getSaveFileName(self, "Save Image...", ".", "Images (*.raw *.jpg *.png *.bmp *.pgm *.tif)"))
      if fileName == "":
        raise Exception, "No File Name Specified"
      
      if fileName.lower().endswith(".raw"):
        bSaveOk = pycaqtimage.pySaveRawImageData(self.imageBuffer, param.orientation, fileName)
        if not bSaveOk:
          raise Exception, "Failed to Save to Raw File %s" % (fileName)
        QMessageBox.information(self, "File Save Succeeded", "Image has been saved to a 16-bit raw file: %s" % (fileName) )
        print 'Saved to a 16-bit raw file %s' %(fileName)            
      else:      
        imageData = pycaqtimage.pyGetImageData8bit(self.imageBuffer, param.orientation, self.bits)
        image = Image.new('L', param.getSizeTuple())
        image.putdata(imageData)
        try:
          image.save(fileName)
        except:
          raise Exception, "File type not supported: %s" % (fileName)
        QMessageBox.information(self, "File Save Succeeded", "Image has been saved to an 8-bit image file: %s" % (fileName) )
        print 'Saved to an 8-bit image file %s' %(fileName)            
    except Exception, e:
      print "fileSave failed:", e
      QMessageBox.warning(self, "File Save Failed", str(e))

  def onPostElog(self):
    sTmpJpeg = tempfile.NamedTemporaryFile(mode='r+b',suffix='.jpeg') 
    sFnJpg   = sTmpJpeg.name
    if 0 == os.system('import -trim -frame -border -crop 972x1164+0+0 -window "%s" %s' % (self.sWindowTitle, sFnJpg)):
      print "Window saved to %s" % sFnJpg
      if 0 == \
        os.system('LogBookImagePoster.py -i %s -w https://pswww/pcdsn/ws-auth -u %sopr -e current -d "%s" -a "%s"' %\
          (self.instrument.upper(), self.instrument.lower(), self.sWindowTitle, sFnJpg) ):
        #os.system('LogBookImagePoster.py -i XCS -w https://pswww/pcdsn/ws-auth -u xcsopr -e current -d "%s" -a "%s"' %\
        #  (self.sWindowTitle, sFnJpg) ):
        print "Elog Post Okay"
      else:
        print "Elog Post Failed"

  def setOrientation(self, orientation, reorient=True):
    self.ui.orient0.setChecked(orientation == param.ORIENT0)
    self.ui.orient90.setChecked(orientation == param.ORIENT90)
    self.ui.orient180.setChecked(orientation == param.ORIENT180)
    self.ui.orient270.setChecked(orientation == param.ORIENT270)
    self.ui.orient0F.setChecked(orientation == param.ORIENT0F)
    self.ui.orient90F.setChecked(orientation == param.ORIENT90F)
    self.ui.orient180F.setChecked(orientation == param.ORIENT180F)
    self.ui.orient270F.setChecked(orientation == param.ORIENT270F)
    if param.orientation != orientation:
      param.orientation = orientation
#      if reorient and (self.viewwidth != self.viewheight):
      if reorient:
        self.changeSize(self.viewheight, self.viewwidth, self.projsize, True)
    self.updateMarkerText(True, True, 0, 15)
    self.updateRoiText()
    self.updateall()
    if self.cfg == None: self.dumpConfig()

  def onAverageSet(self):
    if self.avgState == LOCAL_AVERAGE:
      try:
        self.average = int(self.ui.average.text())
        if self.average == 0:
          self.average = 1
          self.ui.average.setText("1")
        self.updateMiscInfo()        
      except:
        self.average = 1
        self.ui.average.setText("1")
      pycaqtimage.pySetFrameAverage(self.average, self.imageBuffer)
    else:
      pycaqtimage.pySetFrameAverage(1, self.imageBuffer)

  # Note: this function is called by the CA library, from another thread
  def sizeCallback(self, exception=None):           
    if exception is None:
      self.event.emit(QtCore.SIGNAL("onSizeUpdate"))
    else:
      print "sizeCallback(): %-30s " % (self.name), exception

  def onSizeUpdate(self):
    try:
      newx = self.colPv.value / self.scale
      newy = self.rowPv.value / self.scale
      if newx != param.x or newy != self.y:
        self.setImageSize(newx, newy, False)
    except:
      pass

  # This monitors LIVE_IMAGE_FULL... which updates at 5 Hz, whether we have an image or not!
  # Therefore, we need to check the time and just skip it if it's a repeat!
  def haveImageCallback(self, exception=None):
    if exception is None:
      if self.notify.secs != self.lastimagetime[0] or self.notify.nsec != self.lastimagetime[1]:
        self.lastimagetime = [self.notify.secs, self.notify.nsec]
        self.haveNewImage = True
        self.wantImage(False)

  # This is called when we might want a new image.
  #
  # So when *do* we want a new image?  When:
  #     - Our timer goes off (we call this routine without a parameter
  #       and so set wantNewImage True)
  #     - We have finished processing the previous image (imagePvUpdateCallback
  #       has set lastGetDone True)
  #     - We have a new image in the IOC (haveImageCallback has received
  #       a new image timestamp and has set haveNewImage True).
  # 
  def wantImage(self, want=True):
    self.wantNewImage = want
    if self.wantNewImage and self.haveNewImage and self.lastGetDone and self.camera != None:
      try:
        if self.nordPv:
          self.count = int(self.nordPv.value)
        self.camera.get(count=self.count)
        pyca.flush_io()
      except:
        pass
      self.haveNewImage = False
      self.lastGetDone = False


  # Note: this function is called by the CA library, from another thread, when we have a new image.
  def imagePvUpdateCallback(self, exception=None):
    self.lastGetDone = True
    if exception is None:
      currentTime       =  time.time()
      self.dataUpdates  += 1
      self.event.emit(QtCore.SIGNAL("onImageUpdate")) # Send out the signal to notify windows update (in the GUI thread)
      self.wantImage(False)
    else:
      print "imagePvUpdateCallback(): %-30s " %(self.name), exception

  # Note: this function is triggered by getting a new image.
  def onImageUpdate(self):
    # Guard against camera going away on shutdown or while switching cameras
    if not self.camera:
        return
    try:
      self.dispUpdates += 1
      if self.useglobmarks2:
        self.updateCross3and4()
      self.updateMarkerValue()
      self.updateMiscInfo()
      self.updateall()
    except Exception, e:
      print e

  # Note: this function is called by the CA library, from another thread      
  def lensPvUpdateCallback(self, exception = None):
    if exception is None:
      self.fLensValue = float(self.lensPv.value)
      self.event.emit(QtCore.SIGNAL("onMiscUpdate")) # Send out the signal to notify windows update (in the GUI thread)
    else:
      print "lensPvUpdateCallback(): %-30s " %(self.name), exception

  def avgPvUpdateCallback(self, exception = None):
    if exception is None:
      self.event.emit(QtCore.SIGNAL("onAvgUpdate"))

  def onMiscUpdate(self):    
    self.updateMiscInfo()

  def onAvgUpdate(self):
    if self.avgPv != None:
      self.ui.remote_average.setText(str(int(self.avgPv.value)))
      
  def updateProj(self):
    try:
      (roiMean, roiVar, projXmin, projXmax, projYmin, projYmax) = \
        pycaqtimage.pyUpdateProj( self.imageBuffer, param.orientation, self.iScaleIndex,
                                  self.ui.checkBoxProjRoi.isChecked(), self.ui.checkBoxProjAutoRange.isChecked(),
                                  self.iRangeMin, self.iRangeMax, 
                                  self.ui.display_image.rectRoi.abs(), self.ui.display_image.arectZoom.abs(),
                                  self.imageProjX, self.imageProjY )
      self.ui.projH.update()
      self.ui.projV.update()
            
      if roiMean == 0:
        roiVarByMean = 0
      else:
        roiVarByMean = roiVar / roiMean
      roi = self.ui.display_image.rectRoi.oriented()
      self.ui.labelRoiInfo.setText( "ROI Mean %-7.2f Std %-7.2f Var/Mean %-7.2f (%d,%d) W %d H %d" % (
        roiMean, math.sqrt(roiVar), roiVarByMean,
        roi.x(), roi.y(), roi.width(), roi.height() ) )        
      if param.isRotated():
        self.ui.labelProjHmax.setText( "%d -" % projYmax )
        self.ui.labelProjMin.setText ( "%d\n%d\\" % (projYmin, projXmin) )
        self.ui.labelProjVmax.setText( "| %d" % projXmax )
      else:
        self.ui.labelProjHmax.setText( "%d -" % projXmax )
        self.ui.labelProjMin.setText ( "%d\n%d\\" % (projXmin, projYmin) )
        self.ui.labelProjVmax.setText( "| %d" % projYmax )
    except Exception, e:
      print "updateProj:: exception: ", e             
      
  def updateMiscInfo(self):
    if self.avgState == LOCAL_AVERAGE:
      self.ui.labelMiscInfo.setText( "AvgShot# %d/%d Color scale [%d,%d] Zoom %.3f" % ( 
        self.averageCur, self.average, self.iRangeMin, self.iRangeMax, param.zoom) )
    else:
      self.ui.labelMiscInfo.setText( "AvgShot# %d/%d Color scale [%d,%d] Zoom %.3f" % ( 
        self.averageCur, 1, self.iRangeMin, self.iRangeMax, param.zoom) )
    if (self.fLensValue != self.fLensPrevValue):
      self.fLensPrevValue = self.fLensValue
      self.ui.horizontalSliderLens.setValue(self.fLensValue)
      self.ui.lineEditLens.setText('%.2f' % self.fLensValue)

  # This is called at 1Hz when rfshTimer expires.
  def UpdateRate(self):
    now                  = time.time()
    delta                = now - self.lastUpdateTime
    self.itime.append(delta)
    self.itime.pop(0)

    dispUpdates          = self.dispUpdates - self.lastDispUpdates
    self.idispUpdates.append(dispUpdates)
    self.idispUpdates.pop(0)
    dispRate             = (float)(sum(self.idispUpdates))/sum(self.itime)
    self.ui.label_dispRate.setText('%.1f Hz' %dispRate)

    dataUpdates          = self.dataUpdates - self.lastDataUpdates
    self.idataUpdates.append(dataUpdates)
    self.idataUpdates.pop(0)
    dataRate             = (float)(sum(self.idataUpdates))/sum(self.itime)
    self.ui.label_dataRate.setText('%.1f Hz' %dataRate)

    self.lastUpdateTime  = now
    self.lastDispUpdates = self.dispUpdates
    self.lastDataUpdates = self.dataUpdates

    # Also, check if someone is requesting us to disconnect!
    self.activeCheck()

  def readCameraFile(self, fn):
    dir = os.path.dirname(fn)  # Strip off filename!
    raw = open(fn,"r").readlines()
    lines = []
    for l in raw:
      s = l.split()
      if len(s) >= 1 and s[0] == "include":
        if s[1][0] != '/':
          lines.extend(self.readCameraFile(dir + "/" + s[1]))
        else:
          lines.extend(self.readCameraFile(s[1]))
      else:
        lines.append(l)
    return lines
    
  def updateCameraCombo(self):
    self.lType       = []
    self.lFlags      = []
    self.lCameraList = []
    self.lCtrlList   = []
    self.lCameraDesc = []
    self.lEvrList    = []
    self.lLensList   = []
    self.camactions  = []
    self.ui.menuCameras.clear()
    sEvr = ""
    try:
      if self.options.oneline != None:
        lCameraListLine = [self.options.oneline]
        self.options.camera = "0"
      else:
        if (self.cameraListFilename[0] == '/'):
          fnCameraList = self.cameraListFilename
        else:
          fnCameraList = self.cwd + "/" + self.cameraListFilename
        lCameraListLine = self.readCameraFile(fnCameraList)
      self.lCameraList = []
      iCamera = -1
      for sCamera in lCameraListLine:
        sCamera = sCamera.lstrip()
        if sCamera.startswith("#") or sCamera == "":
          continue
        iCamera += 1
        
        lsCameraLine = sCamera.split(",")        
        if len(lsCameraLine) < 2:
          throw("")

        sTypeFlag = lsCameraLine[0].strip().split(":")
        sType     = sTypeFlag[0]
        if len(sTypeFlag) > 1:
          sFlag   = sTypeFlag[1]
        else:
          sFlag   = ""
        
        sCameraCtrlPvs = lsCameraLine[1].strip().split(";")
        sCameraPv = sCameraCtrlPvs[0]
        if len(sCameraCtrlPvs) > 1:
          sCtrlPv = sCameraCtrlPvs[1]
        else:
          sCtrlPv = sCameraCtrlPvs[0]
        sEvrNew   = lsCameraLine[2].strip()
        if len(lsCameraLine) >= 4:
          sCameraDesc = lsCameraLine[3].strip()
        else:
          sCameraDesc = sCameraPv
        if len(lsCameraLine) >= 5:
          sLensPv = lsCameraLine[4].strip()
        else:
          sLensPv = ""

        if sEvrNew != "":
          sEvr = sEvrNew
          
        self.lType      .append(sType)
        self.lFlags     .append(sFlag)
        self.lCameraList.append(sCameraPv)
        self.lCtrlList  .append(sCtrlPv)
        self.lCameraDesc.append(sCameraDesc)
        self.lEvrList   .append(sEvr)
        self.lLensList  .append(sLensPv)

        self.ui.comboBoxCamera.addItem(sCameraDesc)

        try:
          action = QAction(self)
          action.setObjectName(sCameraPv)
          action.setText(sCameraDesc)
          action.setCheckable(True)
          action.setChecked(False)
          self.ui.menuCameras.addAction(action)
          self.camactions.append(action)
        except:
          print "Failed to create camera action for %s" % sCameraDesc
        
        if sLensPv == "": sLensPv = "None"
        print "Camera [%d] %s Pv %s Evr %s LensPv %s" % (iCamera, sCameraDesc, sCameraPv, sEvr, sLensPv)
        
    except:
      #import traceback
      #traceback.print_exc(file=sys.stdout)
      print '!! Failed to read camera pv list from \"%s\"' % (fnCameraList)
      sys.exit(0)

  def disconnectPv(self, pv):
    if pv != None:
      try:
        pv.disconnect();
        pyca.flush_io()
      except:
        pass
    return None

  def xtcdirinit(self):
    self.xtcrdrdialog.ui.currentdir.setText(self.xtcdir)
    self.xtcrdrdialog.ui.xtcfile.clear()
    dirlist = os.listdir(self.xtcdir)
    dirlist.sort()
    for file in dirlist:
      match = re.search("(e...-r....)-s..-c...xtc", file)
      if match:
        self.xtcrdrdialog.ui.xtcfile.addItem(match.group(1))

  def onXtcrdrDir(self):
    file = str(QFileDialog.getExistingDirectory(self, "XTC File Directory", self.xtcdir))
    if file != "":
      self.xtcdir = file;
      self.xtcdirinit()

  def findatom(self, name):
    length = len(name)
    for a in self.xtcrdr.atoms:
      if a[-length:] == name:
        return a
    return None
  
  def onXtcrdrOpen(self):
    try:
      file = self.xtcdir + "/" + self.xtcrdrdialog.ui.xtcfile.currentText() + "-s00"
      self.xtcrdr = xtcrdr()
      self.xtcidx = 0
      l = self.xtcrdr.open(str(file))
      if (l == None):
        QMessageBox.critical(None,
                             "Error", "Failed to open %s" % (str(file)),
                             QMessageBox.Ok, QMessageBox.Ok)
        return
      self.xtclocs = [l]
      self.xtcrdrdialog.ui.location.setText("%d:%d" % self.xtclocs[self.xtcidx])
      #
      # Search for an atom that identifies the correct type of camera.
      # If we have two or more, do we want a combobox to choose and not
      # just take the first?
      #
      camera_atom = ""
      if self.simtype == "O":
        p = re.compile("\|Opal1000-")
        for atom in self.xtcrdr.atoms:
          if p.search(atom) != None:
            camera_atom = atom
            break
      elif self.simtype == "P":
        # Future pulnix code.
        pass
      self.xtcrdr.associate(camera_atom, self.notify)
      self.xtcrdr.associate(camera_atom, self.camera)

      atom = self.findatom("DX1")
      if (atom):
        self.xtcrdr.associate(atom, self.globmarkpvs2[0])

      atom = self.findatom("DY1")
      if (atom):
        self.xtcrdr.associate(atom, self.globmarkpvs2[1])

      atom = self.findatom("DX2")
      if (atom):
        self.xtcrdr.associate(atom, self.globmarkpvs2[2])

      atom = self.findatom("DY2")
      if (atom):
        self.xtcrdr.associate(atom, self.globmarkpvs2[3])

      self.xtcrdr.process()
    except:
      pass

  def onXtcrdrNext(self):
    if self.xtcrdr == None:
      return
    try:
      newloc = self.xtcrdr.next()
      if newloc != None:
        self.xtcidx += 1
        if self.xtcidx == len(self.xtclocs):
          self.xtclocs.append(newloc)
        self.xtcrdrdialog.ui.location.setText("%d:%d" % self.xtclocs[self.xtcidx])
        self.xtcrdr.process()
    except:
      pass

  def onXtcrdrSkip(self):
    if self.xtcrdr == None:
      return
    try:
      v = int(self.xtcrdrdialog.ui.skipCount.text())
      while (v > 0):
        newloc = self.xtcrdr.next()
        if newloc != None:
          self.xtcidx += 1
          if self.xtcidx == len(self.xtclocs):
            self.xtclocs.append(newloc)
          v -= 1
        else:
          self.xtcrdr.moveto(self.xtclocs[self.xtcidx])
          v = 0
      self.xtcrdrdialog.ui.location.setText("%d:%d" % self.xtclocs[self.xtcidx])
      self.xtcrdr.process()
    except:
      pass

  def onXtcrdrPrev(self):
    if self.xtcrdr == None or self.xtcidx == 0:
      return
    try:
      self.xtcidx -= 1
      self.xtcrdr.moveto(self.xtclocs[self.xtcidx])
      self.xtcrdrdialog.ui.location.setText("%d:%d" % self.xtclocs[self.xtcidx])
      self.xtcrdr.process()
    except:
      pass

  def onXtcrdrBack(self):
    if self.xtcrdr == None or self.xtcidx == 0:
      return
    try:
      v = int(self.xtcrdrdialog.ui.skipCount.text())
      if (v > self.xtcidx):
        self.xtcidx = 0
      else:
        self.xtcidx -= v
      self.xtcrdr.moveto(self.xtclocs[self.xtcidx])
      self.xtcrdrdialog.ui.location.setText("%d:%d" % self.xtclocs[self.xtcidx])
      self.xtcrdr.process()
    except:
      pass
  
  def connectPv(self, name, timeout=5.0, count=None):
    try:
      if self.simtype == None:
        pv = Pv(name)
        pv.count = count
        try:
          pv.connect(timeout)
        except Exception as exc:
          print exc
          QMessageBox.critical(None,
                               "Error", "Failed to connect to PV %s" % (name),
                               QMessageBox.Ok, QMessageBox.Ok)
          return None
        try:
          pv.get(False, timeout, count=count)
        except Exception as exc:
          print exc
          QMessageBox.critical(None,
                               "Error", "Connected, but unable to read PV %s" % (name),
                               QMessageBox.Ok, QMessageBox.Ok)
          return None
        return pv
      elif self.simtype == "O":
        tgt = name.split(":")[-1]
        if tgt[0:5] == "Cross":
          return None

        pv = Pv(name, True)
        if tgt[0:2] == "DX" or tgt[0:2] == "DY":
          pv.setvalue(0)
        elif tgt == "N_OF_ROW" or tgt == "N_OF_COL":
          pv.setvalue(1024)
        elif tgt == "N_OF_BITS":
          pv.setvalue(12)
        elif tgt == "LIVE_IMAGE_FULL":
          pv.setvalue(tuple(1024*1024*[0]))
        elif tgt[0:6] == "PARAMS":
          pv.setvalue(25*[0.0])
          pv.value[0] = 0.5
        else:
          print "Do we need to simulate %s?" % name
        return pv
        
    except Exception as exc:
      print exc
      QMessageBox.critical(None,
                           "Error", "Failed to connect to PV %s" % (name),
                           QMessageBox.Ok, QMessageBox.Ok)
      return None

  def onCrossUpdate(self, n):
    if (n >= 2):
      if (self.globmarkpvs2[2*n-4].nsec != self.camera.nsec or
          self.globmarkpvs2[2*n-3].nsec != self.camera.nsec or
          self.globmarkpvs2[2*n-4].secs != self.camera.secs or
          self.globmarkpvs2[2*n-3].secs != self.camera.secs):
        return
      self.ui.display_image.lMarker[n].setAbs(self.globmarkpvs2[2*n-4].value, self.globmarkpvs2[2*n-3].value)
    else:
      self.ui.display_image.lMarker[n].setAbs(self.globmarkpvs[2*n+0].value, self.globmarkpvs[2*n+1].value)
    self.updateMarkerText(True, True, 0, 1 << n)
    self.updateMarkerValue()
    self.updateall()
    if self.cfg == None:
      self.dumpConfig()

  def updateCross3and4(self):
    try:
      fid = self.camera.nsec & 0x1ffff
      secs = self.camera.secs
      if self.markhash[fid][0] == secs and self.markhash[fid][1] == secs:
        self.ui.display_image.lMarker[2].setAbs(self.markhash[fid][4], self.markhash[fid][5])
      if self.markhash[fid][2] == secs and self.markhash[fid][3] == secs:
        self.ui.display_image.lMarker[3].setAbs(self.markhash[fid][6], self.markhash[fid][7])
      self.updateMarkerText(True, True, 0, 12)
    except Exception, e:
      print "updateCross3and4 exception: %s" % e

  def addmarkhash(self, pv, idx):
    fid = pv.nsec & 0x1ffff
    secs = pv.secs
    if self.markhash[fid][idx] == secs:
      return False
    self.markhash[fid][idx] = secs
    self.markhash[fid][idx+4] = pv.value
    return True

  def cross1mon(self, exception=None):           
    if exception is None:
      self.event.emit(QtCore.SIGNAL("onCross1Update"))
      
  def cross2mon(self, exception=None):           
    if exception is None:
      self.event.emit(QtCore.SIGNAL("onCross2Update"))

  def cross3Xmon(self, exception=None):           
    if exception is None:
      if self.addmarkhash(self.globmarkpvs2[0], 0):
        self.event.emit(QtCore.SIGNAL("onCross3Update"))

  def cross3Ymon(self, exception=None):           
    if exception is None:
      if self.addmarkhash(self.globmarkpvs2[1], 1):
        self.event.emit(QtCore.SIGNAL("onCross3Update"))

  def cross4Xmon(self, exception=None):           
    if exception is None:
      if self.addmarkhash(self.globmarkpvs2[2], 2):
        self.event.emit(QtCore.SIGNAL("onCross4Update"))

  def cross4Ymon(self, exception=None):           
    if exception is None:
      if self.addmarkhash(self.globmarkpvs2[3], 3):
        self.event.emit(QtCore.SIGNAL("onCross4Update"))

  def connectMarkerPVs(self):
    self.globmarkpvs = [self.connectPv(self.ctrlBase + ":Cross1X"),
                        self.connectPv(self.ctrlBase + ":Cross1Y"),
                        self.connectPv(self.ctrlBase + ":Cross2X"),
                        self.connectPv(self.ctrlBase + ":Cross2Y")]
    if None in self.globmarkpvs:
      return self.disconnectMarkerPVs()
    self.globmarkpvs[0].monitor_cb = self.cross1mon
    self.globmarkpvs[1].monitor_cb = self.cross1mon
    self.globmarkpvs[2].monitor_cb = self.cross2mon
    self.globmarkpvs[3].monitor_cb = self.cross2mon
    for i in self.globmarkpvs:
      i.monitor(pyca.DBE_VALUE)
    self.ui.Disp_Xmark1.readpvname = self.globmarkpvs[0].name
    self.markerdialog.ui.Disp_Xmark1.readpvname = self.globmarkpvs[0].name
    self.ui.Disp_Ymark1.readpvname = self.globmarkpvs[1].name
    self.markerdialog.ui.Disp_Ymark1.readpvname = self.globmarkpvs[1].name
    self.ui.Disp_Xmark2.readpvname = self.globmarkpvs[2].name
    self.markerdialog.ui.Disp_Xmark2.readpvname = self.globmarkpvs[2].name
    self.ui.Disp_Ymark2.readpvname = self.globmarkpvs[3].name
    self.markerdialog.ui.Disp_Ymark2.readpvname = self.globmarkpvs[3].name
    return True

  def connectMarkerPVs2(self):
    self.globmarkpvs2 = [self.connectPv(self.ctrlBase + ":DX1_SLOW"),
                         self.connectPv(self.ctrlBase + ":DY1_SLOW"),
                         self.connectPv(self.ctrlBase + ":DX2_SLOW"),
                         self.connectPv(self.ctrlBase + ":DY2_SLOW")]
    if None in self.globmarkpvs2:
      return self.disconnectMarkerPVs2()
    self.globmarkpvs2[0].monitor_cb = self.cross3Xmon
    self.globmarkpvs2[1].monitor_cb = self.cross3Ymon
    self.globmarkpvs2[2].monitor_cb = self.cross4Xmon
    self.globmarkpvs2[3].monitor_cb = self.cross4Ymon
    for i in self.globmarkpvs2:
      i.monitor(pyca.DBE_VALUE)
    self.ui.Disp_Xmark3.readpvname = self.globmarkpvs2[0].name
    self.markerdialog.ui.Disp_Xmark3.readpvname = self.globmarkpvs2[0].name
    self.ui.Disp_Ymark3.readpvname = self.globmarkpvs2[1].name
    self.markerdialog.ui.Disp_Ymark3.readpvname = self.globmarkpvs2[1].name
    self.ui.Disp_Xmark4.readpvname = self.globmarkpvs2[2].name
    self.markerdialog.ui.Disp_Xmark4.readpvname = self.globmarkpvs2[2].name
    self.ui.Disp_Ymark4.readpvname = self.globmarkpvs2[3].name
    self.markerdialog.ui.Disp_Ymark4.readpvname = self.globmarkpvs2[3].name
    return True

  def disconnectMarkerPVs(self):
    self.ui.Disp_Xmark1.readpvname = None
    self.markerdialog.ui.Disp_Xmark1.readpvname = None
    self.ui.Disp_Ymark1.readpvname = None
    self.markerdialog.ui.Disp_Ymark1.readpvname = None
    self.ui.Disp_Xmark2.readpvname = None
    self.markerdialog.ui.Disp_Xmark2.readpvname = None
    self.ui.Disp_Ymark2.readpvname = None
    self.markerdialog.ui.Disp_Ymark2.readpvname = None
    for i in self.globmarkpvs:
      try:
        i.disconnect()
      except:
        pass
    self.globmarkpvs = []
    return False

  def disconnectMarkerPVs2(self):
    self.ui.Disp_Xmark3.readpvname = None
    self.markerdialog.ui.Disp_Xmark3.readpvname = None
    self.ui.Disp_Ymark3.readpvname = None
    self.markerdialog.ui.Disp_Ymark3.readpvname = None
    self.ui.Disp_Xmark4.readpvname = None
    self.markerdialog.ui.Disp_Xmark4.readpvname = None
    self.ui.Disp_Ymark4.readpvname = None
    self.markerdialog.ui.Disp_Ymark4.readpvname = None
    for i in self.globmarkpvs2:
      try:
        i.disconnect()
      except:
        pass
    self.globmarkpvs2 = []
    return False

  def setupDrags(self):
    if self.camera != None:
      self.ui.display_image.readpvname = self.camera.name
    else:
      self.ui.display_image.readpvname = None
    if self.iocRoiXPv != None:
      self.ui.IOC_RoiX.readpvname = self.iocRoiXPv.name
    else:
      self.ui.IOC_RoiX.readpvname = None
    if self.iocRoiYPv != None:
      self.ui.IOC_RoiY.readpvname = self.iocRoiYPv.name
    else:
      self.ui.IOC_RoiY.readpvname = None
    if self.iocRoiWPv != None:
      self.ui.IOC_RoiW.readpvname = self.iocRoiWPv.name
    else:
      self.ui.IOC_RoiW.readpvname = None
    if self.iocRoiHPv != None:
      self.ui.IOC_RoiH.readpvname = self.iocRoiHPv.name
    else:
      self.ui.IOC_RoiH.readpvname = None
    if self.shiftPv != None:
      self.ui.shiftSlider.readpvname = self.shiftPv.name
      self.ui.shiftText.readpvname = self.shiftPv.name
    else:
      self.ui.shiftSlider.readpvname = None
      self.ui.shiftText.readpvname = None
    if self.lensPv != None:
      self.ui.horizontalSliderLens.readpvname = self.lensPv.name
      self.ui.lineEditLens.readpvname = self.lensPv.name
    else:
      self.ui.horizontalSliderLens.readpvname = None
      self.ui.lineEditLens.readpvname = None
    if self.avgPv != None:
      self.ui.remote_average.readpvname = self.avgPv.name
    else:
      self.ui.remote_average.readpvname = None
    
  def connectCamera(self, sCameraPv, index, sNotifyPv=None):
    timeout = 1.0
    self.camera    = self.disconnectPv(self.camera)
    self.notify    = self.disconnectPv(self.notify)
    self.nordPv    = self.disconnectPv(self.nordPv)
    self.rowPv     = self.disconnectPv(self.rowPv)
    self.colPv     = self.disconnectPv(self.colPv)
    self.shiftPv   = self.disconnectPv(self.shiftPv)
    self.iocRoiXPv = self.disconnectPv(self.iocRoiXPv)
    self.iocRoiYPv = self.disconnectPv(self.iocRoiYPv)
    self.iocRoiWPv = self.disconnectPv(self.iocRoiWPv)
    self.iocRoiHPv = self.disconnectPv(self.iocRoiHPv)
    self.params1Pv = self.disconnectPv(self.params1Pv)
    self.params2Pv = self.disconnectPv(self.params2Pv)
    sType = self.lType[index]
    # XTC is a special hack to display images from a file.
    if sType == "XTC":
      if "O" in self.lFlags[index]:
        # A simulated Opal.
        self.simtype = "O"
        self.xtcrdrdialog.show()
      else:
        self.simtype = None
        self.xtcrdrdialog.hide()
    else:
      self.simtype = None
      self.xtcrdrdialog.hide()
    self.xtcrdr = None

    self.cfgname = self.cameraBase + "," + sType
    if self.lFlags[index] != "":
      self.cfgname += "," + self.lFlags[index]

    # Set camera type
    print "Setting camtype for %s ..." % ( sType )
    if sType == "GE" or sType == "XTC" or sType == "DREC":
      self.camtype = [sType]
    else:
      self.camtype = caget(self.cameraBase + ":ID")
      if self.camtype != None and self.camtype != "":
        self.camtype = self.camtype.split()
      else:
        self.camtype = ["unknown"]

    # Try to connect to the camera
    try:
      self.nordPv = self.connectPv(sCameraPv + ".NORD")
      self.count = int(self.nordPv.value)
    except:
      self.nordPv = None
      self.count = None
    self.camera = self.connectPv(sCameraPv, count=self.count)
    if self.camera == None:
      self.ui.label_connected.setText("NO")
      return

    # Try to get the camera size!
    self.scale = 1
    if sType == "IC":
      if "Z" in self.lFlags[index]:
        self.rowPv     = self.connectPv(self.cameraBase + ":IMAGE:DoPrj.NOVA")
        self.colPv     = self.connectPv(self.cameraBase + ":IMAGE:DoPrj.NOVB")
        self.shiftPv   = None
        self.iocRoiXPv = self.connectPv(self.cameraBase + ":ROI_X_Start")
        self.iocRoiYPv = self.connectPv(self.cameraBase + ":ROI_Y_Start")
        self.iocRoiWPv = self.connectPv(self.cameraBase + ":ROI_X_End")
        self.iocRoiHPv = self.connectPv(self.cameraBase + ":ROI_Y_End")
        self.bits = 8
      elif "R" in self.lFlags[index]:
        self.rowPv     = self.connectPv(self.cameraBase + ":ROI_YNP")
        self.colPv     = self.connectPv(self.cameraBase + ":ROI_XNP")
        self.shiftPv   = None
        self.iocRoiXPv = self.connectPv(self.cameraBase + ":ROI_X")
        self.iocRoiYPv = self.connectPv(self.cameraBase + ":ROI_Y")
        self.iocRoiWPv = self.connectPv(self.cameraBase + ":ROI_XNP")
        self.iocRoiHPv = self.connectPv(self.cameraBase + ":ROI_YNP")
        self.bits = 12
      elif "M" in self.lFlags[index]:
        self.rowPv     = self.connectPv(self.cameraBase + ":IC_YNP")
        self.colPv     = self.connectPv(self.cameraBase + ":IC_XNP")
        self.shiftPv   = None
        self.iocRoiXPv = self.connectPv(self.cameraBase + ":ROI_X_SET")
        self.iocRoiYPv = self.connectPv(self.cameraBase + ":ROI_Y_SET")
        self.iocRoiWPv = self.connectPv(self.cameraBase + ":ROI_XNP_SET")
        self.iocRoiHPv = self.connectPv(self.cameraBase + ":ROI_YNP_SET")
        self.bits = caget(self.cameraBase + ":ROI_BITS")   # This should be monitored!
      else:
        self.rowPv     = self.connectPv(self.cameraBase + ":COMPRESSOR.VALF")
        self.colPv     = self.connectPv(self.cameraBase + ":COMPRESSOR.VALE")
        self.shiftPv   = self.connectPv(self.cameraBase + ":SHIFT")
        self.iocRoiXPv = self.connectPv(self.cameraBase + ":ROI_X")
        self.iocRoiYPv = self.connectPv(self.cameraBase + ":ROI_Y")
        self.iocRoiWPv = self.connectPv(self.cameraBase + ":ROI_XNP")
        self.iocRoiHPv = self.connectPv(self.cameraBase + ":ROI_YNP")
        self.bits = 8
      self.ui.groupBoxIOC.setVisible(self.ui.showconf.isChecked())
      self.ui.shiftWidget.setVisible(self.ui.showconf.isChecked() and self.shiftPv != None)
      self.isColor = False
    elif sType == "GE":
      if caget(self.cameraBase + ":ArraySize0_RBV") == 3:
        # It's a color camera!
        self.rowPv = self.connectPv(self.cameraBase + ":ArraySize2_RBV")
        self.colPv = self.connectPv(self.cameraBase + ":ArraySize1_RBV")
        self.isColor = True
        self.bits = caget(self.cameraBase + ":BIT_DEPTH")
        if self.bits == None:
          self.bits = 10
      else:
        # Just B/W!
        self.rowPv = self.connectPv(self.cameraBase + ":ArraySize1_RBV")
        self.colPv = self.connectPv(self.cameraBase + ":ArraySize0_RBV")
        self.isColor = False
        if self.lFlags[index] != "":
          self.bits = int(self.lFlags[index])
        else:
          self.bits = caget(self.cameraBase + ":BitsPerPixel_RBV")
          if self.bits == None:
            self.bits = caget(self.cameraBase + ":BIT_DEPTH")
            if self.bits == None:
              self.bits = 8
        self.ui.groupBoxIOC.setVisible(False)
    elif sType == "MCC":
      self.rowPv = self.connectPv(self.cameraBase + ":ROI_YNP")
      self.colPv = self.connectPv(self.cameraBase + ":ROI_XNP")
      self.ui.groupBoxIOC.setVisible(False)
      if self.simtype == None:
        self.bits = caget(self.cameraBase + ":N_OF_BITS")
      elif self.simtype == "O":
        self.bits = 12
      else:
        self.bits = None
      if (self.bits == None):
        self.bits = 12              # Sigh.  This is probably more than enough.
      self.isColor = False
    elif sType == "DREC":
      self.rowPv = self.connectPv(self.cameraBase + ".CROW")
      self.colPv = self.connectPv(self.cameraBase + ".CCOL")
      self.bits = caget(self.cameraBase + ".CBIT")
      self.ui.groupBoxIOC.setVisible(False)
      self.isColor = False
    else:
      if sType == "LIO" or sType == "LI":
        self.scale = 2
      if sType == "LIX":
        self.scale = 2
        self.colPv = self.connectPv(self.cameraBase + ":ROI_XNP")
        self.rowPv = self.connectPv(self.cameraBase + ":ROI_YNP")
      else:
        self.rowPv = self.connectPv(self.cameraBase + ":N_OF_ROW")
        self.colPv = self.connectPv(self.cameraBase + ":N_OF_COL")
      self.ui.groupBoxIOC.setVisible(False)
      if self.simtype == None:
        self.bits = caget(self.cameraBase + ":N_OF_BITS")
      elif self.simtype == "O":
        self.bits = 12
      else:
        self.bits = None
      if (self.bits == None):
        self.bits = 12              # Sigh.  This is probably more than enough.
      self.isColor = False

    havedrop = "D" in self.lFlags[index]
    self.ui.menuDroplet.menuAction().setVisible(havedrop)
    self.ui.groupBoxDrop.setVisible(havedrop)
    if havedrop:
      self.params1Pv = self.connectPv(self.cameraBase + ":PARAMS1")
      self.params2Pv = self.connectPv(self.cameraBase + ":PARAMS2")
      
    self.maxcolor = (1 << self.bits) - 1
    self.ui.horizontalSliderRangeMin.setMaximum(self.maxcolor)
    self.ui.horizontalSliderRangeMin.setTickInterval((1 << self.bits)/4)
    self.ui.horizontalSliderRangeMax.setMaximum(self.maxcolor)
    self.ui.horizontalSliderRangeMax.setTickInterval((1 << self.bits)/4)
    
    # See if we've connected to a camera with valid height and width
    if ( self.camera == None or
         self.rowPv == None  or self.rowPv.value == 0 or
         self.colPv == None  or self.colPv.value == 0 ):
      self.ui.label_connected.setText("NO")
      return

    if (sNotifyPv == None):
      self.notify = self.connectPv(sCameraPv, count=1)
    else:
      self.notify = self.connectPv(sNotifyPv, count=1)
    self.haveNewImage    = False
    self.lastGetDone     = True
    self.ui.label_connected.setText("YES")
    if self.isColor:
      self.camera.processor  = pycaqtimage.pyCreateColorImagePvCallbackFunc(self.imageBuffer)
      self.ui.grayScale.setVisible(True)
    else:
      self.camera.processor  = pycaqtimage.pyCreateImagePvCallbackFunc(self.imageBuffer)
      self.ui.grayScale.setVisible(False)
    self.notify.monitor_cb = self.haveImageCallback
    self.camera.getevt_cb = self.imagePvUpdateCallback
    self.rowPv.monitor_cb = self.sizeCallback
    self.colPv.monitor_cb = self.sizeCallback
    # Now, before we monitor, update the camera size!
    self.setImageSize(self.colPv.value / self.scale, self.rowPv.value / self.scale, True)
    self.updateMarkerText(True, True, 0, 15)
    self.notify.monitor(pyca.DBE_VALUE, False, 1) # Just 1 pixel, so a new image is available.
    self.rowPv.monitor(pyca.DBE_VALUE)
    self.colPv.monitor(pyca.DBE_VALUE)
    if self.shiftPv != None:
      self.shiftPv.monitor_cb   = self.iocroiCallback
      self.shiftPv.monitor(pyca.DBE_VALUE)
    if self.iocRoiXPv != None:
      self.iocRoiXPv.monitor_cb = self.iocroiCallback
      self.iocRoiXPv.monitor(pyca.DBE_VALUE)
    if self.iocRoiYPv != None:
      self.iocRoiYPv.monitor_cb = self.iocroiCallback
      self.iocRoiYPv.monitor(pyca.DBE_VALUE)
    if self.iocRoiWPv != None:
      self.iocRoiWPv.monitor_cb = self.iocroiCallback
      self.iocRoiWPv.monitor(pyca.DBE_VALUE)
    if self.iocRoiHPv != None:
      self.iocRoiHPv.monitor_cb = self.iocroiCallback
      self.iocRoiHPv.monitor(pyca.DBE_VALUE)
    if self.params1Pv != None:
      self.params1Pv.monitor_cb = self.param1Callback
      self.params1Pv.monitor(pyca.DBE_VALUE)
    if self.params2Pv != None:
      self.params2Pv.monitor_cb = self.param2Callback
      self.params2Pv.monitor(pyca.DBE_VALUE)
    pyca.flush_io()
    self.sWindowTitle = "Camera: " + self.lCameraDesc[index]
    self.setWindowTitle(QApplication.translate("MainWindow", self.sWindowTitle, None, QApplication.UnicodeUTF8))
    self.advdialog.setWindowTitle(self.sWindowTitle + " Advanced Mode")
    self.markerdialog.setWindowTitle(self.sWindowTitle + " Marker Settings")
    self.specificdialog.setWindowTitle(self.sWindowTitle + " Camera Settings")
    self.dropletdialog.setWindowTitle(self.sWindowTitle + " Droplet Settings")

    # Get camera configuration
    self.getConfig()

  def setCameraMenu(self, index):
    for a in self.camactions:
      a.setChecked(False)
    if index >= 0 and index < len(self.camactions):
      self.camactions[index].setChecked(True)

  def onCameraMenuSelect(self, action):
    index = self.camactions.index(action)
    if index >= 0 and index < len(self.camactions):
      self.ui.comboBoxCamera.setCurrentIndex(index)
  
  def onCameraSelect(self, index):
    self.clear()    
    if index < 0:
      return      
    if index >= len(self.lCameraList):
      print "index %d out of range (max: %d)" % (index, len(self.lCameraList) - 1)
      return        
    sCameraPv = str(self.lCameraList[index])
    if sCameraPv == "":
      return
    if self.cameraBase != "":
      self.activeClear()
    self.index = index
    self.cameraBase = sCameraPv

    self.startResize()
    self.activeSet()
    self.timeoutdialog.newconn()

    self.ctrlBase   = str(self.lCtrlList[index])

    self.setCameraMenu(index)
                               
    sLensPv = self.lLensList[index]
    sEvrPv  = self.lEvrList [index]
    sType   = self.lType[index]
    
    if sType == "AVG" or sType == "LIF":
      self.connectCamera(sCameraPv + ":LIVE_IMAGE_FULL", index)
    elif sType == "LIO" or sType == "LIX":
      self.connectCamera(sCameraPv + ":LIVE_IMAGE_12B", index)
    elif sType == "LI":
      self.connectCamera(sCameraPv + ":LIVE_IMAGE", index)
    elif sType == "IC":
      self.connectCamera(sCameraPv + ":IMAGE_CMPX", index)
    elif sType == "GE":
      self.connectCamera(sCameraPv + ":ArrayData", index)
    elif sType == "XTC":
      self.connectCamera(sCameraPv + ":LIVE_IMAGE_FULL", index)
    elif sType == "MCC":
#     self.connectCamera(sCameraPv + ":IMAGE", index)
      self.connectCamera(sCameraPv + ":BUFD_IMG", index)
    elif sType == "DREC":
      self.connectCamera(sCameraPv + ".ISLO", index)

    if sType == "AVG":
      self.ui.rem_avg.setVisible(True)
      self.ui.remote_average.setVisible(True)
      # Connect and monitor :AVERAGER.A (# of frames).
      try:
        self.avgPv = Pv(sCameraPv + ":AVERAGER.A")
        timeout = 1.0
        self.avgPv.connect(timeout)
        self.avgPv.monitor_cb = self.avgPvUpdateCallback
        self.avgPv.monitor(pyca.DBE_VALUE)
        pyca.flush_io()
      except:
        QMessageBox.critical(None,
                             "Error", "Failed to connect to Averager [%d] %s" % (index, sCameraPv),
                             QMessageBox.Ok, QMessageBox.Ok)
    else:
      self.ui.rem_avg.setVisible(False)
      self.ui.remote_average.setVisible(False)
      self.avgPv = None
    self.avgState = SINGLE_FRAME;
    self.ui.singleframe.setChecked(True)
    self.average = 1
    
    sLensPvDesc = sLensPv if sLensPv != "" else "None"
    print "Using Camera [%d] Pv %s Evr %s LensPv %s" % (index, sCameraPv, sEvrPv, sLensPvDesc )
    if sLensPv == "": 
      self.lensPv = None
      self.ui.labelLens.setVisible(False)
      self.ui.horizontalSliderLens.setVisible(False)
      self.ui.lineEditLens.setVisible(False)
    else:
      timeout = 1.0
      try:
        self.ui.labelLens.setVisible(True)
        self.ui.horizontalSliderLens.setVisible(True)
        self.ui.lineEditLens.setVisible(True)
        sLensSplit = sLensPv.split("/")
        if len(sLensSplit) == 3:
          lensName = sLensSplit[0].split(";")
          try:
            if sLensSplit[1] == "":
              self.ui.horizontalSliderLens.setMinimum(0)
            else:
              self.ui.horizontalSliderLens.setMinimum(int(sLensSplit[1]))
            self.ui.horizontalSliderLens.setMaximum(int(sLensSplit[2]))
          except:
            self.ui.horizontalSliderLens.setMinimum(0)
            self.ui.horizontalSliderLens.setMaximum(100)
        else:
          lensName = sLensPv.split(";")
          self.ui.horizontalSliderLens.setMinimum(0)
          self.ui.horizontalSliderLens.setMaximum(100)
        if len(lensName) > 1:
          self.putlensPv = Pv(lensName[0])
          self.lensPv = Pv(lensName[1])
        else:
          self.putlensPv = None
          self.lensPv = Pv(lensName[0])
        self.lensPv.connect(timeout)
        self.lensPv.monitor_cb = self.lensPvUpdateCallback
        self.lensPv.monitor(pyca.DBE_VALUE)
        if self.putlensPv != None:
          self.putlensPv.connect(timeout)
        pyca.flush_io()
      except:
        QMessageBox.critical(None,
                             "Error", "Failed to connect to Lens [%d] %s" % (index, sLensPv),
                             QMessageBox.Ok, QMessageBox.Ok)
    self.setupSpecific()
    self.setupDrags()
    self.finishResize()

  def onExpertMode(self):
    if self.ui.showexpert.isChecked():
      self.advdialog.ui.viewWidth.setText(str(self.viewwidth))
      self.advdialog.ui.viewHeight.setText(str(self.viewheight))
      self.advdialog.ui.projSize.setText(str(self.projsize))
      self.advdialog.ui.configCheckBox.setChecked(self.dispspec == 1)
      self.advdialog.show()
    else:
      self.advdialog.hide()

  def doShowDroplet(self):
    self.dropletdialog.show()

  def doShowSpecific(self):
    try:
      if self.camera == None:
        raise Exception
      if self.dispspec == 1:
        QMessageBox.critical(None,
                             "Warning", "Camera-specific configuration is on main screen!",
                             QMessageBox.Ok, QMessageBox.Ok)
        return
      camtype = self.camtype[0]
      if camtype == "UP685":
        raise Exception
      else:
        self.specificdialog.resize(400,1)
        self.specificdialog.show()
    except:
      pass

  #
  # Connect a gui element to two PVs, pvname for read, writepvname for writing.
  # The writepvname is actually just saved, but a monitor is setup for the read
  # pv which calls the callback.
  #
  def setupGUIMonitor(self, pvname, gui, callback, writepvname):
    try:
      if writepvname == None:
        gui.writepvname = None
      else:
        gui.writepvname = self.ctrlBase + writepvname
      gui.readpvname = self.ctrlBase + pvname
      pv = Pv(gui.readpvname)
      pv.connect(1.0)
      pv.monitor_cb = lambda e=None: callback(e, pv, gui)
      pv.monitor(pyca.DBE_VALUE)
      pyca.flush_io()
      self.otherpvs.append(pv)
    except:
      pass

  def lineEditMonitorCallback(self, exception, pv, lineedit):
    if exception is None:
      lineedit.setText("%g" % pv.value)

  def setupLineEditMonitor(self, pvname, lineedit, writepvname):
    self.setupGUIMonitor(pvname, lineedit, self.lineEditMonitorCallback, writepvname)

  def comboMonitorCallback(self, exception, pv, combobox):
    if exception is None:
      combobox.lastwrite = pv.value
      combobox.setCurrentIndex(pv.value)

  def setupComboMonitor(self, pvname, combobox, writepvname):
    combobox.lastwrite = -1
    self.setupGUIMonitor(pvname, combobox, self.comboMonitorCallback, writepvname)

  def comboWriteCallback(self, combobox, idx):
    if combobox.writepvname == None:
      return
    try:
      if idx != combobox.lastwrite:
        combobox.lastwrite = idx
        caput(combobox.writepvname, idx)
    except:
      pass

  def lineIntWriteCallback(self, lineedit):
    if lineedit.writepvname == None:
      return
    try:
      v = int(lineedit.text())
      caput(lineedit.writepvname, v)
    except:
      pass

  def lineFloatWriteCallback(self, lineedit):
    if lineedit.writepvname == None:
      return
    try:
      v = float(lineedit.text())
      caput(lineedit.writepvname, v)
    except:
      pass

  def setupButtonMonitor(self, pvname, button, writepvname):
    self.setupGUIMonitor(pvname, button, self.buttonMonitorCallback, writepvname)

  def buttonMonitorCallback(self, exception, pv, button):
    if exception is None:
      if pv.value == 1:
        button.setChecked(True)
        button.setText("Running")
      else:
        button.setChecked(False)
        button.setText("Stopped")

  def buttonWriteCallback(self, button):
    if button.isChecked():
      button.setText("Running")
      caput(button.writepvname, 1)
    else:
      button.setText("Stopped")
      caput(button.writepvname, 0)

  def setupSpecific(self):
    self.specificdialog.ui.gigeBox.hide()
    self.specificdialog.ui.opalBox.hide()
    self.specificdialog.ui.pulnixBox.hide()
    self.specificdialog.ui.up900Box.hide()
    camtype = self.camtype[0]
    if camtype == "UP685":
      return
    if camtype == "UP900":
      self.specificdialog.ui.up900Box.show()
      self.setupComboMonitor   (":Shutter",  self.specificdialog.ui.timeU,       ":Shutter")
      self.setupLineEditMonitor(":ReadGain", self.specificdialog.ui.gainU,       ":Gain")
      return
    if (camtype == "OPAL-1000m/CL" or camtype == "OPAL-1000m/Q" or
          camtype == "OPAL-4000m/CL"):
      self.specificdialog.ui.opalBox.show()
      self.ui.actionGlobalMarkers.setChecked(self.useglobmarks)
      self.setupComboMonitor   (":MO",       self.specificdialog.ui.cameramodeO, ":SetMO")
      self.setupLineEditMonitor(":ReadGain", self.specificdialog.ui.gainO,       ":Gain")
      self.setupLineEditMonitor(":IT",       self.specificdialog.ui.timeO,       ":SetIT")
      self.setupLineEditMonitor(":FP",       self.specificdialog.ui.periodO,     ":SetFP")
      return
    if camtype == "JAI,":
      self.specificdialog.ui.pulnixBox.show()
      self.specificdialog.ui.cameramodeP.hide()  # This just doesn't work!
      self.specificdialog.ui.cmlabelP.hide()
      self.ui.actionGlobalMarkers.setChecked(self.useglobmarks)
      self.setupComboMonitor   (":ShutterMode", self.specificdialog.ui.cameramodeP, None)
      self.setupComboMonitor   (":Shutter",     self.specificdialog.ui.timeP,       ":Shutter")
      self.setupLineEditMonitor(":GainA",       self.specificdialog.ui.gainAP,      ":GainA")
      self.setupLineEditMonitor(":GainB",       self.specificdialog.ui.gainBP,      ":GainB")
      return
    if camtype == "GE":
      self.specificdialog.ui.gigeBox.show()
      self.ui.actionGlobalMarkers.setChecked(self.useglobmarks)
      self.setupComboMonitor   (":TriggerMode_RBV",   self.specificdialog.ui.cameramodeG, ":TriggerMode")
      self.setupLineEditMonitor(":Gain_RBV",          self.specificdialog.ui.gainG,       ":Gain")
      self.setupLineEditMonitor(":AcquireTime_RBV",   self.specificdialog.ui.timeG,       ":AcquireTime")
      self.setupLineEditMonitor(":AcquirePeriod_RBV", self.specificdialog.ui.periodG,     ":AcquirePeriod")
      self.setupButtonMonitor  (":Acquire",           self.specificdialog.ui.runButtonG,  ":Acquire")
      return

  def changeSize(self, newwidth, newheight, newproj, settext, doresize=True):
    if( self.colPv == None or self.colPv == 0 or
        self.rowPv == None or self.rowPv == 0 ):
        return
    if newwidth >= 400 and newheight >= 400 and newproj >= 250:
      if (self.viewwidth != newwidth or self.viewheight != newheight or
          self.projsize != newproj):
        self.viewwidth = newwidth
        self.viewheight = newheight
        self.projsize = newproj
        if settext:
          self.advdialog.ui.viewWidth.setText(str(self.viewwidth))
          self.advdialog.ui.viewHeight.setText(str(self.viewheight))
          self.advdialog.ui.projSize.setText(str(self.projsize))
        if doresize:
          self.startResize()
          self.ui.display_image.doResize(QSize(self.viewwidth, self.viewheight))
          sizeProjX = QSize(self.viewwidth, self.projsize)
          self.ui.projH.doResize(sizeProjX)
          sizeProjY = QSize(self.projsize, self.viewheight)
          self.ui.projV.doResize(sizeProjY)
          self.ui.projectionFrame.setFixedSize(QSize(self.projsize, self.projsize))
          self.ui.projectionFrame_left.setFixedWidth(self.projsize)
          self.ui.projectionFrame_right.setFixedHeight(self.projsize)
          self.finishResize()
      self.setImageSize(self.colPv.value / self.scale, self.rowPv.value / self.scale, False)
      if self.cfg == None:
        self.dumpConfig()

  def onAdvanced(self, button):
    role = self.advdialog.ui.buttonBox.buttonRole(button)
    if role == QDialogButtonBox.ApplyRole or role == QDialogButtonBox.AcceptRole:
      try:
        newwidth = int(self.advdialog.ui.viewWidth.text())
        newheight = int(self.advdialog.ui.viewHeight.text())
        newproj = int(self.advdialog.ui.projSize.text())
        self.setDispSpec(int(self.advdialog.ui.configCheckBox.isChecked()))
        self.changeSize(newwidth, newheight, newproj, False)
        self.advdialog.ui.viewWidth.setText(str(self.viewwidth))
        self.advdialog.ui.viewHeight.setText(str(self.viewheight))
        self.advdialog.ui.projSize.setText(str(self.projsize))
      except:
        print "onAdvanced threw an exception"
    if role == QDialogButtonBox.RejectRole or role == QDialogButtonBox.AcceptRole:
      self.ui.showexpert.setChecked(False)

  def onSpecific(self, button):
    pass

  def onDroplet(self, button):
    role = self.dropletdialog.ui.buttonBox.buttonRole(button)
    if role == QDialogButtonBox.ApplyRole or role == QDialogButtonBox.AcceptRole:
      try:
        nf1 = float(self.dropletdialog.ui.noisefloor1.text())
        l = list(self.params1Pv.value)
        l[0] = nf1
        self.params1Pv.put(tuple(l))
      except:
        print "onDroplet threw an exception"
      try:
        nf2 = float(self.dropletdialog.ui.noisefloor2.text())
        l = list(self.params2Pv.value)
        l[0] = nf2
        self.params2Pv.put(tuple(l))
      except:
        print "onDroplet threw an exception"
      try:
        pyca.flush_io()
      except:
        print "onDroplet threw an exception"
        
  def onOpenEvr(self):
    iCamera = self.ui.comboBoxCamera.currentIndex()
    if self.lEvrList[iCamera] != "None":
      print "Open Evr %s for camera [%d] %s..." % (self.lEvrList[iCamera], iCamera, self.lCameraList[iCamera])
      os.system(self.cwd + "/openEvr.sh " + self.lEvrList[iCamera] + " &")
                           
  def onSliderRangeMinChanged(self, newSliderValue):
    self.ui.lineEditRangeMin.setText(str(newSliderValue))
    self.iRangeMin = newSliderValue
    if newSliderValue > self.iRangeMax:
      self.ui.horizontalSliderRangeMax.setValue(newSliderValue)
    self.setColorMap()
    self.updateProj()
    self.updateMiscInfo()

  def onSliderRangeMaxChanged(self, newSliderValue):
    self.ui.lineEditRangeMax.setText(str(newSliderValue))
    self.iRangeMax = newSliderValue
    if newSliderValue < self.iRangeMin:
      self.ui.horizontalSliderRangeMin.setValue(newSliderValue)
    self.setColorMap()
    self.updateProj()
    self.updateMiscInfo()

  def onSliderLensChanged(self, newSliderValue):
    self.ui.lineEditLens.setText(str(newSliderValue))
                           
  def onSliderLensReleased(self):
    newSliderValue = self.ui.horizontalSliderLens.value()
    if self.lensPv != None:
      try:
        if self.putlensPv != None:
          self.putlensPv.put(newSliderValue)
        else:
          self.lensPv.put(newSliderValue)
        pyca.flush_io()
      except pyca.pyexc, e:
        print 'pyca exception: %s' %(e)
      except pyca.caexc, e:
        print 'channel access exception: %s' %(e)

  def onRangeMinTextEnter(self):
    try:
      value = int(self.ui.lineEditRangeMin.text())
    except:
      value = 0
      
    if value < 0: value = 0
    if value > self.maxcolor: value = self.maxcolor
    self.ui.horizontalSliderRangeMin.setValue(value)

  def onRangeMaxTextEnter(self):
    try:
      value = int(self.ui.lineEditRangeMax.text())
    except:
      value = 0
      
    if value < 0: value = 0
    if value > self.maxcolor: value = self.maxcolor
    self.ui.horizontalSliderRangeMax.setValue(value)

  def onLensEnter(self):
    try:
      value = int(self.ui.lineEditLens.text())
    except:
      value = 0

    mn = self.ui.horizontalSliderLens.minimum()
    mx = self.ui.horizontalSliderLens.maximum()
    if value < mn: value = mn
    if value > mx: value = mx
    self.ui.horizontalSliderLens.setValue(value)
    if self.lensPv != None:
      try:
        if self.putlensPv != None:
          self.putlensPv.put(value)
        else:
          self.lensPv.put(value)
        pyca.flush_io()
      except pyca.pyexc, e:
        print 'pyca exception: %s' %(e)
      except pyca.caexc, e:
        print 'channel access exception: %s' %(e)

  def onRemAvgEnter(self):
    try:
      value = int(self.ui.remote_average.text())
    except:
      value = 0
      
    if value < 1: value = 1
    if self.avgPv != None:
      try:
        self.avgPv.put(value)
        pyca.flush_io()
      except pyca.pyexc, e:
        print 'pyca exception: %s' %(e)
      except pyca.caexc, e:
        print 'channel access exception: %s' %(e)

  def onShiftText(self):
    try:
      value = int(self.ui.shiftText.text())
      if value < 0: value = 0
      if value > 8: value = 8
      self.ui.shiftText.setText(str(value))
      self.ui.shiftSlider.setValue(value)
      self.shiftPv.put(value)
      pyca.flush_io()
    except pyca.pyexc, e:
      print 'pyca exception: %s' %(e)
    except pyca.caexc, e:
      print 'channel access exception: %s' %(e)
    except:
      pass

  def onShiftSliderChanged(self, newSliderValue):
    self.ui.shiftText.setText(str(newSliderValue))
                           
  def onShiftSliderReleased(self):
    newSliderValue = self.ui.shiftSlider.value()
    try:
      self.shiftPv.put(newSliderValue)
      pyca.flush_io()
    except pyca.pyexc, e:
      print 'pyca exception: %s' %(e)
    except pyca.caexc, e:
      print 'channel access exception: %s' %(e)

  def onIOCROI(self, gui, name):
    try:
      v = int(gui.text())
      caput(name, v)
    except:
      pass

  def onIOCROIX(self):
    self.onIOCROI(self.ui.IOC_RoiX, self.cameraBase + ":ROI_X_SET")

  def onIOCROIY(self):
    self.onIOCROI(self.ui.IOC_RoiY, self.cameraBase + ":ROI_Y_SET")

  def onIOCROIW(self):
    self.onIOCROI(self.ui.IOC_RoiW, self.cameraBase + ":ROI_XNP_SET")

  def onIOCROIH(self):
    self.onIOCROI(self.ui.IOC_RoiH, self.cameraBase + ":ROI_YNP_SET")

  # Note: this function is called by the CA library, from another thread
  def iocroiCallback(self, exception=None):           
    if exception is None:
      self.event.emit(QtCore.SIGNAL("onIOCUpdate"))
    else:
      print "iocroiCallback(): %-30s " % (self.name), exception

  def onIOCUpdate(self):
    if (self.shiftPv != None):
      try:
        v = int(self.shiftPv.value)
        self.ui.shiftText.setText(str(v))
        self.ui.shiftSlider.setValue(v)
      except:
        pass
    if (self.iocRoiXPv != None):
      try:
        v = int(self.iocRoiXPv.value)
        self.ui.IOC_RoiX.setText(str(v))
      except:
        pass
    if (self.iocRoiYPv != None):
      try:
        v = int(self.iocRoiYPv.value)
        self.ui.IOC_RoiY.setText(str(v))
      except:
        pass
      pass
    if (self.iocRoiHPv != None):
      try:
        v = int(self.iocRoiHPv.value)
        self.ui.IOC_RoiH.setText(str(v))
      except:
        pass
      pass
    if (self.iocRoiWPv != None):
      try:
        v = int(self.iocRoiWPv.value)
        self.ui.IOC_RoiW.setText(str(v))
      except:
        pass

  def onReconnect(self):
    self.timeoutdialog.reconn()

  def onForceDisco(self):
    if self.cameraBase != "" and not self.haveforce:
      self.forcedialog = forcedialog(self.activedir + self.cameraBase + "/", self)
      self.haveforce = True

  # We have been idle for a while!
  def do_disco(self):
    self.discoTimer.stop()
    self.timeoutdialog.activate()

  def stop_disco(self):
    self.discoTimer.stop()

  def setDisco(self, secs):
    self.discoTimer.start(1000 * secs)
    if self.notify != None and not self.notify.ismonitored:
      self.notify.monitor(pyca.DBE_VALUE, False, 1)
      pyca.flush_io()

  def onTimeoutExpiry(self):
    self.notify.unsubscribe()
    pyca.flush_io()

  def activeCheck(self):
    if self.cameraBase == "":
      return
    file = self.activedir + self.cameraBase + "/" + self.description
    try:
      f = open(file)
      l = f.readlines()
      if (len(l) > 1):
        self.timeoutdialog.force(l[1].strip())
        self.activeSet()
    except:
      pass

  def activeClear(self):
    try:
      file = self.activedir + self.cameraBase + "/" + self.description
      os.unlink(file)
    except:
      pass

  def activeSet(self):
    try:
      dir = self.activedir + self.cameraBase
      try:
        os.mkdir(dir)
      except:
        pass # It might already exist!
      f = open(dir + "/" + self.description, "w")
      f.write(os.ttyname(0) + "\n")
      f.close()
    except:
      pass

  def setDispSpec(self, v):
    if v != self.dispspec:
      if v == 0:
        self.specificdialog.ui.verticalLayout.addWidget(self.specificdialog.ui.gigeBox)
        self.specificdialog.ui.verticalLayout.addWidget(self.specificdialog.ui.pulnixBox)
        self.specificdialog.ui.verticalLayout.addWidget(self.specificdialog.ui.opalBox)
        self.specificdialog.ui.verticalLayout.addWidget(self.specificdialog.ui.buttonBox)
      else:
        # Sigh.  The last item is a spacer which we need to keep as the last item!
        spc = self.ui.RightPanel.itemAt(self.ui.RightPanel.count() - 1)
        self.ui.RightPanel.removeItem(spc)
        self.ui.RightPanel.addWidget(self.specificdialog.ui.gigeBox)
        self.ui.RightPanel.addWidget(self.specificdialog.ui.pulnixBox)
        self.ui.RightPanel.addWidget(self.specificdialog.ui.opalBox)
        self.ui.RightPanel.addItem(spc)
        self.specificdialog.ui.verticalLayout.removeWidget(self.specificdialog.ui.buttonBox)
      self.ui.RightPanel.invalidate()
      self.adjustSize()
      self.update()
      self.dispspec = v

  def dumpConfig(self):
    if self.camera != None and self.options == None:
      f = open(self.cfgdir + self.cfgname, "w")
      g = open(self.cfgdir + "GLOBAL", "w")

      f.write("projsize    " + str(self.projsize) + "\n")
      f.write("viewwidth   " + str(self.viewwidth) + "\n")
      f.write("viewheight  " + str(self.viewheight) + "\n")
      g.write("config      " + str(int(self.ui.showconf.isChecked())) + "\n")
      g.write("projection  " + str(int(self.ui.showproj.isChecked())) + "\n")
      g.write("markers     " + str(int(self.ui.showmarker.isChecked())) + "\n")
      f.write("portrait    " + str(int(param.orientation == param.ORIENT90)) + "\n")
      f.write("orientation " + str(param.orientation) + "\n")
      f.write("autorange   " + str(int(self.ui.checkBoxProjAutoRange.isChecked())) + "\n")
      f.write("projROI     " + str(int(self.ui.checkBoxProjRoi.isChecked())) + "\n")
      f.write("use_abs     1\n")
      rz = self.ui.display_image.rectZoom.abs()
      f.write("rectzoom    " + str(rz.x()) + " "
                             + str(rz.y()) + " "
                             + str(rz.width()) + " "
                             + str(rz.height()) + "\n")
      f.write("colormap    " + str(self.ui.comboBoxColor.currentText()) + "\n")
      f.write("colorscale  " + str(self.ui.comboBoxScale.currentText()) + "\n")
      f.write("colormin    " + self.ui.lineEditRangeMin.text() + "\n")
      f.write("colormax    " + self.ui.lineEditRangeMax.text() + "\n")
      f.write("grayscale   " + str(int(self.ui.grayScale.isChecked())) + "\n")
      roi = self.ui.display_image.rectRoi.abs()
      f.write("ROI         %d %d %d %d\n" % (roi.x(), roi.y(), roi.width(), roi.height()))
      f.write("globmarks   " + str(int(self.useglobmarks)) + "\n")
      f.write("globmarks2  " + str(int(self.useglobmarks2)) + "\n")
      lMarker = self.ui.display_image.lMarker
      for i in range(4):
        f.write("m%d          %d %d\n" % (i+1, lMarker[i].abs().x(), lMarker[i].abs().y()))
      g.write("xtcdir      " + self.xtcdir + "\n")
      g.write("dispspec    " + str(self.dispspec) + "\n")

      f.close()
      g.close()

      settings = QtCore.QSettings("SLAC", "CamViewer");
      settings.setValue("geometry/%s" % self.cfgname, self.saveGeometry())
      settings.setValue("windowState/%s" % self.cfgname, self.saveState())


  def getConfig(self):
    if self.camera == None:
      return
    self.cfg = cfginfo()
    if not self.cfg.read(self.cfgdir + "GLOBAL"):
      self.cfg.add("config", "1")
      self.cfg.add("projection", "1")
      self.cfg.add("markers", "1")
      self.cfg.add("orientation", str(param.ORIENT0))
      self.cfg.add("dispspec", "0")
    if self.options != None:
      # Let the command line options override the config file!
      if self.options.config != None:
        self.cfg.add("config", self.options.config)
      if self.options.proj != None:
        self.cfg.add("projection", self.options.proj)
      if self.options.marker != None:
        self.cfg.add("markers", self.options.marker)
      if self.options.camcfg != None:
        self.cfg.add("dispspec", self.options.camcfg)
    if not self.fixname:
      # OK, old school!  Get rid of all of the final ":.*" from each camera!
      self.fixname = True
      for file in os.listdir(self.cfgdir):
        match = re.search("^(.*):(AVG_IMAGE|IMAGE_CMPX|LIVE_IMAGE_FULL|ArrayData)$", file)
        if match:
          try:
            os.rename(self.cfgdir + file, self.cfgdir + match.group(1))
          except:
            pass

    # Read the config file
    if not self.cfg.read(self.cfgdir + self.cfgname):
      # OK, didn't work, look for an old one.
      if not self.cfg.read(self.cfgdir + self.cameraBase):
        # Bail if we can't find it
        # But first, let's immediately process the command line options, if any.
        mk = int(self.cfg.markers)
        self.ui.showmarker.setChecked(mk)
        self.doShowMarker()
        dc = int(self.cfg.dispspec)
        self.setDispSpec(dc)
        self.ui.showconf.setChecked(int(self.cfg.config))
        self.doShowConf()
        self.ui.showproj.setChecked(int(self.cfg.projection))
        self.doShowProj()
        if self.options != None:
          if self.options.orientation != None:
            self.setOrientation(int(self.options.orientation))
          elif self.options.lportrait != None:
            if int(self.options.lportrait):
              self.setOrientation(param.ORIENT90)
            else:
              self.setOrientation(param.ORIENT0)
          if self.options.cmap != None:
            self.ui.comboBoxColor.setCurrentIndex(self.ui.comboBoxColor.findText(self.options.cmap))
            self.colorMap = self.options.cmap.lower()
            self.ui.grayScale.setChecked(True)  # If we want a color map, force gray scale!
            self.setColorMap()
          self.options = None
        self.dumpConfig()
        self.cfg = None
        return

    # Let command line options override local config file
    if self.options != None:
      if self.options.orientation != None:
        self.cfg.add("cmd_orientation", int(self.options.orientation))
      elif self.options.lportrait != None:
        if self.options.lportrait == "0":
          self.cfg.add("cmd_orientation", param.ORIENT0)
        else:
          self.cfg.add("cmd_orientation", param.ORIENT90)
      if self.options.cmap != None:
        self.cfg.add("colormap", self.options.cmap)
      self.options = None

    try:
      use_abs = int(self.cfg.use_abs)
    except:
      use_abs = 0

    # Set the window size
    settings = QtCore.QSettings("SLAC", "CamViewer");
    pos = self.pos()
    self.restoreGeometry(settings.value("geometry/%s" % self.cfgname).toByteArray());
    self.move(pos)   # Just restore the size, keep the position!
    self.restoreState(settings.value("windowState/%s" % self.cfgname).toByteArray());

    # I think we're going to assume that since we've written this file, it's correct.
    # Do, or do not.  There is no try.
    newwidth = self.cfg.viewwidth
    newheight = self.cfg.viewheight
    if int(newwidth) < self.minwidth:
      newwidth = str(self.minwidth)
    if int(newheight) < self.minheight:
      newheight = str(self.minheight)
    newproj = self.cfg.projsize
    self.advdialog.ui.viewWidth.setText(newwidth)
    self.advdialog.ui.viewHeight.setText(newheight)
    self.advdialog.ui.projSize.setText(newproj)
    self.ui.showconf.setChecked(int(self.cfg.config))
    self.doShowConf()
    self.ui.showproj.setChecked(int(self.cfg.projection))
    self.doShowProj()
    # These are new fields, so they might not be in old configs!
    try:
      mk = int(self.cfg.markers)
    except:
      mk = 1
    self.ui.showmarker.setChecked(mk)
    self.doShowMarker()
    try:
      dc = int(self.cfg.dispspec)
    except:
      dc = 0
    self.setDispSpec(dc)
    try:
      orientation = self.cfg.orientation
    except:
      orientation = param.ORIENT0
    self.setOrientation(int(orientation))
    self.ui.checkBoxProjAutoRange.setChecked(int(self.cfg.autorange))
    self.ui.checkBoxProjRoi.setChecked(int(self.cfg.projROI))
    try:
      self.ui.display_image.setRectZoom(float(self.cfg.rectzoom[0]), float(self.cfg.rectzoom[1]),
                                        float(self.cfg.rectzoom[2]), float(self.cfg.rectzoom[3]))
    except:
      pass
    try:
      self.ui.display_image.roiSet(float(self.cfg.roi[0]), float(self.cfg.roi[1]),
                                   float(self.cfg.roi[2]), float(self.cfg.roi[3]), rel=(use_abs==0))
    except:
      pass
    self.updateall()
    self.ui.comboBoxColor.setCurrentIndex(self.ui.comboBoxColor.findText(self.cfg.colormap))
    self.colorMap = self.cfg.colormap.lower()
    # OK, we're changing this to introduce more scales!  So,
    # "Log Scale" --> "Log2 Scale" and "Exp Scale" --> "Exp2 Scale"
    if self.cfg.colorscale[0] == "Log":
      self.cfg.colorscale[0] = "Log2"
    elif self.cfg.colorscale[0] == "Exp":
      self.cfg.colorscale[0] = "Exp2"
    self.iScaleIndex = self.ui.comboBoxScale.findText(self.cfg.colorscale[0] + " " +
                                                      self.cfg.colorscale[1])
    self.ui.comboBoxScale.setCurrentIndex(self.iScaleIndex)
    self.ui.lineEditRangeMin.setText(self.cfg.colormin)
    self.onRangeMinTextEnter()
    self.ui.lineEditRangeMax.setText(self.cfg.colormax)
    self.onRangeMaxTextEnter()
    try:
      self.ui.grayScale.setChecked(int(self.cfg.grayscale))
      self.onCheckGrayUpdate(int(self.cfg.grayscale))
    except:
      pass
    self.setColorMap()
    try:
      self.useglobmarks = bool(int(self.cfg.globmarks))
    except:
      self.useglobmarks = False
    if self.useglobmarks:
      self.useglobmarks = self.connectMarkerPVs()
    self.ui.actionGlobalMarkers.setChecked(self.useglobmarks)
    try:
      self.useglobmarks2 = bool(int(self.cfg.globmarks2))
    except:
      self.useglobmarks2 = False
    if self.useglobmarks2:
      self.useglobmarks2 = self.connectMarkerPVs2()
    self.ui.showdrops.setChecked(self.useglobmarks2)
    self.ui.actionShowDrop.setChecked(self.useglobmarks2)
    if self.useglobmarks:
      self.onCrossUpdate(0)
      self.onCrossUpdate(1)
    else:
      if use_abs == 1:
        self.ui.display_image.lMarker[0].setAbs(int(self.cfg.m1[0]), int(self.cfg.m1[1]))
        self.ui.display_image.lMarker[1].setAbs(int(self.cfg.m2[0]), int(self.cfg.m2[1]))
      else:
        self.ui.display_image.lMarker[0].setRel(int(self.cfg.m1[0]), int(self.cfg.m1[1]))
        self.ui.display_image.lMarker[1].setRel(int(self.cfg.m2[0]), int(self.cfg.m2[1]))
    if self.useglobmarks2:
      self.onCrossUpdate(2)
      self.onCrossUpdate(3)
    else:
      if use_abs == 1:
        self.ui.display_image.lMarker[2].setAbs(int(self.cfg.m3[0]), int(self.cfg.m3[1]))
        self.ui.display_image.lMarker[3].setAbs(int(self.cfg.m4[0]), int(self.cfg.m4[1]))
      else:
        self.ui.display_image.lMarker[2].setRel(int(self.cfg.m3[0]), int(self.cfg.m3[1]))
        self.ui.display_image.lMarker[3].setRel(int(self.cfg.m4[0]), int(self.cfg.m4[1]))
    self.updateMarkerText()
    self.changeSize(int(newwidth), int(newheight), int(newproj), False)
    try:
      self.xtcdir = self.cfg.xtcdir
    except:
      self.xtcdir = os.getenv("HOME")
    try:
      # OK, see if we've delayed the command line orientation setting until now.
      orientation = self.cfg.cmd_orientation
      self.setOrientation(int(orientation))
    except:
      pass
    self.cfg = None
