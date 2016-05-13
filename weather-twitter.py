#! /usr/bin/python -u
# -*- coding: utf-8 -*-

"""
Based in:
http://stackoverflow.com/questions/15870619/python-webcam-http-streaming-and-image-capture
and
http://stackoverflow.com/questions/245447/how-do-i-draw-text-at-an-angle-using-pythons-pil
"""

HOMEDIR = "/home/pi"

import pygame
import pygame.camera
import time
import sys
import os
import twitter
import ConfigParser
import json
import requests
import Image
import ImageFont, ImageDraw, ImageOps

# test machine?
if os.uname()[1] == 'elxaf7qtt32':
    # my laptop
    HOMEDIR = "/home/ehellou"


configuration = "%s/.twitterc" % HOMEDIR
SAVEDIR = "%s/weather" % HOMEDIR
IMGSIZE = (1280, 720)

def Far2Celsius(temp):
    temp = float(temp)
    celsius = (temp - 32) * 5 / 9
    return "%0.2f" % celsius

def get_content():
    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    msg = []
    msg.append("Stockholm")
    msg.append(timestamp)

    url = "https://api.forecast.io/forecast/%s/%s" % (wth_key, wth_loc)
    req = requests.get(url)
    jdata = json.loads(req.text)

    print jdata.keys()
    print jdata["currently"]

    summary = jdata["currently"]["summary"]
    temp = jdata["currently"]["temperature"]
    temp = Far2Celsius(temp)

    msg.append("%sC" % temp)
    msg.append(summary)

    return msg

def ReadConfig():
    global cons_key, cons_sec, acc_key, acc_sec, wth_key, wth_loc

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
    wth_key = cfg.get("FORECAST.IO", "KEY")
    wth_loc = cfg.get("FORECAST.IO", "LOCATION")

def TweetPhoto():
    """
    """
    print "Pygame init"
    pygame.init()
    print "Camera init"
    pygame.camera.init()
    # you can get your camera resolution by command "uvcdynctrl -f"
    cam = pygame.camera.Camera("/dev/video0", IMGSIZE)

    print "Camera start"
    cam.start()
    time.sleep(5)
    print "Getting image"
    image = cam.get_image()
    time.sleep(1)
    print "Camera stop"
    cam.stop()

    if not os.path.exists(SAVEDIR):
        os.makedirs(SAVEDIR)
    timestamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())
    year = time.strftime("%Y", time.localtime())
    filename = "%s/%s.jpg" % (SAVEDIR, timestamp)
    print "Saving file %s" % filename
    pygame.image.save(image, filename)

    ReadConfig()

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
        msg_body = "\n".join(msg[1:])
        im = Image.open(filename)

        f_top = ImageFont.truetype(font="Arial", size=60)
        f_body = ImageFont.truetype(font="Arial", size=20)
        txt = Image.new('L', IMGSIZE)
        d = ImageDraw.Draw(txt)
        d.text( (10, 10), msg[0], font=f_top, fill=255)
        d.text( (10, 80), msg_body, font=f_body, fill=255)
        w = txt.rotate(0, expand=1)

        im.paste( ImageOps.colorize(w, (0,0,0), (255,255,255)), (0,0), w)
        im.save(filename)

        msg = "%s #weather" % " ".join(msg)
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
