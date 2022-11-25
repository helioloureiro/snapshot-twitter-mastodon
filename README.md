Snapshot Twitter Mastodon
=========================
It is a simple script to take screenshots and publish on twitter and on Mastodon.


snapshot-twitter-mastodon.py
=============================
It reads an "agenda" file to find out what is happening and include it.

It attended PyConSe in a very nice way, but lacks a better code, mainly
for agenda handling.  Once that said, it worked quite fine.

weather-twitter-mastodon.py
===========================
It is running in my apartment's window and takes a picture every 15 minutes.
It remains publishing for now at Twitter, but it might stop in case Elon
decides to charge for API usage or something alike.

https://twitter.com/helio_weather

And it is also running on Mastodon

https://mastodon.social/@helio_weather

Usage
=====
For a raspberrypi supporting it, I just made a call via crontab to run
every 5 minutes.

Password/keys/secret stuff was left out, in a configuration file (.twitterc)
following the ConfigParser format, which is mostly like:

[twitter]
key = abced
anotherkey = 12312313123

For mastodon, create and configure `toot`.
It  will generate the configuration file that will be used for Mastodon posts.

Weather
=======
It was extendend to use as script to gather weather information via
http://forecast.io API.

Requirements
============
Just found it requires some extra packages to work (at the least on raspbian):
 * ttf-mscorefonts-installer
 * python-imaging
 * uvcdynctrl
 * Mastodon.py
 
Bugs
====
No big ones at this moment.
