#!/usr/bin/python
#qt_wrap_interlaced_mjpeg.py:
VERSION_STRING = '2013-03-25 14:30'
# wraps an interlaced MJPEG essence (e.g., Avid 20:1, NTSC 30i) as a QuickTime file
# Written by Aaron Miller <aaron.miller04@gmail.com> in Winter 2012

import os, sys
from getopt import getopt
from math import ceil

from struct import pack, unpack

from collections import namedtuple

import quicktime
from quicktime import Obj, QTAtom

from StringIO import StringIO

FTYP_TEMPLATE = '\x00\x00\x00\x14ftypqt  \x00\x00\x02\x00qt  '

MOOV_TEMPLATE = '\x00\x00\x02\x83moov\x00\x00\x00lmvhd\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
 '\x00\x00\x00\x03\xe8\x00\x00\x00\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
 '\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'\
 '\x00\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
 '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x02\x0ftrak\x00\x00\x00\\tkhd'\
 '\x00\x00\x00\x0f\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00'\
 '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00'\
 '\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00@\x00'\
 '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xabmdia\x00\x00\x00 mdhd\x00\x00\x00\x00\x00'\
 '\x00\x00\x00\x00\x00\x00\x00\x00\x00u0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00-hdlr\x00\x00\x00'\
 '\x00mhlrvide\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0cVideoHandler\x00\x00\x01Vminf\x00'\
 '\x00\x00\x14vmhd\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00,hdlr\x00\x00\x00\x00'\
 'dhlrurl \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0bDataHandler\x00\x00\x00$dinf\x00\x00\x00'\
 '\x1cdref\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x0curl \x00\x00\x00\x01\x00\x00\x00\xeastbl\x00'\
 '\x00\x00\x8astsd\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00zjpeg\x00\x00\x00\x00\x00\x00\x00\x01'\
 '\x00\x00\x00\x00FFMP\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00H\x00\x00\x00H\x00\x00\x00'\
 '\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
 '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x18\xff\xff\x00\x00\x00$glbl,\x00\x00\x00\x18'\
 '\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x08\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x00\x00'\
 '\x00\x18stts\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03\xe9\x00\x00\x00\x1cstsc\x00'\
 '\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x14stsz\x00'\
 '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10stco\x00\x00\x00\x00\x00\x00\x00\x00'

MAX_MJPEG_FRAME_BYTES = 1<<24      #  maximum size (in bytes) of one MJPEG frame (both fields); 1<<24 == 16 MB


def find_all(needle, haystack):
    """Returns a list of all offsets into the haystack string where the needle string occurs, or an
    empty list if none were found."""
    all_offsets = []
    idx = -1

    while True:
        idx = haystack.find(needle, idx+1)
        if idx == -1:
            break
        all_offsets.append(idx)

    return all_offsets

