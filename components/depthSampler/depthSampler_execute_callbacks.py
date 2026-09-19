# Attach this callback DAT to an Execute DAT inside the depthSampler component.
# Enable Frame End so detections and the depth TOP have cooked before Update().

def onFrameEnd(frame):
    parent().Update()
    return
