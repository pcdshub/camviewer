#!/bin/csh -f
setenv PSPKG_ROOT /reg/common/package
setenv PSPKG_RELEASE controls-0.0.6
source $PSPKG_ROOT/etc/set_env.csh
setenv EPICS_CA_MAX_ARRAY_BYTES 10000000
limit coredumpsize unlimited
rehash

echo Launching camviewer w/ $argv:q from `pwd`
./camviewer.pyw $argv:q
