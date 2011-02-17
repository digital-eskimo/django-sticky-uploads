import os
import time
import errno
import shutil
from django.forms.fields import FileField, ImageField
try:
    from django.forms.widgets import ClearableFileInput as SuperFileInput
except ImportError:
    from django.forms.widgets import FileInput as SuperFileInput
from django.utils.safestring import mark_safe
from django.core.files.uploadedfile import TemporaryUploadedFile
from . import settings

#---[ Utility functions ]------------------------------------------------------

def count_files(root):
    return sum([len(files) for path, dirs, files in os.walk(root)])

def make_directories(path):
    """ Make directories recursively; don't worry if they all exist already """
    try:
        os.makedirs(os.path.dirname(path))
    except OSError, e:
        if e.errno != errno.EEXIST: # don't complain if already exists
            raise

#---[ Classes ]----------------------------------------------------------------

class StickyFileInput(SuperFileInput):
    """ A FileInput which retains uploaded files between requests.

    This is achieved by storing temporary copies of uploaded files using
    identifiers for the user, form-session and file, and passing this data
    between client and server using hidden inputs to allow the file to be
    identified during subsequent interactions.

    Temporary ("sticky") files are purged periodically based on settings
    to ensure that the server does not get clogged.
    """

    def __init__(self, *args, **kwargs):
        self.user_token = None
        self.sticky_session_id = None
        self.sticky_file_name = None
        super(StickyFileInput, self).__init__(*args, **kwargs)

    def flush_sticky_storage(self, force=False):
        if not os.path.exists(settings.DIR):
            return # nothing to flush

        if count_files(settings.DIR) > settings.MAX_STICKY_FILES:
            shutil.rmtree(settings.DIR, ignore_errors=True)
            return

        for user_directory in os.listdir(settings.DIR):
            user_path = os.path.join(settings.DIR, user_directory)
            user_files = os.listdir(user_path)

            if count_files(user_path) > settings.MAX_FILES_PER_USER:
                shutil.rmtree(user_path, ignore_errors=True)
                continue

            for directory_name in user_files:
                try:
                    directory_age = time.time() - float(directory_name)
                except ValueError:
                    continue # name doesn't parse into a float; leave it alone
                path = os.path.join(user_path, directory_name)
                if directory_age > settings.STICKINESS or force:
                    if not os.path.isdir(path): # not a directory!?
                        continue # better safe than sorry
                    shutil.rmtree(path, ignore_errors=True)

            if len(user_files) == 0: # prune empty directories
                shutil.rmtree(user_path, ignore_errors=True)

    def get_hidden_input_name(self, name, suffix):
        return '%s_%s' % (name, suffix)

    def get_hidden_inputs(self, name):
        if self.sticky_file_name:
            return (
                "<span>You have already uploaded <strong>%s</strong>; leave "
                "this field blank if you'd like to use that file.</span>"
                "<input type='hidden' name='%s' value='%s' />"
                "<input type='hidden' name='%s' value='%s' />" % (
                self.sticky_file_name,
                self.get_hidden_input_name(name, 'sticky_file'),
                self.sticky_file_name,
                self.get_hidden_input_name(name, 'sticky_session_id'),
                self.sticky_session_id))
        return ''

    def render(self, name, value, attrs=None):
        normal = super(StickyFileInput, self).render(name, value, attrs=attrs)
        return mark_safe(u"%s%s" % (self.get_hidden_inputs(name), normal))

    def get_sticky_path(self):
        if not all(
            (self.sticky_session_id, self.sticky_file_name, self.user_token)):
            raise ValueError("Missing data; cannot calculate path.")
        directory = os.path.join(
            settings.DIR, self.user_token, self.sticky_session_id)
        return os.path.join(directory, self.sticky_file_name)

    def save_sticky_copy(self, source):
        self.flush_sticky_storage()
        path = self.get_sticky_path()
        make_directories(path)
        sticky_file = open(path, 'w')
        source.seek(0) # rewind just in case
        sticky_file.write(source.read()) # copy data
        source.seek(0) # rewind again

    def load_sticky_copy(self):
        try:
            return open(self.get_sticky_path(), 'r')
        except ValueError, IOError: # missing data or cannot find file
            # throw away useless data so we don't tell user we have their file
            self.sticky_session_id = None
            self.sticky_file_name = None
            return None

    def value_from_datadict(self, data, files, name):
        """ Normally returns files.get(name, None). Here we also check `data`.
        -- if the appropriate hidden _sticky_file input is set, we can look for
        the temporary file instead and return that if it exists.

        This method seems to be called multiple times with the same arguments,
        so to prevent excessive storage activity the return value is cached
        and returned without processing on subsequent calls.

        There is an assumption that the arguments will not change between calls
        for any given instance, which appears to be valid, so no argument
        checks are performed.
        """
        if hasattr(self, '_value'):
            return self._value

        self.user_token = data.get('csrfmiddlewaretoken', None)

        # look for normal file
        value = super(
            StickyFileInput, self).value_from_datadict(data, files, name)

        if value: # got one, save a temporary copy just in case
            self.sticky_file_name = value.name
            self.sticky_session_id = '%.6f' % time.time()
            self.save_sticky_copy(value.file)
        else: # check for temporary copy
            self.sticky_file_name = (
                data.get(
                    self.get_hidden_input_name(name, 'sticky_file'), None))
            self.sticky_session_id = data.get(
                self.get_hidden_input_name(name, 'sticky_session_id'), None)
            sticky_copy = self.load_sticky_copy()
            if sticky_copy:
                sticky_copy.seek(0, 2) # seek to end
                value = TemporaryUploadedFile(
                    name = self.sticky_file_name,
                    content_type = None,
                    size = sticky_copy.tell(),
                    charset = None
                    )
                value.file = sticky_copy
                value.file.seek(0)
                value.temporary_file_path = lambda: self.get_sticky_path()

        setattr(self, '_value', value) # cache
        return self._value


class StickyImageField(ImageField):
    widget = StickyFileInput


class StickyFileField(FileField):
    widget = StickyFileInput
