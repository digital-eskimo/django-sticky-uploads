""" Any of the settings below can be easily overridden in the project settings
by simply defining a value with the PREFIX included in its name.
e.g. STICKY_UPLOADS_STICKINESS = 7200 """

from django.conf import settings
import os
import sys

PREFIX = 'STICKY_UPLOADS_'
DEFAULT_SETTINGS = {
    'DIR': os.path.join(settings.FILE_UPLOAD_TEMP_DIR or '', '.sticky_files'),
    'STICKINESS': 3600, # seconds until temporary files could be deleted
    'MAX_FILES_PER_USER': 10,
    'MAX_STICKY_FILES': 1000,
    }

def prefixed(string):
    return '%s%s' % (PREFIX, string)

for name, default in DEFAULT_SETTINGS.items():
    setattr(sys.modules[__name__], name,
            getattr(settings, prefixed(name), default))
