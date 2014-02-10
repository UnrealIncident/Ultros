# coding=utf-8
__author__ = "Gareth Coles"


class Lower(object):
    """
    Class for implementing a dialectizer.

    You need to define one function.
    - sub(string): Dialectize and return the input.
    """

    def sub(self, string):
        return string.lower()