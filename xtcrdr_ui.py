# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'xtcrdr.ui'
#
# Created: Mon Sep 15 15:38:32 2014
#      by: PyQt4 UI code generator 4.10.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName(_fromUtf8("Dialog"))
        Dialog.resize(424, 192)
        self.gridLayout = QtGui.QGridLayout(Dialog)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.xtcfile = QtGui.QComboBox(Dialog)
        self.xtcfile.setObjectName(_fromUtf8("xtcfile"))
        self.gridLayout.addWidget(self.xtcfile, 1, 2, 1, 1)
        self.label_3 = QtGui.QLabel(Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_3.sizePolicy().hasHeightForWidth())
        self.label_3.setSizePolicy(sizePolicy)
        self.label_3.setMinimumSize(QtCore.QSize(26, 0))
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.gridLayout.addWidget(self.label_3, 3, 1, 1, 1)
        self.location = QtGui.QLabel(Dialog)
        self.location.setText(_fromUtf8(""))
        self.location.setObjectName(_fromUtf8("location"))
        self.gridLayout.addWidget(self.location, 3, 2, 1, 1)
        self.skipButton = QtGui.QPushButton(Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.skipButton.sizePolicy().hasHeightForWidth())
        self.skipButton.setSizePolicy(sizePolicy)
        self.skipButton.setObjectName(_fromUtf8("skipButton"))
        self.gridLayout.addWidget(self.skipButton, 5, 2, 1, 1)
        self.skipCount = QtGui.QLineEdit(Dialog)
        self.skipCount.setObjectName(_fromUtf8("skipCount"))
        self.gridLayout.addWidget(self.skipCount, 7, 2, 1, 1)
        self.label_2 = QtGui.QLabel(Dialog)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout.addWidget(self.label_2, 7, 1, 1, 1)
        self.openButton = QtGui.QPushButton(Dialog)
        self.openButton.setObjectName(_fromUtf8("openButton"))
        self.gridLayout.addWidget(self.openButton, 1, 1, 1, 1)
        self.nextButton = QtGui.QPushButton(Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.nextButton.sizePolicy().hasHeightForWidth())
        self.nextButton.setSizePolicy(sizePolicy)
        self.nextButton.setObjectName(_fromUtf8("nextButton"))
        self.gridLayout.addWidget(self.nextButton, 5, 1, 1, 1)
        self.prevButton = QtGui.QPushButton(Dialog)
        self.prevButton.setObjectName(_fromUtf8("prevButton"))
        self.gridLayout.addWidget(self.prevButton, 4, 1, 1, 1)
        self.backButton = QtGui.QPushButton(Dialog)
        self.backButton.setObjectName(_fromUtf8("backButton"))
        self.gridLayout.addWidget(self.backButton, 4, 2, 1, 1)
        self.dirselect = QtGui.QPushButton(Dialog)
        self.dirselect.setObjectName(_fromUtf8("dirselect"))
        self.gridLayout.addWidget(self.dirselect, 0, 1, 1, 1)
        self.currentdir = QtGui.QLabel(Dialog)
        self.currentdir.setText(_fromUtf8(""))
        self.currentdir.setObjectName(_fromUtf8("currentdir"))
        self.gridLayout.addWidget(self.currentdir, 0, 2, 1, 1)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(_translate("Dialog", "Dialog", None))
        self.label_3.setText(_translate("Dialog", "File Offset:", None))
        self.skipButton.setText(_translate("Dialog", "Skip", None))
        self.skipCount.setText(_translate("Dialog", "10", None))
        self.label_2.setText(_translate("Dialog", "Skip Count:", None))
        self.openButton.setText(_translate("Dialog", "Open XTC File", None))
        self.nextButton.setText(_translate("Dialog", "Next", None))
        self.prevButton.setText(_translate("Dialog", "Previous", None))
        self.backButton.setText(_translate("Dialog", "Skip Back", None))
        self.dirselect.setText(_translate("Dialog", "Select Directory", None))

