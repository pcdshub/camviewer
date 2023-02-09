from PyQt5 import QtCore
from PyQt5.QtGui import *
from PyQt5.QtCore import QTimer, Qt, QPoint, QPointF, QSize, QRectF, QObject
import numpy as np

ORIENT0 = 0
ORIENT0F = 1
ORIENT90 = 2
ORIENT90F = 3
ORIENT180 = 4
ORIENT180F = 5
ORIENT270 = 6
ORIENT270F = 7

orientation = 0

# These are all *image* variables.
x = 640
y = 480
ypad = (x - y) / 2
xpad = 0
maxd = x

# Convience indexes for plotting.
x_fwd = np.arange(x)
x_rev = np.arange(x - 1, -1, -1)
y_fwd = np.arange(y)
y_rev = np.arange(y - 1, -1, -1)

# These aren't.
projsize = 300
zoom = 1.0


def setImageSize(newx, newy):
    global x, y, xpad, ypad, maxd, x_fwd, x_rev, y_fwd, y_rev
    x = int(newx)
    y = int(newy)
    x_fwd = np.arange(x)
    x_rev = np.arange(x - 1, -1, -1)
    y_fwd = np.arange(y)
    y_rev = np.arange(y - 1, -1, -1)
    if newx >= newy:
        ypad = (newx - newy) / 2
        xpad = 0
        maxd = newx
    else:
        ypad = 0
        xpad = (newy - newx) / 2
        maxd = newy


# Get the desired QImage size (oriented!)
def getSize():
    global x, y, orientation
    if orientation & 2 == 2:
        return QSize(y, x)
    else:
        return QSize(x, y)


def getSizeTuple():
    global x, y, orientation
    if orientation & 2 == 2:
        return (y, x)
    else:
        return (x, y)


def isRotated():
    global orientation
    return orientation & 2 == 2


def width():
    global x, y, orientation
    if orientation & 2 == 2:
        return y
    else:
        return x


def height():
    global x, y, orientation
    if orientation & 2 == 2:
        return x
    else:
        return y


def xpad_oriented():
    global xpad, ypad, orientation
    if orientation & 2 == 2:
        return ypad
    else:
        return xpad


def ypad_oriented():
    global x, y, orientation
    if orientation & 2 == 2:
        return xpad
    else:
        return ypad


class Point(object):
    # Create with absolute image coordinates by default.
    #
    # x, y are absolute image coordinates of the point, abs() is the absolute image QPointF, and
    # oriented() is the correctly oriented QPointF.
    def __init__(self, xx, yy, rel=False):
        self._abs = None
        self._rel = None
        self.orientation = -1
        if rel:
            self.setRel(xx, yy)
        else:
            self.setAbs(xx, yy)

    def calcAbs(self, xx, yy):
        global x, y, orientation
        if orientation == ORIENT0:
            self._abs = QPointF(xx, yy)
        elif orientation == ORIENT0F:
            self._abs = QPointF(x - 1 - xx, yy)
        elif orientation == ORIENT90:
            self._abs = QPointF(x - 1 - yy, xx)
        elif orientation == ORIENT90F:
            self._abs = QPointF(yy, xx)
        elif orientation == ORIENT180:
            self._abs = QPointF(x - 1 - xx, y - 1 - yy)
        elif orientation == ORIENT180F:
            self._abs = QPointF(xx, y - 1 - yy)
        elif orientation == ORIENT270:
            self._abs = QPointF(yy, y - 1 - xx)
        elif orientation == ORIENT270F:
            self._abs = QPointF(x - 1 - yy, y - 1 - xx)
        self.x = self._abs.x()
        self.y = self._abs.y()

    def setRel(self, xx, yy):
        global orientation
        self._rel = QPointF(xx, yy)
        self.orientation = orientation
        self.calcAbs(xx, yy)

    def setAbs(self, xx, yy):
        self.x = xx
        self.y = yy
        self._abs = QPointF(xx, yy)
        self._rel = None

    def abs(self):
        return self._abs

    def oriented(self):
        global orientation, x, y
        if self.orientation == orientation and self._rel is not None:
            return self._rel
        self.orientation = orientation
        if orientation == ORIENT0:
            self._rel = QPointF(self.x, self.y)
        elif orientation == ORIENT0F:
            self._rel = QPointF(x - 1 - self.x, self.y)
        elif orientation == ORIENT90:
            self._rel = QPointF(self.y, x - 1 - self.x)
        elif orientation == ORIENT90F:
            self._rel = QPointF(self.y, self.x)
        elif orientation == ORIENT180:
            self._rel = QPointF(x - 1 - self.x, y - 1 - self.y)
        elif orientation == ORIENT180F:
            self._rel = QPointF(self.x, y - 1 - self.y)
        elif orientation == ORIENT270:
            self._rel = QPointF(y - 1 - self.y, self.x)
        elif orientation == ORIENT270F:
            self._rel = QPointF(y - 1 - self.y, x - 1 - self.x)
        return self._rel

    def pr(self, text=""):
        pt = self.oriented()
        print("%sabs(%g,%g) rel(%g,%g)" % (text, self.x, self.y, pt.x(), pt.y()))


