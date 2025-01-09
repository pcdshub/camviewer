# NOTES:
# OK, New regime: all of the rotation is handled by the false coloring processor for the image PV.
# So, now this processor is given an orientation, and everything is automatically rotated with
# x going right and y going down, (0,0) in the upper left corner.  The Rect and Point classes in
# the param module automatically deal with absolute image coordinates as well as rotated ones.
#
# So, we only have to deal with true screen coordinates and how the oriented image is mapped to
# this.
#
from __future__ import annotations

from camviewer_ui import Ui_MainWindow
from psp.Pv import Pv
from dialogs import advdialog
from dialogs import markerdialog
from dialogs import specificdialog
from dialogs import forcedialog

import sys
import os
from pycaqtimage import pycaqtimage
import pyca
import math
import re
import time
import functools
import numpy as np
import numpy.typing as npt
import tempfile
import shutil
import typing
import contextlib
import subprocess

from PyQt5.QtWidgets import (
    QSizePolicy,
    QLabel,
    QMainWindow,
    QSpacerItem,
    QFileDialog,
    QMessageBox,
    QAction,
    QDialogButtonBox,
    QApplication,
)
from PyQt5.QtGui import (
    QClipboard,
    QPixmap,
    QDrag,
    QImageWriter,
)
from PyQt5.QtCore import (
    QTimer,
    QPoint,
    QSize,
    QObject,
    QEvent,
    Qt,
    QMimeData,
    QSettings,
    pyqtSignal,
)

import param


#
# Utility functions to put/get Pv values.
#
def caput(pvname, value, timeout=1.0):
    try:
        pv = Pv(pvname, initialize=True)
        pv.wait_ready(timeout)
        pv.put(value, timeout)
        pv.disconnect()
    except pyca.pyexc as e:
        print("pyca exception: %s" % (e))
    except pyca.caexc as e:
        print("channel access exception: %s" % (e))


def caget(pvname, timeout=1.0):
    try:
        pv = Pv(pvname, initialize=True)
        pv.wait_ready(timeout)
        v = pv.value
        pv.disconnect()
        return v
    except pyca.pyexc as e:
        print("pyca exception: %s" % (e))
        return None
    except pyca.caexc as e:
        print("channel access exception: %s" % (e))
        return None


#
# A configuration object class.
#
class cfginfo:
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
        except Exception:
            return False

    def add(self, attr, val):
        self.dict[attr] = val

    def __getattr__(self, name):
        if name in self.dict.keys():
            return self.dict[name]
        else:
            raise AttributeError


class FilterObject(QObject):
    def __init__(self, app: QApplication, main: GraphicUserInterface):
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
        self.renderlabel.setMinimumSize(QSize(0, 20))
        self.renderlabel.setMaximumSize(QSize(16777215, 100))
        self.last = QPoint(0, 0)

    def eventFilter(self, obj, event):
        if event.type() in [QEvent.MouseButtonPress, QEvent.KeyPress]:
            self.main.refresh_rate_timer()
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.MidButton:
            p = event.globalPos()
            w = self.app.widgetAt(p)
            if w == obj and self.last != p:
                self.last = p
                try:
                    t = w.writepvname
                except Exception:
                    t = None
                if t is None:
                    try:
                        t = w.readpvname
                    except Exception:
                        t = None
                if t is None:
                    return False
                self.clip.setText(t, QClipboard.Selection)
                mimeData = QMimeData()
                mimeData.setText(t)
                self.renderlabel.setText(t)
                self.renderlabel.adjustSize()
                pixmap = QPixmap(self.renderlabel.size())
                self.renderlabel.render(pixmap)
                drag = QDrag(self.main)
                drag.setMimeData(mimeData)
                drag.setPixmap(pixmap)
                drag.exec_(Qt.CopyAction)
        return False


SINGLE_FRAME = 0
LOCAL_AVERAGE = 2


