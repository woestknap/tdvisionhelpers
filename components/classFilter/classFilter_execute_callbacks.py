# Attach this callback DAT to an Execute DAT inside the classFilter component.
# Enable Frame End so the canonical input DAT has cooked before Update().

def onFrameEnd(frame):
    parent().Update()
    return
