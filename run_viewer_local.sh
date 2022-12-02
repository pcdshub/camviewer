#!/bin/bash -f

export PCDS_CONDA_VER=5.1.1
source /cds/group/pcds/pyps/conda/pcds_conda
export EPICS_CA_MAX_ARRAY_BYTES=10000000
ulimit -c unlimited

echo Launching camviewer w/ $@ from `pwd`
./camviewer.pyw $@

