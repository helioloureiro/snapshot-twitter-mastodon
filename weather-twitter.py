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
import argparse
import json
import requests
from PIL import Image
from PIL import ImageFont, ImageDraw, ImageOps
from picturequality import brightness
import re
# pycamera is gone.  So lets rely on pygame.
# import pygame
# import pygame.camera

## Trying to fix images too dark
import numpy as np
import imageio



# stop annoying messages
# src: http://stackoverflow.com/questions/11029717/how-do-i-disable-log-messages-from-the-requests-library
#requests.packages.urllib3.disable_warnings()

DEVICE = "/dev/video0"
IMGSIZE = (1280, 720)
HOMEDIR =  os.environ.get("HOME")
CONFIGURATION = f"{HOMEDIR}/.twitterc"
SAVEDIR = f"{HOMEDIR}/weather"
FAILDIR = f"{SAVEDIR}/images"
WEATHERJSONFILE = "/tmp/weather.json"
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DISCARDFRAMES = 10
LOCKDIR = "/tmp"
LOCKPREFIX = ".weather"
FAILCOUNTER = 10 # amount ot attempts to get a picture
WARMUP = 10 # try to start webcam
THRESHOLD = 15 # quality threshold
TIMEOUT =  10 * 60 # 10 minutes

PID = os.getpid()
LOCKFILE = f"{LOCKDIR}/{LOCKPREFIX}.{PID}"



start_time = time.time()

def debug(*msg):
    if os.environ.get("DEBUG"):
        print(*msg)

def Far2Celsius(temp):
    """
    Simple temperature conversion for the right system (metric)
    """
    temp = float(temp)
    celsius = (temp - 32) * 5 / 9
    return "%0.1f" % celsius

def darkness(imageFile : str): -> float
    # anything below 10 is too dark
    return np.mean(imageio.imread(imageFile, as_gray=True))

class LibCameraInterface:
    def __init__(self, sleep_time=30): None

    def get_image(self, destination):
        debug("LibCameraInterface.get_image()")
        import subprocess
        width, height = IMGSIZE
        command = f"/usr/bin/libcamera-jpeg --width={width} --height={height} -o {destination}"
        subprocess.call(command.split())
        darkLevel = darkness(destination)
        if darkLevel <= 10:
            ## Too dark, increase brightness
            command = f"/usr/bin/libcamera-jpeg --width={width} --height={height}" + \
                f"--brightness=0.5 -o {destination}"
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


