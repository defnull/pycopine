#!/usr/bin/env python
import sys

extras = {}
try:
    from setuptools import setup
    if sys.version_info < (3, 2):
        extras['install_requires'] = ['futures']
except ImportError:
    from distutils.core import setup

setup(
    name='pycopine',
    version='0.1-dev',
    packages=['pycopine'],
    description='Latency and fault tolerance library inspired by Hystrix.',
    url='https://github.com/defnull/pycopine',
    download_url='http://pypi.python.org/pypi/pycopine/',
    author='Marcel Hellkamp',
    author_email='marc@gsites.de',
    classifiers= [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
    ],
    **extras
)
