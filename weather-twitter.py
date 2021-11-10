#! /usr/bin/python3 -u
# -*- coding: utf-8 -*-

"""
Based in:
http://stackoverflow.com/questions/15870619/python-webcam-http-streaming-and-image-capture
and
http://stackoverflow.com/questions/245447/how-do-i-draw-text-at-an-angle-using-pythons-pil
"""

HOMEDIR = "/home/pi"

import time
import sys
import os
# pip3 install python-twitter
import twitter
import configparser
import json
import requests
from PIL import Image
from PIL import ImageFont, ImageDraw, ImageOps
import threading
from picturequality import brightness
import re
from random import randint, random
from shutil import copy

# pycamera is gone.  So lets rely on pygame.
# import pygame
# import pygame.camera



# stop annoying messages
# src: http://stackoverflow.com/questions/11029717/how-do-i-disable-log-messages-from-the-requests-library
#requests.packages.urllib3.disable_warnings()

DEVICE = "/dev/video0"
IMGSIZE = (1280, 720)
HOMEDIR =  os.environ.get("HOME")
CONFIGURATION = f"{HOMEDIR}/.twitterc"
SAVEDIR = f"{HOMEDIR}/weather"
FAILDIR = f"{SAVEDIR}/images"
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DISCARDFRAMES = 10
LOCKDIR = "/tmp"
LOCKPREFIX = ".weather"
FAILCOUNTER = 10 # amount ot attempts to get a picture
WARMUP = 10 # try to start webcam
THRESHOLD = 15 # quality threshold
DEBUG = True
TIMEOUT =  10 * 60 # 10 minutes

PID = os.getpid()
LOCKFILE = f"{LOCKDIR}/{LOCKPREFIX}.{PID}"
plock = threading.Lock() # control print
failed_img = "%s.failed_img.jpg" % sys.argv[0]
error_tries = FAILCOUNTER
start_time = time.time()

def debug(msg):
    if DEBUG:
        plock.acquire()
        print(msg)
        plock.release()

def Far2Celsius(temp):
    """
    Simple temperature conversion for the right system (metric)
    """
    temp = float(temp)
    celsius = (temp - 32) * 5 / 9
    return "%0.1f" % celsius

class LibCameraInterface:
    def __init__(self, sleep_time=30): None

    def get_image(self, destination):
        import subprocess
        width, height = IMGSIZE
        command = f"/usr/bin/libcamera-jpeg --width={width} --height={height} -o {destination}"
        subprocess.call(command.split())

class CameraInterface:
    def __init__(self, sleep_time=30):
        import pygame
        import pygame.camera
        self.waiting = sleep_time

        debug("Pygame init")
        pygame.init()
        pygame.camera.init()
        self.cam = pygame.camera.Camera(DEVICE, IMGSIZE)

    def get_image(self, destination):
        self.image_file = destination
        self.cam.start()
        time.sleep(self.waiting)
        image = self.cam.get_image()
        self.cam.stop()
        debug(f"CameraInterface.get_image(): saving image into {self.image_file}")
        #pygame.image.save(image, self.image_file)
        # it should be simple as just save, but for some unknown reason pygame
        # is crashing with the following message:
        # NotImplementedError: saving images of extended format is not available
        # so lets use PIL to generate the image instead.
        raw = pygame.image.tostring(image, 'RGB')
        raw_image = Image.frombytes('RGB', image.get_size(), raw)
        raw_image.save(self.image_file)

class Unix:
    def __init__(self): None

    @staticmethod
    def lockpid():
        """
        Create a pid based lock file.
        Return true to "locked" and false in case of failure (already in use).
        """
        directory = os.listdir(LOCKDIR)
        lockedfile = None
        for filename in directory:
            if not re.search(LOCKPREFIX, filename): continue
            lockedfile = filename
        if lockedfile:
            # double check
            p = lockedfile.split(".")[-1]
            pid = int(p)
            try:
                # SIGNAL 18 is SIGCONT
                # it should be ignored
                os.kill(pid, 18)
                print("Process already running")
                return False
            except ProcessLookupError:
                debug(f"Dead file found ({LOCKDIR}/{lockedfile}).  Removing.")
                os.unlink(f"{LOCKDIR}/{lockedfile}")

        with open(LOCKFILE, 'w') as fd:
            fd.write(f"{PID}\n")
        return True

    @staticmethod
    def unlockpid():
        if os.path.exists(LOCKFILE):
            debug("Removing lock")
            os.unlink(LOCKFILE)


