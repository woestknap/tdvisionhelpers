# Attach this callback DAT to an Execute DAT inside attachmentTransform.
# Enable Frame End so the source pose DATs have cooked before Update().


def onFrameEnd(frame):
    parent().Update()
    return
