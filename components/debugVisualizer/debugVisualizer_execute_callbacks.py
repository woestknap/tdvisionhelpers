# Attach this callback DAT to an Execute DAT inside the debugVisualizer component.
# Enable Frame End so the selected object, velocity, and zone state are current.

def onFrameEnd(frame):
    parent().Update()
    return