def get_content():
    """
    Retrieve weather information
    """
    global wth_key, wth_loc

    debug("Getting text content")
    timestamp = time.strftime("Date: %Y-%m-%d %H:%M", time.localtime())
    msg = []
    msg.append("Stockholm")
    msg.append(timestamp)

    if sys.argv[-1] == "dry-run":
        debug("Saving queries making an internal response")
        msg.append(u"Temperature: %d°C" % randint(0,35) )
        msg.append(u"Summary: super nice day ever!!!" )
        return msg

    debug(" * requesting json about weather")
    url = "https://api.darksky.net/forecast/%s/%s" % (wth_key, wth_loc)
    req = requests.get(url)
    jdata = json.loads(req.text)

    # this was just to follow up - not needed
    #print jdata.keys()
    #print jdata["currently"]

    debug(" * converting from Farenheit to Celsius")
    summary = jdata["currently"]["summary"]
    temp = jdata["currently"]["temperature"]
    temp = Far2Celsius(temp)

    msg.append(u"Temperature: %s°C" % temp)
    msg.append("Summary: %s" %summary)

    debug(" * * Weather update finished")
    return msg

def getfailedimg():
    """
    Get an alternative image in case of failure
    """
    if not os.path.exists(FAILDIR):
        debug("Directory not found: %s" % FAILDIR)
        return None
    IMGS = []
    for filename in os.listdir(FAILDIR):
        if not re.search("jpg|gif|png", filename):
            continue
        IMGS.append("%s/%s" % (FAILDIR, filename) )
    # get a randomic one
    pos = randint(0, len(IMGS) - 1)
    chosen_one = IMGS[pos]
    copy(chosen_one, failed_img)
    return failed_img

def ReadConfig():
    """
    Configuration from file ~/.twitterc
    """
    global cons_key, cons_sec, acc_key, acc_sec, wth_key, wth_loc

    cfg = configparser.ConfigParser()
    debug(f"Reading configuration: {CONFIGURATION}")
    if not os.path.exists(CONFIGURATION):
        raise Exception(f"Failed to find configuration file {CONFIGURATION}")
    cfg.read(CONFIGURATION)
    cons_key = cfg.get("TWITTER", "CONS_KEY")
    cons_sec = cfg.get("TWITTER", "CONS_SEC")
    acc_key = cfg.get("TWITTER", "ACC_KEY")
    acc_sec = cfg.get("TWITTER", "ACC_SEC")
    wth_key = cfg.get("FORECAST.IO", "KEY")
    wth_loc = cfg.get("FORECAST.IO", "LOCATION")

def GetPhoto(f = None, quality = None):
    """
    Photo aquisition
    """
    global filename, FAILCOUNTER, error_tries

    debug("GetPhoto: failcounter=%d" % FAILCOUNTER)
    if FAILCOUNTER < 0:
        print("Fail counter reached maximum attempts.  Failed.")
        debug("Trying to return a failed img.")
        filename = getfailedimg()
        if not filename:
            sys.exit(1)
        debug("Using failed img: %s" % filename)
        # it needs to be 0ed or it will fail
        FAILCOUNTER = 0
        return 0
    filename = None
    #if not os.path.exists(SAVEDIR):
    #    os.makedirs(SAVEDIR)
    year = time.strftime("%Y", time.localtime())
    month = time.strftime("%m", time.localtime())
    if not os.path.exists("%s/%s/%s" % (SAVEDIR, year, month)):
        os.makedirs("%s/%s/%s" % (SAVEDIR, year, month) )
    if not f:
        timestamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())
        filename = "%s/%s/%s/%s.jpg" % (SAVEDIR, year, month, timestamp)
    else:
        filename = f
    debug("Saving file %s" % filename)
    cam = LibCameraInterface()
    cam.get_image(filename)

def TheWalkingDead(walker=None):
    """
    After a certain time, it is sure task won't be completed.
    So kill it.
    """
    if not walker:
        return
    count = 0
    if sys.version_info.major < 3:
        raise Exception("Python version not supported.  Move to Python3.")

    if sys.version_info.minor <= 8:
        check = walker.isAlive
    else:
        check = walker.is_alive
    while(check()):
        time.sleep(random())
        current_time = time.time()
        delta = current_time - start_time
        # print "Thread(%s) counter=%d delta=%0.2f" % (walker, count, delta)
        if delta > TIMEOUT:
            debug("Reached timeout.  Killing pid")
            try:
                os.kill(PID, 9)
            except ProcessLookupError:
                # process is already killed
                pass
            count += 1


