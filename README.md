qt_tools
========

QuickTime Tools - utilities for reading and manipulating Apple QuickTime files (.mov extension).

### Components

qt_wrap_interlaced_mjpeg.py - wraps an interlaced MJPEG essence (e.g., Avid 20:1, NTSC 30i) as a QuickTime file.
This is required because only the QuickTime container can provide FFmpeg with the necessary metadata to handle
interlaced MJPEG formats correctly.

quicktime.py - not included here. Contact me for more information.
