from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QImage, QPen, QColor, QPainter
from PyQt5.QtCore import Qt, QPointF, QSize, QRectF
import param


# Comments are whether we are in image or screen coordinates.
class DisplayImage(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        gui = parent
        x = gui.parentWidget()
        while x is not None:
            gui = x
            x = gui.parentWidget()
        self.gui = gui
        self.hint = QSize(self.gui.viewwidth, self.gui.viewheight)
        self.retry = False
        self.pcnt = 0
        size = param.getSize()
        self.image = QImage(size, QImage.Format_RGB32)
        self.image.fill(0)
        self.rectZoom = param.Rect(0, 0, param.x, param.y)  # image
        self.arectZoom = param.Rect(0, 0, param.x, param.y)  # image
        self.rectRoi = param.Rect(0, 0, param.x, param.y)  # image
        self.paintevents = 0
        self.xoff = QPointF(20, 0)
        self.yoff = QPointF(0, 20)
        self.setZoom()
        self.cursorPos = param.Point(0, 0)  # image
        self.setMouseTracking(True)
        self.rectImage = QRectF(0, 0, size.width(), size.height())  # screen
        self.sWindowTitle = "Camera: None"

        # set marker data
        self.lMarker = [
            param.Point(-100, -100),  # image
            param.Point(param.x + 100, -100),
            param.Point(param.x + 100, param.y + 100),
            param.Point(-100, param.y + 100),
        ]
        self.lPenColor = [
            (0 / 255.0, 128 / 255.0, 255 / 255.0),  # matplotlib colors!!
            (255 / 255.0, 0 / 255.0, 0 / 255.0),
            (0 / 255.0, 204 / 255.0, 204 / 255.0),
            (204 / 255.0, 0 / 255.0, 204 / 255.0),
        ]
        self.lPenMarker = [
            QPen(QColor(0, 128, 255), 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
            QPen(QColor(255, 0, 0), 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
            QPen(QColor(0, 204, 204), 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
            QPen(QColor(204, 0, 204), 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
        ]
        self.lPenProj = [
            QPen(QColor(0, 128, 255), 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin),
            QPen(QColor(255, 0, 0), 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin),
            QPen(QColor(0, 204, 204), 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin),
            QPen(QColor(204, 0, 204), 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin),
        ]
        self.penMarkerBack = QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self.penProjBack = QPen(Qt.black, 1, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin)
        self.penRoi = QPen(Qt.green, 1, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
        self.penRoiBack = QPen(Qt.black, 1, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
        self.roiInvX = False
        self.roiInvY = False

    def contextMenuEvent(self, ev):
        ui = self.gui.ui
        # Fix up the menu!
        if ui.showconf.isChecked():
            ui.actionShow_Configuration.setText("Hide Configuration")
        else:
            ui.actionShow_Configuration.setText("Show Configuration")
        if ui.showproj.isChecked():
            ui.actionShow_Projection.setText("Hide Projection")
        else:
            ui.actionShow_Projection.setText("Show Projection")
        # Start the menu!
        action = ui.menuPopup.exec_(ev.globalPos())
        # Take the action!
        if action == ui.actionReset_ROI:
            self.gui.onRoiReset()
        elif action == ui.actionZoom_to_ROI:
            self.zoomToRoi()
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
        if s is None:
            s = self.size()
        self.hint = s
        self.updateGeometry()

    def sizeHint(self):
        return self.hint

    def setRectZoom(self, x, y, w, h):
        self.rectZoom = param.Rect(x, y, w, h)
        self.setZoom()

    def setImageSize(self, reset=True):
        size = param.getSize()
        self.image = QImage(size, QImage.Format_RGB32)
        self.image.fill(0)
        if reset:
            self.rectZoom = param.Rect(0, 0, param.x, param.y)
            self.rectRoi = param.Rect(0, 0, param.x, param.y)
        self.setZoom()
        self.gui.updateRoiText()
        self.gui.updateMiscInfo()
        if reset:
            self.lMarker = [
                param.Point(-100, -100),  # image
                param.Point(param.x + 100, -100),
                param.Point(param.x + 100, param.y + 100),
                param.Point(-100, param.y + 100),
            ]

    def pWidth(self):
        if param.orientation & 2:
            return self.height()
        else:
            return self.width()

    def pHeight(self):
        if param.orientation & 2:
            return self.width()
        else:
            return self.height()

    def paintEvent(self, event):
        if self.gui.dispUpdates == 0:
            return

        painter = QPainter(self)
        # painter.setRenderHint(QPainter.Antialiasing)

        self.paintevents += 1

        fZoomedWidth = param.zoom * self.arectZoom.oriented().width()
        fZoomedHeight = param.zoom * self.arectZoom.oriented().height()

        self.rectImage = QRectF(
            (self.width() - fZoomedWidth) / 2,
            (self.height() - fZoomedHeight) / 2,
            fZoomedWidth,
            fZoomedHeight,
        )

        # Draw arectZoom portion of image into rectImage
        painter.drawImage(self.rectImage, self.image, self.arectZoom.oriented())

        painter.setOpacity(1)

        lbProjChecked = [
            self.gui.ui.checkBoxM1Lineout.isChecked(),
            self.gui.ui.checkBoxM2Lineout.isChecked(),
            self.gui.ui.checkBoxM3Lineout.isChecked(),
            self.gui.ui.checkBoxM4Lineout.isChecked(),
        ]

        for (iMarker, ptMarker) in enumerate(self.lMarker):
            markerImage = (
                ptMarker.oriented() - self.arectZoom.oriented().topLeft()
            ) * param.zoom + self.rectImage.topLeft()  # screen

            painter.setPen(self.penMarkerBack)
            painter.drawLine(
                markerImage - self.xoff + QPointF(1, 1),
                markerImage + self.xoff + QPointF(1, 1),
            )
            painter.drawLine(
                markerImage - self.yoff + QPointF(1, 1),
                markerImage + self.yoff + QPointF(1, 1),
            )

            painter.setPen(self.lPenMarker[iMarker])
            painter.drawLine(markerImage - self.xoff, markerImage + self.xoff)
            painter.drawLine(markerImage - self.yoff, markerImage + self.yoff)

            if lbProjChecked[iMarker]:
                painter.setPen(self.penProjBack)
                painter.drawLine(
                    markerImage.x() + 1, 1, markerImage.x() + 1, self.pHeight()
                )
                painter.drawLine(
                    1, markerImage.y() + 1, self.pWidth(), markerImage.y() + 1
                )
                painter.setPen(self.lPenProj[iMarker])
                painter.drawLine(
                    markerImage.x(), 0, markerImage.x(), self.pHeight() - 1
                )
                painter.drawLine(0, markerImage.y(), self.pWidth() - 1, markerImage.y())

        roiTopLeft = (
            self.rectRoi.oriented().topLeft() - self.arectZoom.oriented().topLeft()
        ) * param.zoom + self.rectImage.topLeft()  # image
        roiSize = self.rectRoi.oriented().size() * param.zoom
        painter.setPen(self.penRoiBack)
        painter.drawRect(QRectF(roiTopLeft + QPointF(1, 1), roiSize))
        painter.setPen(self.penRoi)
        painter.drawRect(QRectF(roiTopLeft, roiSize))

    def mousePressEvent(self, event):
        # OK, what's going on here?
        # arectZoom is coordinates in the image.
        # rectImage is coordinates on the screen.
        # posx is coordinates on the screen as well.
        posx = event.x()
        posy = event.y()

        # rectImage is inside (xpos, ypos).  Convert to oriented image coordinates.
        imgx = (posx - self.rectImage.x()) * (
            self.arectZoom.oriented().width() / self.rectImage.width()
        ) + self.arectZoom.oriented().x()
        imgy = (posy - self.rectImage.y()) * (
            self.arectZoom.oriented().height() / self.rectImage.height()
        ) + self.arectZoom.oriented().y()

        self.cursorPos = param.Point(imgx, imgy, rel=True)

        if self.gui.iSpecialMouseMode == 0:
            self.lastMousePos = event.pos()
            return

        if self.gui.iSpecialMouseMode == 5:
            self.roiInvX = False
            self.roiInvY = False
            self.rectRoi.setRel(imgx, imgy, 2, 2)
            self.gui.updateRoiText()
            self.gui.updateProj()
            if self.gui.cfg is None:
                self.gui.dumpConfig()
        elif self.gui.iSpecialMouseMode >= 1 and self.gui.iSpecialMouseMode <= 4:
            self.lMarker[self.gui.iSpecialMouseMode - 1].setRel(imgx, imgy)
            self.lMarker[self.gui.iSpecialMouseMode - 1].pr(
                "Set marker %d to (%d, %d): " % (self.gui.iSpecialMouseMode, imgx, imgy)
            )
            self.gui.updateMarkerText(
                True,
                True,
                1 << (self.gui.iSpecialMouseMode - 1),
                1 << (self.gui.iSpecialMouseMode - 1),
            )
            self.gui.updateProj()
            if self.gui.cfg is None:
                self.gui.dumpConfig()
        self.update()

    def mouseMoveEvent(self, event):
        posx = event.x()
        posy = event.y()

        imgx = (posx - self.rectImage.x()) * (
            self.arectZoom.oriented().width() / self.rectImage.width()
        ) + self.arectZoom.oriented().x()
        imgy = (posy - self.rectImage.y()) * (
            self.arectZoom.oriented().height() / self.rectImage.height()
        ) + self.arectZoom.oriented().y()

        self.cursorPos = param.Point(imgx, imgy, rel=True)

        if self.gui.iSpecialMouseMode == 0:
            if not (event.buttons() & Qt.LeftButton):
                return
            return self.moveImage(event)

        if self.gui.iSpecialMouseMode <= 5 and not (event.buttons() & Qt.LeftButton):
            return

        if self.gui.iSpecialMouseMode == 5:
            if self.roiInvX:
                if imgx > self.rectRoi.oriented().right():
                    self.roiInvX = False
            else:
                if imgx < self.rectRoi.oriented().left():
                    self.roiInvX = True

            if self.roiInvX:
                self.rectRoi.setLeft(imgx)
            else:
                self.rectRoi.setRight(imgx)

            if self.roiInvY:
                if imgy > self.rectRoi.oriented().bottom():
                    self.roiInvY = False
            else:
                if imgy < self.rectRoi.oriented().top():
                    self.roiInvY = True

            if self.roiInvY:
                self.rectRoi.setTop(imgy)
            else:
                self.rectRoi.setBottom(imgy)

            self.gui.updateRoiText()
            self.gui.updateProj()
            if self.gui.cfg is None:
                self.gui.dumpConfig()
        elif self.gui.iSpecialMouseMode >= 1 and self.gui.iSpecialMouseMode <= 4:
            self.lMarker[self.gui.iSpecialMouseMode - 1].setRel(imgx, imgy)
            self.gui.updateMarkerText(
                True,
                True,
                1 << (self.gui.iSpecialMouseMode - 1),
                1 << (self.gui.iSpecialMouseMode - 1),
            )
            self.gui.updateProj()
            if self.gui.cfg is None:
                self.gui.dumpConfig()

        self.update()

    def mouseReleaseEvent(self, event):
        if self.gui.iSpecialMouseMode != 0:
            return self.mouseMoveEvent(event)
        return self.moveImage(event)

    def wheelEvent(self, event):
        if event.angleDelta().y() < 0:
            fFactor = 1.5
        else:
            fFactor = 1 / 1.5

        zoomSize = self.rectZoom.oriented().size() * fFactor

        posx = event.x()
        posy = event.y()

        shiftRatioX = (posx - self.rectImage.x()) / self.rectImage.width()
        shiftRatioY = (posy - self.rectImage.y()) / self.rectImage.height()
        imgx = (
            shiftRatioX * self.arectZoom.oriented().width()
            + self.arectZoom.oriented().x()
        )
        imgy = (
            shiftRatioY * self.arectZoom.oriented().height()
            + self.arectZoom.oriented().y()
        )

        pointNewTopLeft = QPointF(
            imgx - zoomSize.width() * shiftRatioX,
            imgy - zoomSize.height() * shiftRatioY,
        )
        self.rectZoom = param.Rect(
            pointNewTopLeft.x(),
            pointNewTopLeft.y(),
            zoomSize.height(),
            zoomSize.width(),
            rel=True,
        )
        self.setZoom()
        self.gui.updateall()
        if self.gui.cfg is None:
            self.gui.dumpConfig()

    def moveImage(self, event):
        dx = (event.x() - self.lastMousePos.x()) * (
            self.arectZoom.oriented().width() / self.rectImage.width()
        )
        dy = (event.y() - self.lastMousePos.y()) * (
            self.arectZoom.oriented().height() / self.rectImage.height()
        )
        self.lastMousePos = event.pos()
        self.rectZoom = param.Rect(
            self.rectZoom.oriented().x() - dx,
            self.rectZoom.oriented().y() - dy,
            self.rectZoom.oriented().width(),
            self.rectZoom.oriented().height(),
            rel=True,
        )
        self.setZoom()
        self.gui.updateall()
        if self.gui.cfg is None:
            self.gui.dumpConfig()

    def zoomByFactor(self, fFactor):
        zoomSize = self.arectZoom.oriented().size() / fFactor
        zoomCenterShift = QPointF(zoomSize.width(), zoomSize.height()) * 0.5
        tl = self.arectZoom.oriented().center() - zoomCenterShift
        self.rectZoom = param.Rect(
            tl.x(), tl.y(), zoomSize.width(), zoomSize.height(), rel=True
        )
        self.setZoom()
        self.gui.updateall()
        if self.gui.cfg is None:
            self.gui.dumpConfig()

    def zoomToRoi(self):
        self.rectZoom = param.Rect(
            self.rectRoi.x, self.rectRoi.y, self.rectRoi.w, self.rectRoi.h
        )
        self.setZoom()
        self.gui.updateall()
        if self.gui.cfg is None:
            self.gui.dumpConfig()

    # This must be called after setting rectZoom so that arectZoom is correctly set!
    #
    # rectZoom is our *desired* zoom rectangle.
    # This routine "fixes" it to make it actually fit in the available space.
    def setZoom(self):
        if self.rectZoom.oriented().width() <= 0:
            self.rectZoom.setWidth(1)
        if self.rectZoom.oriented().height() <= 0:
            self.rectZoom.setHeight(1)

        self.arectZoom = param.Rect(
            self.rectZoom.x, self.rectZoom.y, self.rectZoom.w, self.rectZoom.h
        )

        h = self.height()
        w = self.width()

        fWidthRatio = w / self.arectZoom.oriented().width()
        fHeightRatio = h / self.arectZoom.oriented().height()

        if abs((fWidthRatio - fHeightRatio) / fWidthRatio) < 0.01:
            param.zoom = w / self.arectZoom.oriented().width()
            return

        if fWidthRatio > fHeightRatio:
            fNewZoomWidth = (
                self.arectZoom.oriented().width() * fWidthRatio / fHeightRatio
            )
            fNewZoomX = (
                self.arectZoom.oriented().x()
                + (self.arectZoom.oriented().width() - fNewZoomWidth) * 0.5
            )
            self.arectZoom.setLeft(fNewZoomX)
            self.arectZoom.setWidth(fNewZoomWidth)
        else:
            fNewZoomHeight = (
                self.arectZoom.oriented().height() * fHeightRatio / fWidthRatio
            )
            fNewZoomY = (
                self.arectZoom.oriented().y()
                + (self.arectZoom.oriented().height() - fNewZoomHeight) * 0.5
            )
            self.arectZoom.setTop(fNewZoomY)
            self.arectZoom.setHeight(fNewZoomHeight)
        param.zoom = w / self.arectZoom.oriented().width()

    def zoomReset(self):
        self.zoomByFactor(self.rectZoom.oriented().width() / self.width())

    def roiReset(self):
        self.rectRoi = param.Rect(0, 0, param.width(), param.height())
        self.gui.updateRoiText()
        self.update()
        if self.gui.cfg is None:
            self.gui.dumpConfig()

    def roiSet(self, x, y, w, h, rel=False):
        self.rectRoi = param.Rect(x, y, w, h, rel=rel)
        self.gui.updateRoiText()
        self.update()
        if self.gui.cfg is None:
            self.gui.dumpConfig()
