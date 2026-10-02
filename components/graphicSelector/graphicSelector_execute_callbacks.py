# Attach this callback DAT to an Execute DAT inside graphicSelector.
# Enable Frame End so stabilized transform data has cooked before Update().


def onFrameEnd(frame):
    parent().Update()
    return
