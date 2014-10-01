# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'advanced.ui'
#
# Created: Wed Jan 15 13:49:59 2014
#      by: PyQt4 UI code generator 4.9.1
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName(_fromUtf8("Dialog"))
        Dialog.resize(380, 171)
        self.gridLayout = QtGui.QGridLayout(Dialog)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.label = QtGui.QLabel(Dialog)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout.addWidget(self.label, 0, 0, 1, 2)
        self.viewWidth = QtGui.QLineEdit(Dialog)
        self.viewWidth.setObjectName(_fromUtf8("viewWidth"))
        self.gridLayout.addWidget(self.viewWidth, 0, 2, 1, 1)
        self.label_3 = QtGui.QLabel(Dialog)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 2)
        self.viewHeight = QtGui.QLineEdit(Dialog)
        self.viewHeight.setObjectName(_fromUtf8("viewHeight"))
        self.gridLayout.addWidget(self.viewHeight, 1, 2, 1, 1)
        self.label_2 = QtGui.QLabel(Dialog)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout.addWidget(self.label_2, 2, 0, 1, 2)
        self.projSize = QtGui.QLineEdit(Dialog)
        self.projSize.setObjectName(_fromUtf8("projSize"))
        self.gridLayout.addWidget(self.projSize, 2, 2, 1, 1)
        self.configCheckBox = QtGui.QCheckBox(Dialog)
        self.configCheckBox.setObjectName(_fromUtf8("configCheckBox"))
        self.gridLayout.addWidget(self.configCheckBox, 3, 0, 1, 3)
        self.showevr = QtGui.QPushButton(Dialog)
        self.showevr.setMinimumSize(QtCore.QSize(0, 33))
        self.showevr.setObjectName(_fromUtf8("showevr"))
        self.gridLayout.addWidget(self.showevr, 4, 0, 1, 1)
        self.buttonBox = QtGui.QDialogButtonBox(Dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Apply|QtGui.QDialogButtonBox.Close|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(False)
        self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
        self.gridLayout.addWidget(self.buttonBox, 4, 1, 1, 2)

        self.retranslateUi(Dialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("accepted()")), Dialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("rejected()")), Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtGui.QApplication.translate("Dialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("Dialog", "Viewing Area Width (> 400 pixels)", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("Dialog", "Viewing Area Height (> 400 pixels)", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("Dialog", "Projection Size (> 250 pixels)", None, QtGui.QApplication.UnicodeUTF8))
        self.configCheckBox.setText(QtGui.QApplication.translate("Dialog", "Display Camera Configuration on Main Screen", None, QtGui.QApplication.UnicodeUTF8))
        self.showevr.setText(QtGui.QApplication.translate("Dialog", "Open Evr", None, QtGui.QApplication.UnicodeUTF8))

