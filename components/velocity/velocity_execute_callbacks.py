# Attach this callback DAT to an Execute DAT inside the velocity component.
# Enable Frame End so smoother has completed its current-frame update.

def onFrameEnd(frame):
    parent().Update()
    return
