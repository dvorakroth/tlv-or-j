#!/usr/bin/env python3

from sklearn import svm
from PIL import Image
import numpy

import math

def long2tileFrac(lon, zoom):
    return (lon+180.0) / 360.0 * (2.0 ** zoom)

def lat2tileFrac(lat,zoom):
    return (
        1.0 - math.log(math.tan(lat*math.pi/180.0) + 1.0/math.cos(lat*math.pi/180.0))/math.pi
    )/2.0 * (2.0 ** zoom)


def tileFrac2long(x,z):
	return (x/(2.0**z)*360.0-180.0)

def tileFrac2lat(y,z):
	n = math.pi - 2.0*math.pi*y/(2.0**z)
	return (180.0/math.pi * math.atan(0.5*(math.exp(n)-math.exp(-n))))

vecTileFrac2Long = numpy.vectorize(tileFrac2long)
vecTileFrac2Lat  = numpy.vectorize(tileFrac2lat)

def make_meshgrid(x_min, y_min, x_max, y_max, width, height):
    h_x = (x_max - x_min) / width
    h_y = (y_max - y_min) / height
    xx, yy = numpy.meshgrid(numpy.arange(x_min, x_max, h_x),
                         numpy.arange(y_min, y_max, h_y))
    return xx, yy

# wolfgang the wonder wolf says be careful with your zoomlevels because it increases image size exponentially (base 4)
def get_heatmap_pseudomercator(points_xyj, min_x_deg, max_x_deg, min_y_deg, max_y_deg, zoomlevel, tilesize):
    # first of all calculate what the min/max x/y are in tile coords

    min_x_tile = long2tileFrac(min_x_deg, zoomlevel)
    max_x_tile = long2tileFrac(max_x_deg, zoomlevel)

    # these are "backwards" on purpose:
    min_y_tile = lat2tileFrac(max_y_deg, zoomlevel)
    max_y_tile = lat2tileFrac(min_y_deg, zoomlevel)

    # and now we have an image size:
    image_width = math.floor((max_x_tile - min_x_tile) * tilesize)
    image_height = math.floor((max_y_tile - min_y_tile) * tilesize)

    merc_xx, merc_yy = make_meshgrid(min_x_tile, min_y_tile, max_x_tile, max_y_tile, image_width, image_height)

    # and finally, these are the coordinates that correspond to each pixel of the resulting image:
    coord_xx = vecTileFrac2Long(merc_xx, zoomlevel)
    coord_yy = vecTileFrac2Lat(merc_yy, zoomlevel)

    # i guess now would be a good time as any to create and train our predictive model
    _xrange = (max_x_deg - min_x_deg)
    _yrange = (max_y_deg - min_y_deg)

    Xy = numpy.array(
        [[
            (p[0] - min_x_deg) / _xrange,
            (p[1] - min_y_deg) / _yrange,
            p[2]
        ] for p in points_xyj]
    )
    X = Xy[:, :2]
    y = Xy[:, 2]

    #model = svm.SVC(kernel='poly', degree=3, gamma='auto', C=1.0)
    print("before training model")
    model = svm.NuSVC(kernel='poly', gamma='scale', nu=0.3, degree=3)
    model.fit(X, y)
    print("after training model")

    # list of all coordinates in pixel order, but scaled to the same range as X
    normalizedcoords_per_pixel = numpy.c_[
        ((coord_xx - min_x_deg) / _xrange).ravel(),
        ((coord_yy - min_y_deg) / _yrange).ravel()
    ]

    # and FINALLY finally,, these are the actual pixel values!
    pixel_values_flat = numpy.clip(
        model.decision_function(normalizedcoords_per_pixel),
        0.0,
        1.0
    ) * 255

    # now all that's left is to turn that into a pillow image @_@
    pixel_values_shaped = numpy.uint8(pixel_values_flat.reshape((image_height, image_width)))

    image = Image.fromarray(pixel_values_shaped)

    return image



# oh god this took me forever to manage to do urgh

# Given the weights W=svc.coef_[0] and the intercept I=svc.intercept_ ,
# the decision boundary is the line

# y = a*x - b

# with

# a = -W[0]/W[1]
# b = I[0]/W[1]

# https://scikit-learn.org/stable/auto_examples/svm/plot_linearsvc_support_vectors.html
# https://stackoverflow.com/questions/23794277/extract-decision-boundary-with-scikit-learn-linear-svm

# def get_boundary_line(points_xyj, min_x, max_x, min_y, max_y):
#     _xrange = (max_x - min_x)
#     _yrange = (max_y - min_y)

#     Xy = numpy.array(
#         [[
#             (p[0] - min_x) / _xrange,
#             (p[1] - min_y) / _yrange,
#             p[2]
#         ] for p in points_xyj]
#     )
#     X = Xy[:, :2]
#     y = Xy[:, 2]

#     svc = LinearSVC(C=1, loss="hinge", max_iter=3000).fit(X, y)

#     W = svc.coef_[0]
#     I = svc.intercept_

#     a = -W[0]/W[1]
#     b = I[0]/W[1]

#     # urgh urgh urgh

#     # TODO: MATH!!!!!
#     # check for the two cases of a vertical line and a horizontal line, and sort those out
#     # check for the case of a > 0 and clip accordingly using the inverse function
#     # and then also a < 0 lol

#     # ALSO TODO: maybe scrap the linear thing completely????? i mean u kno maybe i could do some
#     # wild bicubic bezier crap????? 

#     boundary = lambda x: a*x - b
#     # y = ax - b  <==>  y + b = ax  <==>  (y + b)/a = x
#     boundary_inverse = lambda y: (y+b)/a

#     westmost_point = (min_x, min_y + boundary(0) * _yrange)

#     if westmost_point[1] < 

#     return [[min_x, min_y + boundary(0) * _yrange], [max_x, min_y + boundary(1) * _yrange]]
