#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
extensions = ['sphinx.ext.autodoc']
master_doc = 'index'
project = u'Pycopine'
copyright = str('2009-%s, Marcel Hellkamp' % (time.strftime('%Y')))
release = '0.1-dev' # Do not edit (see VERSION file)
version = ".".join(release.split(".")[:2])
add_function_parentheses = True
add_module_names = False
pygments_style = 'sphinx'
autodoc_member_order = 'bysource'
exclude_patterns = ['_build']
