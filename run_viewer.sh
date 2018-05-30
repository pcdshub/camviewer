#!/bin/bash -f
export h=$(dirname $0)
if [ -d $h ]; then
	cd $h
fi
export PSPKG_ROOT=/reg/common/package
export PSPKG_RELEASE=controls-0.0.6
source $PSPKG_ROOT/etc/set_env.sh
export EPICS_CA_MAX_ARRAY_BYTES=10000000
ulimit -c unlimited

echo Launching camviewer w/ $@ from `pwd`
./camviewer.pyw $@ >& /tmp/camviewer.pyw.`date +%y-%m-%d_%T` &
echo Log file: /tmp/camviewer.pyw.`date +%y-%m-%d_%T`

