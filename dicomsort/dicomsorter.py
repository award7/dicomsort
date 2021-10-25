import itertools
import os
import pydicom
import shutil

from collections import abc
from queue import Empty, Queue
from threading import Thread

from dicomsort import errors, utils

THREAD_COUNT = 2


class Dicom:
    def __init__(
            self,
            *,
            filename,
            dcm=None
    ):
        """
        Takes a dicom filename in and returns instance that can be used to sort
        """
        # Be sure to do encoding because Windows sucks
        self.filename = filename

        # Load the DICOM object
        if dcm:
            self.dicom = dcm
        else:
            self.dicom = pydicom.read_file(self.filename)

        self.series_first = False

        self.default_overrides = {
            'ImageType': self._image_type,
            'FileExtension': self._file_extension,
            'SeriesDescription': self._series_description
        }

        self.overrides = dict(self.default_overrides)

    def __getitem__(self, attr):
        """
        Points the reference to the property unless an override is specified
        """
        try:
            item = self.overrides[attr]
            if isinstance(item, abc.Callable):
                return item()

            return item
        except KeyError:
            return getattr(self.dicom, attr)

    def _file_extension(self):
        filename, extension = os.path.splitext(self.dicom.filename)
        return extension

    def _series_description(self):
        if not hasattr(self.dicom, 'SeriesDescription'):
            out = 'Series%04d' % self.dicom.SeriesNumber
        else:
            if self.series_first:
                out = 'Series%04d_%s' % (self.dicom.SeriesNumber,
                                         self.dicom.SeriesDescription)
            else:
                out = '%s_Series%04d' % (self.dicom.SeriesDescription,
                                         self.dicom.SeriesNumber)

        # Strip so we don't have any leading/trailing spaces
        return out.strip()

    def _patient_age(self):
        """
        Computes the age of the patient
        """
        if 'PatientAge' in self.dicom:
            age = self.dicom.PatientAge
        elif 'PatientBirthDate' not in self.dicom or \
                self.dicom.PatientBirthDate == '':
            age = ''
        else:
            age = (int(self.dicom.StudyDate) -
                   int(self.dicom.PatientBirthDate)) / 10000
            age = '%03dY' % age

        return age

    def _image_type(self):
        """
        Determines the human-readable type of the image
        """

        types = {
            'Phase': {'P', },
            '3DRecon': {'CSA 3D EDITOR', },
            'Phoenix': {'CSA REPORT', },
            'Mag': {'FFE', 'M'},
        }

        try:
            image_type = set(self.dicom.ImageType)
        except AttributeError:
            return 'Unknown'

        for typeString, match in types.items():
            if match.issubset(image_type):
                if typeString == '3DRecon':
                    self.dicom.InstanceNumber = self.dicom.SeriesNumber

                return typeString

        return 'Image'

    def get_destination(self, root, directory_format, filename_format):
        # First we need to clean up the elements of directory_format to make
        # sure that we don't have any bad characters (including /) in the
        # folder names
        directory = root
        for item in directory_format:
            try:
                subdir = utils.recursive_replace_tokens(item, self)
                subdir = utils.clean_directory_name(subdir)
            except AttributeError:
                subdir = 'UNKNOWN'

            directory = os.path.join(directory, subdir)

        # Maximum recursion is 5 so we don't end up with any infinite loop
        # situations
        try:
            filename = utils.recursive_replace_tokens(filename_format, self)
            filename = utils.clean_path(filename)
            out = os.path.join(directory, filename)
        except AttributeError:
            # Now just use the initial filename
            origname = os.path.split(self.filename)[1]
            out = os.path.join(directory, origname)

        return out

    def sort(self, root, directory_fields, filename_string, test=False,
             rootdir=None, keep_original=True):

        # If we want to sort in place
        if directory_fields is None:
            destination = os.path.relpath(self.filename, rootdir[0])
            destination = os.path.join(root, destination)
        else:
            destination = self.get_destination(
                root, directory_fields, filename_string
            )

        if test:
            print(destination)
            return

        utils.mkdir(os.path.dirname(destination))

        # Check if destination exists
        while os.path.exists(destination):
            destination = destination + '.copy'

        if self.is_anonymous():
            # Actually write the anonymous data
            # write everything in anonymization_lookup -> Parse it so we can
            # have dynamic fields
            for key in self.anonymization_lookup.keys():
                replacement_value = self.anonymization_lookup[key] % self
                try:
                    self.dicom.data_element(key).value = replacement_value
                except KeyError:
                    continue

            self.dicom.save_as(destination)

            if keep_original is False:
                os.remove(self.filename)

        else:
            if keep_original:
                shutil.copy(self.filename, destination)
            else:
                shutil.move(self.filename, destination)


