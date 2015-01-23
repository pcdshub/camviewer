all: pycaqtimage.so
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
