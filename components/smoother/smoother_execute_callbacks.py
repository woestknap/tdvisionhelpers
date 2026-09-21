# Attach this callback DAT to an Execute DAT inside the smoother component.
# Enable Frame End so objectSelector has completed its current-frame update.

def onFrameEnd(frame):
    parent().Update()
    return
