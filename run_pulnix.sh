#!/bin/bash
source /reg/g/pcds/setup/epicsenv-3.14.12.sh
source /reg/g/pcds/setup/python25.sh

# Add in the qt bin and lib paths
pathmunge   /reg/common/package/qt/4.6.2/bin
ldpathmunge /reg/common/package/qt/4.6.2/lib/x86_64-linux

export EPICS_CA_MAX_ARRAY_BYTES=8644500

# Change to script directory
cd `dirname $0`

export logFile=/tmp/pycaqtViewer.`date '+%y-%m-%d_%H%M%S'`

# Note: Must specify --instr, --pvlist, and either --camera or --camerapv
# Example:
# <path>/run_pulnix.sh --instr SXR --pvlist sxr.lst --camera 2
echo Launching pycaqt viewer with options $* ...
./pulnix6740.pyw $* >& $logFile &

echo Running tail -f on logFile $logFile
echo Hit Ctrl-C to stop watching the log file.
echo Viewer will continue.

# Give the user a chance to see our tail message
sleep 1
tail -f $logFile

