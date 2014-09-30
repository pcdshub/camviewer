# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'droplet.ui'
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
        Dialog.resize(270, 212)
        self.verticalLayout = QtGui.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.gigeBox = QtGui.QGroupBox(Dialog)
        self.gigeBox.setObjectName(_fromUtf8("gigeBox"))
        self.gridLayout = QtGui.QGridLayout(self.gigeBox)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.gainlabel = QtGui.QLabel(self.gigeBox)
        self.gainlabel.setObjectName(_fromUtf8("gainlabel"))
        self.gridLayout.addWidget(self.gainlabel, 0, 0, 1, 1)
        self.param1_0 = QtGui.QLineEdit(self.gigeBox)
        self.param1_0.setObjectName(_fromUtf8("param1_0"))
        self.gridLayout.addWidget(self.param1_0, 0, 1, 1, 1)
        self.label_6 = QtGui.QLabel(self.gigeBox)
        self.label_6.setObjectName(_fromUtf8("label_6"))
        self.gridLayout.addWidget(self.label_6, 1, 0, 1, 1)
        self.param1_1 = QtGui.QLineEdit(self.gigeBox)
        self.param1_1.setObjectName(_fromUtf8("param1_1"))
        self.gridLayout.addWidget(self.param1_1, 1, 1, 1, 1)
        self.gainlabel_2 = QtGui.QLabel(self.gigeBox)
        self.gainlabel_2.setObjectName(_fromUtf8("gainlabel_2"))
        self.gridLayout.addWidget(self.gainlabel_2, 2, 0, 1, 1)
        self.param2_0 = QtGui.QLineEdit(self.gigeBox)
        self.param2_0.setObjectName(_fromUtf8("param2_0"))
        self.gridLayout.addWidget(self.param2_0, 2, 1, 1, 1)
        self.label_5 = QtGui.QLabel(self.gigeBox)
        self.label_5.setObjectName(_fromUtf8("label_5"))
        self.gridLayout.addWidget(self.label_5, 3, 0, 1, 1)
        self.param2_1 = QtGui.QLineEdit(self.gigeBox)
        self.param2_1.setObjectName(_fromUtf8("param2_1"))
        self.gridLayout.addWidget(self.param2_1, 3, 1, 1, 1)
        self.verticalLayout.addWidget(self.gigeBox)
        self.buttonBox = QtGui.QDialogButtonBox(Dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Apply|QtGui.QDialogButtonBox.Close|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(Dialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("accepted()")), Dialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("rejected()")), Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(_translate("Dialog", "Dialog", None))
        self.gigeBox.setTitle(_translate("Dialog", "Droplet Finder Parameters", None))
        self.gainlabel.setText(_translate("Dialog", "Gradient Threshold 1", None))
        self.label_6.setText(_translate("Dialog", "Projection Fraction 1", None))
        self.gainlabel_2.setText(_translate("Dialog", "Gradient Threshold 2", None))
        self.label_5.setText(_translate("Dialog", "Projection Fraction 2", None))

