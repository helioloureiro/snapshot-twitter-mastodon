#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Based in:
http://stackoverflow.com/questions/15870619/python-webcam-http-streaming-and-image-capture
and
http://stackoverflow.com/questions/245447/how-do-i-draw-text-at-an-angle-using-pythons-pil
"""

import time
import sys
import os
import configparser
import argparse
import json
import re
from enum import Enum

# pycamera is gone.  So lets rely on pygame.
# import pygame
# import pygame.camera
import subprocess

from PIL import Image, ImageFont, ImageDraw, ImageOps
import requests


## Trying to fix images too dark
import numpy as np
import imageio.v2 as imageio

# fediverse
from mastodon import Mastodon

# pip3 install python-twitter
import twitter

import pygame
import pygame.camera


# stop annoying messages
# src: http://stackoverflow.com/questions/11029717/how-do-i-disable-log-messages-from-the-requests-library
#requests.packages.urllib3.disable_warnings()

HOMEDIR = os.environ.get("HOME")

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
TOOTCONFIG = f"{HOMEDIR}/.config/toot/config.json"

PID = os.getpid()
LOCKFILE = f"{LOCKDIR}/{LOCKPREFIX}.{PID}"

start_time = time.time()

# src: https://dev.meteostat.net/formats.html#weather-condition-codes
# Note: it seems open-meteo uses other extra code.
# src2: https://open-meteo.com/en/docs
WeatherConditionCodes = {
    0:  "Clear sky",
    1: 	"Mainly Clear",
    2 :	"Partily Cloud",
    3 :	"Overcast",
    4 :	"Overcast",
    5 :	"Fog",
    6 :	"Freezing Fog",
    7 :	"Light Rain",
    8 :	"Rain",
    9 :	"Heavy Rain",
    10 : "Freezing Rain",
    11 : "Heavy Freezing Rain",
    12 : "Sleet",
    13 : "Heavy Sleet",
    14 : "Light Snowfall",
    15 : "Snowfall",
    16 : "Heavy Snowfall",
    17 : "Rain Shower",
    18 : "Heavy Rain Shower",
    19 : "Sleet Shower",
    20 : "Heavy Sleet Shower",
    21 : "Snow Shower",
    22 : "Heavy Snow Shower",
    23 : "Lightning",
    24 : "Hail",
    25 : "Thunderstorm",
    26 : "Heavy Thunderstorm",
    27 : "Storm",
    45 : "Fog",
    48: "Depositing Rime Fog",
    51: "Drizzle Light",
    53: "Drizzle Moderate",
    55: "Drizzle Dense",
    56: "Freezing Drizzle Light",
    57: "Freezing Drizzle Dense",
    61: "Rain Slight",
    63: "Rain Moderate",
    65: "Rain Heavy Intense",
    66: "Freezing Rain Light",
    67: "Freezing Rain Heavy Intensit",
    71: "Snow Fall Slight",
    73: "Snow Fall Moderate",
    75: "Snow Fall Heavy Intensit",
    77: "Snow Grains",
    80: "Rain Showers Slight",
    81: "Rain Showers Moderate",
    82: "Rain Showers Violent",
    85: "Snow Showers Slight",
    86: "Snow Showers Heavy",
    95: "Thunderstorm Slight",
    96: "Thunderstorm with Slight",
    99: "Thunderstorm with Heavy Hail"
}

def runShell(*command):
    return subprocess.check_output(*command)

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


def darkness(imageFile : str) -> float:
    # anything below 10 is too dark
    return np.mean(imageio.imread(imageFile, as_gray=True))

class Weather(Enum):
    DARKSKY = 1
    OPENMETEO = 2

class LibCameraInterface:
    def __init__(self, sleep_time=30): None

    def get_image(self, destination):
        debug("LibCameraInterface.get_image()")
        width, height = IMGSIZE
        command =  [
            "/usr/bin/rpicam-still",
            "--width=" + str(width),
            "--height=" + str(height),
            "-o",
             destination
        ]
        runShell(command)

        # test quality
        img = Image.open(destination)
        quality = np.mean(img)

        ## too dark
        if quality < 10:
            self.get_dark_image(destination)

        ## too bright
        if quality > 200:
            self.get_brighter_image(destination)

    def get_dark_image(self, destination):
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


    def get_brighter_image(self, destination):
        debug("LibCameraInterface.get_brighter_image()")
        width, height = IMGSIZE
        command =  [
            "/usr/bin/rpicam-still",
            "--width=" + str(width),
            "--height=" + str(height),
            "--brightness=-0.1",
            "--shutter=5000",
            "--exposure=sport",
            "-o",
             destination
        ]
        runShell(command)


class CameraInterface:
    def __init__(self, sleep_time=30):
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

class WeatherForecast:
    '''
    The json structed spects a few fields.  So even getting different source
    instead darksky.net, we can set the data in same structure.

    jData = {
        "currenctly" : {
            "summary" : "clear|raining|etc",
            "temperature" : "in Farenheit for darksky, Celsius for others"
        }
    }
    '''
    def __init__(self, source=Weather.OPENMETEO, forecastIOKey=None, forecastIOLocation=None):
        self.source = source
        if source == Weather.DARKSKY:
            self.url = f"https://api.darksky.net/forecast/{forecastIOKey}/{forecastIOLocation}"
        elif source == Weather.OPENMETEO:
            self.url = "https://api.open-meteo.com/v1/metno?latitude=59.3544367&longitude=17.8822503&current_weather=true"
        else:
            raise Exception("Unknow weather forecast source.")

        if self.isThereWeatherJson(WEATHERJSONFILE) and self.isNotTooOldData(WEATHERJSONFILE):
            self.jdata = self.LoadSavedForecastData(WEATHERJSONFILE)
        else:
            self.jdata = self.fetchForecastJson()
            self.SaveForecastData(self.jdata, WEATHERJSONFILE)
    def GetSource(self):
        return self.source

    def GetTemperature(self):
        if self.GetSource() == Weather.DARKSKY:
            temperature = self.jdata["currently"]["temperature"]
            return Far2Celsius(temperature)
        # to be fixed later
        return self.jdata["current_weather"]["temperature"]

    def GetSummary(self):
        if self.GetSource() == Weather.DARKSKY:
             return self.jdata["currently"]["summary"]
        # to be fixed later
        code =  self.jdata["current_weather"]["weathercode"]
        return WeatherConditionCodes[int(code)]

    def fetchForecastJson(self):
        """
        Retrieve weather information.
        """
        debug("WeatherScreenshot.GetForecastFromWeb()")
        req = requests.get(self.url)
        jdata = json.loads(req.text)

        return jdata

    def isThereWeatherJson(self, filename):
        debug("WeatherScreenshot.isThereWeatherJson()")
        return os.path.exists(filename)

    def isNotTooOldData(self, filename):
        """
        If file is older than 1 hour, it is considered outdated.
        """
        debug("WeatherScreenshot.isNotTooOldData()")
        fileStats = os.stat(filename)
        modificationTime = fileStats.st_mtime
        timeNow = time.time()
        deltaInHours = (timeNow - modificationTime)/(60*60)
        debug(" * delta time in hours:", deltaInHours)
        if deltaInHours >= 1:
            return False
        return True

    def SaveForecastData(self, jData, filename):
        """
        Remove old file in order to create new file stats and save the data.
        """
        debug("WeatherScreenshot.SaveForecastData()")
        if os.path.exists(filename):
            os.unlink(filename)
        with open(filename, 'w') as output:
            output.write(json.dumps(jData, indent=4))

    def LoadSavedForecastData(self, filename):
        debug("WeatherScreenshot.LoadSavedForecastData()")
        with open(filename) as inputFile:
            jData = json.loads(inputFile.read())
        return jData


class WeatherScreenshot(object):
    def __init__(self, mastodonUsername="", twitterFlag=False, dryRunFlag=False):
        self.filename = None
        debug("\n ### WeatherScreenshot [%s] ### " % time.ctime())
        # config must be read in order to get weather keys, etc
        self.ReadConfig()
        if len(mastodonUsername) > 0 and dryRunFlag == False:
            self.MastodonAuthenticate(mastodonUsername)
        self.SetTimeStampAndSaveFileName()
        self.CreateDirectories(self.savefile)
        self.dryRunFlag = dryRunFlag
        self.weatherForecast = WeatherForecast()

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

    def MastodonAuthenticate(self, userid):
        with open(TOOTCONFIG) as tootConfig:
            config = json.load(tootConfig)

        self.mastodon = Mastodon(
            access_token = config['users'][userid]['access_token'],
            api_base_url = config['users'][userid]['instance']
            )
        self.me = self.mastodon.me()
        print('Mastodon login completed')

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
        debug(" * Retrieving info...")
        imageText = []
        imageText.append("Stockholm")
        imageText.append(self.prettyTimestamp)
        imageText.append(f"Temperature: {self.weatherForecast.GetTemperature()}°C")
        imageText.append(f"Summary: {self.weatherForecast.GetSummary()}")

        debug(" * * Weather update finished")

        if imageText is None:
            imageText = [ f"Just another shot at {self.timestamp}" ]
        else:
            self.UpdateImageWithText(imageText, self.savefile)

        # adding the credit to the right guys (awesome guys btw)
        if self.WeatherForecast.source == Weather.Overcast:
            imageText.append("via http://forecast.io/#/f/59.4029,17.9436")
        elif self.WeatherForecast.source == Weather.OPENMETEO:
            imageText.append("via https://api.open-meteo.com/v1/metno?latitude=59.3544367&longitude=17.8822503&current_weather=true")

        twitterText = "\n".join(imageText)

        if self.dryRunFlag:
            print("Stopping here because of dry-run mode.")
            return

        debug(" * Autenticating in Twitter")
        # App python-tweeter
        # https://dev.twitter.com/apps/815176
        tw = twitter.Api(
            consumer_key = self.credentials["twitter_cons_key"],
            consumer_secret = self.credentials["twitter_cons_sec"],
            access_token_key = self.credentials["twitter_acc_key"],
            access_token_secret = self.credentials["twitter_acc_sec"]
            )

        try:
            debug("Posting on Twitter")
            tw.PostUpdate(status = twitterText, media = self.savefile)
            debug("done!")
        except Exception as e:
            print("Failed for some reason:", e)

    def SendMastodon(self):
        debug("WeatherScreenshot.SendMastodon()")
        debug(" * Retrieving info...")

        imageText = []
        imageText.append("Stockholm")
        imageText.append(self.prettyTimestamp)
        imageText.append(f"Temperature: {self.weatherForecast.GetTemperature()}°C")
        imageText.append(f"Summary: {self.weatherForecast.GetSummary()}")

        if imageText is None:
            imageText = [ f"Just another shot at {self.timestamp}" ]
        else:
            self.UpdateImageWithText(imageText, self.savefile)

        # adding the credit to the right guys (awesome guys btw)
        if self.WeatherForecast.source == Weather.Overcast:
            imageText.append("via http://forecast.io/#/f/59.4029,17.9436")
        elif self.WeatherForecast.source == Weather.OPENMETEO:
            imageText.append("via https://api.open-meteo.com/v1/metno?latitude=59.3544367&longitude=17.8822503&current_weather=true")
        tootText = "\n".join(imageText)

        if self.dryRunFlag:
            print("Stopping here because of dry-run mode.")
            return

        try:
            debug("Posting on Mastodon")
            mediaData = self.mastodon.media_post(self.savefile)
            self.mastodon.status_post(tootText, media_ids=[mediaData.id])
            debug("done!")
        except Exception as e:
            print("Failed for some reason:", e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='It takes a snapshot from camera, gets current weather forecast and publishes onlne')
    parser.add_argument("--mastodonuser", help="Your registered mastodon account at toot configuration")
    parser.add_argument("--twitter", action='store_true', help="To send the post to Twitter")
    parser.add_argument('--dryrun', action='store_true', default=False,
            help='Run as dry-run or not.  If dry-run is set to \"true\", no message is sent on Twitter and/or Mastodon')
    args = parser.parse_args()

    if args.dryrun:
        print('Dry-Run mode enabled')

    if not args.mastodonuser and not args.twitter:
        parser.print_help()
        sys.exit(os.EX_USAGE)

    if args.mastodonuser and not os.path.exists(TOOTCONFIG):
        print("ERROR: toot not configured yet.  Use toot to create your configuration.")
        sys.exit(os.EX_CONFIG)

    try:
        if Unix.lockpid():
            shot = WeatherScreenshot(args.mastodonuser, args.twitter, args.dryrun)
            shot.GetPhoto()
            if args.twitter == True:
                shot.SendTwitter()
            else:
                print('Skipped SendTwitter since flag is False')
            if args.mastodonuser is not None and len(args.mastodonuser) > 0:
                shot.SendMastodon()
            else:
                print('Skipped SendMastodon since or username is missing or its length is zero')
            Unix.unlockpid()
    except KeyboardInterrupt:
        sys.exit(0)
