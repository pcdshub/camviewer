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
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        acq_layout = QHBoxLayout()
        acq_layout.addWidget(self.start_button)
        acq_layout.addWidget(self.stop_button)
        self.form.addRow(self.acq_label, acq_layout)

        # If we don't have PVs, stop here.
        if not base_pv:
            self.full_name = "Disconnected"
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
        self.acq_set_pv.add_rwaccess_callback(self.acquire_rw_cb)
        self.acq_set_pv.do_initialize = True
        self.acq_set_pv.do_monitor = True
        self.acq_set_pv.connect()
        self.pvs_to_clean_up.append(self.acq_set_pv)
        self.start_button.clicked.connect(partial(self.set_acq_value, 1))
        self.stop_button.clicked.connect(partial(self.set_acq_value, 0))

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

    def manuf_monitor(self, error: Exception | None) -> None:
        """
        Monitor callback for new manufacturer value.

        Each camera has a manufacturer and a model, which
        together define if and which special widgets to
        generate.
        """
        if error is None:
            self.manufacturer = self.manuf_pv.value
            self.manuf_ready.emit()

    def model_monitor(self, error: Exception | None) -> None:
        """
        Monitor callback for a new model value.

        Each camera has a manufacturer and a model, which
        together define if and which special widgets to
        generate.
        """
        if error is None:
            self.model = self.model_pv.value
            self.model_ready.emit()

    def finish_form(self) -> QFormLayout:
        """
        Completes the layout, adding any cam-specific widgets.

        The main part of this function is meant to be run exactly once.
        We should not be able to move to the main body until
        both the manufacturer and the model are known.

        Cam-specific "finisher" functions should have the signature:

        def finished(
            form: QFormlayout,
            base_pv: str,
        ) -> tuple[list[Pv], list[pyqtSignal]]

        Where the return values are the pvs and signals we need to clean
        up at widget close.
        """
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
        """
        Monitor callback for a new value of the Acquire_RBV PV.

        This PV tells us whether the PV is or is not acquiring data.
        As this value changes, we update a label for the display.
        """
        if error is None:
            if self.acq_status_pv.value:
                text = START_TEXT
            else:
                text = STOP_TEXT
            self.acq_label.setText(text)

    def set_acq_value(self, value: int) -> None:
        """
        Slot to start or stop camera acquisition.
        """
        try:
            self.acq_set_pv.put(value)
        except Exception:
            ...

    def acquire_rw_cb(self, _: bool, write_access: bool) -> None:
        """
        Read/write access callback for enabling/disabling the acquire buttons.

        We disable the buttons when there is no write access as an indicator
        that the user can't change the setting.

        Read access is passed in by pyca but is ignored here.
        """
        self.start_button.setEnabled(write_access)
        self.stop_button.setEnabled(write_access)

    def cleanup(self) -> None:
        """
        Tidy up all the callbacks and widgets associated with the generated cam screen.

        Disconnects all the PVs, disconnects all of the signals, and removes all
        of the widgets from the layout.
        """
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
    gain_spinbox.setEnabled(False)

    gain_layout = QHBoxLayout()
    gain_layout.addWidget(gain_label)
    gain_layout.addWidget(gain_spinbox)

    form.addRow("EM Gain", gain_layout)

    def update_gain_widgets(error: Exception | None):
        if error is None:
            gain_label.setText(str(gain_rbv_pv.value))
            gain_spinbox.setValue(int(gain_rbv_pv.value))

    def gain_rw_cb(_: bool, write_access: bool):
        gain_spinbox.setEnabled(write_access)

    gain_rbv_pv = Pv(
        f"{base_pv}:AndorEMGain_RBV",
        monitor=update_gain_widgets,
        initialize=True,
    )
    gain_set_pv = Pv(f"{base_pv}:AndorEMGain")
    gain_set_pv.add_rwaccess_callback(gain_rw_cb)
    gain_set_pv.do_initialize = True
    gain_set_pv.do_monitor = True
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