class Rect(object):
    # Create with absolute image coordinates by default
    def __init__(self, xx, yy, ww, hh, rel=False):
        self._abs = None
        self._rel = None
        self.orientation = -1
        if rel:
            self.setRel(xx, yy, ww, hh)
        else:
            self.setAbs(xx, yy, ww, hh)

    def setRel(self, xx, yy, ww, hh):
        global orientation
        if ww < 0:
            xx = xx + ww + 1
            ww = -ww
        if hh < 0:
            yy = yy + hh + 1
            hh = hh
        self._rel = QRectF(xx, yy, ww, hh)
        self.orientation = orientation
        self.calcAbs(xx, yy, ww, hh)

    def setAbs(self, xx, yy, ww, hh):
        if ww >= 0:
            self.x = xx
            self.w = ww
        else:
            self.x = xx + ww + 1
            self.w = -ww
        if hh >= 0:
            self.y = yy
            self.h = hh
        else:
            self.y = yy + hh + 1
            self.h = hh
        self._abs = QRectF(self.x, self.y, self.w, self.h)
        self._rel = None

    def calcAbs(self, xx, yy, ww, hh):
        global orientation
        if orientation == ORIENT0:
            self._abs = QRectF(xx, yy, ww, hh)
        elif orientation == ORIENT0F:
            self._abs = QRectF(x - xx - ww, yy, ww, hh)
        elif orientation == ORIENT90:
            self._abs = QRectF(x - yy - hh, xx, hh, ww)
        elif orientation == ORIENT90F:
            self._abs = QRectF(yy, xx, hh, ww)
        elif orientation == ORIENT180:
            self._abs = QRectF(x - xx - ww, y - yy - hh, ww, hh)
        elif orientation == ORIENT180F:
            self._abs = QRectF(xx, y - yy - hh, ww, hh)
        elif orientation == ORIENT270:
            self._abs = QRectF(yy, y - xx - ww, hh, ww)
        elif orientation == ORIENT270F:
            self._abs = QRectF(x - yy - hh, y - xx - ww, hh, ww)
        self.x = self._abs.x()
        self.y = self._abs.y()
        self.w = self._abs.width()
        self.h = self._abs.height()

    def abs(self):
        return self._abs

    def oriented(self):
        global orientation, x, y
        if self.orientation == orientation and self._rel is not None:
            return self._rel
        self.orientation = orientation
        if orientation == ORIENT0:
            self._rel = QRectF(self.x, self.y, self.w, self.h)
        elif orientation == ORIENT0F:
            self._rel = QRectF(x - self.x - self.w, self.y, self.w, self.h)
        elif orientation == ORIENT90:
            self._rel = QRectF(self.y, x - self.x - self.w, self.h, self.w)
        elif orientation == ORIENT90F:
            self._rel = QRectF(self.y, self.x, self.h, self.w)
        elif orientation == ORIENT180:
            self._rel = QRectF(x - self.x - self.w, y - self.y - self.h, self.w, self.h)
        elif orientation == ORIENT180F:
            self._rel = QRectF(self.x, y - self.y - self.h, self.w, self.h)
        elif orientation == ORIENT270:
            self._rel = QRectF(y - self.y - self.h, self.x, self.h, self.w)
        elif orientation == ORIENT270F:
            self._rel = QRectF(y - self.y - self.h, x - self.x - self.w, self.h, self.w)
        return self._rel

    # These all set in *oriented* coordinates!
    def setLeft(self, xx):
        pt = self.oriented()
        self.setRel(xx, pt.y(), pt.width(), pt.height())

    def setRight(self, xx):
        pt = self.oriented()
        self.setRel(pt.x(), pt.y(), xx - pt.x() + 1, pt.height())

    def setTop(self, yy):
        pt = self.oriented()
        self.setRel(pt.x(), yy, pt.width(), pt.height())

    def setBottom(self, yy):
        pt = self.oriented()
        self.setRel(pt.x(), pt.y(), pt.width(), yy - pt.y() + 1)

    def setWidth(self, ww):
        pt = self.oriented()
        self.setRel(pt.x(), pt.y(), ww, pt.height())

    def setHeight(self, hh):
        pt = self.oriented()
        self.setRel(pt.x(), pt.y(), pt.width(), hh)

    def pr(self, text=""):
        pt = self.oriented()
        print(
            "%sabs(%g,%g,%g,%g) rel(%g,%g,%g,%g)"
            % (
                text,
                self.x,
                self.y,
                self.w,
                self.h,
                pt.x(),
                pt.y(),
                pt.width(),
                pt.height(),
            )
        )
