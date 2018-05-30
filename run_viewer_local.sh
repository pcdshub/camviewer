#!/bin/bash -f

export PSPKG_ROOT=/reg/common/package
export PSPKG_RELEASE=controls-0.0.6
source $PSPKG_ROOT/etc/set_env.sh
export EPICS_CA_MAX_ARRAY_BYTES=10000000
ulimit -c unlimited

echo Launching camviewer w/ $@ from `pwd`
./camviewer.pyw $@