def analyze_and_copy_mjpeg(out_qt_file, in_mjpeg_file):
    """Read the raw MJPEG essence from in_mjpeg_file and write it into an 'mdat' atom (to
    out_qt_file); simultaneously, analyze the MJPEG data for frame sizes and offsets.
    Returns a 2-tuple of (frame_offsets, frame_sizes).

    Does not support MJPEG frame sizes greater than MAX_MJPEG_FRAME_BYTES (16 MB).
    NOTE: assumes that out_qt_file position is at end of 'ftyp' atom!!!"""

    # every MJPEG picture/field begins with the 4-byte sequence 0xff, 0xd8, 0xff, 0xe0 (SOI & APP0 markers)
    SOI_APP0 = '\xff\xd8\xff\xe0'

    mdat_file_pos = None
    mdat_off64_pos = None
    # 1) write 'mdat' atom header
    mdat_file_pos = out_qt_file.tell()
    out_qt_file.write(pack('>I4s', 1, 'mdat'))  # size=1 because an 64-bit extended size follows the atom type
    mdat_off64_pos = out_qt_file.tell()
    out_qt_file.write(pack('>Q', 0xeeeeeeeeeee)) # placeholder


    initial_mjpeg_bytes = None
    buffer_number = -1                          # incremented at beginning of loop
    frame_offsets, frame_sizes = ([], [])       # parallel lists; these are the return values of this function
    eof = False
                                                # in initial_mjpeg_bytes, so this will be False
    while (not eof) or (initial_mjpeg_bytes is not None):
        buffer_number += 1
        # 2a) read several megabytes of MJPEG data from in_mjpeg_file; prepend to this the initial_mjpeg_bytes
        #     (then, set it to None), if not none; if reached end of file, set eof to True
        if not eof:
            b = in_mjpeg_file.read(MAX_MJPEG_FRAME_BYTES)
            if len(b) < MAX_MJPEG_FRAME_BYTES:
                eof = True
            if initial_mjpeg_bytes is not None:
                b = initial_mjpeg_bytes + b
                initial_mjpeg_bytes = None
        else:
            # instead of reading from file, process initial_mjpeg_bytes
            assert initial_mjpeg_bytes is not None
            b = initial_mjpeg_bytes
            initial_mjpeg_bytes = None

        frames_in_b = []
        # 2b) break into discrete frames (pairs of MJPEG pictures/fields) using SOI_APP0; save remaining bytes
        #     at the end into initial_mjpeg_bytes
        offsets_in_b = find_all(SOI_APP0, b)
        if len(offsets_in_b) > 0 and offsets_in_b[0] > 0:
            # junk at the beginning of file: remove it and re-initialize offsets_in_b
            if buffer_number == 0:
                print >>sys.stderr, "WARNING: ignoring %d bytes of junk at beginning of the MJPEG file!" % offsets_in_b[0]
                b = b[ offsets_in_b[0] : ]
                offsets_in_b = find_all(SOI_APP0, b)
            else:
                raise ValueError("Inconsistent program state! offsets_in_b[0] is %d, and MJPEG file position is %d" % \
                                 (offsets_in_b[0], in_mjpeg_file.tell()))

        if eof:
            assert len(offsets_in_b) >= 1
            cut_offset = len(b)
        elif len(offsets_in_b) > 1:
            if len(offsets_in_b) % 2 == 1:
                # odd number of frames: cut at last SOI_APP0 in b
                cut_offset = offsets_in_b[-1]
                offsets_in_b = offsets_in_b[:-1]
            else:
                # even number of frames: cut at second-to-last SOI_APP0 in b
                assert len(offsets_in_b) >= 2, "Expected at least two occurrences of SOI_APP0 in buffer (found %d)" % \
                                                len(offsets_in_b)
                cut_offset = offsets_in_b[-2]
                offsets_in_b = offsets_in_b[:-2]
            # split off the last partial/full MJPEG picture/field
            assert initial_mjpeg_bytes is None
            initial_mjpeg_bytes = b[cut_offset:]
            assert find_all(SOI_APP0, initial_mjpeg_bytes)[0] == 0
            b = b[:cut_offset]

        # using offsets_in_b, break b into parts, which go in frames_in_b
        # appending the length of b simplifies the code
        if len(offsets_in_b) % 2 == 1:
            offsets_in_b += [None, len(b)] # I expect that offsets_in_b[-2] never gets used
        else:
            offsets_in_b.append(len(b))

        for i in xrange(0, len(offsets_in_b)-1, 2):
            frames_in_b.append( b[ offsets_in_b[i] : offsets_in_b[i+2] ] )
        b = None      # free the memory

        sizes_in_b = [len(frame) for frame in frames_in_b]

        # 2c) write the retrieved frames (frames_in_b) to out_qt_file; in the process of doing this, save
        #     offsets (into out_qt_file) and frame byte-sizes (in the frame_offsets and frame_sizes lists,
        #     respectively)
        for frame in frames_in_b:
            # 2c.1) write the retrieved frame to out_qt_file
            off0 = out_qt_file.tell()
            out_qt_file.write(frame)
            off1 = out_qt_file.tell()
            assert off1 - off0 == len(frame)

            # 2c.2) append to frame_offsets and frame_sizes
            frame_offsets.append(off0)
            frame_sizes.append(off1 - off0)
        frame = None
        frames_in_b = None

    assert initial_mjpeg_bytes is None

    # 3) seek back to the previously saved offset of the 64-bit 'mdat' atom size, and write it; then, seek to end
    #    of file

    mdat_file_end = out_qt_file.tell()
    out_qt_file.seek(mdat_off64_pos)
    mdat_size = mdat_file_end - mdat_file_pos
    assert mdat_size > 16                     # sanity check
    out_qt_file.write(pack('>Q', mdat_size))  # write it!
    out_qt_file.seek(0, 2)                    # seek back to end of file

    return (frame_offsets, frame_sizes)


Durations = namedtuple('Durations', ['track_duration', 'track_frame_duration',
                                     'media_duration', 'media_frame_duration'])

def calc_durations(num_frames, framerate,  media_timescale=30000, track_timescale=1000):
    """When given both the number of frames in the file (num_frames) and the framerate
    (from the "-r" option), calculate the values of the total file duration and also the
    frame durations in both track/movie and media time-scales.

    Returns a Durations namedtuple containing 4 values: (track_duration, track_frame_duration,
    media_duration, media_frame_duration) -- only the last one is floating-point."""
    #TODO: it might be necessary to return an additional value: media_timescale

    # calculate media_frame_duration using framerate (supplied by "-r" option)
    media_frame_duration = media_timescale/framerate    # floating point, not integer!

    track_timescale =  1000    # this is in the 'moov' template
    media_timescale = 30000    # also in 'moov' template
    assert media_timescale > 0
    track_frame_duration = (media_frame_duration * track_timescale)/media_timescale     # floating point, not integer!

    track_duration = int(ceil(num_frames * track_frame_duration))

    # now, round the track_frame_duration -- this is not as important; probably unused
    track_frame_duration = int(round(track_frame_duration))

    # calculate the media_duration (and ceil it)
    media_duration = int(ceil(num_frames * media_frame_duration))

    # return the calculated values
    d = Durations(track_duration, track_frame_duration,     # int, int,
                  media_duration, media_frame_duration)     # int, float
    return d




