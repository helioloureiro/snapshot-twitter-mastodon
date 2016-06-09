#! /usr/bin/python -u
# -*- coding: utf-8 -*-

import sys
import os
import Image

def usage(msg):
    if msg:
        print msg
    print "Use: %s <image.jpg>" % sys.argv[0]
    if not msg:
        sys.exit(0)
    sys.exit(1)

def brightness(filename, quality=15, verbose=False):
    """
    source: http://stackoverflow.com/questions/6442118/python-measuring-pixel-brightness
    """
    img = Image.open(filename)
    #Convert the image te RGB if it is a .gif for example
    img = img.convert ('RGB')
    RANK = {}
    #coordinates of the pixel
    X_i,Y_i = 0,0
    (X_f, Y_f) = img.size
    #Get RGB
    for i in xrange(X_i, X_f):
        for j in xrange(Y_i, Y_f):
            #print "i:", i,",j:", j
            pixelRGB = img.getpixel((i,j))
            R,G,B = pixelRGB
            br = sum([R,G,B])/ 3 ## 0 is dark (black) and 255 is bright (white)
            if RANK.has_key(br):
                RANK[br] += 1
            else:
                RANK[br] = 1

    color_order = []
    pic_size = X_f * Y_f
    if verbose:
        print "Picture size:", pic_size
    for k in sorted(RANK, key=RANK.get, reverse=True):
        amount = RANK[k]
        # if low than 15%, ignore
        if amount < (.15 * pic_size):
            continue
        if verbose:
            print "%d => %d (%02f)" % (k, RANK[k], RANK[k] * 100.0 / pic_size)
        color_order.append(k)
    if color_order:
        if verbose:
            print color_order
        # get first color
        k = color_order[0]
        v = RANK[k]
        if (v / pic_size * 100.) <= quality:
            return 0
        return -1
    return 0

def main():
    if len(sys.argv) == 1:
        usage("ERROR: missing argument")
    img = sys.argv[1]
    if not os.path.exists(img):
        usage("ERROR: File not found")
    r = brightness(img)
    if r < 0:
        print "%s: low quality" % img
        sys.exit(r)
    else:
        print "%s: good or acceptable quality" % img

if __name__ == '__main__':
    main()