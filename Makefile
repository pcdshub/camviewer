all: pycaqtimage.so
#SIPTAG    = Qt_4_6_2
#SIPINC    = /reg/common/package/python/2.5.5/share/sip/PyQt4
#PYTHONINC = /reg/common/package/python/2.5.5/include/python2.5
#SIPHDIR   = /reg/common/package/python/2.5.5/include/python2.5
#QTINC     = /reg/common/package/qt/4.6.2/include
#QTLIB     = /reg/common/package/qt/4.6.2/lib/x86_64-linux-opt

#SIPTAG    = Qt_4_6_2
#SIPINC    = /reg/common/package/PyQt/4.7.2-python2.7/x86_64-rhel5-gcc41-opt/share/sip
#PYTHONINC = /reg/common/package/python/2.7.5/x86_64-rhel5-gcc41-opt/include/python2.7
#SIPHDIR   = /reg/common/package/sip/4.10.1-python2.7/x86_64-rhel5-gcc41-opt/include/python2.7
#QTINC     = /reg/common/package/qt/4.8.4/x86_64-rhel5-gcc41-opt/include
#QTLIB     = /reg/common/package/qt/4.8.4/x86_64-rhel5-gcc41-opt/lib

SIPTAG    = Qt_4_6_2
SIPINC    = $(PSPKG_RELDIR)/share/sip
PYTHONINC = $(PSPKG_RELDIR)/include/python2.7
SIPHDIR   = $(PSPKG_RELDIR)/include/python2.7
QTINC     = $(PSPKG_RELDIR)/include
QTLIB     = $(PSPKG_RELDIR)/lib

pycaqtimage.so: pycaqtimage_sip_wrap.sip
	sip -t $(SIPTAG) -t WS_X11 -I$(SIPINC) \
	    -e -j 1 -c . pycaqtimage_sip_wrap.sip
	g++ -I$(PYTHONINC) -I$(SIPHDIR) -I$(QTINC) -I$(QTINC)/QtCore -I$(QTINC)/QtGui \
	    -fno-strict-aliasing -fPIC -D_REENTRANT -D__pentium__ -Wall -O4 -m64 \
	    -c sippycaqtimagepart0.cpp
	g++ -m64 -shared -L$(QTLIB) -lQtGui \
	    sippycaqtimagepart0.o -o pycaqtimage.so