def WeatherScreenshot():
    global filename

    debug("\n ### WeatherScreenshot [%s] ### " % time.ctime())
    debug("Threading image acquisition")
    th = threading.Thread(target=GetPhoto)
    th.start()
    twd = threading.Thread(target=TheWalkingDead, args=(th,))
    twd.walker = "Testing"
    twd.start()
    if not twd.is_alive():
        sys.exit(1)

    ReadConfig()

    debug("Autenticating in Twitter")
    # App python-tweeter
    # https://dev.twitter.com/apps/815176
    tw = twitter.Api(
        consumer_key = cons_key,
        consumer_secret = cons_sec,
        access_token_key = acc_key,
        access_token_secret = acc_sec
        )
    debug("Retrieving info...")
    msg = get_content()
    th.join()
    twd.join()

    if FAILCOUNTER < 0:
        print("Failed to acquire image.  Quitting...")
        sys.exit(1)
    if not msg:
        msg = "Just another shot at %s" % \
            time.strftime("%H:%M", time.localtime())
    if msg:
        im = Image.open(filename)
        # just get truetype fonts on package ttf-mscorefonts-installer
        try:
            f_top = ImageFont.truetype(font="Impact", size=60)
        except TypeError:
            # older versions hasn't font and require full path
            arialpath = "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf"
            f_top = ImageFont.truetype(arialpath, size=60)
        try:
            f_body = ImageFont.truetype(font="Arial", size=20)
        except TypeError:
            # older versions hasn't font and require full path
            arialpath = "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"
            f_body = ImageFont.truetype(arialpath, size=20)

        """
        # SHADOW
        step = 1

        for c in [ WHITE, BLACK ]:
            txt = Image.new('L', IMGSIZE)
            d = ImageDraw.Draw(txt)
            d.text( (10 + step, 10 + step), msg[0], font=f_top, fill=255)
            position = 80
            for m in msg[1:]:
                d.text( (10 + step, position + step), m, font=f_body, fill=255)
                position += 20
            w = txt.rotate(0, expand=1)
            step = 0
            im.paste(ImageOps.colorize(w, c, c), (0,0), w)
            im.save(filename)
        """
        step = 0
        debug("Writting in WHITE")
        txt = Image.new('L', IMGSIZE)
        d = ImageDraw.Draw(txt)

        ## Title ##
        # border first
        d.text((10 + step + 1, 10 + step), msg[0], font=f_top, fill=255)
        d.text((10 + step - 1, 10 + step), msg[0], font=f_top, fill=255)
        d.text((10 + step, 10 + step + 1), msg[0], font=f_top, fill=255)
        d.text((10 + step, 10 + step - 1), msg[0], font=f_top, fill=255)

        ## Body ##
        position = 80
        for m in msg[1:]:
            # border first
            d.text( (10 + step + 1, position + step), m, font=f_body, fill=255)
            d.text( (10 + step - 1, position + step), m, font=f_body, fill=255)
            d.text( (10 + step, position + step + 1), m, font=f_body, fill=255)
            d.text( (10 + step, position + step - 1), m, font=f_body, fill=255)
            # content
            d.text( (10 + step, position + step), m, font=f_body, fill=255)
            position += 20

        # final touch
        w = txt.rotate(0, expand=1)
        im.paste(ImageOps.colorize(w, WHITE, WHITE), (0,0), w)
        im.save(filename)

        debug("Writting in BLACK")
        txt = Image.new('L', IMGSIZE)
        d = ImageDraw.Draw(txt)
        # content
        d.text((10 + step, 10 + step), msg[0], font=f_top, fill=255)
        position = 80
        for m in msg[1:]:
            # content
            d.text( (10 + step, position + step), m, font=f_body, fill=255)
            position += 20

        # final touch
        w = txt.rotate(0, expand=1)
        im.paste(ImageOps.colorize(w, BLACK, BLACK), (0,0), w)
        im.save(filename)

        # adding the credit to the right guys (awesome guys btw)
        msg = u"%s \nvia http://forecast.io/#/f/59.4029,17.9436" % "\n".join(msg)
        try:
            print(u"%s" % msg)
        except UnicodeEncodeError:
            # I just hate this...
            pass
        if sys.argv[-1] == "dry-run":
            debug("Just dry-run mode.  Done!")
            return
        try:
            tw.PostUpdate(status = msg,media = filename)
            debug("done!")
        except Exception as e:
            print("Failed for some reason:", e)
            # it failed so... deal w/ it.
            pass
    else:
        print("no message available")


if __name__ == '__main__':
    try:
        if Unix.lockpid():
            WeatherScreenshot()
            Unix.unlockpid()
    except KeyboardInterrupt:
        sys.exit(0)
