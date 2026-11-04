"""Cross-platform advisory process locks. Windows uses conservative exclusive locks."""
import os
import errno
import time
if os.name=='nt':
    import msvcrt
else:
    import fcntl

LOCK_SH=1
LOCK_EX=2
LOCK_NB=4
LOCK_UN=8


def flock(stream,mode):
    if os.name!='nt':
        flags=fcntl.LOCK_UN if mode&LOCK_UN else (fcntl.LOCK_EX if mode&LOCK_EX else fcntl.LOCK_SH)|(fcntl.LOCK_NB if mode&LOCK_NB else 0)
        return fcntl.flock(stream,flags)
    stream.seek(0)
    if mode&LOCK_UN:return msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
    while True:
        try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1);return
        except OSError as error:
            if error.errno not in (errno.EACCES,errno.EAGAIN,errno.EDEADLK):raise
            if mode&LOCK_NB:raise BlockingIOError(error.errno,'Lock is busy') from error
            time.sleep(.02)