class GraphicUserInterface(QMainWindow):
    # Define our signals.
    imageUpdate = pyqtSignal()
    miscUpdate = pyqtSignal()
    sizeUpdate = pyqtSignal()
    cross1Update = pyqtSignal()
    cross2Update = pyqtSignal()
    cross3Update = pyqtSignal()
    cross4Update = pyqtSignal()
    retry_save_image = pyqtSignal()

    def __init__(
        self,
        app,
        cwd,
        instrument,
        camera,
        cameraPv,
        cameraListFilename,
        cfgdir,
        activedir,
        rate,
        idle,
        min_timeout,
        max_timeout,
        options,
    ):
        QMainWindow.__init__(self)
        self.app = app
        self.cwd = cwd
        self.rcnt = 0
        self.resizing = False
        self.cfgdir = cfgdir
        self.cfg = None
        self.activedir = activedir
        self.instrument = instrument
        self.description = "%s:%d" % (os.uname()[1], os.getpid())
        self.min_timeout = min_timeout
        self.max_timeout = max_timeout
        self.options = options

        if self.options.pos is not None:
            try:
                p = self.options.pos.split(",")
                p = QPoint(int(p[0]), int(p[1]))
                self.move(p)
            except Exception:
                pass

        # View parameters
        self.viewwidth = 640  # Size of our viewing area.
        self.viewheight = 640  # Size of our viewing area.
        self.projsize = 300  # Size of our projection window.
        self.minwidth = 450
        self.minheight = 450
        self.minproj = 250

        # Default to VGA!
        param.setImageSize(640, 480)
        self.isColor = False
        self.bits = 10
        self.maxcolor = 1023
        self.lastUpdateTime = time.time()
        self.dispUpdates = 0
        self.lastDispUpdates = 0
        self.average = 1
        param.orientation = param.ORIENT0
        self.connected = False
        self.cameraBase = ""
        self.camera = None
        self.notify = None
        self.haveNewImage = False
        self.lastGetDone = True
        self.wantNewImage = True
        self.lensPv = None
        self.putlensPv = None
        self.nordPv = None
        self.nelmPv = None
        self.count = None
        self.maxcount = None
        self.rowPv = None
        self.colPv = None
        self.launch_gui_pv = None
        self.launch_edm_pv = None
        self.launch_gui_script = ""
        self.launch_edm_script = ""
        self.scale = 1
        self.fLensPrevValue = -1
        self.fLensValue = 0
        self.avgState = SINGLE_FRAME
        self.index = -1
        self.averageCur = 0
        self.iRangeMin = 0
        self.iRangeMax = 1023
        self.camactions = []
        self.lastwidth = 0
        self.useglobmarks = False
        self.useglobmarks2 = False
        self.globmarkpvs = []
        self.globmarkpvs2 = []
        self.lastimagetime = [0, 0]
        self.dispspec = 0
        self.otherpvs = []

        self.markhash = []
        for i in range(131072):
            self.markhash.append(8 * [0])

        self.itime = 10 * [0.0]
        self.idispUpdates = 10 * [0]
        self.idataUpdates = 10 * [0]

        self.rfshTimer = QTimer()
        self.acquire_image_timer = QTimer()
        self.rate_limit_timer = QTimer()
        self.refresh_timeout_display_timer = QTimer()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.projH.set_x()
        self.ui.projV.set_y()
        self.RPSpacer = QSpacerItem(20, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.ui.RightPanel.addItem(self.RPSpacer)

        self.ui.xmark = [
            self.ui.Disp_Xmark1,
            self.ui.Disp_Xmark2,
            self.ui.Disp_Xmark3,
            self.ui.Disp_Xmark4,
        ]
        self.ui.ymark = [
            self.ui.Disp_Ymark1,
            self.ui.Disp_Ymark2,
            self.ui.Disp_Ymark3,
            self.ui.Disp_Ymark4,
        ]
        self.ui.pBM = [
            self.ui.pushButtonMarker1,
            self.ui.pushButtonMarker2,
            self.ui.pushButtonMarker3,
            self.ui.pushButtonMarker4,
            self.ui.pushButtonRoiSet,
        ]
        self.ui.actM = [
            self.ui.actionM1,
            self.ui.actionM2,
            self.ui.actionM3,
            self.ui.actionM4,
            self.ui.actionROI,
        ]
        self.advdialog = advdialog(self)
        self.advdialog.hide()

        self.markerdialog = markerdialog(self)
        self.markerdialog.xmark = [
            self.markerdialog.ui.Disp_Xmark1,
            self.markerdialog.ui.Disp_Xmark2,
            self.markerdialog.ui.Disp_Xmark3,
            self.markerdialog.ui.Disp_Xmark4,
        ]
        self.markerdialog.ymark = [
            self.markerdialog.ui.Disp_Ymark1,
            self.markerdialog.ui.Disp_Ymark2,
            self.markerdialog.ui.Disp_Ymark3,
            self.markerdialog.ui.Disp_Ymark4,
        ]
        self.markerdialog.pBM = [
            self.markerdialog.ui.pushButtonMarker1,
            self.markerdialog.ui.pushButtonMarker2,
            self.markerdialog.ui.pushButtonMarker3,
            self.markerdialog.ui.pushButtonMarker4,
            None,
        ]
        self.markerdialog.hide()

        self.specificdialog = specificdialog(self)
        self.specificdialog.hide()

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
        self.ui.groupBoxFits.setVisible(False)

        # Resize the main window!
        self.ui.display_image.setImageSize(False)

        self.iScaleIndex = 0
        self.ui.comboBoxScale.currentIndexChanged.connect(
            self.onComboBoxScaleIndexChanged
        )

        self.cameraListFilename = cameraListFilename

        if param.orientation & 2:
            self.px = np.zeros((param.y), dtype=np.float64)
            self.py = np.zeros((param.x), dtype=np.float64)
            self.image = np.zeros((param.x, param.y), dtype=np.uint32)
        else:
            self.px = np.zeros((param.x), dtype=np.float64)
            self.py = np.zeros((param.y), dtype=np.float64)
            self.image = np.zeros((param.y, param.x), dtype=np.uint32)
        self.imageBuffer = pycaqtimage.pyCreateImageBuffer(
            self.ui.display_image.image,
            self.px,
            self.py,
            self.image,
            param.x,
            param.y,
            param.orientation,
        )

        self.updateRoiText()
        self.updateMarkerText(True, True, 0, 15)

        self.max_px = 0
        self.min_px = 0

        sizeProjX = QSize(self.viewwidth, self.projsize)
        self.ui.projH.doResize(sizeProjX)

        sizeProjY = QSize(self.projsize, self.viewheight)
        self.ui.projV.doResize(sizeProjY)

        self.ui.display_image.doResize(QSize(self.viewwidth, self.viewheight))

        self.camconn_pvs: list[Pv] = []
        self.update_cam_rate_label(0)
        self.updateCameraCombo()

        self.ui.checkBoxProjAutoRange.stateChanged.connect(self.onCheckProjUpdate)

        self.ui.horizontalSliderRangeMin.sliderReleased.connect(
            self.on_slider_range_min_released
        )
        self.ui.horizontalSliderRangeMax.sliderReleased.connect(
            self.on_slider_range_max_released
        )
        self.ui.lineEditRangeMin.returnPressed.connect(
            self.on_range_min_text_enter_pressed
        )
        self.ui.lineEditRangeMax.returnPressed.connect(
            self.on_range_max_text_enter_pressed
        )
        self.ui.pushbutton_auto_range.pressed.connect(self.set_auto_range)
        self.ui.checkbox_auto_range.stateChanged.connect(self.set_auto_range)

        self.ui.horizontalSliderLens.sliderReleased.connect(self.onSliderLensReleased)
        self.ui.horizontalSliderLens.valueChanged.connect(self.onSliderLensChanged)
        self.ui.lineEditLens.returnPressed.connect(self.onLensEnter)

        self.ui.singleframe.toggled.connect(self.onCheckDisplayUpdate)
        self.ui.grayScale.stateChanged.connect(self.onCheckGrayUpdate)
        self.ui.local_avg.toggled.connect(self.onCheckDisplayUpdate)

        self.ui.comboBoxColor.currentIndexChanged.connect(
            self.onComboBoxColorIndexChanged
        )
        self.hot()  # default option

        for i in range(4):
            self.ui.xmark[i].returnPressed.connect(
                functools.partial(self.onMarkerTextEnter, i)
            )
            self.ui.ymark[i].returnPressed.connect(
                functools.partial(self.onMarkerTextEnter, i)
            )

            self.markerdialog.xmark[i].returnPressed.connect(
                functools.partial(self.onMarkerDialogEnter, i)
            )
            self.markerdialog.ymark[i].returnPressed.connect(
                functools.partial(self.onMarkerDialogEnter, i)
            )

        self.ui.Disp_RoiX.returnPressed.connect(self.onRoiTextEnter)
        self.ui.Disp_RoiY.returnPressed.connect(self.onRoiTextEnter)
        self.ui.Disp_RoiW.returnPressed.connect(self.onRoiTextEnter)
        self.ui.Disp_RoiH.returnPressed.connect(self.onRoiTextEnter)

        #
        # Special Mouse Mode:
        #   1-4: Marker 1-4, 5: ROI
        self.iSpecialMouseMode = 0

        for i in range(4):
            self.ui.pBM[i].clicked.connect(functools.partial(self.onMarkerSet, i))
            self.markerdialog.pBM[i].clicked.connect(
                functools.partial(self.onMarkerDialogSet, i)
            )
            self.ui.actM[i].triggered.connect(functools.partial(self.onMarkerTrig, i))

        self.ui.pushButtonRoiSet.clicked.connect(self.onRoiSet)
        self.ui.pushButtonRoiReset.clicked.connect(self.onRoiReset)

        self.ui.actionMS.triggered.connect(self.onMarkerSettingsTrig)
        self.ui.actionROI.triggered.connect(self.onRoiTrig)
        self.ui.actionResetROI.triggered.connect(self.onRoiReset)
        self.ui.actionResetMarkers.triggered.connect(self.onMarkerReset)

        self.ui.pushButtonZoomRoi.clicked.connect(self.onZoomRoi)
        self.ui.pushButtonZoomIn.clicked.connect(self.onZoomIn)
        self.ui.pushButtonZoomOut.clicked.connect(self.onZoomOut)
        self.ui.pushButtonZoomReset.clicked.connect(self.onZoomReset)

        self.ui.actionZoomROI.triggered.connect(self.onZoomRoi)
        self.ui.actionZoomIn.triggered.connect(self.onZoomIn)
        self.ui.actionZoomOut.triggered.connect(self.onZoomOut)
        self.ui.actionZoomReset.triggered.connect(self.onZoomReset)

        self.ui.actionReconnect.triggered.connect(self.on_reconnect)
        self.ui.actionForce.triggered.connect(self.on_force_disconnect)

        self.rfshTimer.timeout.connect(self.UpdateRate)
        self.rfshTimer.start(1000)

        self.acquire_image_timer.timeout.connect(self.wantImage)
        rate = max(int(rate), 1)
        self.user_set_max_image_rate(rate)

        self.ui.spinbox_set_max_rate.setValue(rate)
        self.ui.spinbox_set_max_rate.valueChanged.connect(self.user_set_max_image_rate)

        self.rate_limit_timer.timeout.connect(self.apply_rate_limit)

        self.refresh_timeout_display_timer.timeout.connect(self.update_timeout_display)
        self.refresh_timeout_display_timer.setInterval(1000 * 20)
        self.refresh_timeout_display_timer.start()

        self.ui.average.returnPressed.connect(self.onAverageSet)
        self.ui.comboBoxOrientation.currentIndexChanged.connect(
            self.onOrientationSelect
        )
        self.ui.orient0.triggered.connect(lambda: self.setOrientation(param.ORIENT0))
        self.ui.orient90.triggered.connect(lambda: self.setOrientation(param.ORIENT90))
        self.ui.orient180.triggered.connect(
            lambda: self.setOrientation(param.ORIENT180)
        )
        self.ui.orient270.triggered.connect(
            lambda: self.setOrientation(param.ORIENT270)
        )
        self.ui.orient0F.triggered.connect(lambda: self.setOrientation(param.ORIENT0F))
        self.ui.orient90F.triggered.connect(
            lambda: self.setOrientation(param.ORIENT90F)
        )
        self.ui.orient180F.triggered.connect(
            lambda: self.setOrientation(param.ORIENT180F)
        )
        self.ui.orient270F.triggered.connect(
            lambda: self.setOrientation(param.ORIENT270F)
        )
        self.setOrientation(param.ORIENT0)  # default to use unrotated

        self.ui.FileSave.triggered.connect(self.onfileSave)
        self.retry_save_image.connect(self.onfileSave)

        self.imageUpdate.connect(self.onImageUpdate)
        self.miscUpdate.connect(self.onMiscUpdate)
        self.sizeUpdate.connect(self.onSizeUpdate)
        self.cross1Update.connect(lambda: self.onCrossUpdate(0))
        self.cross2Update.connect(lambda: self.onCrossUpdate(1))
        self.cross3Update.connect(lambda: self.onCrossUpdate(2))
        self.cross4Update.connect(lambda: self.onCrossUpdate(3))

        self.ui.showconf.triggered.connect(self.doShowConf)
        self.ui.showproj.triggered.connect(self.doShowProj)
        self.ui.showmarker.triggered.connect(self.doShowMarker)
        self.ui.showexpert.triggered.connect(self.onExpertMode)
        self.ui.showspecific.triggered.connect(self.doShowSpecific)
        self.ui.actionGlobalMarkers.triggered.connect(self.onGlobMarks)
        self.advdialog.ui.showexpert.clicked.connect(self.on_open_expert)
        self.onExpertMode()

        self.ui.checkBoxProjRoi.stateChanged.connect(self.onGenericConfigChange)
        self.ui.checkBoxM1Lineout.stateChanged.connect(self.onGenericConfigChange)
        self.ui.checkBoxM2Lineout.stateChanged.connect(self.onGenericConfigChange)
        self.ui.checkBoxM3Lineout.stateChanged.connect(self.onGenericConfigChange)
        self.ui.checkBoxM4Lineout.stateChanged.connect(self.onGenericConfigChange)
        self.ui.radioGaussian.toggled.connect(self.onGenericConfigChange)
        self.ui.radioSG4.toggled.connect(self.onGenericConfigChange)
        self.ui.radioSG6.toggled.connect(self.onGenericConfigChange)
        self.ui.checkBoxFits.stateChanged.connect(self.onCheckFitsUpdate)
        self.ui.lineEditCalib.returnPressed.connect(self.onCalibTextEnter)
        self.calib = 1.0
        self.calibPVName = ""
        self.calibPV = None
        self.displayFormat = "%12.8g"

        self.advdialog.ui.buttonBox.clicked.connect(self.onAdvanced)
        self.specificdialog.ui.buttonBox.clicked.connect(self.onSpecific)

        self.specificdialog.ui.cameramodeG.currentIndexChanged.connect(
            lambda n: self.comboWriteCallback(self.specificdialog.ui.cameramodeG, n)
        )
        self.specificdialog.ui.gainG.returnPressed.connect(
            lambda: self.lineFloatWriteCallback(self.specificdialog.ui.gainG)
        )
        self.specificdialog.ui.timeG.returnPressed.connect(
            lambda: self.lineFloatWriteCallback(self.specificdialog.ui.timeG)
        )
        self.specificdialog.ui.periodG.returnPressed.connect(
            lambda: self.lineFloatWriteCallback(self.specificdialog.ui.periodG)
        )
        self.specificdialog.ui.runButtonG.clicked.connect(
            lambda: self.buttonWriteCallback(self.specificdialog.ui.runButtonG)
        )

        # set camera pv and start display
        self.ui.menuCameras.triggered.connect(self.onCameraMenuSelect)
        self.ui.comboBoxCamera.activated.connect(self.onCameraSelect)

        # Sigh, we might change this if taking a one-liner!
        camera = options.camera
        if camera is not None:
            try:
                cameraIndex = int(camera)
            except Exception:
                # OK, I suppose it's a name!  Default to 0, then look for it!
                cameraIndex = 0
                for i in range(len(self.lCameraDesc)):
                    if self.lCameraDesc[i].find(camera) >= 0:
                        cameraIndex = i
                        break

        if cameraPv is not None:
            try:
                idx = self.lCameraList.index(cameraPv)
                print("Camera PV %s --> index %d" % (cameraPv, idx))
                cameraIndex = idx
            except Exception:
                # Can't find an exact match.  Is this a prefix?
                p = re.compile(cameraPv + ".*$")
                idx = -1
                for i in range(len(self.lCameraList)):
                    m = p.search(self.lCameraList[i])
                    if m is not None:
                        idx = i
                        break
                if idx >= 0:
                    print("Camera PV %s --> index %d" % (cameraPv, idx))
                    cameraIndex = idx
                else:
                    # OK, not a prefix.  Try stripping off the end and look for
                    # the same base.
                    m = re.search("(.*):([^:]*)$", cameraPv)
                    if m is None:
                        print("Cannot find camera PV %s!" % cameraPv)
                    else:
                        try:
                            pvname = m.group(1)
                            pvnamelen = len(pvname)
                            idx = -1
                            for i in range(len(self.lCameraList)):
                                if self.lCameraList[i][:pvnamelen] == pvname:
                                    idx = i
                                    break
                            if idx <= -1:
                                raise Exception("No match")
                            print("Camera PV %s --> index %d" % (cameraPv, idx))
                            cameraIndex = idx
                        except Exception:
                            print("Cannot find camera PV %s!" % cameraPv)
        try:
            self.ui.comboBoxCamera.setCurrentIndex(-1)
            if cameraIndex < 0 or cameraIndex >= len(self.lCameraList):
                print("Invalid camera index %d" % cameraIndex)
                cameraIndex = 0
            self.onCameraSelect(int(cameraIndex))
        except Exception:
            pass
        self.efilter = FilterObject(self.app, self)

    def closeEvent(self, event):
        self.end_monitors()
        if self.cameraBase != "":
            self.activeClear()
        if self.haveforce and self.forcedialog is not None:
            self.forcedialog.close()
        self.advdialog.close()
        self.markerdialog.close()
        self.specificdialog.close()
        if self.cfg is None:
            self.dumpConfig()
        QMainWindow.closeEvent(self, event)

    def end_monitors(self):
        all_mons = []
        all_mons.extend(self.camconn_pvs)
        all_mons.extend(self.globmarkpvs)
        all_mons.extend(self.globmarkpvs2)
        all_mons.extend(self.otherpvs)
        all_mons.append(self.notify)
        all_mons.append(self.rowPv)
        all_mons.append(self.colPv)
        all_mons.append(self.launch_gui_pv)
        all_mons.append(self.launch_edm_pv)
        all_mons.append(self.lensPv)
        all_mons.append(self.calibPV)
        for pv in all_mons:
            if pv is not None:
                pv.monitor_stop()
        pyca.flush_io()

    def setImageSize(self, newx, newy, reset=True):
        if newx == 0 or newy == 0:
            return
        param.setImageSize(newx, newy)
        self.ui.display_image.setImageSize(reset)
        if param.orientation & 2:
            self.px = np.zeros((param.y), dtype=np.float64)
            self.py = np.zeros((param.x), dtype=np.float64)
            self.image = np.zeros((param.x, param.y), dtype=np.uint32)
        else:
            self.px = np.zeros((param.x), dtype=np.float64)
            self.py = np.zeros((param.y), dtype=np.float64)
            self.image = np.zeros((param.y, param.x), dtype=np.uint32)
        self.imageBuffer = pycaqtimage.pyCreateImageBuffer(
            self.ui.display_image.image,
            self.px,
            self.py,
            self.image,
            param.x,
            param.y,
            param.orientation,
        )
        if self.camera is not None:
            if self.isColor:
                self.camera.processor = pycaqtimage.pyCreateColorImagePvCallbackFunc(
                    self.imageBuffer
                )
            #        self.ui.grayScale.setVisible(True)
            else:
                self.camera.processor = pycaqtimage.pyCreateImagePvCallbackFunc(
                    self.imageBuffer
                )
            #        self.ui.grayScale.setVisible(False)
            pycaqtimage.pySetImageBufferGray(
                self.imageBuffer, self.ui.grayScale.isChecked()
            )

    def doShowProj(self):
        v = self.ui.showproj.isChecked()
        self.ui.projH.setVisible(v)
        self.ui.projV.setVisible(v)
        self.ui.projectionFrame.setVisible(v)
        self.ui.groupBoxFits.setVisible(v and self.ui.checkBoxFits.isChecked())
        if self.cfg is None:
            # print("done doShowProj")
            self.dumpConfig()

    def doShowMarker(self):
        v = self.ui.showmarker.isChecked()
        self.ui.groupBoxMarker.setVisible(v)
        self.ui.RightPanel.invalidate()
        if self.cfg is None:
            # print("done doShowMarker")
            self.dumpConfig()

    def doShowConf(self):
        v = self.ui.showconf.isChecked()
        self.ui.groupBoxAverage.setVisible(v)
        self.ui.groupBoxCamera.setVisible(v)
        self.ui.groupBoxColor.setVisible(v)
        self.ui.groupBoxZoom.setVisible(v)
        self.ui.groupBoxROI.setVisible(v)
        self.ui.RightPanel.invalidate()
        if self.cfg is None:
            # print("done doShowConf")
            self.dumpConfig()

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
        x -= w / 2
        y -= h / 2
        self.ui.display_image.roiSet(x, y, w, h)

    def onFetchROI2(self):
        x = caget(self.cameraBase + ":ROI_X2")
        y = caget(self.cameraBase + ":ROI_Y2")
        w = caget(self.cameraBase + ":ROI_WIDTH2")
        h = caget(self.cameraBase + ":ROI_HEIGHT2")
        x -= w / 2
        y -= h / 2
        self.ui.display_image.roiSet(x, y, w, h)

    def getROI(self):
        roi = self.ui.display_image.rectRoi.abs()
        x = roi.left()
        y = roi.top()
        w = roi.width()
        h = roi.height()
        return (int(x + w / 2 + 0.5), int(y + h / 2 + 0.5), int(w), int(h))

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
        if ugm != self.useglobmarks:  # If something has changed...
            if ugm:
                self.useglobmarks = self.connectMarkerPVs()
                if self.useglobmarks:
                    self.onCrossUpdate(0)
                    self.onCrossUpdate(1)
            else:
                self.useglobmarks = self.disconnectMarkerPVs()
            if self.cfg is None:
                self.dumpConfig()

    def setUseGlobalMarkers2(self, ugm):
        if ugm != self.useglobmarks2:  # If something has changed...
            if ugm:
                self.useglobmarks2 = self.connectMarkerPVs2()
                if self.useglobmarks2:
                    self.onCrossUpdate(2)
                    self.onCrossUpdate(3)
            else:
                self.useglobmarks2 = self.disconnectMarkerPVs2()
            if self.cfg is None:
                self.dumpConfig()

    def onMarkerTextEnter(self, n):
        self.ui.display_image.lMarker[n].setRel(
            float(self.ui.xmark[n].text()), float(self.ui.ymark[n].text())
        )
        if n <= 1:
            self.updateMarkerText(False, True, 1 << n, 1 << n)
        else:
            self.updateMarkerText(False, True, 0, 1 << n)
        self.updateMarkerValue()
        self.updateall()
        if self.cfg is None:
            self.dumpConfig()

    def onMarkerDialogEnter(self, n):
        self.ui.display_image.lMarker[n].setRel(
            float(self.markerdialog.xmark[n].text()),
            float(self.markerdialog.ymark[n].text()),
        )
        if n <= 1:
            self.updateMarkerText(False, True, 1 << n, 1 << n)
        else:
            self.updateMarkerText(False, True, 0, 1 << n)
        self.updateMarkerValue()
        self.updateall()
        if self.cfg is None:
            self.dumpConfig()

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
                    self.globmarkpvs[2 * i + 0].put(newx)
                    self.globmarkpvs[2 * i + 1].put(newy)
        self.updateMarkerValue()

    def updateMarkerValue(self):
        lValue = pycaqtimage.pyGetPixelValue(
            self.imageBuffer,
            self.ui.display_image.cursorPos.oriented(),
            self.ui.display_image.lMarker[0].oriented(),
            self.ui.display_image.lMarker[1].oriented(),
            self.ui.display_image.lMarker[2].oriented(),
            self.ui.display_image.lMarker[3].oriented(),
        )
        self.averageCur = lValue[5]
        sMarkerInfoText = ""
        if lValue[0] >= 0:
            pt = self.ui.display_image.cursorPos.oriented()
            sMarkerInfoText += "(%d,%d): %-4d " % (pt.x(), pt.y(), lValue[0])
        for iMarker in range(4):
            if lValue[iMarker + 1] >= 0:
                pt = self.ui.display_image.lMarker[iMarker].oriented()
                sMarkerInfoText += "%d:(%d,%d): %-4d " % (
                    1 + iMarker,
                    pt.x(),
                    pt.y(),
                    lValue[iMarker + 1],
                )
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
        if self.cfg is None:
            self.dumpConfig()

    def onCheckGrayUpdate(self, newval):
        pycaqtimage.pySetImageBufferGray(self.imageBuffer, newval)
        if self.cfg is None:
            self.dumpConfig()

    def onCheckDisplayUpdate(self, newval):
        if not newval:
            return  # Only do this for the checked one!
        if self.ui.singleframe.isChecked():
            self.avgState = SINGLE_FRAME
            if self.isColor:
                pycaqtimage.pySetImageBufferGray(
                    self.imageBuffer, self.ui.grayScale.isChecked()
                )
        elif self.ui.local_avg.isChecked():
            self.avgState = LOCAL_AVERAGE
        self.onAverageSet()

    def onCheckFitsUpdate(self):
        self.ui.groupBoxFits.setVisible(self.ui.checkBoxFits.isChecked())
        if self.cfg is None:
            self.dumpConfig()

    def onGenericConfigChange(self):
        if self.cfg is None:
            self.dumpConfig()

    def clearSpecialMouseMode(self, keepMode, bNewCheckedState):
        for i in range(1, 6):
            if keepMode != i:
                self.ui.pBM[i - 1].setChecked(False)
                if self.markerdialog.pBM[i - 1] is not None:
                    self.markerdialog.pBM[i - 1].setChecked(False)
                self.ui.actM[i - 1].setChecked(False)
        if bNewCheckedState:
            self.iSpecialMouseMode = keepMode
        else:
            self.iSpecialMouseMode = 0
        if self.iSpecialMouseMode == 0:
            self.ui.display_image.setCursor(Qt.ArrowCursor)
        else:
            self.ui.display_image.setCursor(Qt.CrossCursor)

    def onMarkerSet(self, n, bChecked):
        self.clearSpecialMouseMode(n + 1, bChecked)
        self.ui.actM[n].setChecked(bChecked)
        self.markerdialog.pBM[n].setChecked(bChecked)
        self.ui.display_image.update()

    def onMarkerDialogSet(self, n, bChecked):
        self.clearSpecialMouseMode(n + 1, bChecked)
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
        self.clearSpecialMouseMode(n + 1, bChecked)
        self.ui.pBM[n].setChecked(bChecked)
        self.markerdialog.pBM[n].setChecked(bChecked)
        self.ui.display_image.update()

    def onMarkerReset(self):
        self.ui.display_image.lMarker = [
            param.Point(-100, -100),
            param.Point(param.x + 100, -100),
            param.Point(param.x + 100, param.y + 100),
            param.Point(-100, param.y + 100),
        ]
        self.updateMarkerText(True, True, 3, 15)
        self.updateall()
        if self.cfg is None:
            self.dumpConfig()

    def onRoiTrig(self):
        bChecked = self.ui.actionROI.isChecked()
        self.clearSpecialMouseMode(5, bChecked)
        self.ui.pushButtonRoiSet.setChecked(bChecked)
        self.ui.display_image.update()

    def onRoiReset(self):
        self.clearSpecialMouseMode(0, False)
        self.ui.display_image.roiReset()

    def onRoiTextEnter(self):
        self.ui.display_image.rectRoi = param.Rect(
            float(self.ui.Disp_RoiX.text()),
            float(self.ui.Disp_RoiY.text()),
            float(self.ui.Disp_RoiW.text()),
            float(self.ui.Disp_RoiH.text()),
            rel=True,
        )
        self.updateRoiText()
        self.updateall()
        if self.cfg is None:
            self.dumpConfig()

    def updateRoiText(self):
        rct = self.ui.display_image.rectRoi.oriented()
        self.ui.Disp_RoiX.setText("%.0f" % rct.x())
        self.ui.Disp_RoiY.setText("%.0f" % rct.y())
        self.ui.Disp_RoiW.setText("%.0f" % rct.width())
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
            pycaqtimage.pydspl_setup_color_map(
                fnColorMap, self.iRangeMin, self.iRangeMax, self.iScaleIndex
            )
        else:
            pycaqtimage.pydspl_setup_gray(
                self.iRangeMin, self.iRangeMax, self.iScaleIndex
            )
        # If the image isn't frozen, this isn't really necessary.  But it bothers me when it *is*
        # frozen!
        pycaqtimage.pyRecolorImageBuffer(self.imageBuffer)
        self.ui.display_image.update()
        if self.cfg is None:
            self.dumpConfig()

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
            except Exception:
                pass
            self.camera = None
        if self.notify is not None:
            try:
                self.notify.disconnect()
            except Exception:
                pass
            self.notify = None
        if self.lensPv is not None:
            try:
                self.lensPv.disconnect()
            except Exception:
                pass
            self.lensPv = None
        if self.putlensPv is not None:
            try:
                self.putlensPv.disconnect()
            except Exception:
                pass
            self.putlensPv = None
        for pv in self.otherpvs:
            try:
                pv.disconnect()
            except Exception:
                pass
        self.otherpvs = []

    def shutdown(self):
        self.clear()
        self.rfshTimer.stop()
        self.acquire_image_timer.stop()
        # print("shutdown")

    def onfileSave(self):
        try:
            filename = QFileDialog.getSaveFileName(
                parent=self,
                caption="Save Image...",
                directory=os.path.expanduser("~"),
                filter="Images (*.npy *.jpg *.png *.bmp *.pgm *.tif)",
            )[0]
            if filename == "":
                # The only way to get here is by clicking "X" or "Cancel"
                return
            file_ext = os.path.splitext(filename)[1]
            if file_ext == ".npy":
                # This either works or raises an OSError such as PermissionError
                np.save(filename, self.image)
                return self.show_file_success(filename=filename, file_ext=file_ext)
            save_ok = self.ui.display_image.image.save(
                filename, format=None, quality=-1
            )
            if save_ok:
                # QImage.save returned True, so the save succeeded.
                return self.show_file_success(filename=filename, file_ext=file_ext)
            # QImage.save returned False, so the save failed.
            # Check for obvious errors, then retry the save
            # No write permissions?
            # If the file exists, we need to check the filename. Otherwise, we check the dirname.
            if os.path.exists(filename):
                can_write = os.access(path=filename, mode=os.W_OK)
            else:
                directory = os.path.dirname(filename)
                can_write = os.access(path=directory, mode=os.W_OK)
            if not can_write:
                return self.warn_and_retry_save(
                    message=f"No permissions to write {filename}! Please pick a different location."
                )
            # Invalid image type?
            image_types = [".npy"] + [
                "." + qba.data().decode("utf-8")
                for qba in QImageWriter.supportedImageFormats()
            ]
            if file_ext not in image_types:
                return self.warn_and_retry_save(
                    message=f"Invalid image type {file_ext}! Please pick from the list {image_types}."
                )
            # I guess we have no idea what went wrong
            return self.warn_and_retry_save(
                message="Unknown failure! Please try again."
            )
        except OSError as exc:
            self.warn_and_retry_save(message=str(exc))
        except Exception as exc:
            print("fileSave failed:", exc)
            QMessageBox.warning(
                self, "File Save Failed", f"Internal error, cancelling save: {exc}"
            )

    def show_file_success(self, filename: str, file_ext: str):
        QMessageBox.information(
            self,
            "File Save Succeeded",
            f"Image has been saved as a {file_ext} file: {filename}",
        )
        print(f"Saved to a {file_ext} file: {filename}")

    def warn_and_retry_save(self, message: str):
        QMessageBox.warning(
            self,
            "File Save Failed",
            message,
        )
        self.retry_save_image.emit()

    def onOrientationSelect(self, index):
        self.setOrientation(param.idx2orient[index], fromCombo=True)

    def setOrientation(self, orientation, reorient=True, fromCombo=False):
        if not fromCombo:
            self.ui.comboBoxOrientation.setCurrentIndex(param.orient2idx[orientation])
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
            if reorient:
                self.changeSize(self.viewheight, self.viewwidth, self.projsize, True)
        self.updateMarkerText(True, True, 0, 15)
        self.updateRoiText()
        self.updateall()
        if self.cfg is None:
            self.dumpConfig()

    def onAverageSet(self):
        if self.avgState == LOCAL_AVERAGE:
            try:
                self.average = int(self.ui.average.text())
                if self.average == 0:
                    self.average = 1
                    self.ui.average.setText("1")
                self.updateMiscInfo()
            except Exception:
                self.average = 1
                self.ui.average.setText("1")
            pycaqtimage.pySetFrameAverage(self.average, self.imageBuffer)
        else:
            pycaqtimage.pySetFrameAverage(1, self.imageBuffer)

    def onCalibTextEnter(self):
        try:
            self.calib = float(self.ui.lineEditCalib.text())
            if self.calibPV is not None:
                self.calibPV.put(self.calib)
            if self.cfg is None:
                self.dumpConfig()
        except Exception:
            self.ui.lineEditCalib.setText(str(self.calib))

    # Note: this function is called by the CA library, from another thread
    def sizeCallback(self, exception=None):
        if exception is None:
            self.sizeUpdate.emit()
        else:
            print("sizeCallback(): %-30s " % (self.name), exception)

    def onSizeUpdate(self):
        try:
            newx = self.colPv.value / self.scale
            newy = self.rowPv.value / self.scale
            if newx != param.x or newy != self.y:
                self.setImageSize(newx, newy, False)
        except Exception:
            pass

    def user_set_max_image_rate(self, rate: int) -> None:
        """
        Call set_max_image_rate and record the value as the desired rate.

        After init, this should only be called by user input.

        This desired rate is used so that after a timeout, we can
        restore the GUI to the user's last desired rate when they
        interact with the GUI again.
        """
        self.last_des_max_rate = rate
        self.set_max_image_rate(rate)

    def set_max_image_rate(self, rate: int) -> None:
        """
        Update the maximum allowed rate by restarting the appropriate timer.

        Rate is expected to be a positive integer in Hz.

        When the aquire_image_timer expires, wantImage is called.
        If a new image is available at this time, it will be fetched and rendered.
        See the old comments from around that function.

        The image rate will determine the rate limiting timeout.
        1 Hz will never time out
        5 Hz or less will time out in a week
        30 Hz and greater will time out in a day
        """
        rate = int(rate)
        if rate <= 0:
            raise ValueError("Rate must be greater than zero!")
        self.acquire_image_timer.start(int(1000.0 / rate))
        self.ui.label_max_rate_value.setText(f"{rate} Hz")

        if rate <= 1:
            self.disable_rate_timer()
        else:
            self.set_rate_limit_duration(
                np.interp(rate, [5, 30], [self.max_timeout, self.min_timeout])
            )

    # This monitors LIVE_IMAGE_FULL... which updates at 5 Hz, whether we have an image or not!
    # Therefore, we need to check the time and just skip it if it's a repeat!
    def haveImageCallback(self, exception=None):
        if exception is None:
            if (
                self.notify.secs != self.lastimagetime[0]
                or self.notify.nsec != self.lastimagetime[1]
            ):
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
        if (
            self.wantNewImage
            and self.haveNewImage
            and self.lastGetDone
            and self.camera is not None
        ):
            try:
                if self.nordPv:
                    self.count = int(self.nordPv.value)
                    if self.count == 0:
                        sz = int(self.rowPv.value) * int(self.colPv.value)
                        if sz > 0 and sz < self.maxcount:
                            self.count = sz
                        else:
                            self.count = self.maxcount
                self.camera.get(timeout=None)
                pyca.flush_io()
            except Exception:
                pass
            self.haveNewImage = False
            self.lastGetDone = False

    # Note: this function is called by the CA library, from another thread, when we have a new image.
    def imagePvUpdateCallback(self, exception=None):
        self.lastGetDone = True
        if exception is None:
            self.imageUpdate.emit()  # Send out the signal to notify windows update (in the GUI thread)
            self.wantImage(False)
        else:
            print("imagePvUpdateCallback(): %-30s " % (self.name), exception)

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
        except Exception as e:
            print(e)

    # Note: this function is called by the CA library, from another thread
    def lensPvUpdateCallback(self, exception=None):
        if exception is None:
            self.fLensValue = float(self.lensPv.value)
            self.miscUpdate.emit()  # Send out the signal to notify windows update (in the GUI thread)
        else:
            print("lensPvUpdateCallback(): %-30s " % (self.name), exception)

    def onMiscUpdate(self):
        self.updateMiscInfo()

    def updateProj(self):
        try:
            (
                roiMean,
                roiVar,
                projXmin,
                projXmax,
                projYmin,
                projYmax,
                self.max_px,
                self.min_px,
            ) = pycaqtimage.pyUpdateProj(
                self.imageBuffer,
                self.ui.checkBoxProjAutoRange.isChecked(),
                self.iRangeMin,
                self.iRangeMax,
                self.ui.display_image.rectRoi.oriented(),
            )
            (projXmin, projXmax) = self.ui.projH.makeImage(
                projXmin, projXmax, projYmin, projYmax
            )
            (projYmin, projYmax) = self.ui.projV.makeImage(
                projXmin, projXmax, projYmin, projYmax
            )
            if self.ui.checkbox_auto_range.isChecked():
                self.set_new_max_pixel(self.max_px)
                self.set_new_min_pixel(self.min_px)
            if roiMean == 0:
                roiVarByMean = 0
            else:
                roiVarByMean = roiVar / roiMean
            roi = self.ui.display_image.rectRoi.oriented()
            self.ui.labelRoiInfo.setText(
                "ROI Mean %-7.2f Std %-7.2f Var/Mean %-7.2f Min %d Max %d (%d,%d) W %d H %d"
                % (
                    roiMean,
                    math.sqrt(roiVar),
                    roiVarByMean,
                    self.min_px,
                    self.max_px,
                    roi.x(),
                    roi.y(),
                    roi.width(),
                    roi.height(),
                )
            )
            self.ui.labelProjHmax.setText("%d -" % projXmax)
            self.ui.labelProjMin.setText("%d\n%d\\" % (projXmin, projYmin))
            self.ui.labelProjVmax.setText("| %d" % projYmax)
        except Exception as e:
            print("updateProj:: exception: ", e)

    def updateMiscInfo(self):
        if self.avgState == LOCAL_AVERAGE:
            self.ui.labelMiscInfo.setText(
                "AvgShot# %d/%d Color scale [%d,%d] Zoom %.3f"
                % (
                    self.averageCur,
                    self.average,
                    self.iRangeMin,
                    self.iRangeMax,
                    param.zoom,
                )
            )
        else:
            self.ui.labelMiscInfo.setText(
                "AvgShot# %d/%d Color scale [%d,%d] Zoom %.3f"
                % (self.averageCur, 1, self.iRangeMin, self.iRangeMax, param.zoom)
            )
        if self.fLensValue != self.fLensPrevValue:
            self.fLensPrevValue = self.fLensValue
            self.ui.horizontalSliderLens.setValue(self.fLensValue)
            self.ui.lineEditLens.setText("%.2f" % self.fLensValue)

    # This is called at 1Hz when rfshTimer expires.
    def UpdateRate(self):
        now = time.time()
        delta = now - self.lastUpdateTime
        self.itime.append(delta)
        self.itime.pop(0)

        dispUpdates = self.dispUpdates - self.lastDispUpdates
        self.idispUpdates.append(dispUpdates)
        self.idispUpdates.pop(0)
        dispRate = (float)(sum(self.idispUpdates)) / sum(self.itime)
        self.ui.label_dispRate.setText("%.1f Hz" % dispRate)

        self.lastUpdateTime = now
        self.lastDispUpdates = self.dispUpdates

        # Also, check if someone is requesting us to disconnect!
        self.activeCheck()

    def readCameraFile(self, fn):
        dir = os.path.dirname(fn)  # Strip off filename!
        raw = open(fn, "r").readlines()
        lines = []
        for line in raw:
            s = line.split()
            if len(s) >= 1 and s[0] == "include":
                if s[1][0] != "/":
                    lines.extend(self.readCameraFile(dir + "/" + s[1]))
                else:
                    lines.extend(self.readCameraFile(s[1]))
            else:
                lines.append(line)
        return lines

    def updateCameraCombo(self):
        for pv in self.camconn_pvs:
            pv.disconnect()
        self.lType = []
        self.lFlags = []
        self.lCameraList = []
        self.lCtrlList = []
        self.lCameraDesc = []
        self.lEvrList = []
        self.lLensList = []
        self.camactions = []
        self.camconn = []
        self.camrates = []
        self.camconn_pvs = []
        self.ui.menuCameras.clear()
        sEvr = ""
        try:
            if self.options.oneline is not None:
                lCameraListLine = [self.options.oneline]
                self.options.camera = "0"
            else:
                if self.cameraListFilename[0] == "/":
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
                    raise Exception("Short line in config: %s" % sCamera)

                sTypeFlag = lsCameraLine[0].strip().split(":")
                sType = sTypeFlag[0]
                if len(sTypeFlag) > 1:
                    sFlag = sTypeFlag[1]
                else:
                    sFlag = ""

                sCameraCtrlPvs = lsCameraLine[1].strip().split(";")
                sCameraPv = sCameraCtrlPvs[0]
                if len(sCameraCtrlPvs) > 1:
                    sCtrlPv = sCameraCtrlPvs[1]
                else:
                    sCtrlPv = sCameraCtrlPvs[0]
                sEvrNew = lsCameraLine[2].strip()
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

                if sType != "GE" and sType != "AD":
                    print(
                        "Unsupported camera type: %s for %s (%s)"
                        % (sType, sCameraPv, sCameraDesc)
                    )
                    iCamera -= 1
                    continue

                self.lType.append(sType)
                self.lFlags.append(sFlag)
                self.lCameraList.append(sCameraPv)
                self.lCtrlList.append(sCtrlPv)
                self.lCameraDesc.append(sCameraDesc)
                self.lEvrList.append(sEvr)
                self.lLensList.append(sLensPv)

                self.ui.comboBoxCamera.addItem(sCameraDesc)

                try:
                    action = QAction(self)
                    action.setObjectName(sCameraPv)
                    action.setText(sCameraDesc + " (Offline)")
                    action.setCheckable(True)
                    action.setChecked(False)
                    self.ui.menuCameras.addAction(action)
                    self.camactions.append(action)
                except Exception:
                    print("Failed to create camera action for %s" % sCameraDesc)

                if sLensPv == "":
                    sLensPv = "None"

                pv = Pv(sCtrlPv + ":ArrayRate_RBV")
                self.camconn_pvs.append(pv)
                self.camconn.append(False)
                self.camrates.append(0)
                index = len(self.camconn_pvs) - 1
                pv.add_connection_callback(
                    functools.partial(
                        self.cam_combo_connect,
                        index=index,
                    )
                )
                pv.add_monitor_callback(
                    functools.partial(
                        self.cam_combo_rate,
                        index=index,
                    )
                )
                pv.do_initialize = True
                pv.do_monitor = True
                pv.connect(None)
                print(
                    "Camera [%d] %s Pv %s Evr %s LensPv %s"
                    % (iCamera, sCameraDesc, sCameraPv, sEvr, sLensPv)
                )

        except Exception:
            # import traceback
            # traceback.print_exc(file=sys.stdout)
            print('!! Failed to read camera pv list from "%s"' % (fnCameraList))
            sys.exit(0)

    def cam_combo_connect(self, is_connected: bool, index: int):
        """
        Update camera name in actions when it goes online/offline

        Here, we stash the connected/disconnected boolean with
        all the others and call for an update of the action text.
        """
        self.camconn[index] = is_connected
        self.update_cam_action_text(index=index)

    def cam_combo_rate(self, exception=None, index: int = 0):
        """
        Update camera rate in actions when it goes to zero.

        Here, we stash the rate float with all the others
        and call for an update of the action text.

        We also update the "camera rate" indicator if the pv
        we're monitoring is associated with the active camera.
        """
        if exception is not None:
            return
        self.camrates[index] = self.camconn_pvs[index].value
        if index == self.index:
            self.update_cam_rate_label()
        self.update_cam_action_text(index=index)

    def update_cam_rate_label(self, value: float | None = None):
        """
        Set the current shown rate near the "camera rate" indicator.

        If no value is given, we'll use the current value of the
        rate PV associated with the active camera.
        """
        if value is None:
            value = self.camrates[self.index]
        self.ui.label_cam_rate.setText(f"{value:.1f} Hz")

    def update_cam_action_text(self, index: int):
        """
        Based on the cached values, update the camera text in the "cameras" menu.

        This should be called any time either the connection state or the
        rate value changes enough to possibly affect the desired display here.
        """
        if not self.camconn[index]:
            text = " (Offline)"
        elif not self.camrates[index]:
            text = " (Stopped)"
        else:
            text = ""
        self.camactions[index].setText(self.lCameraDesc[index] + text)

    def disconnectPv(self, pv):
        if pv is not None:
            try:
                pv.disconnect()
                pyca.flush_io()
            except Exception:
                pass
        return None

    def connectPv(self, name, timeout=5.0, count=None):
        try:
            pv = Pv(name, count=count, initialize=True)
            try:
                pv.wait_ready(timeout)
            except Exception as exc:
                print(exc)
                QMessageBox.critical(
                    None,
                    "Error",
                    "Failed to initialize PV %s" % (name),
                    QMessageBox.Ok,
                    QMessageBox.Ok,
                )
                return None
            return pv
        except Exception as exc:
            print(exc)
            QMessageBox.critical(
                None,
                "Error",
                "Failed to connect to PV %s" % (name),
                QMessageBox.Ok,
                QMessageBox.Ok,
            )
            return None

    def onCrossUpdate(self, n):
        if n >= 2:
            if (
                self.globmarkpvs2[2 * n - 4].nsec != self.camera.nsec
                or self.globmarkpvs2[2 * n - 3].nsec != self.camera.nsec
                or self.globmarkpvs2[2 * n - 4].secs != self.camera.secs
                or self.globmarkpvs2[2 * n - 3].secs != self.camera.secs
            ):
                return
            self.ui.display_image.lMarker[n].setAbs(
                self.globmarkpvs2[2 * n - 4].value, self.globmarkpvs2[2 * n - 3].value
            )
        else:
            self.ui.display_image.lMarker[n].setAbs(
                self.globmarkpvs[2 * n + 0].value, self.globmarkpvs[2 * n + 1].value
            )
        self.updateMarkerText(True, True, 0, 1 << n)
        self.updateMarkerValue()
        self.updateall()
        if self.cfg is None:
            self.dumpConfig()

    def updateCross3and4(self):
        try:
            fid = self.camera.nsec & 0x1FFFF
            secs = self.camera.secs
            if self.markhash[fid][0] == secs and self.markhash[fid][1] == secs:
                self.ui.display_image.lMarker[2].setAbs(
                    self.markhash[fid][4], self.markhash[fid][5]
                )
            if self.markhash[fid][2] == secs and self.markhash[fid][3] == secs:
                self.ui.display_image.lMarker[3].setAbs(
                    self.markhash[fid][6], self.markhash[fid][7]
                )
            self.updateMarkerText(True, True, 0, 12)
        except Exception as e:
            print("updateCross3and4 exception: %s" % e)

    def addmarkhash(self, pv, idx):
        fid = pv.nsec & 0x1FFFF
        secs = pv.secs
        if self.markhash[fid][idx] == secs:
            return False
        self.markhash[fid][idx] = secs
        self.markhash[fid][idx + 4] = pv.value
        return True

    def cross1mon(self, exception=None):
        if exception is None:
            self.cross1Update.emit()

    def cross2mon(self, exception=None):
        if exception is None:
            self.cross2Update.emit()

    def cross3Xmon(self, exception=None):
        if exception is None:
            if self.addmarkhash(self.globmarkpvs2[0], 0):
                self.cross3Update.emit()

    def cross3Ymon(self, exception=None):
        if exception is None:
            if self.addmarkhash(self.globmarkpvs2[1], 1):
                self.cross3Update.emit()

    def cross4Xmon(self, exception=None):
        if exception is None:
            if self.addmarkhash(self.globmarkpvs2[2], 2):
                self.cross4Update.emit()

    def cross4Ymon(self, exception=None):
        if exception is None:
            if self.addmarkhash(self.globmarkpvs2[3], 3):
                self.cross4Update.emit()

    def connectMarkerPVs(self):
        self.globmarkpvs = [
            self.connectPv(self.ctrlBase + ":Cross1X"),
            self.connectPv(self.ctrlBase + ":Cross1Y"),
            self.connectPv(self.ctrlBase + ":Cross2X"),
            self.connectPv(self.ctrlBase + ":Cross2Y"),
        ]
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
        self.globmarkpvs2 = [
            self.connectPv(self.ctrlBase + ":DX1_SLOW"),
            self.connectPv(self.ctrlBase + ":DY1_SLOW"),
            self.connectPv(self.ctrlBase + ":DX2_SLOW"),
            self.connectPv(self.ctrlBase + ":DY2_SLOW"),
        ]
        if None in self.globmarkpvs2:
            return self.disconnectMarkerPVs2()
        self.globmarkpvs2[0].add_monitor_callback(self.cross3Xmon)
        self.globmarkpvs2[1].add_monitor_callback(self.cross3Ymon)
        self.globmarkpvs2[2].add_monitor_callback(self.cross4Xmon)
        self.globmarkpvs2[3].add_monitor_callback(self.cross4Ymon)
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
            except Exception:
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
            except Exception:
                pass
        self.globmarkpvs2 = []
        return False

    def setupDrags(self):
        if self.camera is not None:
            self.ui.display_image.readpvname = self.camera.name
        else:
            self.ui.display_image.readpvname = None
        if self.lensPv is not None:
            self.ui.horizontalSliderLens.readpvname = self.lensPv.name
            self.ui.lineEditLens.readpvname = self.lensPv.name
        else:
            self.ui.horizontalSliderLens.readpvname = None
            self.ui.lineEditLens.readpvname = None

    def connectCamera(self, sCameraPv, index, sNotifyPv=None):
        self.camera = self.disconnectPv(self.camera)
        self.notify = self.disconnectPv(self.notify)
        self.nordPv = self.disconnectPv(self.nordPv)
        self.nelmPv = self.disconnectPv(self.nelmPv)
        self.rowPv = self.disconnectPv(self.rowPv)
        self.colPv = self.disconnectPv(self.colPv)
        self.calibPV = self.disconnectPv(self.calibPV)
        self.launch_gui_pv = self.disconnectPv(self.launch_gui_pv)
        self.launch_edm_pv = self.disconnectPv(self.launch_edm_pv)
        self.launch_gui_script = ""
        self.launch_edm_script = ""
        self.calibPVName = ""
        self.displayFormat = "%12.8g"

        self.cfgname = self.cameraBase + ",GE"
        if self.lFlags[index] != "":
            self.cfgname += "," + self.lFlags[index]

        # Try to connect to the camera
        try:
            self.nordPv = self.connectPv(sCameraPv + ".NORD")
            self.count = int(self.nordPv.value)
        except Exception:
            self.nordPv = None
            self.count = None
        try:
            self.nelmPv = self.connectPv(sCameraPv + ".NELM")
            self.maxcount = int(self.nelmPv.value)
        except Exception:
            self.nelmPv = None
            self.maxcount = None
        if self.count is None or self.count == 0:
            self.count = self.maxcount
        self.camera = self.connectPv(sCameraPv, count=self.count)
        if self.camera is None:
            self.ui.label_connected.setText("NO")
            return
        print("Connected!")

        # Try to get the camera size!
        self.scale = 1
        if caget(self.cameraBase + ":ArraySize0_RBV") == 3:
            # It's a color camera!
            self.rowPv = self.connectPv(self.cameraBase + ":ArraySize2_RBV")
            self.colPv = self.connectPv(self.cameraBase + ":ArraySize1_RBV")
            self.isColor = True
            self.bits = caget(self.cameraBase + ":BIT_DEPTH")
            if self.bits is None:
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
                if self.bits is None:
                    self.bits = caget(self.cameraBase + ":BIT_DEPTH")
                    if self.bits is None:
                        self.bits = 8

        self.maxcolor = (1 << self.bits) - 1
        self.ui.horizontalSliderRangeMin.setMaximum(self.maxcolor)
        self.ui.horizontalSliderRangeMin.setTickInterval((1 << self.bits) / 4)
        self.ui.horizontalSliderRangeMax.setMaximum(self.maxcolor)
        self.ui.horizontalSliderRangeMax.setTickInterval((1 << self.bits) / 4)

        # See if we've connected to a camera with valid height and width
        if (
            self.camera is None
            or self.rowPv is None
            or self.rowPv.value == 0
            or self.colPv is None
            or self.colPv.value == 0
        ):
            self.ui.label_connected.setText("NO")
            return

        if sNotifyPv is None:
            self.notify = self.connectPv(sCameraPv, count=1)
        else:
            self.notify = self.connectPv(sNotifyPv, count=1)
        self.haveNewImage = False
        self.lastGetDone = True
        self.ui.label_connected.setText("YES")
        if self.isColor:
            self.camera.processor = pycaqtimage.pyCreateColorImagePvCallbackFunc(
                self.imageBuffer
            )
            self.ui.grayScale.setVisible(True)
        else:
            self.camera.processor = pycaqtimage.pyCreateImagePvCallbackFunc(
                self.imageBuffer
            )
            self.ui.grayScale.setVisible(False)
        self.notify.add_monitor_callback(self.haveImageCallback)
        self.camera.getevt_cb = self.imagePvUpdateCallback
        self.rowPv.add_monitor_callback(self.sizeCallback)
        self.colPv.add_monitor_callback(self.sizeCallback)
        # Now, before we monitor, update the camera size!
        self.setImageSize(
            self.colPv.value / self.scale, self.rowPv.value / self.scale, True
        )
        self.updateMarkerText(True, True, 0, 15)
        self.notify.monitor(
            pyca.DBE_VALUE, False, 1
        )  # Just 1 pixel, so a new image is available.
        self.rowPv.monitor(pyca.DBE_VALUE)
        self.colPv.monitor(pyca.DBE_VALUE)
        pyca.flush_io()
        # Deliberately after flush_io so we don't wait for them
        self.launch_gui_pv = Pv(
            self.ctrlBase + ":LAUNCH_GUI",
            initialize=True,
            monitor=self.new_launch_gui_script,
            use_numpy=True,
        )
        self.launch_edm_pv = Pv(
            self.ctrlBase + ":LAUNCH_EDM",
            initialize=True,
            monitor=self.new_launch_edm_script,
            use_numpy=True,
        )
        self.sWindowTitle = "Camera: " + self.lCameraDesc[index]
        self.setWindowTitle("MainWindow")
        self.advdialog.setWindowTitle(self.sWindowTitle + " Advanced Mode")
        self.markerdialog.setWindowTitle(self.sWindowTitle + " Marker Settings")
        self.specificdialog.setWindowTitle(self.sWindowTitle + " Camera Settings")

        # Get camera configuration
        self.getConfig()

    def normalize_selectors(self):
        """
        Update the visual appearance of the camera combobox and the menu to be correct.

        The combobox should display the currently connected camera and only the
        action associated with the currently connected camera should be checked.
        """
        self.ui.comboBoxCamera.setCurrentIndex(self.index)
        for num, action in enumerate(self.camactions):
            action.setChecked(num == self.index)

    def onCameraMenuSelect(self, action):
        index = self.camactions.index(action)
        if index >= 0 and index < len(self.camactions):
            self.onCameraSelect(index)

    def onCameraSelect(self, index):
        if index < 0:
            return
        if index >= len(self.lCameraList):
            print(
                "index %d out of range (max: %d)" % (index, len(self.lCameraList) - 1)
            )
            return
        if not self.camconn[index]:
            QMessageBox.critical(
                None,
                "Error",
                (
                    f"PV named {self.camconn_pvs[index].name} did not connect.\n"
                    f"IOC for {self.lCameraDesc[index]} is offline!"
                ),
                QMessageBox.Ok,
                QMessageBox.Ok,
            )
            self.normalize_selectors()
            return
        self.clear()
        sCameraPv = str(self.lCameraList[index])
        if sCameraPv == "":
            return
        if self.cameraBase != "":
            self.activeClear()
        self.index = index
        self.update_cam_rate_label()
        self.cameraBase = sCameraPv

        self.activeSet()

        self.ctrlBase = str(self.lCtrlList[index])

        sLensPv = self.lLensList[index]
        sEvrPv = self.lEvrList[index]

        self.connectCamera(sCameraPv + ":ArrayData", index)

        self.avgState = SINGLE_FRAME
        self.ui.singleframe.setChecked(True)
        self.average = 1

        sLensPvDesc = sLensPv if sLensPv != "" else "None"
        print(
            "Using Camera [%d] Pv %s Evr %s LensPv %s"
            % (index, sCameraPv, sEvrPv, sLensPvDesc)
        )
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
                    except Exception:
                        self.ui.horizontalSliderLens.setMinimum(0)
                        self.ui.horizontalSliderLens.setMaximum(100)
                else:
                    lensName = sLensPv.split(";")
                    self.ui.horizontalSliderLens.setMinimum(0)
                    self.ui.horizontalSliderLens.setMaximum(100)
                if len(lensName) > 1:
                    self.putlensPv = Pv(lensName[0], initialize=True)
                    self.lensPv = Pv(
                        lensName[1], initialize=True, monitor=self.lensPvUpdateCallback
                    )
                else:
                    self.putlensPv = None
                    self.lensPv = Pv(
                        lensName[0], initialize=True, monitor=self.lensPvUpdateCallback
                    )
                self.lensPv.wait_ready(timeout)
                if self.putlensPv is not None:
                    self.putlensPv.wait_ready(timeout)
                pyca.flush_io()
            except Exception:
                QMessageBox.critical(
                    None,
                    "Error",
                    "Failed to connect to Lens [%d] %s" % (index, sLensPv),
                    QMessageBox.Ok,
                    QMessageBox.Ok,
                )
        self.setupSpecific()
        self.setupDrags()
        self.normalize_selectors()

    def onExpertMode(self):
        if self.ui.showexpert.isChecked():
            self.advdialog.ui.viewWidth.setText(str(self.viewwidth))
            self.advdialog.ui.viewHeight.setText(str(self.viewheight))
            self.advdialog.ui.projSize.setText(str(self.projsize))
            self.advdialog.ui.configCheckBox.setChecked(self.dispspec == 1)
            self.advdialog.ui.calibPVName.setText(self.calibPVName)
            self.advdialog.ui.displayFormat.setText(self.displayFormat)
            self.advdialog.show()
        else:
            self.advdialog.hide()

    def doShowSpecific(self):
        try:
            if self.camera is None:
                raise Exception
            if self.dispspec == 1:
                QMessageBox.critical(
                    None,
                    "Warning",
                    "Camera-specific configuration is on main screen!",
                    QMessageBox.Ok,
                    QMessageBox.Ok,
                )
                return
            self.specificdialog.resize(400, 1)
            self.specificdialog.show()
        except Exception:
            pass

    #
    # Connect a gui element to two PVs, pvname for read, writepvname for writing.
    # The writepvname is actually just saved, but a monitor is setup for the read
    # pv which calls the callback.
    #
    def setupGUIMonitor(self, pvname, gui, callback, writepvname):
        try:
            if writepvname is None:
                gui.writepvname = None
            else:
                gui.writepvname = self.ctrlBase + writepvname
            gui.readpvname = self.ctrlBase + pvname
            pv = Pv(gui.readpvname, initialize=True)
            pv.wait_ready(1.0)
            pv.add_monitor_callback(lambda e=None: callback(e, pv, gui))
            callback(None, pv, gui)
            self.otherpvs.append(pv)
        except Exception:
            pass

    def lineEditMonitorCallback(self, exception, pv, lineedit):
        if exception is None:
            lineedit.setText("%g" % pv.value)

    def setupLineEditMonitor(self, pvname, lineedit, writepvname):
        self.setupGUIMonitor(
            pvname, lineedit, self.lineEditMonitorCallback, writepvname
        )

    def comboMonitorCallback(self, exception, pv, combobox):
        if exception is None:
            combobox.lastwrite = pv.value
            combobox.setCurrentIndex(pv.value)

    def setupComboMonitor(self, pvname, combobox, writepvname):
        combobox.lastwrite = -1
        self.setupGUIMonitor(pvname, combobox, self.comboMonitorCallback, writepvname)

    def comboWriteCallback(self, combobox, idx):
        if combobox.writepvname is None:
            return
        try:
            if idx != combobox.lastwrite:
                combobox.lastwrite = idx
                caput(combobox.writepvname, idx)
        except Exception:
            pass

    def lineIntWriteCallback(self, lineedit):
        if lineedit.writepvname is None:
            return
        try:
            v = int(lineedit.text())
            caput(lineedit.writepvname, v)
        except Exception:
            pass

    def lineFloatWriteCallback(self, lineedit):
        if lineedit.writepvname is None:
            return
        try:
            v = float(lineedit.text())
            caput(lineedit.writepvname, v)
        except Exception:
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
        self.ui.actionGlobalMarkers.setChecked(self.useglobmarks)
        self.setupComboMonitor(
            ":TriggerMode_RBV", self.specificdialog.ui.cameramodeG, ":TriggerMode"
        )
        self.setupLineEditMonitor(":Gain_RBV", self.specificdialog.ui.gainG, ":Gain")
        self.setupLineEditMonitor(
            ":AcquireTime_RBV", self.specificdialog.ui.timeG, ":AcquireTime"
        )
        self.setupLineEditMonitor(
            ":AcquirePeriod_RBV", self.specificdialog.ui.periodG, ":AcquirePeriod"
        )
        self.setupButtonMonitor(
            ":Acquire", self.specificdialog.ui.runButtonG, ":Acquire"
        )
        return

    def changeSize(self, newwidth, newheight, newproj, settext, doresize=True):
        if (
            self.colPv is None
            or self.colPv == 0
            or self.rowPv is None
            or self.rowPv == 0
        ):
            return
        if newwidth >= 400 and newheight >= 400 and newproj >= 250:
            if (
                self.viewwidth != newwidth
                or self.viewheight != newheight
                or self.projsize != newproj
            ):
                self.viewwidth = newwidth
                self.viewheight = newheight
                self.projsize = newproj
                if settext:
                    self.advdialog.ui.viewWidth.setText(str(self.viewwidth))
                    self.advdialog.ui.viewHeight.setText(str(self.viewheight))
                    self.advdialog.ui.projSize.setText(str(self.projsize))
                if doresize:
                    self.ui.display_image.doResize(
                        QSize(self.viewwidth, self.viewheight)
                    )
                    sizeProjX = QSize(self.viewwidth, self.projsize)
                    self.ui.projH.doResize(sizeProjX)
                    sizeProjY = QSize(self.projsize, self.viewheight)
                    self.ui.projV.doResize(sizeProjY)
                    self.ui.projectionFrame.setFixedSize(
                        QSize(self.projsize, self.projsize)
                    )
            self.setImageSize(
                self.colPv.value / self.scale, self.rowPv.value / self.scale, False
            )
            if self.cfg is None:
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
            except Exception:
                print("onAdvanced resizing threw an exception")
            self.setCalibPV(self.advdialog.ui.calibPVName.text())
            if self.validDisplayFormat(self.advdialog.ui.displayFormat.text()):
                self.displayFormat = self.advdialog.ui.displayFormat.text()
        if role == QDialogButtonBox.RejectRole or role == QDialogButtonBox.AcceptRole:
            self.ui.showexpert.setChecked(False)

    def validDisplayFormat(self, rawString):
        return re.match(r"^%\d+(\.\d*)?[efg]$", rawString) is not None

    def calibPVmon(self, exception=None):
        if exception is None:
            self.calib = self.calibPV.value
            self.ui.lineEditCalib.setText(str(self.calib))

    def setCalibPV(self, pvname):
        try:
            if pvname == "":
                self.calibPV = self.disconnectPv(self.calibPV)
                self.calibPVName = ""
            else:
                pv = self.connectPv(pvname)
                pv.monitor_cb = self.calibPVmon
                self.calib = pv.value
                self.ui.lineEditCalib.setText(str(self.calib))
                pv.monitor(pyca.DBE_VALUE)
                self.calibPV = self.disconnectPv(self.calibPV)
                self.calibPV = pv
                self.calibPVName = pvname
        except Exception:
            pass  # The failing PV routine should have popped up a message.

    def onSpecific(self, button):
        pass

    def new_launch_gui_script(self, exc: Exception | None = None):
        """
        This function will be called if the camera has a "LAUNCH_GUI" PV.

        The contents of this PV will be a int8 array that encodes an ascii string.
        This string is the filepath of a script that can be run to open the
        expert screen.

        We stash this string for later use.
        """
        try:
            if exc is None and self.launch_gui_pv is not None:
                self.launch_gui_script = decode_char_waveform(
                    self.launch_gui_pv.data["value"]
                )
        except Exception as exc:
            print(f"Error receiving new launch gui script: {exc}")

    def new_launch_edm_script(self, exc: Exception | None = None):
        """
        This is the same as new_launch_gui_script above, except it uses the older "LAUNCH_EDM" PV.

        Old IOCs may not have "LAUNCH_GUI" yet.
        This PV was renamed to be more gui framework agnostic.
        """
        try:
            if exc is None and self.launch_edm_pv is not None:
                self.launch_edm_script = decode_char_waveform(
                    self.launch_edm_pv.data["value"]
                )
        except Exception as exc:
            print(f"Error receiving new launch edm script: {exc}")

    def on_open_expert(self):
        """
        Open the appropriate expert screen script.

        Requires the LAUNCH_GUI or LAUNCH_EDM PV to have given us a value
        at some point.
        """
        script = self.launch_gui_script or self.launch_edm_script
        if not script:
            QMessageBox.critical(
                None,
                "Error",
                "No expert screen available, PVs did not connect.",
                QMessageBox.Ok,
                QMessageBox.Ok,
            )
            return
        print(f"Running {script}")
        # Not handling other errors for now
        subprocess.run([script])

    def set_new_min_pixel(self, value: int):
        """
        Sets the minimum pixel threshold for monochrome colormap scaling.

        This cannot be set to be higher than the max pixel threshold.
        If this is done, the max pixel threshold will be increased to
        match this new value.

        Pixels whose values are below this number will all render as the
        same color after we apply the color map. Pixels whose values are
        above this number, up to the max pixel value, will be assigned
        colors from the color map based on the other settings.

        Internally, this does the following:
        - Sets an attribute that will be applied the next time the image
          is rendered
        - Updates the sliders and text boxes appropriately to match
          the new value

        If you would like to render a new image immediately instead of
        waiting for the next frame, you need to call
        ``self.after_new_min_or_max_pixel()`` afterwards.
        This is kept separate so we can set this value during
        a re-render if we need to.
        """
        value = max(0, value)
        value = min(self.maxcolor, value)
        self.iRangeMin = value
        if value > self.iRangeMax:
            self.iRangeMax = value
        self.update_visible_pixel_ranges()

    def set_new_max_pixel(self, value: int):
        """
        Sets the maximum pixel threshold for monochrome colormap scaling.

        This cannot be set to be lower than the min pixel threshold.
        If this is done, the min pixel threshold will be decreased to
        match this new value.

        Pixels whose values are above this number will all render as the
        same color after we apply the color map. Pixels whose values are
        below this number, down to the min pixel value, will be assigned
        colors from the color map based on the other settings.

        Internally, this does the following:
        - Sets an attribute that will be applied the next time the image
          is rendered
        - Updates the sliders and text boxes appropriately to match
          the new value

        If you would like to render a new image immediately instead of
        waiting for the next frame, you need to call
        ``self.after_new_min_or_max_pixel()`` afterwards.
        This is kept separate so we can set this value during
        a re-render if we need to.
        """
        value = max(0, value)
        value = min(self.maxcolor, value)
        self.iRangeMax = value
        if value < self.iRangeMin:
            self.iRangeMin = value
        self.update_visible_pixel_ranges()

    def after_new_min_or_max_pixel(self):
        """
        Updates the rendered image to reflect new color map scaling.
        """
        self.setColorMap()
        self.updateProj()
        self.updateMiscInfo()

    def update_visible_pixel_ranges(self):
        """
        Sets the visual state of the pixel range widgets correctly.

        This is so we can move the slider or type into the text box and
        update the other widget with the new value.
        """
        self.ui.horizontalSliderRangeMax.setValue(self.iRangeMax)
        self.ui.horizontalSliderRangeMin.setValue(self.iRangeMin)
        self.ui.lineEditRangeMax.setText(str(self.iRangeMax))
        self.ui.lineEditRangeMin.setText(str(self.iRangeMin))

    def on_slider_range_min_released(self):
        """
        When the user lets go of the slider, update the value and rerender.
        """
        self.set_new_min_pixel(self.ui.horizontalSliderRangeMin.value())
        self.after_new_min_or_max_pixel()

    def on_slider_range_max_released(self):
        """
        When the user lets go of the slider, update the value and rerender.
        """
        self.set_new_max_pixel(self.ui.horizontalSliderRangeMax.value())
        self.after_new_min_or_max_pixel()

    def onSliderLensChanged(self, newSliderValue):
        self.ui.lineEditLens.setText(str(newSliderValue))

    def onSliderLensReleased(self):
        newSliderValue = self.ui.horizontalSliderLens.value()
        if self.lensPv is not None:
            try:
                if self.putlensPv is not None:
                    self.putlensPv.put(newSliderValue)
                else:
                    self.lensPv.put(newSliderValue)
                pyca.flush_io()
            except pyca.pyexc as e:
                print("pyca exception: %s" % (e))
            except pyca.caexc as e:
                print("channel access exception: %s" % (e))

    def on_range_min_text_enter_pressed(self):
        """
        When the user presses enter on the pixel text boxes, update the value and rerender.
        """
        try:
            value = int(self.ui.lineEditRangeMin.text())
        except Exception:
            value = 0
        self.set_new_min_pixel(value)
        self.after_new_min_or_max_pixel()

    def on_range_max_text_enter_pressed(self):
        """
        When the user presses enter on the pixel text boxes, update the value and rerender.
        """
        try:
            value = int(self.ui.lineEditRangeMax.text())
        except Exception:
            value = 0
        self.set_new_max_pixel(value)
        self.after_new_min_or_max_pixel()

    def set_auto_range(self, checked: None | Qt.CheckState = None):
        """
        Apply an automatic pixel range to the image and rerender.

        This takes the current maximum and minimum pixel values
        from the last collected image and sets them as the maximum
        and minimum pixel thresholds for the colormap.

        This is intended to be called as a slot from signals emitted
        from clicking a QPushButton or from checking a QCheckbox.

        If the QPushButton is clicked or the QCheckbox is checked,
        immediately apply an automatic range to the live image.

        This allows the user to set an automatic range on demand
        by clicking a button, and it allows the "auto every frame"
        checkbox to immediately apply auto scaling instead of waiting
        for the next frame.
        """
        if checked in (None, Qt.Checked):
            self.set_new_max_pixel(self.max_px)
            self.set_new_min_pixel(self.min_px)
            self.after_new_min_or_max_pixel()

    def onLensEnter(self):
        try:
            value = int(self.ui.lineEditLens.text())
        except Exception:
            value = 0

        mn = self.ui.horizontalSliderLens.minimum()
        mx = self.ui.horizontalSliderLens.maximum()
        if value < mn:
            value = mn
        if value > mx:
            value = mx
        self.ui.horizontalSliderLens.setValue(value)
        if self.lensPv is not None:
            try:
                if self.putlensPv is not None:
                    self.putlensPv.put(value)
                else:
                    self.lensPv.put(value)
                pyca.flush_io()
            except pyca.pyexc as e:
                print("pyca exception: %s" % (e))
            except pyca.caexc as e:
                print("channel access exception: %s" % (e))

    def on_reconnect(self):
        """
        Disconnect from the currently selected camera's PV and reconnect to them.

        This is called from the menu bar under Administration -> Reconnect
        """
        self.onCameraSelect(self.ui.comboBoxCamera.currentIndex())

    def on_force_disconnect(self):
        """
        Open a small GUI for doing something (?) to your own camviewer processes.

        This is currently very bugged.
        This is called from the menu bar under Administration -> Force Disconnect
        """
        if self.cameraBase != "" and not self.haveforce:
            self.forcedialog = forcedialog(self.activedir + self.cameraBase + "/", self)
            self.haveforce = True

    def update_timeout_display(self, msec: int | None = None):
        """
        Show the user how much time until the rate_limit_timer expires.

        If the timer is not active, this will set the display text to "Never",
        or to "Timed Out" if we've completely timed out.

        Otherwise, it will set the display text in the most appropriate form
        from the options:

        - x days, y hours
        - x hours, y mins
        - x mins
        - under 1 minute

        This function is meant to be called periodically using the
        refresh_timeout_display_timer, or manually to set a specific value
        when the user selects a new timeout duration.
        """
        if msec is None:
            if not self.rate_limit_timer.isActive():
                if self.last_des_max_rate <= 1:
                    text = "Never"
                else:
                    text = "Timed Out"
                self.ui.label_rate_timeout_value.setText(text)
                return
            msec = self.rate_limit_timer.remainingTime()
        sec = msec // 1000
        mins, sec = divmod(sec, 60)
        hours, mins = divmod(mins, 60)
        days, hours = divmod(hours, 24)

        if days:
            text = f"{days} days, {hours} hours"
        elif hours:
            text = f"{hours} hours, {mins} mins"
        elif mins:
            text = f"{mins} mins"
        else:
            text = "under 1 minute"

        self.ui.label_rate_timeout_value.setText(text)

    def apply_rate_limit(self):
        """
        Decrease the maximum allowed image rate to 1 Hz.

        This is meant to be called when the rate_limit_timer
        expires, which means the user has not interacted
        with the GUI for a long time.
        """
        self.disable_rate_timer()
        self.set_max_image_rate(1)

    def disable_rate_timer(self):
        """
        Stop the rate_limit_timer and update the timeout display accordingly.

        This is means to be called when we get a rate_limit_timer timeout,
        or when the user manually limits their own rate to 1 Hz.
        """
        self.rate_limit_timer.stop()
        self.update_timeout_display()

    def refresh_rate_timer(self):
        """
        Reset rate_limit_timer to the full timeout value.

        If the user's last selected max rate is greater than 1,
        restore this selection.

        This is meant to be called when the user is no longer idle.

        When the associated timer times out, it will force the rate
        limit down to 1 Hz. Calling this function will ensure
        that the timer starts again from the full timeout duration
        and that any previous call to apply_rate_limit will be
        reversed.
        """
        if self.last_des_max_rate > 1:
            self.rate_limit_timer.start()
            self.set_max_image_rate(self.last_des_max_rate)

    def set_rate_limit_duration(self, secs):
        """
        Set a new duration on the rate_limit_timer.

        This handles starting the rate_limit_timer,
        restarts the refresh_timeout_display_timer,
        and directly updates the displayed timeout to exactly
        the new duration we just set.

        This ensures that we get a consistent starting point
        for the displayed time remaining text.

        This also starts the notify PV monitor if it didn't get started
        in the normal flow of camera PV setup, which is normally
        used to let this process know when a new image is available.
        It's unlikely this bit of code is needed but I don't want to
        tempt fate by removing it.
        """
        msec = int(1000 * secs)
        self.rate_limit_timer.start(msec)
        self.refresh_timeout_display_timer.start()
        self.update_timeout_display(msec)
        if self.notify is not None and not self.notify.ismonitored:
            self.notify.monitor(pyca.DBE_VALUE, False, 1)
            pyca.flush_io()

    def activeCheck(self):
        if self.cameraBase == "":
            return
        file = self.activedir + self.cameraBase + "/" + self.description
        try:
            f = open(file)
            lines = f.readlines()
            if len(lines) > 1:
                self.activeSet()
        except Exception:
            pass

    def activeClear(self):
        try:
            file = self.activedir + self.cameraBase + "/" + self.description
            os.unlink(file)
        except Exception:
            pass

    def activeSet(self):
        try:
            dir = self.activedir + self.cameraBase
            try:
                os.mkdir(dir)
            except Exception:
                pass  # It might already exist!
            f = open(dir + "/" + self.description, "w")
            f.write(os.ttyname(0) + "\n")
            f.close()
        except Exception:
            pass

    def setDispSpec(self, v):
        if v != self.dispspec:
            if v == 0:
                self.specificdialog.ui.verticalLayout.addWidget(
                    self.specificdialog.ui.areadetBox
                )
            else:
                # Sigh.  The last item is a spacer which we need to keep as the last item!
                spc = self.ui.RightPanel.itemAt(self.ui.RightPanel.count() - 1)
                self.ui.RightPanel.removeItem(spc)
                self.ui.RightPanel.addWidget(self.specificdialog.ui.areadetBox)
                self.ui.RightPanel.addItem(spc)
                self.specificdialog.ui.verticalLayout.removeWidget(
                    self.specificdialog.ui.buttonBox
                )
            self.ui.RightPanel.invalidate()
            self.adjustSize()
            self.update()
            self.dispspec = v

    def dumpConfig(self):
        if self.camera is not None and self.options is None:
            write_camera_config(self)
            write_global_config(self)

            settings = QSettings("SLAC", "CamViewer")
            settings.setValue("geometry/%s" % self.cfgname, self.saveGeometry())
            settings.setValue("windowState/%s" % self.cfgname, self.saveState())
            if self.oldcfg:
                try:
                    self.oldcfg = False
                    os.unlink(self.cfgdir + self.cfgname)
                except Exception:
                    pass

    def getConfig(self):
        if self.camera is None:
            return
        self.cfg = cfginfo()
        # Global defaults.
        self.cfg.add("config", "0")
        self.cfg.add("projection", "0")
        self.cfg.add("markers", "0")
        self.cfg.add("dispspec", "0")
        if not self.cfg.read(self.cfgdir + "GLOBAL"):
            self.cfg.add("config", "1")
            self.cfg.add("projection", "1")
            self.cfg.add("markers", "1")
            self.cfg.add("dispspec", "0")
        if self.options is not None:
            # Let the command line options override the config file!
            if self.options.config is not None:
                self.cfg.add("config", self.options.config)
            if self.options.proj is not None:
                self.cfg.add("projection", self.options.proj)
            if self.options.marker is not None:
                self.cfg.add("markers", self.options.marker)
            if self.options.camcfg is not None:
                self.cfg.add("dispspec", self.options.camcfg)

        # Read the config file
        #
        # New Regime: We're going back to the Ancien Regime!  Config files
        # are just the camera base name.  But... we'll try to read the old
        # names first.  When we first save a new one, we will delete the old
        # one.
        if self.cfg.read(self.cfgdir + self.cfgname):
            self.oldcfg = True
        else:
            # OK, didn't work, look for a new one!
            self.oldcfg = False
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
                if self.options is not None:
                    if self.options.orientation is not None:
                        self.setOrientation(int(self.options.orientation))
                    elif self.options.lportrait is not None:
                        if int(self.options.lportrait):
                            self.setOrientation(param.ORIENT90)
                        else:
                            self.setOrientation(param.ORIENT0)
                    if self.options.cmap is not None:
                        self.ui.comboBoxColor.setCurrentIndex(
                            self.ui.comboBoxColor.findText(self.options.cmap)
                        )
                        self.colorMap = self.options.cmap.lower()
                        self.ui.grayScale.setChecked(
                            True
                        )  # If we want a color map, force gray scale!
                        self.setColorMap()
                    self.options = None
                self.dumpConfig()
                self.cfg = None
                return

        # Let command line options override local config file
        if self.options is not None:
            if self.options.orientation is not None:
                self.cfg.add("cmd_orientation", int(self.options.orientation))
            elif self.options.lportrait is not None:
                if self.options.lportrait == "0":
                    self.cfg.add("cmd_orientation", param.ORIENT0)
                else:
                    self.cfg.add("cmd_orientation", param.ORIENT90)
            if self.options.cmap is not None:
                self.cfg.add("colormap", self.options.cmap)
            self.options = None

        try:
            use_abs = int(self.cfg.use_abs)
        except Exception:
            use_abs = 0

        # Set the window size
        settings = QSettings("SLAC", "CamViewer")
        pos = self.pos()
        v = settings.value("geometry/%s" % self.cfgname)
        if v is not None:
            self.restoreGeometry(v)
        self.move(pos)  # Just restore the size, keep the position!
        v = settings.value("windowState/%s" % self.cfgname)
        if v is not None:
            self.restoreState(v)

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
        except Exception:
            mk = 1
        self.ui.showmarker.setChecked(mk)
        self.doShowMarker()
        try:
            dc = int(self.cfg.dispspec)
        except Exception:
            dc = 0
        self.setDispSpec(dc)
        try:
            orientation = self.cfg.orientation
        except Exception:
            orientation = param.ORIENT0
        self.setOrientation(int(orientation))
        self.ui.checkBoxProjAutoRange.setChecked(int(self.cfg.autorange))
        try:
            self.ui.display_image.setRectZoom(
                float(self.cfg.rectzoom[0]),
                float(self.cfg.rectzoom[1]),
                float(self.cfg.rectzoom[2]),
                float(self.cfg.rectzoom[3]),
            )
        except Exception:
            pass
        try:
            self.ui.display_image.roiSet(
                float(self.cfg.ROI[0]),
                float(self.cfg.ROI[1]),
                float(self.cfg.ROI[2]),
                float(self.cfg.ROI[3]),
                rel=(use_abs == 0),
            )
        except Exception:
            pass
        self.updateall()
        self.ui.comboBoxColor.setCurrentIndex(
            self.ui.comboBoxColor.findText(self.cfg.colormap)
        )
        self.colorMap = self.cfg.colormap.lower()
        # OK, we're changing this to introduce more scales!  So,
        # "Log Scale" --> "Log2 Scale" and "Exp Scale" --> "Exp2 Scale"
        if self.cfg.colorscale[0] == "Log":
            self.cfg.colorscale[0] = "Log2"
        elif self.cfg.colorscale[0] == "Exp":
            self.cfg.colorscale[0] = "Exp2"
        self.iScaleIndex = self.ui.comboBoxScale.findText(
            self.cfg.colorscale[0] + " " + self.cfg.colorscale[1]
        )
        self.ui.comboBoxScale.setCurrentIndex(self.iScaleIndex)
        try:
            self.set_new_min_pixel(int(self.cfg.colormin))
            self.set_new_max_pixel(int(self.cfg.colormax))
        except Exception:
            print("Failed to load min or max pixel value from config file.")
        try:
            self.ui.grayScale.setChecked(int(self.cfg.grayscale))
            self.onCheckGrayUpdate(int(self.cfg.grayscale))
        except Exception:
            pass
        self.setColorMap()
        try:
            self.useglobmarks = bool(int(self.cfg.globmarks))
        except Exception:
            self.useglobmarks = False
        if self.useglobmarks:
            self.useglobmarks = self.connectMarkerPVs()
        self.ui.actionGlobalMarkers.setChecked(self.useglobmarks)
        try:
            self.useglobmarks2 = bool(int(self.cfg.globmarks2))
        except Exception:
            self.useglobmarks2 = False
        if self.useglobmarks2:
            self.useglobmarks2 = self.connectMarkerPVs2()
        if self.useglobmarks:
            self.onCrossUpdate(0)
            self.onCrossUpdate(1)
        else:
            if use_abs == 1:
                self.ui.display_image.lMarker[0].setAbs(
                    int(self.cfg.m1[0]), int(self.cfg.m1[1])
                )
                self.ui.display_image.lMarker[1].setAbs(
                    int(self.cfg.m2[0]), int(self.cfg.m2[1])
                )
            else:
                self.ui.display_image.lMarker[0].setRel(
                    int(self.cfg.m1[0]), int(self.cfg.m1[1])
                )
                self.ui.display_image.lMarker[1].setRel(
                    int(self.cfg.m2[0]), int(self.cfg.m2[1])
                )
        if self.useglobmarks2:
            self.onCrossUpdate(2)
            self.onCrossUpdate(3)
        else:
            if use_abs == 1:
                self.ui.display_image.lMarker[2].setAbs(
                    int(self.cfg.m3[0]), int(self.cfg.m3[1])
                )
                self.ui.display_image.lMarker[3].setAbs(
                    int(self.cfg.m4[0]), int(self.cfg.m4[1])
                )
            else:
                self.ui.display_image.lMarker[2].setRel(
                    int(self.cfg.m3[0]), int(self.cfg.m3[1])
                )
                self.ui.display_image.lMarker[3].setRel(
                    int(self.cfg.m4[0]), int(self.cfg.m4[1])
                )
        self.updateMarkerText()
        self.changeSize(int(newwidth), int(newheight), int(newproj), False)
        try:
            # OK, see if we've delayed the command line orientation setting until now.
            orientation = self.cfg.cmd_orientation
            self.setOrientation(int(orientation))
        except Exception:
            pass
        # Process projection settings, if any.
        try:
            self.ui.checkBoxProjRoi.setChecked(self.cfg.projroi == "1")
            check = [ll == "1" for ll in self.cfg.projlineout]
            self.ui.checkBoxM1Lineout.setChecked(check[0])
            self.ui.checkBoxM2Lineout.setChecked(check[1])
            self.ui.checkBoxM3Lineout.setChecked(check[2])
            self.ui.checkBoxM4Lineout.setChecked(check[3])
            self.ui.checkBoxFits.setChecked(self.cfg.projfit == "1")
            check = [ll == "1" for ll in self.cfg.projfittype]
            if check[0]:
                self.ui.radioGaussian.setChecked(True)
            if check[1]:
                self.ui.radioSG4.setChecked(True)
            if check[2]:
                self.ui.radioSG6.setChecked(True)
            self.calib = float(self.cfg.projcalib)
            self.ui.lineEditCalib.setText(str(self.calib))
        except Exception:
            pass
        try:
            if self.cfg.projcalibPV[0] == '"' and self.cfg.projcalibPV[-1] == '"':
                self.setCalibPV(self.cfg.projcalibPV[1:-1])
            else:
                self.calibPVName = ""
                self.calibPV = None
        except Exception:
            self.calibPVName = ""
            self.calibPV = None
        try:
            self.ui.checkBoxConstant.setChecked(self.cfg.projconstant == "1")
        except Exception:
            pass
        try:
            if (
                self.cfg.projdisplayFormat[0] == '"'
                and self.cfg.projdisplayFormat[-1] == '"'
            ):
                self.displayFormat = self.cfg.projdisplayFormat[1:-1]
            else:
                self.displayFormat = "%12.8g"
        except Exception:
            self.displayFormat = "%12.8g"

        self.cfg = None


def write_camera_config(gui: GraphicUserInterface) -> None:
    with atomic_writer(gui.cfgdir + gui.cameraBase) as fd:
        fd.write("projsize    " + str(gui.projsize) + "\n")
        fd.write("viewwidth   " + str(gui.viewwidth) + "\n")
        fd.write("viewheight  " + str(gui.viewheight) + "\n")
        fd.write("portrait    " + str(int(param.orientation == param.ORIENT90)) + "\n")
        fd.write("orientation " + str(param.orientation) + "\n")
        fd.write(
            "autorange   " + str(int(gui.ui.checkBoxProjAutoRange.isChecked())) + "\n"
        )
        fd.write("use_abs     1\n")
        rz = gui.ui.display_image.rectZoom.abs()
        fd.write(
            "rectzoom    "
            + str(rz.x())
            + " "
            + str(rz.y())
            + " "
            + str(rz.width())
            + " "
            + str(rz.height())
            + "\n"
        )
        fd.write("colormap    " + str(gui.ui.comboBoxColor.currentText()) + "\n")
        fd.write("colorscale  " + str(gui.ui.comboBoxScale.currentText()) + "\n")
        fd.write("colormin    " + gui.ui.lineEditRangeMin.text() + "\n")
        fd.write("colormax    " + gui.ui.lineEditRangeMax.text() + "\n")
        fd.write("grayscale   " + str(int(gui.ui.grayScale.isChecked())) + "\n")
        roi = gui.ui.display_image.rectRoi.abs()
        fd.write(
            "ROI         %d %d %d %d\n" % (roi.x(), roi.y(), roi.width(), roi.height())
        )
        fd.write("globmarks   " + str(int(gui.useglobmarks)) + "\n")
        fd.write("globmarks2  " + str(int(gui.useglobmarks2)) + "\n")
        lMarker = gui.ui.display_image.lMarker
        for i in range(4):
            fd.write(
                "m%d          %d %d\n"
                % (i + 1, lMarker[i].abs().x(), lMarker[i].abs().y())
            )
        fd.write("projroi     " + str(int(gui.ui.checkBoxProjRoi.isChecked())) + "\n")
        fd.write(
            "projlineout "
            + str(int(gui.ui.checkBoxM1Lineout.isChecked()))
            + " "
            + str(int(gui.ui.checkBoxM2Lineout.isChecked()))
            + " "
            + str(int(gui.ui.checkBoxM3Lineout.isChecked()))
            + " "
            + str(int(gui.ui.checkBoxM4Lineout.isChecked()))
            + "\n"
        )
        fd.write("projfit     " + str(int(gui.ui.checkBoxFits.isChecked())) + "\n")
        fd.write(
            "projfittype "
            + str(int(gui.ui.radioGaussian.isChecked()))
            + " "
            + str(int(gui.ui.radioSG4.isChecked()))
            + " "
            + str(int(gui.ui.radioSG6.isChecked()))
            + "\n"
        )
        fd.write("projconstant " + str(int(gui.ui.checkBoxConstant.isChecked())) + "\n")
        fd.write("projcalib   %g\n" % gui.calib)
        fd.write('projcalibPV "%s"\n' % gui.calibPVName)
        fd.write('projdisplayFormat "%s"\n' % gui.displayFormat)


def write_global_config(gui: GraphicUserInterface) -> None:
    with atomic_writer(gui.cfgdir + "GLOBAL") as fd:
        fd.write("config      " + str(int(gui.ui.showconf.isChecked())) + "\n")
        fd.write("projection  " + str(int(gui.ui.showproj.isChecked())) + "\n")
        fd.write("markers     " + str(int(gui.ui.showmarker.isChecked())) + "\n")
        fd.write("dispspec    " + str(gui.dispspec) + "\n")


@contextlib.contextmanager
def atomic_writer(path: str) -> typing.Iterator[typing.TextIO]:
    with tempfile.NamedTemporaryFile("w", delete=False) as fd:
        try:
            yield fd
        except Exception as exc:
            # There is some issue and the temp file is not complete.
            # Avoid the else block, we don't want to keep the corrupt file.
            # Show some error instead of bricking the gui
            print(f"Error writing {path}: {exc}")
        else:
            # File must be closed before we can chmod and move it
            fd.close()
            # Set -rw-r--r-- instead of temp file default -rw-------
            os.chmod(fd.name, 0o644)
            shutil.move(fd.name, path)
    # If the tempfile still exists, we should clean it up.
    if os.path.exists(fd.name):
        os.remove(fd.name)


def decode_char_waveform(waveform: npt.NDArray[np.int8]) -> str:
    """
    Convert an epics char waveform to a string.

    In pyca, these can be loaded into numpy arrays via passing
    numpy=True as a kwarg.

    The waveform is an array of signed 8-bit integers whose
    unsigned representations correspond to the ascii character codes.
    The string is null-terminated.
    """
    # Implementation lifted from PyDM's "parse_value_for_display"
    zeros = np.where(waveform == 0)[0]
    if zeros.size > 0:
        waveform = waveform[: zeros[0]]
    return waveform.tobytes().decode(encoding="ascii", errors="ignore")