class WeatherScreenshot(object):
    def __init__(self):
        self.filename = None
        debug("\n ### WeatherScreenshot [%s] ### " % time.ctime())
        self.ReadConfig()
        self.SetTimeStampAndSaveFileName()
        self.CreateDirectories(self.savefile)
        self.GetOptions()

    def GetOptions(self):
        debug("WeatherScreenshot.GetOptions()")
        parser = argparse.ArgumentParser(description='Take a screenshot, get weather info and publish on Twitter.',
        formatter_class=argparse.MetavarTypeHelpFormatter)
        parser.add_argument('--dry-run', dest='dryRun',
            default=False, type=bool,
            help='Run as dry-run or not.  If dry-run is set to \"true\", no message is sent on Twitter')

        args = parser.parse_args()
        self.dryRun = args.dryRun
        debug(" * dry-run status:", self.dryRun)


    def ReadConfig(self):
        """
        Configuration from file ~/.twitterc
        """
        debug("WeatherScreenshot.ReadConfig()")
        cfg = configparser.ConfigParser()
        debug(f"Reading configuration: {CONFIGURATION}")
        if not os.path.exists(CONFIGURATION):
            raise Exception(f"Failed to find configuration file {CONFIGURATION}")
        cfg.read(CONFIGURATION)

        self.credentials = {
            "twitter_cons_key" : cfg.get("TWITTER", "CONS_KEY"),
            "twitter_cons_sec" : cfg.get("TWITTER", "CONS_SEC"),
            "twitter_acc_key"  : cfg.get("TWITTER", "ACC_KEY"),
            "twitter_acc_sec"  : cfg.get("TWITTER", "ACC_SEC"),
            "forecast_io_key"  : cfg.get("FORECAST.IO", "KEY"),
            "forecast_io_loc"  : cfg.get("FORECAST.IO", "LOCATION")
        }

    def SetTimeStampAndSaveFileName(self):
        debug("WeatherScreenshot.SetTimeStampAndSaveFileName()")
        year = time.strftime("%Y", time.localtime())
        month = time.strftime("%m", time.localtime())
        self.timestamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())
        self.prettyTimestamp = time.strftime("Date: %Y-%m-%d %H:%M", time.localtime())
        self.savefile = f"{SAVEDIR}/{year}/{month}/{self.timestamp}.jpg"

    def CreateDirectories(self, filename):
        debug("WeatherScreenshot.CreateDirectories()")
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

    def GetForecastFromWeb(self):
        """
        Retrieve weather information from forcast.io.
        """
        debug("WeatherScreenshot.GetForecastFromWeb()")
        forecast_io_key = self.credentials["forecast_io_key"]
        forecast_io_location = self.credentials["forecast_io_loc"]

        debug(" * requesting json about weather")
        url = f"https://api.darksky.net/forecast/{forecast_io_key}/{forecast_io_location}"
        req = requests.get(url)
        jdata = json.loads(req.text)

        return jdata

    def isThereWeatherJson(self):
        debug("WeatherScreenshot.isThereWeatherJson()")
        return os.path.exists(WEATHERJSONFILE)

    def isNotTooOldData(self, filename):
        """
        If file is older than 3 hours, it is considered outdated.
        """
        debug("WeatherScreenshot.isNotTooOldData()")
        fileStats = os.stat(filename)
        modificationTime = fileStats.st_mtime
        timeNow = time.time()
        deltaInHours = (timeNow - modificationTime)/(60*60)
        debug(" * delta time in hours:", deltaInHours)
        if deltaInHours >= 3:
            return False
        return True

    def SaveForecastData(self, jData):
        """
        Remove old file in order to create new file stats and save the data.
        """
        debug("WeatherScreenshot.SaveForecastData()")
        if os.path.exists(WEATHERJSONFILE):
            os.unlink(WEATHERJSONFILE)
        with open(WEATHERJSONFILE, 'w') as output:
            output.write(json.dumps(jData, indent=4))

    def LoadSavedForecastData(self):
        debug("WeatherScreenshot.LoadSavedForecastData()")
        with open(WEATHERJSONFILE) as inputFile:
            jData = json.loads(inputFile.read())
        return jData

    def GetWeatherForecast(self):
        """
        Check if forecast json file exists and isn't older than 3 hours.
        Otherwise fetch from forecast.io and save it.
        """
        debug("WeatherScreenshot.GetWeatherForecast()")
        getNewData = False
        if self.isThereWeatherJson():
            debug(" * There is a json file")
            if self.isNotTooOldData(WEATHERJSONFILE):
                debug(" * Data isn't too old - reuse")
                getNewData = False
            else:
                debug(" * Data is outdated - renew")
                getNewData = True

        else:
            debug(" * No json file found")
            getNewData = True

        if getNewData:
            debug(" * Getting new data to renew")
            jData = self.GetForecastFromWeb()
            self.SaveForecastData(jData)
        else:
            debug(" * Re-using already saved data")
            jData = self.LoadSavedForecastData()

        debug(" * converting from Farenheit to Celsius")
        summary = jData["currently"]["summary"]
        temp = jData["currently"]["temperature"]
        temp = Far2Celsius(temp)

        msg = []
        msg.append("Stockholm")
        msg.append(self.prettyTimestamp)
        msg.append(u"Temperature: %s°C" % temp)
        msg.append("Summary: %s" %summary)

        debug(" * * Weather update finished")
        return msg

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
        debug("WeatherScreenshot.UpdateImageWithText()")
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

    def SendTwitter(self):
        debug("WeatherScreenshot.SendTwitter()")
        debug(" * Autenticating in Twitter")
        # App python-tweeter
        # https://dev.twitter.com/apps/815176
        tw = twitter.Api(
            consumer_key = self.credentials["twitter_cons_key"],
            consumer_secret = self.credentials["twitter_cons_sec"],
            access_token_key = self.credentials["twitter_acc_key"],
            access_token_secret = self.credentials["twitter_acc_sec"]
            )
        debug(" * Retrieving info...")
        imageText = self.GetWeatherForecast()

        if imageText is None:
            imageText = [ f"Just another shot at {self.timestamp}" ]
        else:
            self.UpdateImageWithText(imageText, self.savefile)

        # adding the credit to the right guys (awesome guys btw)
        imageText.append("via http://forecast.io/#/f/59.4029,17.9436")
        twitterText = "\n".join(imageText)

        if self.dryRun:
            print("Stopping here because of dry-run mode.")
            return

        try:
            debug("Posting on Twitter")
            tw.PostUpdate(status = twitterText, media = self.savefile)
            debug("done!")
        except Exception as e:
            print("Failed for some reason:", e)


if __name__ == '__main__':
    try:
        if Unix.lockpid():
            shot = WeatherScreenshot()
            shot.GetPhoto()
            shot.SendTwitter()
            Unix.unlockpid()
    except KeyboardInterrupt:
        sys.exit(0)