class Sorter(Thread):
    def __init__(
            self,
            *,
            queue,
            target: str,
            sort_order: list,
            filename: str,
            anonymization: dict = {},
            keep_filename=False,
            iterator=None,
            test=False,
            listener=None,
            total=None,
            root=None,
            series_first=False,
            keep_original=True
    ):
        self.directory_format = sort_order
        self.filename = filename
        self.queue = queue
        self.anonymization_lookup = anonymization or dict()
        self.keep_filename = keep_filename
        self.series_first = series_first
        self.keep_original = keep_original
        self.output_directory = target
        self.test = test
        self.iter = iterator
        self.root = root
        self.total = total or self.queue.qsize()

        self.is_gui = False

        if listener:
            self.listener = listener
            self.is_gui = True

        Thread.__init__(self)
        self.start()

    def sort_image(self, filename):
        dcm = utils.isdicom(filename)

        if not dcm:
            return

        dcm = Dicom(filename, dcm)
        dcm.set_anonymization_rules(self.anonymization_lookup)
        dcm.series_first = self.series_first

        dcm.sort(
            self.output_directory,
            self.directory_format,
            self.filename,
            test=self.test,
            rootdir=self.root,
            keep_original=self.keep_original
        )

    def run(self):
        while True:
            try:
                filename = self.queue.get_nowait()
                self.sort_image(filename)
            # TODO: Rescue any other errors and quarantine the files
            except Empty:
                return


class DicomSorter:
    def __init__(
            self,
            *,
            source: str = None,
            target: str,
            filename: str = '%(ImageType)s_(%(InstanceNumber)04d)%(FileExtension)s',
            keep_filename: bool = False,
            series_first: bool = False,
            keep_original: bool = True,
            sort_order: list = ['SeriesDescription'],
            anonymization: dict = {
                'PatientName': 'PatientID',
                'PatientBirthDate': ''
            }
    ):
        """

        param source: source to raw dicom files to be sorted
        type: str

        param filename: parameterized string to rename files. Use `None` to keep original file name.
        type: str

        param keep_filename: to use the original file name instead of renaming. TO BE REMOVED!!

        param series_first: to use the SeriesDescription field as the first sorting field. TO BE REMOVED!!

        param keep_original: to keep the original dicom files

        param sort_order: ordered list of fields to use when ordering files. Each field will add a child directory to
                            the immediate ancestor.

        param anonymization: anonymize fields as key-value pairs. Can use templating to replace with other fields.

        """
        # Use current directory by default
        if not source:
            source = [os.getcwd(), ]

        if not isinstance(source, list):
            source = [source, ]

        self.source = source
        self.target = target
        self.filename = filename
        self.keep_filename = keep_filename
        self.series_first = series_first
        self.keep_original = keep_original
        self.sort_order = sort_order

        if not isinstance(anonymization, dict):
            raise Exception('Anon rules must be a dictionary')
        self.anonymization = anonymization

        self.queue = Queue()
        self.sorters = list()

    def sort(self, output_directory, test=False, listener=None):
        # This should be moved to a worker thread
        for path in self.source:
            for root, _, files in os.walk(path):
                for filename in files:
                    self.queue.put(os.path.join(root, filename))
        number_of_files = self.queue.qsize()
        iterator = itertools.count(1)

        for _ in range(min(THREAD_COUNT, number_of_files)):
            sorter = Sorter(
                queue=self.queue,
                target=self.target,
                sort_order=self.sort_order,
                filename=self.filename,
                anonymization=self.anonymization,
                iterator=iterator,
                test=test,
                listener=listener,
                total=number_of_files,
                root=self.source,
                keep_original=self.keep_original
            )

            self.sorters.append(sorter)

    # todo: change to 'check_for_dicoms'
    def available_fields(self):
        for path in self.pathname:
            for root, dirs, files in os.walk(path):
                for filename in files:
                    dcm = utils.isdicom(os.path.join(root, filename))
                    if dcm:
                        return dcm.dir('')

        msg = ''.join([';'.join(self.pathname), ' contains no DICOMs'])
        raise errors.DicomFolderError(msg)
