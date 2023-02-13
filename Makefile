SHELL = /bin/bash
ENV = export PCDS_CONDA_VER=5.1.1; source /cds/group/pcds/pyps/conda/pcds_conda;
ALL = pycaqtimage/pycaqtimage.so camviewer_ui.py advanced_ui.py markers_ui.py \
      specific_ui.py timeout_ui.py icon_rc.py

all: $(ALL)

pycaqtimage/pycaqtimage.so: pycaqtimage/configure.py pycaqtimage/pycaqtimage.sip
	$(ENV) python pycaqtimage/configure.py pycaqtimage
	$(ENV) make -C pycaqtimage

camviewer_ui.py: camviewer.ui
	$(ENV) pyuic5 -o camviewer_ui.py camviewer.ui

advanced_ui.py: advanced.ui
	$(ENV) pyuic5 -o advanced_ui.py advanced.ui

markers_ui.py: markers.ui
	$(ENV) pyuic5 -o markers_ui.py markers.ui

specific_ui.py: specific.ui
	$(ENV) pyuic5 -o specific_ui.py specific.ui

timeout_ui.py: timeout.ui
	$(ENV) pyuic5 -o timeout_ui.py timeout.ui

icon_rc.py: icon.qrc
	$(ENV) pyrcc5 -o icon_rc.py icon.qrc

clean:
	-rm camviewer_ui.py advanced_ui.py markers_ui.py specific_ui.py droplet_ui.py xtcrdr_ui.py timeout_ui.py
	-rm icon_rc.py
	-rm *.pyc *~
	-rm pycaqtimage/sip*
	-rm pycaqtimage/*.{exp,sbf,so}
	-rm -rf __pycache__
