#!/bin/bash
unset EPICS_HOST_ARCH
export EPICS_SITE_CONFIG=/reg/g/pcds/package/epics/3.14/RELEASE_SITE
export PATH=/usr/local/bin:/bin:/usr/bin
unset LD_LIBRARY_PATH
unset EPICS_EXTENSIONS
unset EDMLIBS
unset EDMFILES
unset EPICS_BASE
source /reg/g/pcds/package/epics/3.14/tools/current/bin/epicsenv.sh
cd /reg/g/pcds/package/epics/3.14/modules/event/R3.3.0-2.5.0
edm -eolc -x -m "EVR=$1" evrscreens/evr.edl
