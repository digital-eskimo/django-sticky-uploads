#!/usr/bin/env python

from distutils.core import setup

setup(name='django-sticky-uploads',
      version='0.1',
      description='Retain uploaded files between requests with Django forms',
      author='Simon Meers',
      author_email='simon@simonmeers.com',
      url='http://github.com/digital-eskimo/django-sticky-uploads',
      packages=['sticky-uploads',]
     )
