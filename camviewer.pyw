#!/usr/bin/env python

from camviewer_ui_impl import GraphicUserInterface
from PyQt4.QtGui import QApplication

import pyca

import sys
import os

from options import Options

if __name__ == '__main__':
  cwd = os.getcwd()
  os.chdir("/tmp") # change the working dir to /tmp, so the core dump can be generated

  # Options( [mandatory list, optional list, switches list] )
  options = Options(['instrument'],
                    ['camera', 'camerapv', 'pvlist', 'cfgdir', 'activedir',
                     'rate', 'idle', 'config', 'proj', 'marker', 'camcfg',
                     'pos', 'oneline', 'lportrait', 'orientation', 'cmap'],
                    [])
  try:
    options.parse()
  except Exception, msg:
    options.usage(str(msg))
    sys.exit()
    
  rate               = 5.0 if ( options.rate   == None ) else float(options.rate)
  cameraListFilename = 'camera.lst' if (options.pvlist == None) else options.pvlist

  if options.cfgdir == None:
    cfgdir = os.getenv("HOME")
    if cfgdir == None:
      cfgdir = ".yagviewer/"
    else:
      cfgdir = cfgdir + "/.yagviewer/"
  else:
    cfgdir = options.cfgdir
  try:
    os.mkdir(cfgdir)
  except:
    pass

  if options.activedir == None:
    activedir = os.getenv("HOME")
    if activedir == None:
      activedir = ".yagactive/"
    else:
      activedir = activedir + "/.yagactive/"
  else:
    activedir = options.activedir
  try:
    os.mkdir(activedir)
  except:
    pass

  QApplication.setGraphicsSystem("raster")
  app = QApplication([''])
  gui = GraphicUserInterface(app, cwd, options.instrument, options.camera, options.camerapv,
                             cameraListFilename, cfgdir, activedir,
                             rate, options.idle, options)
  try:
#    sys.setcheckinterval(1000) # default is 100
    gui.show()
    retval = app.exec_()
  except KeyboardInterrupt:
    app.exit(1)
    retval = 1
  gui.shutdown()
  sys.exit(retval)
