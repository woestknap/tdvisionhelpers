# Attach this callback DAT to an Execute DAT inside the zoneManager component.
# Enable Frame End so smoother has completed its current-frame update.

def onFrameEnd(frame):
    parent().ext.ZoneManagerExt.Update()
    return
