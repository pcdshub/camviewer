"""
Brief model-specific screens to display below the main controls.

This is to be used when there are important model-specific controls
that are vital to the operation of the camera.

These are limited to simple form layouts that will be included
inside of a stock QGroupBox in the main screen.
"""
from __future__ import annotations

from functools import partial

from psp.Pv import Pv
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QFormLayout, QLabel, QPushButton, QHBoxLayout, QSpinBox


# groupBoxControls


class ModelScreenGenerator(QObject):
    """
    This class creates a cam-specific QFormLayout to include in the main screen.

    The layout will include basic start/stop camera controls for all models
    and additional special controls that have been requested for specific models.
    """

    # GUI needs this to update the QGroupBox with the full model name
    final_name = pyqtSignal(str)
    manuf_ready = pyqtSignal()
    model_ready = pyqtSignal()

    def __init__(self, base_pv: str):
        self.form = QFormLayout()
        self.base_pv = base_pv
        self.manufacturer = ""
        self.model = ""
        self.pvs: list[Pv] = []

        # Put in the form elements that always should be there
        self.acq_label = QLabel("Disconnected")
        start_button = QPushButton("Start")
        stop_button = QPushButton("Stop")
        acq_layout = QHBoxLayout()
        acq_layout.addWidget(self.acq_label)
        acq_layout.addWidget(start_button)
        acq_layout.addWidget(stop_button)
        self.form.addRow("Acquire", acq_layout)

        # If we don't have PVs, stop here.
        # This is used to display something before we select a camera.
        if not base_pv:
            self.final_name.emit("Disconnected")
            return

        # If we have PVs, we can make the widgets work properly
        self.manuf_ready.connect(self.finish_form)
        self.model_ready.connect(self.finish_form)
        self.acq_status_pv = Pv(
            f"{base_pv}:Acquire_RBV",
            monitor=self.new_acq_value,
            initialize=True,
        )
        self.pvs.append(self.acq_status_pv)
        self.acq_set_pv = Pv(f"{base_pv}:Acquire")
        self.acq_set_pv.connect()
        self.pvs.append(self.acq_set_pv)
        start_button.clicked.connect(partial(self.set_acq_value, 1))
        stop_button.clicked.connect(partial(self.set_acq_value, 0))

        # Create a callback to finish the form later, given the model
        self.manuf_pv = Pv(f"{base_pv}:Manufacturer_RBV")
        self.pvs.append(self.manuf_pv)
        self.manuf_cid = self.manuf_pv.add_connection_callback(self.manuf_ready)
        self.manuf_pv.connect()
        self.model_pv = Pv(f"{base_pv}:Model_RBV")
        self.pvs.append(self.model_pv)
        self.model_cid = self.model_pv.add_connection_callback(self.model_ready)
        self.model_pv.connect()

    def get_layout(self) -> QFormLayout:
        return self.form

    def manuf_read(self, is_connected: bool) -> None:
        if is_connected:
            self.manuf_pv.del_connection_callback(self.manuf_cid)
            self.manufacturer = self.manuf_pv.value
            self.manuf_pv.disconnect()
            self.manuf_ready.emit()

    def model_read(self, is_connected: bool) -> None:
        if is_connected:
            self.model_pv.del_connection_callback(self.model_cid)
            self.model = self.model_pv.value
            self.model_pv.disconnect()
            self.model_ready.emit()

    def finish_form(self) -> QFormLayout:
        if not self.manufacturer or not self.model:
            return
        full_name = f"{self.manufacturer} {self.model}"
        self.final_name.emit(full_name)
        try:
            finisher = form_finishers[full_name]
        except KeyError:
            print(f"Using basic controls for {full_name}")
            return
        else:
            print(f"Loading special screen for {full_name}")
        self.pvs.extend(finisher(self.form, self.base_pv))

    def new_acq_value(self, error: Exception | None) -> None:
        if error is None:
            self.acq_label.setText(self.acq_status_pv.value)

    def set_acq_value(self, value: int) -> None:
        try:
            self.acq_set_pv.put(value)
        except Exception:
            ...

    def cleanup(self) -> None:
        for pv in self.pvs:
            pv.disconnect()


def em_gain_andor(form: QFormLayout, base_pv: str) -> list[Pv]:
    """
    Update the basic form layout to include the andor em gain.
    Return the list of Pvs so we can clean up later.
    """
    pvs = []

    gain_label = QLabel()

    def update_gain_label(error: Exception | None):
        if error is None:
            gain_label.setText(str(gain_rbv_pv.value))

    gain_rbv_pv = Pv(
        f"{base_pv}:AndorEMGain_RBV",
        monitor=update_gain_label,
        initialize=True,
    )
    pvs.append(gain_rbv_pv)

    gain_set_pv = Pv(f"{base_pv}:AndorEMGain")
    pvs.append(gain_set_pv)
    gain_set_pv.connect()

    def set_gain_value(value: int):
        try:
            gain_set_pv.put(value)
        except Exception:
            ...

    gain_spinbox = QSpinBox()
    gain_spinbox.valueChanged.connect(set_gain_value)

    gain_layout = QHBoxLayout()
    gain_layout.addWidget(gain_label)
    gain_layout.addWidget(gain_spinbox)
    form.addRow("EM Gain", gain_layout)
    return pvs


form_finishers = {
    "Andor DU888_BV": em_gain_andor,
}
