from .core import *


def host_mac():
    import uuid
    return hex(uuid.getnode())[2:].upper()
