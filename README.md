Snapshot Twitter
===================

It is a simple script to take screenshots and publish on twitter.

It reads an "agenda" file to find out what is happening and include it.

It attended PyConSe in a very nice way, but lacks a better code, mainly
for agenda handling.  Once that said, it worked quite fine.

Usage
=====
For a raspberrypi supporting it, I just made a call via crontab to run
every 5 minutes.

Password/keys/secret stuff was left out, in a configuration file (.twitterc)
following the ConfigParser format, which is mostly like:

[twitter]
key = abced
anotherkey = 12312313123