# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'xtcrdr.ui'
#
# Created: Wed Jul 24 13:19:32 2013
#      by: PyQt4 UI code generator 4.7.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(424, 192)
        self.gridLayout = QtGui.QGridLayout(Dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.xtcfile = QtGui.QComboBox(Dialog)
        self.xtcfile.setObjectName("xtcfile")
        self.gridLayout.addWidget(self.xtcfile, 1, 2, 1, 1)
        self.label_3 = QtGui.QLabel(Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_3.sizePolicy().hasHeightForWidth())
        self.label_3.setSizePolicy(sizePolicy)
        self.label_3.setMinimumSize(QtCore.QSize(26, 0))
        self.label_3.setObjectName("label_3")
        self.gridLayout.addWidget(self.label_3, 3, 1, 1, 1)
        self.location = QtGui.QLabel(Dialog)
        self.location.setText("")
        self.location.setObjectName("location")
        self.gridLayout.addWidget(self.location, 3, 2, 1, 1)
        self.skipButton = QtGui.QPushButton(Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.skipButton.sizePolicy().hasHeightForWidth())
        self.skipButton.setSizePolicy(sizePolicy)
        self.skipButton.setObjectName("skipButton")
        self.gridLayout.addWidget(self.skipButton, 5, 2, 1, 1)
        self.skipCount = QtGui.QLineEdit(Dialog)
        self.skipCount.setObjectName("skipCount")
        self.gridLayout.addWidget(self.skipCount, 7, 2, 1, 1)
        self.label_2 = QtGui.QLabel(Dialog)
        self.label_2.setObjectName("label_2")
        self.gridLayout.addWidget(self.label_2, 7, 1, 1, 1)
        self.openButton = QtGui.QPushButton(Dialog)
        self.openButton.setObjectName("openButton")
        self.gridLayout.addWidget(self.openButton, 1, 1, 1, 1)
        self.nextButton = QtGui.QPushButton(Dialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.nextButton.sizePolicy().hasHeightForWidth())
        self.nextButton.setSizePolicy(sizePolicy)
        self.nextButton.setObjectName("nextButton")
        self.gridLayout.addWidget(self.nextButton, 5, 1, 1, 1)
        self.prevButton = QtGui.QPushButton(Dialog)
        self.prevButton.setObjectName("prevButton")
        self.gridLayout.addWidget(self.prevButton, 4, 1, 1, 1)
        self.backButton = QtGui.QPushButton(Dialog)
        self.backButton.setObjectName("backButton")
        self.gridLayout.addWidget(self.backButton, 4, 2, 1, 1)
        self.dirselect = QtGui.QPushButton(Dialog)
        self.dirselect.setObjectName("dirselect")
        self.gridLayout.addWidget(self.dirselect, 0, 1, 1, 1)
        self.currentdir = QtGui.QLabel(Dialog)
        self.currentdir.setText("")
        self.currentdir.setObjectName("currentdir")
        self.gridLayout.addWidget(self.currentdir, 0, 2, 1, 1)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtGui.QApplication.translate("Dialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("Dialog", "File Offset:", None, QtGui.QApplication.UnicodeUTF8))
        self.skipButton.setText(QtGui.QApplication.translate("Dialog", "Skip", None, QtGui.QApplication.UnicodeUTF8))
        self.skipCount.setText(QtGui.QApplication.translate("Dialog", "10", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("Dialog", "Skip Count:", None, QtGui.QApplication.UnicodeUTF8))
        self.openButton.setText(QtGui.QApplication.translate("Dialog", "Open XTC File", None, QtGui.QApplication.UnicodeUTF8))
        self.nextButton.setText(QtGui.QApplication.translate("Dialog", "Next", None, QtGui.QApplication.UnicodeUTF8))
        self.prevButton.setText(QtGui.QApplication.translate("Dialog", "Previous", None, QtGui.QApplication.UnicodeUTF8))
        self.backButton.setText(QtGui.QApplication.translate("Dialog", "Skip Back", None, QtGui.QApplication.UnicodeUTF8))
        self.dirselect.setText(QtGui.QApplication.translate("Dialog", "Select Directory", None, QtGui.QApplication.UnicodeUTF8))

