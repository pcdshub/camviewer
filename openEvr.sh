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
cd /reg/g/pcds/epics/R7.0.3.1-2.0/modules/event2/R5.6.0/event2Screens/
# This gets weird and squirrelly.  Originally, SLAC was returning 0.
# Then, it started returning 0x1Fxx vs. 0x11xx.  Now it returns full
# 32-bit 0x1Fxxxxxx vs. 0x11xxxxxx.
fpgv=`caget -t $1:CTRL.FPGV`
if [ $fpgv -eq 0 -o $fpgv -ge 520093696 -o \( $fpgv -ge 7936 -a $fpgv -lt 285212672 -a $fpgv -ne 268435459 \) ]; then
    file=event2Screens/evrSLAC.edl
else
    file=event2Screens/evrPmc230.edl
fi
edm -eolc -x -m "EVR=$1" $file >/dev/null 2>/dev/null
