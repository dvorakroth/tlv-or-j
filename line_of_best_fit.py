#!/usr/bin/env python3

from sklearn.svm import LinearSVC
import numpy

# oh god this took me forever to manage to do urgh

# Given the weights W=svc.coef_[0] and the intercept I=svc.intercept_ ,
# the decision boundary is the line

# y = a*x - b

# with

# a = -W[0]/W[1]
# b = I[0]/W[1]

# https://scikit-learn.org/stable/auto_examples/svm/plot_linearsvc_support_vectors.html
# https://stackoverflow.com/questions/23794277/extract-decision-boundary-with-scikit-learn-linear-svm

def get_boundary_line(points_xyj, min_x, max_x, min_y, max_y):
    yrange = (max_y - min_y)

    Xy = numpy.array(
        [[
            (p[0] - min_x) / (max_x - min_x),
            (p[1] - min_y) / yrange,
            p[2]
        ] for p in points_xyj]
    )
    X = Xy[:, :2]
    y = Xy[:, 2]

    svc = LinearSVC(C=1, loss="hinge", max_iter=3000).fit(X, y)

    W = svc.coef_[0]
    I = svc.intercept_

    a = -W[0]/W[1]
    b = I[0]/W[1]

    boundary = lambda x: a*x - b

    return [[min_x, min_y + boundary(0) * yrange], [max_x, min_y + boundary(1) * yrange]]
