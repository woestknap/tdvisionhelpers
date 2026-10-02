# Attach this callback DAT to an Execute DAT inside graphicAttachment.
# Enable Frame End so attachmentTransform data has cooked before Update().


def onFrameEnd(frame):
    parent().Update()
    return
