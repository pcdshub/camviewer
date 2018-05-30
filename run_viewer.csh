#!/bin/tcsh -f
set h = $0:h
if ($h != $0) cd $h
setenv PSPKG_ROOT /reg/common/package
setenv PSPKG_RELEASE controls-0.0.6
source $PSPKG_ROOT/etc/set_env.csh
setenv EPICS_CA_MAX_ARRAY_BYTES 10000000
limit coredumpsize unlimited
rehash

echo Launching camviewer w/ $argv:q from `pwd`
./camviewer.pyw $argv:q >& /tmp/camviewer.pyw.`date +%y-%m-%d_%T` &
echo Log file: /tmp/camviewer.pyw.`date +%y-%m-%d_%T`

