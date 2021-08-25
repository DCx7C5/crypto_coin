# -*- coding: utf-8 -*-

__title__ = 'ccctrl'
__author__ = 'DCx7C5'
__license__ = None
__copyright__ = 'Copyright 2021-present DCx7c5'
__version__ = '0.1.0'

from asyncio import set_event_loop_policy
from uvloop import EventLoopPolicy
from collections import namedtuple
import logging

set_event_loop_policy(EventLoopPolicy())

VersionInfo = namedtuple('VersionInfo', 'major minor micro releaselevel serial')

version_info = VersionInfo(major=0, minor=1, micro=0, releaselevel=None, serial=0)

logging.getLogger(__name__).addHandler(logging.NullHandler())

logging.basicConfig(level=logging.INFO)

