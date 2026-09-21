# Attach this callback DAT to an Execute DAT inside the objectSelector component.
# Enable Frame End so the fused input DAT has cooked before Update().

def onFrameEnd(frame):
    parent().Update()
    return
