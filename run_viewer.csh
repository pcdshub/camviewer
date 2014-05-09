#!/bin/tcsh
cd /reg/g/pcds/controls/pycaqt/camviewer
setenv LD_LIBRARY_PATH /reg/common/package/python/2.5.5/lib:/reg/common/package/qt/4.6.2/lib/x86_64-linux:/reg/g/pcds/package/epics/3.14/base/current/lib/linux-x86_64:/reg/g/pcds/package/epics/3.14/extensions/current/lib/linux-x86_64
setenv PATH /reg/g/pcds/package/epics/3.14/base/current/bin/linux-x86_64:/reg/g/pcds/package/epics/3.14/extensions/current/bin/linux-x86_64:/reg/common/package/python/2.5.5/bin:/reg/common/package/qt/4.6.2/bin:/bin:/usr/bin:$cwd
setenv EPICS_CA_MAX_ARRAY_BYTES 8388608
limit coredumpsize unlimited
rehash

./camviewer.pyw $* >& /tmp/camviewer.pyw.`date +%y-%m-%d_%T` &
