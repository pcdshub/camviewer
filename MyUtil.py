import Xlib
import Xlib.display
import re


def raisewindow(name):
    display = Xlib.display.Display()
    root = display.screen().root
    windowIDs = root.get_full_property(
        display.intern_atom("_NET_CLIENT_LIST"), Xlib.X.AnyPropertyType
    ).value
    for windowID in windowIDs:
        window = display.create_resource_object("window", windowID)
        if not (re.match(name, window.get_wm_name()) is None):
            # I'll pretend I understand what that "2" is.
            cm_event = Xlib.protocol.event.ClientMessage(
                window=window,
                client_type=display.intern_atom("_NET_ACTIVE_WINDOW"),
                data=(32, [2, Xlib.X.CurrentTime, 0, 0, 0]),
            )
            display.send_event(
                root,
                cm_event,
                Xlib.X.SubstructureNotifyMask | Xlib.X.SubstructureRedirectMask,
            )
            display.flush()
            display.close()
            return True
    display.close()
    return False
