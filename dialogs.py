import os
import advanced_ui
import markers_ui
import specific_ui
import timeout_ui
from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QWidget,
    QDialog,
    QApplication,
    QGridLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QMessageBox,
    QCheckBox,
)
from PyQt5.QtGui import QPalette
from PyQt5.QtCore import QTime, QTimer, Qt


class advdialog(QDialog):
    def __init__(self, gui, parent=None):
        QWidget.__init__(self, parent)
        self.gui = gui
        self.ui = advanced_ui.Ui_Dialog()
        self.ui.setupUi(self)

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_Enter or k == Qt.Key_Return:
            return
        QDialog.keyPressEvent(self, event)

    def closeEvent(self, event):
        self.gui.ui.showexpert.setChecked(False)
        QDialog.closeEvent(self, event)


class markerdialog(QDialog):
    def __init__(self, gui, parent=None):
        QWidget.__init__(self, parent)
        self.gui = gui
        self.ui = markers_ui.Ui_Dialog()
        self.ui.setupUi(self)


class specificdialog(QDialog):
    def __init__(self, gui, parent=None):
        QWidget.__init__(self, parent)
        self.gui = gui
        self.ui = specific_ui.Ui_Dialog()
        self.ui.setupUi(self)

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_Enter or k == Qt.Key_Return:
            return
        QDialog.keyPressEvent(self, event)

    def closeEvent(self, event):
        QDialog.closeEvent(self, event)


class forcedialog(QDialog):
    def __init__(self, dir, gui, parent=None):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Disconnect")

        self.dir = dir
        self.gui = gui

        self.gridLayout = QGridLayout(self)

        self.label = QLabel(self)
        self.label.setText("Your ID:")
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.killID = QLineEdit(self)
        self.killID.setText(self.gui.lastforceid)
        self.gridLayout.addWidget(self.killID, 0, 1, 1, 2)

        self.hostheader = QLabel(self)
        self.hostheader.setTextFormat(QtCore.Qt.RichText)
        self.hostheader.setText("<b>Host</b>")
        self.gridLayout.addWidget(self.hostheader, 1, 0, 1, 1)

        self.pidheader = QLabel(self)
        self.pidheader.setTextFormat(QtCore.Qt.RichText)
        self.pidheader.setText("<b>PID</b>")
        self.gridLayout.addWidget(self.pidheader, 1, 1, 1, 1)

        self.ttyheader = QLabel(self)
        self.ttyheader.setTextFormat(QtCore.Qt.RichText)
        self.ttyheader.setText("<b>TTY</b>")
        self.gridLayout.addWidget(self.ttyheader, 1, 2, 1, 1)

        self.checks = []

        dirlist = os.listdir(dir)
        dirlist.sort()
        i = 2
        for file in dirlist:
            try:
                ll = file.split(":")
                if file == self.gui.description:
                    plt = QPalette()
                    plt.setColor(QPalette.WindowText, Qt.red)
                    check = QCheckBox(self)
                    check.setPalette(plt)
                else:
                    check = QCheckBox(self)
                check.setText(ll[0])
                check.forcefile = file
                self.gridLayout.addWidget(check, i, 0, 1, 1)

                # Coloring the labels is easy.
                if file == self.gui.description:
                    pre = '<font color="red">'
                    post = "</font>"
                else:
                    pre = ""
                    post = ""

                pidlabel = QLabel(self)
                pidlabel.setTextFormat(QtCore.Qt.RichText)
                pidlabel.setText(pre + ll[1] + post)
                self.gridLayout.addWidget(pidlabel, i, 1, 1, 1)

                with open(dir + file) as f:
                    lines = f.readlines()
                ttylabel = QLabel(self)
                ttylabel.setTextFormat(QtCore.Qt.RichText)
                ttylabel.setText(pre + lines[0].strip() + post)
                self.gridLayout.addWidget(ttylabel, i, 2, 1, 1)

                i = i + 1
                self.checks.append(check)
            except Exception:
                pass

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok | QDialogButtonBox.YesToAll
        )
        self.gridLayout.addWidget(self.buttonBox, i, 0, 1, 3)

        self.buttonBox.clicked.connect(self.onClick)
        self.show()

    def onClick(self, button):
        stb = self.buttonBox.standardButton(button)
        if stb == QDialogButtonBox.Ok or stb == QDialogButtonBox.YesToAll:
            all = stb == QDialogButtonBox.YesToAll
            id = str(self.killID.text()).strip()
            if id == "":
                QMessageBox.critical(
                    None, "Error", "No Identification!", QMessageBox.Ok, QMessageBox.Ok
                )
                return
            self.gui.lastforceid = id
            id = id + "\n"
            for c in self.checks:
                if all or c.isChecked():
                    try:
                        f = open(self.dir + c.forcefile, "a")
                        f.write(id)
                        f.close()
                    except Exception:
                        pass
        self.close()

    def closeEvent(self, event):
        self.gui.haveforce = False
        self.deleteLater()
        QDialog.closeEvent(self, event)
