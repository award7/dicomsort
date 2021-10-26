import os
import pydicom
import shutil
from collections import abc
from queue import Empty, Queue
from threading import Thread
from dicomsort import utils
from pydicom.errors import InvalidDicomError

THREAD_COUNT = 2


class Dicom:
    def __call__(
            self,
            *,
            source: str,
            target: str,
            filename: str,
            sort_order: list,
            anonymization: dict = {},
            keep_original=True,
            **kwargs
    ) -> None:
        """
        Takes a dicom filename in and returns instance that can be used to sort
        """
        self.source = source
        self.target = target
        self.filename = filename
        self.sort_order = sort_order
        self.anonymization = anonymization
        self.keep_original = keep_original

        # Load the DICOM object
        try:
            self.dcm = pydicom.read_file(filename)
        except InvalidDicomError:
            return

        self.overrides = {
            'ImageType': self._image_type,
            'FileExtension': self._file_extension,
            'SeriesDescription': self._series_description
        }
        self.sort()

    def __getitem__(self, *, attr):
        """
        Points the reference to the property unless an override is specified
        """
        try:
            item = self.overrides[attr]
            if isinstance(item, abc.Callable):
                return item()
            return item
        except KeyError:
            return getattr(self.dcm, attr)

    def _image_type(self) -> str:
        """
        Determines the human-readable type of the image
        """
        # todo: add to dict with other file types?
        types = {
            'Phase': {'P', },
            '3DRecon': {'CSA 3D EDITOR', },
            'Phoenix': {'CSA REPORT', },
            'Mag': {'FFE', 'M'},
        }

        try:
            image_type = set(self.dcm.ImageType)
        except AttributeError:
            return 'Unknown'

        for typeString, match in types.items():
            if match.issubset(image_type):
                if typeString == '3DRecon':
                    self.dcm.InstanceNumber = self.dcm.SeriesNumber
                return typeString
        return 'Image'

    def _file_extension(self) -> str:
        _, extension = os.path.splitext(self.dcm.filename)
        if not extension:
            extension = '.dcm'
        return extension

    def _series_description(self):
        out = 'Series%04d_%s' % (self.dcm.SeriesNumber, self.dcm.SeriesDescription)

        # Strip so we don't have any leading/trailing spaces
        return out.strip()

    def get_destination(self) -> str:
        # First we need to clean up the elements of directory_format to make
        # sure that we don't have any bad characters (including /) in the
        # folder names
        directory = self.source
        for item in self.sort_order:
            try:
                subdir = utils.recursive_replace_tokens(item, self)
                subdir = utils.clean_directory_name(subdir)
            except AttributeError:
                subdir = 'UNKNOWN'

            directory = os.path.join(self.source, subdir)

        # Maximum recursion is 5 so we don't end up with any infinite loop situations
        try:
            filename = utils.recursive_replace_tokens(self.filename, self)
            filename = utils.clean_path(filename)
            out = os.path.join(directory, filename)
        except AttributeError:
            # Now just use the initial filename
            origname = os.path.split(self.filename)[1]
            out = os.path.join(directory, origname)

        return out

    def sort(self) -> None:
        # If we want to sort in place
        if len(self.sort_order) == 0:
            destination = os.path.relpath(self.filename, self.source)
            destination = os.path.join(self.source, destination)
        else:
            destination = self.get_destination()

        utils.mkdir(os.path.dirname(destination))

        # Check if destination exists
        while os.path.exists(destination):
            destination = destination + '.copy'

        # Actually write the anonymous data
        # write everything in anonymization_lookup -> Parse it so we can
        # have dynamic fields
        for key in self.anonymization.keys():
            replacement_value = self.anonymization[key] % self
            try:
                self.dcm.data_element(key).value = replacement_value
            except KeyError:
                continue

            self.dcm.save_as(destination)

            if self.keep_original:
                shutil.copy(self.filename, destination)
            else:
                os.remove(self.filename)


class Sorter(Thread):
    def __init__(
            self,
            *,
            queue: Queue,
            source: str,
            target: str,
            sort_order: list,
            filename: str,
            anonymization: dict = {},
            keep_original: bool = True,
    ):
        self.queue = queue
        self.source = source
        self.target = target
        self.sort_order = sort_order
        self.filename = filename
        self.anonymization = anonymization
        self.keep_original = keep_original

        Thread.__init__(self)
        self.start()

    def sort_image(self, *, filename: str) -> None:
        Dicom(
            source=self.source,
            target=self.target,
            filename=self.filename,
            sort_order=self.sort_order,
            anonymization=self.anonymization,
            keep_original=self.keep_original
        )

    def run(self) -> None:
        while True:
            try:
                filename = self.queue.get_nowait()
                self.sort_image(filename=filename)
            # TODO: Rescue any other errors and quarantine the files
            except Empty:
                return


class DicomSorter:
    def __init__(
            self,
            *,
            source: str,
            target: str,
            sort_order: list = ['SeriesDescription'],
            filename: str = '%(ImageType)s_(%(InstanceNumber)04d)',
            anonymization: dict = {},
            keep_original: bool = True,
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
        self.source = source
        self.target = target
        self.sort_order = sort_order
        self.filename = filename
        self.anonymization = anonymization
        self.keep_original = keep_original
        self.queue = Queue()

    def sort(self) -> None:
        for root, _, files in os.walk(self.source):
            for filename in files:
                self.queue.put(os.path.join(root, filename))

        number_of_files = self.queue.qsize()

        for _ in range(min(THREAD_COUNT, number_of_files)):
            sorter = Sorter(
                queue=self.queue,
                source=self.source,
                target=self.target,
                filename=self.filename,
                sort_order=self.sort_order,
                anonymization=self.anonymization,
                keep_original=self.keep_original
            )