def print_usage():
    print "usage : qt_wrap_interlaced_mjpeg.py -v"
    print "\tqt_wrap_interlaced_mjpeg.py -s <WxH> -r <framerate> -o <output.mov> <raw MJPEG input>"
    print "In order to properly transcode interlaced MJPEG media, FFmpeg requires information from"
    print "the container. qt_wrap_interlaced_mjpeg.py creates this container.  Note that the height"
    print "supplied in the -s option is the full frame height, NOT the height of one field, or one"
    print "MJPEG picture."



if __name__ == '__main__':
    opts, args = getopt(sys.argv[1:], 's:r:o:vh', ['version', 'help'])
    mjpeg_filename = None
    out_filename   = None
    frame_width    = None
    frame_height   = None
    framerate      = None

    for flag, arg in opts:
        if flag == '-s':
            if arg.count('x') != 1:
                print >>sys.stderr, "ERROR: frame size should be of the form WxH, where W and H are positive integers"
                print_usage()
                sys.exit(1)
            try:
                w_str, h_str = arg.split('x')
                frame_width  = int(w_str)
                frame_height = int(h_str)
            except ValueError:
                print >>sys.stderr, "ERROR: frame size should be of the form WxH, where W and H are positive integers"
                print_usage()
                sys.exit(1)
        elif flag == '-r':
            if arg.endswith('ND') or arg.endswith('DF'):   # for compatibility with qt_timecode.py
                print >>sys.stderr, "NOTE: ignoring '%s' at the end of the frame rate" % arg[-2:]
                arg = arg[:-2]
            try:
                framerate = float(arg)
            except ValueError:
                print >>sys.stderr, "ERROR: expected a floating-point frame rate for -r"
                print_usage()
                sys.exit(1)
        elif flag == '-o':
            out_filename = arg
        elif flag in ('-h', '--help'):
            print_usage()
            sys.exit(0)
        elif flag in ('-v', '--version'):
            print VERSION_STRING
            sys.exit(0)
        else:
            print "Unrecognized flag %s" % flag
            print_usage()
            sys.exit(1)

    if len(args) != 1:
        print >>sys.stderr, 'ERROR: expected exactly one MJPEG input file'
        print_usage()
        sys.exit(1)
    else:
        mjpeg_filename = args[0]

    if out_filename is None:
        print >>sys.stderr, 'ERROR: expected a filename for the output QuickTime'
        print_usage()
        sys.exit(1)

    #########################################################

    # 1) produce a moov QTAtom from the template
    sf = StringIO(MOOV_TEMPLATE)
    moov = QTAtom()
    moov.parse(sf, 0)
    moov.trak[0].get(sf, track_type_code='V')
    moov.get(sf)

    out_qt_file = None
    in_mjpeg_file = None
    # 2) open the files specified by mjpeg_filename and out_filename
    try:
        in_mjpeg_file = file(mjpeg_filename, 'rb')
    except IOError, e:
        print >>sys.stderr, "ERROR: while opening input MJPEG file %r: '%r'" % (mjpeg_filename, e)
        sys.exit(1)

    try:
        out_qt_file = file(out_filename, 'wb')
    except IOError, e:
        print >>sys.stderr, "ERROR: while opening output QuickTime file %r: '%r'" % (out_filename, e)
        sys.exit(1)

    # 3) write FTYP_TEMPLATE to out_qt_file
    out_qt_file.seek(0)
    out_qt_file.write(FTYP_TEMPLATE)
    assert out_qt_file.tell() == len(FTYP_TEMPLATE)   # sanity check

    in_mjpeg_file.seek(0)
    # 4) write MJPEG mdat, while simultaneously analyzing the MJPEG data for frame sizes and offsets
    frame_offsets, frame_sizes = analyze_and_copy_mjpeg(out_qt_file, in_mjpeg_file)
    assert len(frame_offsets) == len(frame_sizes)

    num_frames = len(frame_offsets)
    # 5) fill in the moov, update(), and write to out_filename
    d = calc_durations(num_frames, framerate)

    (track_duration, track_frame_duration,
     media_duration, media_frame_duration) = d

    assert float(track_duration)/track_frame_duration >= float(media_duration)/media_frame_duration, \
        "File duration in movie/track time must be at least as large as file duration in media time!"

    moov.mvhd.field.duration = track_duration
    trak = moov.trak[0]
    trak.tkhd.field.trackHeight = frame_height<<16      # fixed point 16.16
    trak.tkhd.field.trackWidth  = frame_width <<16      # fixed point 16.16
    trak.tkhd.field.duration    = track_duration        # track/movie timescale
    trak.mdia.mdhd.field.duration   = media_duration    # media timescale
    stbl = trak.mdia.minf.stbl
    stbl.stsd.field.height  = frame_height
    stbl.stsd.field.width   = frame_width
    stbl.stts.table = [(num_frames, int(round(media_frame_duration)))]
    stbl.stsz.table = frame_sizes
    stbl.stco.table = frame_offsets
    del trak, stbl

    moov.update(recursive=True)

    out_qt_file.seek(0, 2)      # seek to EOF, just in case
    # write to out_filename
    b = moov.get_bytes(sf, with_atom_header=True)
    out_qt_file.write(b)
