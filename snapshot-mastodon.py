#! /usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pygame",
#   "numpy"
# ]
# ///
"""
Based in:
http://stackoverflow.com/questions/15870619/python-webcam-http-streaming-and-image-capture
"""

HOMEDIR = "/home/pi"

import time
import sys
import os
import ConfigParser
import datetime

# External
import pygame
import pygame.camera

# test machine?
if os.uname()[1] == 'elxaf7qtt32':
    # my laptop
    HOMEDIR = "/home/ehellou"
else:
    HOMEDIR=os.getenv('HOME')


configuration = f"{HOMEDIR}/.twitterc"
agenda = f"{HOMEDIR}/pyconse.agenda"
SAVEDIR = f"{HOMEDIR}/pyconse"

def get_content():
    if not os.path.exists(agenda):
        return None
    fd = open(agenda)
    timestamp = time.strftime("%Y-%m-%d", time.localtime())
    YYYY = int(time.strftime("%Y", time.localtime()))
    MM = int(time.strftime("%m", time.localtime()))
    DD = int(time.strftime("%d", time.localtime()))
    now = datetime.datetime.now()
    for line in fd.readlines():
        print(line)
        if not line[0] == '2':
            continue
        try:
            tmstp_date, tmstp_timeslot, tmstp_info = line.split(",")
        except:
            continue
        # not same day?  move forward
        if tmstp_date != timestamp:
            print("No date")
            continue

        tmstp_begin, tmstp_end = tmstp_timeslot.split("-")
        h_beg, m_beg = tmstp_begin.split(":")
        beg = datetime.datetime(YYYY, MM, DD, int(h_beg), int(m_beg))
        delta = now - beg

        # before time?
        if delta.days < 0:
            print("It didn't start yet.")
            continue

        h_end, m_end = tmstp_end.split(":")
        end = datetime.datetime(YYYY, MM, DD, int(h_end), int(m_end))
        delta = end - now
        if delta.days < 0:
            print("It already finished")
            continue

        tmstp_info = tmstp_info.rstrip()
        if tmstp_info == "EMPTY":
            print("Got empty")
            return None
        print(f"Got here, so sending back \"{tmstp_info}\"" )
        return tmstp_info

def TweetPhoto():
    """
    """
    print("Pygame init")
    pygame.init()
    print("Camera init")
    pygame.camera.init()
    # you can get your camera resolution by command "uvcdynctrl -f"
    cam = pygame.camera.Camera("/dev/video1", (1280, 720))

    print("Camera start")
    cam.start()
    time.sleep(1)
    print("Getting image")
    image = cam.get_image()
    time.sleep(1)
    print("Camera stop")
    cam.stop()

    if not os.path.exists(SAVEDIR):
        os.makedirs(SAVEDIR)
    timestamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())
    year = time.strftime("%Y", time.localtime())
    filename = f"{SAVEDIR}/{timestamp}.jpg"
    print(f"Saving file {filename}")
    pygame.image.save(image, filename)

    cfg = ConfigParser.ConfigParser()
    print(f"Reading configuration: {configuration}")
    if not os.path.exists(configuration):
        print("Failed to find configuration file {configuration}")
        sys.exit(1)
    cfg.read(configuration)

    print("Posting...")
    msg = get_content()
    if not msg:
        now = time.strftime("%H:%M", time.localtime())
        msg = (f"Just another shot at {now}")
            
    if msg:
        msg = f"{msg} #pyconse"
        print(msg)
    else:
        print("no message available")
    #print "Removing media file %s" % filename
    #os.unlink(filename)


if __name__ == '__main__':
    try:
        TweetPhoto()
    except KeyboardInterrupt:
        sys.exit(0)
