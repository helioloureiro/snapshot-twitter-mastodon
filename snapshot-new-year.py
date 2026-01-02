#! /usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pillow",
#   "Mastodon.py",
#   "pygame"
# ]
# ///
# pylint: disable=C0103

"""
Based in:
http://stackoverflow.com/questions/15870619/python-webcam-http-streaming-and-image-capture
and
http://stackoverflow.com/questions/245447/how-do-i-draw-text-at-an-angle-using-pythons-pil
"""

import time
import sys
import os
import argparse
import json
import re
import subprocess


# external
from PIL import Image, ImageFont, ImageDraw, ImageOps

# fediverse
from mastodon import Mastodon # pylint: disable=E0401

# pycamera is gone.  So lets rely on pygame.
import pygame # pylint: disable=E0401
import pygame.camera # pylint: disable=E0401


# stop annoying messages
# src: http://stackoverflow.com/questions/11029717/how-do-i-disable-log-messages-from-the-requests-library # pylint: disable=C0301
#requests.packages.urllib3.disable_warnings()

HOMEDIR = os.environ.get("HOME")

DEVICE = "/dev/video0"
IMGSIZE = (1280, 720)
HOMEDIR =  os.environ.get("HOME")
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
TIMEOUT =  10 * 60 # 10 minutes
TOOTCONFIG = f"{HOMEDIR}/.config/toot/config.json"

PID = os.getpid()
LOCKFILE = f"{LOCKDIR}/{LOCKPREFIX}.{PID}"

start_time = time.time()

def runShell(*command):
    """
    Sintax sugar for subprocess
    """
    return subprocess.check_output(*command)

def debug(*msg):
    """
    Debug environment call - it should be replaced
    by logging.debug( ) instead.
    """
    if os.environ.get("DEBUG"):
        print(*msg)

class LibCameraInterface:
    """
    Interface to use libcamera.
    It actually dropped libcamera usage since it was deprecated
    and use rpicam-still binary instead.
    """
    def __init__(self, sleep_time=30):
        pass

    def get_image(self, destination):
        """
        Acquire the image
        """
        debug("LibCameraInterface.get_image()")
        self.get_dark_image(destination)

    def get_dark_image(self, destination):
        """
        Get image with longer exposition
        """
        debug("LibCameraInterface.get_dark_image()")
        width, height = IMGSIZE
        command =  [
            "/usr/bin/rpicam-still",
            "--width=" + str(width),
            "--height=" + str(height),
            "--shutter=3000000",
            "--exposure=normal",
            "-o",
             destination
        ]
        runShell(command)

class CameraInterface:
    """
    Camera Interface to abstract usage or from pygame or from libcamera.
    It is also possible to extend to other camera supports.
    """
    def __init__(self, sleep_time=30):
        self.waiting = sleep_time
        self.image_file = None

        debug("Pygame init")
        pygame.init()
        pygame.camera.init()
        self.cam = pygame.camera.Camera(DEVICE, IMGSIZE)

    def get_image(self, destination):
        """
        Get the image
        """
        debug("CameraInterface.get_image()")
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

class LockFile:
    """
    Class to handle lock files
    """
    @staticmethod
    def create():
        """
        Create a pid based lock file.
        Return true to "locked" and false in case of failure (already in use).
        """

        LockFile._wait_for_lock_release()
        with open(LOCKFILE, 'w', encoding="utf-8") as fd:
            fd.write(f"{PID}\n")
        return True

    @staticmethod
    def _wait_for_lock_release():
        start_time = time.perf_counter()
        directory_list = os.listdir(LOCKDIR)
        locked_file = None
        for filename in directory_list:
            if not re.search(LOCKPREFIX, filename):
                continue
            locked_file = filename

        if locked_file is None:
            return

        while True:
            if time.perf_counter() - start_time > 60:
                raise Exception("It can't create lock file")
            if not os.path.exists(locked_file):
                return
            time.sleep(3)

    @staticmethod
    def remove():
        """
        Remove the lock file.
        """
        if os.path.exists(LOCKFILE):
            debug("Removing lock")
            os.unlink(LOCKFILE)

