"""
Functions to handle example data in the package
"""
import os


def get_data_path():
    """ Returns absolute path of the data directory to access data samples. """
    return os.path.dirname(__file__)
