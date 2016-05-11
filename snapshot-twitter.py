#! /usr/bin/python -u
# -*- coding: utf-8 -*-

"""
Based in:
http://stackoverflow.com/questions/15870619/python-webcam-http-streaming-and-image-capture
"""

HOMEDIR = "/home/pi"

import pygame
import pygame.camera
import time
import sys
import os
import twitter
import ConfigParser
import datetime


# test machine?
if os.uname()[1] == 'elxaf7qtt32':
    # my laptop
    HOMEDIR = "/home/ehellou"


configuration = "%s/.twitterc" % HOMEDIR
agenda = "%s/pyconse.agenda" % HOMEDIR
SAVEDIR = "%s/pyconse" % HOMEDIR

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
        print line
        if not line[0] == '2':
            continue
        try:
            tmstp_date, tmstp_timeslot, tmstp_info = line.split(",")
        except:
            continue
        # not same day?  move forward
        if tmstp_date != timestamp:
            print "No date"
            continue

        tmstp_begin, tmstp_end = tmstp_timeslot.split("-")
        h_beg, m_beg = tmstp_begin.split(":")
        beg = datetime.datetime(YYYY, MM, DD, int(h_beg), int(m_beg))
        delta = now - beg

        # before time?
        if delta.days < 0:
            print "It didn't start yet."
            continue

        h_end, m_end = tmstp_end.split(":")
        end = datetime.datetime(YYYY, MM, DD, int(h_end), int(m_end))
        delta = end - now
        if delta.days < 0:
            print "It already finished"
            continue

        tmstp_info = tmstp_info.rstrip()
        if tmstp_info == "EMPTY":
            print "Got empty"
            return None
        print "Got here, so sending back \"%s\"" % tmstp_info
        return tmstp_info

def TweetPhoto():
    """
    """
    print "Pygame init"
    pygame.init()
    print "Camera init"
    pygame.camera.init()
    # you can get your camera resolution by command "uvcdynctrl -f"
    cam = pygame.camera.Camera("/dev/video1", (1280, 720))

    print "Camera start"
    cam.start()
    time.sleep(1)
    print "Getting image"
    image = cam.get_image()
    time.sleep(1)
    print "Camera stop"
    cam.stop()

    if not os.path.exists(SAVEDIR):
        os.makedir(SAVEDIR)
    timestamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())
    year = time.strftime("%Y", time.localtime())
    filename = "%s/%s.jpg" % (SAVEDIR, timestamp)
    print "Saving file %s" % filename
    pygame.image.save(image, filename)

    cfg = ConfigParser.ConfigParser()
    print "Reading configuration: %s" % configuration
    if not os.path.exists(configuration):
        print "Failed to find configuration file %s" % configuration
        sys.exit(1)
    cfg.read(configuration)
    cons_key = cfg.get("TWITTER", "CONS_KEY")
    cons_sec = cfg.get("TWITTER", "CONS_SEC")
    acc_key = cfg.get("TWITTER", "ACC_KEY")
    acc_sec = cfg.get("TWITTER", "ACC_SEC")

    print "Autenticating in Twitter"
    # App python-tweeter
    # https://dev.twitter.com/apps/815176
    tw = twitter.Api(
        consumer_key = cons_key,
        consumer_secret = cons_sec,
        access_token_key = acc_key,
        access_token_secret = acc_sec
        )
    print "Posting...",
    msg = get_content()
    if not msg:
        msg = "Just another shot at %s" % \
            time.strftime("%H:%M", time.localtime())
    if msg:
        msg = "%s #pyconse" % msg
        print msg
        try:
            tw.PostMedia(status = msg,media = filename)
            print "done!"
        except:
            None
    else:
        print "no message available"
    #print "Removing media file %s" % filename
    #os.unlink(filename)


if __name__ == '__main__':
    try:
        TweetPhoto()
    except KeyboardInterrupt:
        sys.exit(0)