class WindowScreenshot:
    """
    Class for objects over pictures taken from raspberryp pi.
    """
    def __init__(self, mastodonUsername="", dryRunFlag=False):
        self.filename = None
        debug(f"\n ### New Year Screenshots [{time.ctime()}] ### ")
        # config must be read in order to get weather keys, etc

        if len(mastodonUsername) > 0 and dryRunFlag is False:
            self.MastodonAuthenticate(mastodonUsername)

        self.SetTimeStampAndSaveFileName()
        self.CreateDirectories(self.savefile)
        self.dryRunFlag = dryRunFlag

    def MastodonAuthenticate(self, userid):
        """
        Authentication on Mastodon.
        """
        with open(TOOTCONFIG, encoding="utf-8") as tootConfig:
            config = json.load(tootConfig)

        self.mastodon = Mastodon(
            access_token = config['users'][userid]['access_token'],
            api_base_url = config['users'][userid]['instance']
            )
        self.me = self.mastodon.me()
        print('Mastodon login completed')

    def SetTimeStampAndSaveFileName(self):
        """
        Get current time and create a savefile attribute for usage later.
        """
        debug("WeatherScreenshot.SetTimeStampAndSaveFileName()")
        year = time.strftime("%Y", time.localtime())
        month = time.strftime("%m", time.localtime())
        self.timestamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())
        self.prettyTimestamp = time.strftime("Date: %Y-%m-%d %H:%M:%S", time.localtime())
        self.savefile = f"{SAVEDIR}/{year}/{month}/{self.timestamp}.jpg"

    def CreateDirectories(self, filename):
        """
        To create the missing directories if that is the case.
        """
        debug("WindowScreenshot.CreateDirectories()")
        directories = os.path.dirname(filename)
        if not os.path.exists(directories):
            os.makedirs(directories)

    def GetPhoto(self):
        """
        Photo aquisition
        """
        debug("WeatherScreenshot.GetPhoto()")
        debug(f"Saving file {self.savefile}")
        cam = LibCameraInterface()
        cam.get_image(self.savefile)

    def SetImageFont(self):
        """
        Just get truetype fonts on package ttf-mscorefonts-installer.
        """
        debug("WeatherScreenshot.SetImageFont()")
        try:
            fontHead = ImageFont.truetype(font="Impact", size=60)
        except TypeError:
            # older versions hasn't font and require full path
            arialpath = "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf"
            fontHead = ImageFont.truetype(arialpath, size=60)
        try:
            fontBody = ImageFont.truetype(font="Arial", size=20)
        except TypeError:
            # older versions hasn't font and require full path
            arialpath = "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"
            fontBody = ImageFont.truetype(arialpath, size=20)
        return fontHead, fontBody

    def UpdateImageWithText(self, messageArray, imageFile):
        """
        Add the texts into the image.
        """
        debug("WindowScreenshot.UpdateImageWithText()")
        image = Image.open(imageFile)

        fontHead, fontBody = self.SetImageFont()

        step = 0
        debug("Writting in WHITE")
        txt = Image.new('L', IMGSIZE)
        d = ImageDraw.Draw(txt)

        ## Head ##
        # border first
        d.text((10 + step + 1, 10 + step), messageArray[0], font=fontHead, fill=255)
        d.text((10 + step - 1, 10 + step), messageArray[0], font=fontHead, fill=255)
        d.text((10 + step, 10 + step + 1), messageArray[0], font=fontHead, fill=255)
        d.text((10 + step, 10 + step - 1), messageArray[0], font=fontHead, fill=255)

        ## Body ##
        position = 80
        for m in messageArray[1:]:
            # border first
            d.text( (10 + step + 1, position + step), m, font=fontBody, fill=255)
            d.text( (10 + step - 1, position + step), m, font=fontBody, fill=255)
            d.text( (10 + step, position + step + 1), m, font=fontBody, fill=255)
            d.text( (10 + step, position + step - 1), m, font=fontBody, fill=255)
            # content
            d.text( (10 + step, position + step), m, font=fontBody, fill=255)
            position += 20

        # final touch
        w = txt.rotate(0, expand=1)
        image.paste(ImageOps.colorize(w, WHITE, WHITE), (0,0), w)
        image.save(imageFile)

        debug("Writting in BLACK")
        txt = Image.new('L', IMGSIZE)
        d = ImageDraw.Draw(txt)

        # Head
        d.text((10 + step, 10 + step), messageArray[0], font=fontHead, fill=255)

        # Body
        position = 80
        for m in messageArray[1:]:
            # content
            d.text( (10 + step, position + step), m, font=fontBody, fill=255)
            position += 20

        # final touch
        w = txt.rotate(0, expand=1)
        image.paste(ImageOps.colorize(w, BLACK, BLACK), (0,0), w)
        image.save(imageFile)

    def SendMastodon(self):
        """
        Send image and picture to Mastodon fediverse.
        """
        debug("WindowScreenshot.SendMastodon()")
        debug(" * Retrieving info...")

        imageText = []
        imageText.append("Stockholm")
        imageText.append(self.prettyTimestamp)

        if imageText is None:
            imageText = [ f"Just another shot at {self.timestamp}" ]
        else:
            self.UpdateImageWithText(imageText, self.savefile)

        tootText = "\n".join(imageText)

        if self.dryRunFlag:
            print("Stopping here because of dry-run mode.")
            return

        try:
            debug("Posting on Mastodon")
            mediaData = self.mastodon.media_post(self.savefile) # pylint: disable=C0103
            self.mastodon.status_post(tootText, media_ids=[mediaData.id])
            debug("done!")
        except Exception as e: # pylint: disable=C0103, disable=W0718
            print("Failed for some reason:", e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='It takes a snapshot from camera,' +\
        ' gets current weather forecast and publishes onlne')
    parser.add_argument(
        "--mastodonuser", 
        help="Your registered mastodon account at toot configuration")
    parser.add_argument(
        '--dryrun', 
        action='store_true',
        default=False,
        help='Run as dry-run or not.  ' + \
        'If dry-run is set to \"true\", ' + \
        'no message is sent on Twitter and/or Mastodon')
    parser.add_argument(
        '--timeout',
        default=300,
        type=int,
        help="The time to keep taking photos in sequence." + \
        " Default is 300s (5 minutes).")
    args = parser.parse_args()

    if args.dryrun:
        print('Dry-Run mode enabled')

    if not args.mastodonuser:
        parser.print_help()
        sys.exit(os.EX_USAGE)

    if args.mastodonuser and not os.path.exists(TOOTCONFIG):
        print("ERROR: toot not configured yet.  Use toot to create your configuration.")
        sys.exit(os.EX_CONFIG)

    try:
        if LockFile.create():
            shot = WindowScreenshot(args.mastodonuser, args.dryrun)
            start_time = time.perf_counter()
            while time.perf_counter() - start_time < args.timeout:
                shot.GetPhoto()
                if args.mastodonuser is not None and len(args.mastodonuser) > 0:
                    try:
                        # to avoid the lock for too many posts on Mastodon
                        shot.SendMastodon()
                    except: # pylint: disable=W0702
                        pass
                else:
                    print('Skipped SendMastodon since or username is missing or its length is zero')

                time.sleep(10)
            LockFile.remove()
    except KeyboardInterrupt:
        LockFile.remove()
        sys.exit(0)
