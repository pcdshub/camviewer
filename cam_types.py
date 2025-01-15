"""
Brief model-specific screens to display below the main controls.

This is to be used when there are important model-specific controls
that are vital to the operation of the camera.

These are limited to simple form layouts that will be included
inside of a stock QGroupBox in the main screen.
"""
from __future__ import annotations

from functools import partial
from threading import Lock

from psp.Pv import Pv
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QFormLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QSpinBox,
    QMessageBox,
)


STOP_TEXT = "Stopped"
START_TEXT = "Started"


class CamTypeScreenGenerator(QObject):
    """
    This class creates a cam-specific QFormLayout to include in the main screen.

    The layout will include basic start/stop camera controls for all models
    and additional special controls that have been requested for specific models.
    """

    # GUI needs this to update the QGroupBox with the full model name
    final_name = pyqtSignal(str)
    manuf_ready = pyqtSignal()
    model_ready = pyqtSignal()

    def __init__(self, base_pv: str, form: QFormLayout, parent: QObject | None = None):
        super().__init__(parent=parent)
        self.form = form
        self.base_pv = base_pv
        self.manufacturer = ""
        self.model = ""
        self.full_name = ""
        self.pvs_to_clean_up: list[Pv] = []
        self.sigs_to_clean_up: list[pyqtSignal] = [
            self.final_name,
            self.manuf_ready,
            self.model_ready,
        ]
        self.finish_ran = False
        self.finish_lock = Lock()

        # Put in the form elements that always should be there
        self.acq_label = QLabel(STOP_TEXT)
        self.acq_label.setMinimumWidth(80)
        start_button = QPushButton("Start")
        stop_button = QPushButton("Stop")
        acq_layout = QHBoxLayout()
        acq_layout.addWidget(start_button)
        acq_layout.addWidget(stop_button)
        self.form.addRow(self.acq_label, acq_layout)

        # If we don't have PVs, stop here.
        if not base_pv:
            self.full_name = "Disconnected"
            start_button.setDisabled(True)
            stop_button.setDisabled(True)
            return

        # If we have PVs, we can make the widgets work properly
        self.manuf_ready.connect(self.finish_form)
        self.model_ready.connect(self.finish_form)
        self.acq_status_pv = Pv(
            f"{base_pv}:Acquire_RBV",
            monitor=self.new_acq_value,
            initialize=True,
        )
        self.pvs_to_clean_up.append(self.acq_status_pv)
        self.acq_set_pv = Pv(f"{base_pv}:Acquire")
        self.acq_set_pv.connect()
        self.pvs_to_clean_up.append(self.acq_set_pv)
        start_button.clicked.connect(partial(self.set_acq_value, 1))
        stop_button.clicked.connect(partial(self.set_acq_value, 0))

        # Create a callback to finish the form later, given the model
        self.manuf_pv = Pv(
            f"{base_pv}:Manufacturer_RBV",
            monitor=self.manuf_monitor,
            initialize=True,
        )
        self.pvs_to_clean_up.append(self.manuf_pv)
        self.model_pv = Pv(
            f"{base_pv}:Model_RBV",
            monitor=self.model_monitor,
            initialize=True,
        )
        self.pvs_to_clean_up.append(self.model_pv)

    def get_layout(self) -> QFormLayout:
        return self.form

    def manuf_monitor(self, error: Exception | None) -> None:
        if error is None:
            self.manufacturer = self.manuf_pv.value
            self.manuf_ready.emit()

    def model_monitor(self, error: Exception | None) -> None:
        if error is None:
            self.model = self.model_pv.value
            self.model_ready.emit()

    def finish_form(self) -> QFormLayout:
        if not self.manufacturer or not self.model:
            return
        with self.finish_lock:
            if self.finish_ran:
                return
            self.finish_ran = True
        self.manuf_pv.disconnect()
        self.model_pv.disconnect()
        self.pvs_to_clean_up.remove(self.manuf_pv)
        self.pvs_to_clean_up.remove(self.model_pv)
        self.full_name = f"{self.manufacturer} {self.model}"
        self.final_name.emit(self.full_name)
        try:
            finisher = form_finishers[self.full_name]
        except KeyError:
            print(f"Using basic controls for {self.full_name}")
            return
        else:
            print(f"Loading special screen for {self.full_name}")
        try:
            finisher_pvs, finisher_sigs = finisher(self.form, self.base_pv)
        except Exception as exc:
            QMessageBox.warning(
                self.parent(),
                "Internal error",
                f"Error loading model-specific widgets for {self.full_name}: {exc}",
            )
        self.pvs_to_clean_up.extend(finisher_pvs)
        self.sigs_to_clean_up.extend(finisher_sigs)

    def new_acq_value(self, error: Exception | None) -> None:
        if error is None:
            if self.acq_status_pv.value:
                text = START_TEXT
            else:
                text = STOP_TEXT
            self.acq_label.setText(text)

    def set_acq_value(self, value: int) -> None:
        try:
            self.acq_set_pv.put(value)
        except Exception:
            ...

    def cleanup(self) -> None:
        for pv in self.pvs_to_clean_up:
            pv.disconnect()
        self.pvs_to_clean_up = []
        for sig in self.sigs_to_clean_up:
            try:
                sig.disconnect()
            except TypeError:
                ...
        self.sigs_to_clean_up = []
        for _ in range(self.form.rowCount()):
            self.form.removeRow(0)


def em_gain_andor(form: QFormLayout, base_pv: str) -> tuple[list[Pv], list[pyqtSignal]]:
    """
    Update the basic form layout to include the andor em gain.
    Return the list of Pvs so we can clean up later.
    """
    pvs = []
    sigs = []

    gain_label = QLabel()

    gain_spinbox = QSpinBox()
    gain_spinbox.setMaximum(10000000)

    gain_layout = QHBoxLayout()
    gain_layout.addWidget(gain_label)
    gain_layout.addWidget(gain_spinbox)

    form.addRow("EM Gain", gain_layout)

    def update_gain_widgets(error: Exception | None):
        if error is None:
            gain_label.setText(str(gain_rbv_pv.value))
            gain_spinbox.setValue(int(gain_rbv_pv.value))

    gain_rbv_pv = Pv(
        f"{base_pv}:AndorEMGain_RBV",
        monitor=update_gain_widgets,
        initialize=True,
    )
    gain_set_pv = Pv(f"{base_pv}:AndorEMGain")
    gain_set_pv.connect()
    pvs.append(gain_rbv_pv)
    pvs.append(gain_set_pv)

    def set_gain_value():
        try:
            gain_set_pv.put(gain_spinbox.value())
        except Exception as exc:
            print(f"Error updating EM gain PV: {exc}")

    gain_spinbox.editingFinished.connect(set_gain_value)
    sigs.append(gain_spinbox.editingFinished)

    return pvs, sigs


form_finishers = {
    "Andor DU888_BV": em_gain_andor,
}
