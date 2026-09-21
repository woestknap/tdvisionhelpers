# Attach this callback DAT to an Execute DAT inside the visionFusion component.
# Enable Frame End so both current-frame input DATs have cooked before Update().

def onFrameEnd(frame):
    parent().Update()
    return
