#!/bin/bash
export PSPKG_RELEASE=controls-0.0.6
source $PSPKG_ROOT/etc/set_env.sh
make
pyuic4 -o camviewer_ui.py camviewer.ui
pyuic4 -o advanced_ui.py advanced.ui
pyuic4 -o markers_ui.py markers.ui
pyuic4 -o specific_ui.py specific.ui
pyuic4 -o droplet_ui.py droplet.ui
pyuic4 -o xtcrdr_ui.py xtcrdr.ui
pyuic4 -o timeout_ui.py timeout.ui

pyrcc4 -o icon_rc.py icon.qrc
