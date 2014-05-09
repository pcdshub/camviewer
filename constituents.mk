libnames := pycaqtimage

libsrcs_pycaqtimage := pycaqtimage_sip_wrap.cpp
libincs_pycaqtimage := python/include/python2.5 \
                            qt/include \
                            qt/include/QtCore \
                            qt/include/QtGui
liblibs_pycaqtimage := qt/QtGui

SIPFLAGS += -t Qt_4_6_2 -t WS_X11 -I/reg/common/package/python/2.5.5/share/sip/PyQt4
