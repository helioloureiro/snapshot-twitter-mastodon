#! /usr/bin/python -u
# -*- coding: utf-8 -*-

import sys
import os
import Image
import numpy as np
import time

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
    if verbose:
        print "Verbose mode enabled"
    img = Image.open(filename)
    #Convert the image te RGB if it is a .gif for example
    img = img.convert ('RGB')
    RANK = {}
    #coordinates of the pixel
    X_i,Y_i = 0,0
    (X_f, Y_f) = img.size
    # a quarter should be enough
    X_f = X_f / 4
    Y_f = Y_f / 4
    #Get RGB
    time_i = time.time()
    c = 0
    for i in xrange(X_i, X_f):
        for j in xrange(Y_i, Y_f):
            #print "i:", i,",j:", j
            pixelRGB = img.getpixel((i,j))
            R,G,B = pixelRGB
            br = np.sum([R,G,B])/ 3 ## 0 is dark (black) and 255 is bright (white)
            c += 1
            if c >= 1000:
                if verbose:
                    print "X:%d, Y:%d" % (i,j)
                c = 0
            if RANK.has_key(br):
                RANK[br] += 1
            else:
                RANK[br] = 1
    if verbose:
        print "Total time:", (time.time() - time_i)
        time_i2 = time.time()
        print "Histogram:", np.histogram(img)
        print "Histogram time:", (time.time() - time_i)
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
            print "%d => %d (%0.2f%s)" % \
                (k, RANK[k], RANK[k] * 100.0 / pic_size, '%')
        color_order.append(k)
    if not color_order:
        if verbose:
            print "No large matrix found."
        return 0
    if color_order:
        if verbose:
            print "Top color index:", color_order
        # get first color
        k = color_order[0]
        v = RANK[k]
        v = float(v)
        # let caller decide what to do w/ result
        # the pctg of bad quality
        q = int(v/pic_size * 100)
        if verbose:
            print "Pctg w/ same color:", q
            return q
    return 0

def main():
    if len(sys.argv) == 1:
        usage("ERROR: missing argument")
    img = sys.argv[1]
    if not os.path.exists(img):
        usage("ERROR: File not found")
    r = brightness(img, verbose=True)
    if r > 15:
        print "%s: low quality (>15%%)" % img
        sys.exit(r)
    else:
        print "%s: good or acceptable quality" % img

if __name__ == '__main__':
    main()