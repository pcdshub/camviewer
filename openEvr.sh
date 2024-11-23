#!/bin/bash
source /cds/group/pcds/setup/epicsenv-7.0.3.1-2.0.sh
cd /cds/group/pcds/epics/R7.0.3.1-2.0/modules/event2/R6.0.2/
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
