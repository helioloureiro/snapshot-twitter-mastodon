#! /usr/bin/python
# -*- coding: utf-8 -*-

# source: http://stackoverflow.com/questions/245447/how-do-i-draw-text-at-an-angle-using-pythons-pil

import Image
import ImageFont, ImageDraw, ImageOps

im = Image.open("/tmp/2016-05-13_184752.jpg")

#f = ImageFont.load_default()
f = ImageFont.truetype(font="Arial", size=100)
txt = Image.new('L', (640,480))
d = ImageDraw.Draw(txt)
d.text( (10, 10), "Hello world\nlarge", font=f, fill=255)
w = txt.rotate(0, expand=1)

im.paste( ImageOps.colorize(w, (0,0,0), (255,255,255)), (0,0), w)

im.save("/tmp/2016-05-13_184752.jpg")
