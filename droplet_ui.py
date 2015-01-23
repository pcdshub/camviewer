# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'droplet.ui'
#
# Created: Fri Jan 23 14:31:32 2015
#      by: PyQt4 UI code generator 4.7.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(270, 212)
        self.verticalLayout = QtGui.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gigeBox = QtGui.QGroupBox(Dialog)
        self.gigeBox.setObjectName("gigeBox")
        self.gridLayout = QtGui.QGridLayout(self.gigeBox)
        self.gridLayout.setObjectName("gridLayout")
        self.gainlabel = QtGui.QLabel(self.gigeBox)
        self.gainlabel.setObjectName("gainlabel")
        self.gridLayout.addWidget(self.gainlabel, 0, 0, 1, 1)
        self.param1_0 = QtGui.QLineEdit(self.gigeBox)
        self.param1_0.setObjectName("param1_0")
        self.gridLayout.addWidget(self.param1_0, 0, 1, 1, 1)
        self.label_6 = QtGui.QLabel(self.gigeBox)
        self.label_6.setObjectName("label_6")
        self.gridLayout.addWidget(self.label_6, 1, 0, 1, 1)
        self.param1_1 = QtGui.QLineEdit(self.gigeBox)
        self.param1_1.setObjectName("param1_1")
        self.gridLayout.addWidget(self.param1_1, 1, 1, 1, 1)
        self.gainlabel_2 = QtGui.QLabel(self.gigeBox)
        self.gainlabel_2.setObjectName("gainlabel_2")
        self.gridLayout.addWidget(self.gainlabel_2, 2, 0, 1, 1)
        self.param2_0 = QtGui.QLineEdit(self.gigeBox)
        self.param2_0.setObjectName("param2_0")
        self.gridLayout.addWidget(self.param2_0, 2, 1, 1, 1)
        self.label_5 = QtGui.QLabel(self.gigeBox)
        self.label_5.setObjectName("label_5")
        self.gridLayout.addWidget(self.label_5, 3, 0, 1, 1)
        self.param2_1 = QtGui.QLineEdit(self.gigeBox)
        self.param2_1.setObjectName("param2_1")
        self.gridLayout.addWidget(self.param2_1, 3, 1, 1, 1)
        self.verticalLayout.addWidget(self.gigeBox)
        self.buttonBox = QtGui.QDialogButtonBox(Dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Apply|QtGui.QDialogButtonBox.Close|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(Dialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), Dialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtGui.QApplication.translate("Dialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.gigeBox.setTitle(QtGui.QApplication.translate("Dialog", "Droplet Finder Parameters", None, QtGui.QApplication.UnicodeUTF8))
        self.gainlabel.setText(QtGui.QApplication.translate("Dialog", "Gradient Threshold 1", None, QtGui.QApplication.UnicodeUTF8))
        self.label_6.setText(QtGui.QApplication.translate("Dialog", "Projection Fraction 1", None, QtGui.QApplication.UnicodeUTF8))
        self.gainlabel_2.setText(QtGui.QApplication.translate("Dialog", "Gradient Threshold 2", None, QtGui.QApplication.UnicodeUTF8))
        self.label_5.setText(QtGui.QApplication.translate("Dialog", "Projection Fraction 2", None, QtGui.QApplication.UnicodeUTF8))

