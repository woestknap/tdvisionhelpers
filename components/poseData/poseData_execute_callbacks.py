# Attach this callback DAT to an Execute DAT inside the poseData component.
# Enable Frame End so the upstream predictions DAT has cooked before Update().


def onFrameEnd(frame):
    parent().Update()
    return
