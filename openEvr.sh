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
cd /reg/g/pcds/package/epics/3.14/modules/event/R4.0.0-2.9.0/
if [ `caget -t $1:CTRL.FPGV` -lt 520093696 ]; then
#    file=evrScreens/evr.edl
     file=evrScreens/evrPmc230.edl
else
#    file=evrScreens/evr_slac.edl
     file=evrScreens/evrSLAC.edl
fi
edm -eolc -x -m "EVR=$1" $file >/dev/null 2>/dev/null
