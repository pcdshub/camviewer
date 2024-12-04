#!/usr/bin/env python

from camviewer_ui_impl import GraphicUserInterface
from PyQt5.QtWidgets import QApplication

import sys
import os

from options import Options

if __name__ == "__main__":
    cwd = os.getcwd()
    os.chdir(
        "/tmp"
    )  # change the working dir to /tmp, so the core dump can be generated

    # Options( [mandatory list, optional list, switches list] )
    options = Options(
        ["instrument"],
        [
            "camera",
            "camerapv",
            "pvlist",
            "cfgdir",
            "activedir",
            "rate",
            "idle",
            "config",
            "proj",
            "marker",
            "camcfg",
            "pos",
            "oneline",
            "lportrait",
            "orientation",
            "cmap",
            "scale",
            "min_timeout",
            "max_timeout",
        ],
        [],
    )
    try:
        options.parse()
    except Exception as e:
        options.usage(str(e.args))
        sys.exit()

    rate = 5.0 if (options.rate is None) else float(options.rate)
    cameraListFilename = "camera.lst" if (options.pvlist is None) else options.pvlist

    if options.cfgdir is None:
        cfgdir = os.getenv("HOME")
        if cfgdir is None:
            cfgdir = ".yagviewer/"
        else:
            cfgdir = cfgdir + "/.yagviewer/"
    else:
        cfgdir = options.cfgdir
    try:
        os.mkdir(cfgdir)
    except Exception:
        pass

    if options.activedir is None:
        activedir = os.getenv("HOME")
        if activedir is None:
            activedir = ".yagactive/"
        else:
            activedir = activedir + "/.yagactive/"
    else:
        activedir = options.activedir
    try:
        os.mkdir(activedir)
    except Exception:
        pass

    if options.scale is not None:
        os.environ["QT_SCALE_FACTOR"] = options.scale

    if options.min_timeout is None:
        # 1 day
        min_timeout = 24 * 60 * 60
    else:
        min_timeout = int(options.min_timeout)
    if options.max_timeout is None:
        # 7 days
        max_timeout = 7 * 24 * 60 * 60
    else:
        max_timeout = int(options.max_timeout)

    app = QApplication([""])
    app.setStyle("Windows")
    gui = GraphicUserInterface(
        app,
        cwd,
        options.instrument,
        options.camera,
        options.camerapv,
        cameraListFilename,
        cfgdir,
        activedir,
        rate,
        options.idle,
        min_timeout,
        max_timeout,
        options,
    )
    try:
        gui.show()
        retval = app.exec_()
    except KeyboardInterrupt:
        app.exit(1)
        retval = 1
    gui.shutdown()
    sys.exit(retval)
