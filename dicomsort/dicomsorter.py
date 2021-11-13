import re
import os
import pydicom
from queue import Empty, Queue
from threading import Thread
from pydicom.errors import InvalidDicomError
from typing import Optional

THREAD_COUNT = 2


class DicomSorter:
    def __init__(
            self,
            *,
            source: str,
            target: str,
            filename: Optional[str] = None,
            sort_order: Optional[list] = None,
            anonymization: Optional[dict] = None,
            keep_original=True,
            ignore: Optional[dict] = None,
            ignore_all_except: Optional[dict] = None
    ):
        self.source = source
        self.target = target
        if not filename:
            self.filename = 'Image_(%(InstanceNumber)04d)'
        if not sort_order:
            self.sort_order = ['PatientName']
        self.anonymization = anonymization
        self.keep_original = keep_original
        self.ignore = ignore
        self.ignore_all_except = ignore_all_except

    def sort(self) -> None:
        file_queue = Queue()
        for root, _, files in os.walk(self.source):
            for filename in files:
                file_queue.put(os.path.join(root, filename))

        number_of_files = file_queue.qsize()

        for _ in range(min(THREAD_COUNT, number_of_files)):
            sorter = Sorter(
                queue=file_queue,
                source=self.source,
                target=self.target,
                filename=self.filename,
                sort_order=self.sort_order,
                anonymization=self.anonymization,
                keep_original=self.keep_original

            )
            sorter.run()


class Sorter(Thread):
    def __init__(
            self,
            *,
            queue: Queue,
            source: str,
            target: str,
            filename: Optional[str] = None,
            sort_order: Optional[list] = None,
            anonymization: Optional[dict] = None,
            keep_original=True,
            ignore: Optional[dict] = None,
    ):
        self.queue = queue
        self.source = source
        self.target = target
        self.sort_order = sort_order
        self.filename = filename
        self.anonymization = anonymization
        self.keep_original = keep_original
        self.ignore = ignore

        Thread.__init__(self)
        self.start()

    def run(self) -> None:
        while True:
            try:
                raw_file = self.queue.get_nowait()
                Dicom(
                    source=self.source,
                    target=self.target,
                    raw_file=raw_file,
                    filename=self.filename,
                    sort_order=self.sort_order,
                    anonymization=self.anonymization,
                    keep_original=self.keep_original,
                    ignore=self.ignore
                )
            # TODO: Rescue any other errors and quarantine the files
            except Empty:
                return


class Dicom:
    def __init__(
            self,
            *,
            source: str,
            target: str,
            raw_file: str,
            filename: Optional[str] = None,
            sort_order: Optional[list] = None,
            anonymization: Optional[dict] = None,
            keep_original=True,
            ignore: Optional[dict] = None,
            ignore_all_except: Optional[dict] = None
    ) -> None:
        """
        Takes a dicom filename in and returns instance that can be used to sort
        """
        self.source = source
        self.target = target
        self.raw_file = raw_file
        self.filename = filename
        self.sort_order = sort_order
        self.anonymization = anonymization
        self.keep_original = keep_original
        self.ignore = ignore
        self.ignore_all_except = ignore_all_except

        # Load the DICOM object
        try:
            self.dcm = pydicom.read_file(self.raw_file)
        except InvalidDicomError:
            return

        try:
            # ignore_all_except overrides ignore by simply skipping the check to _ignore_checker()
            if self.ignore_all_except:
                self._ignore_all_except_checker()
            elif self.ignore:
                self._ignore_checker()
        except ValueError:
            return

        if self.anonymization:
            self._anonymize()
        self.sort()

        # remove original file if indicated
        if not self.keep_original:
            os.remove(self.filename)

    def __getitem__(self, attr):
        """
        Points the reference to the property unless an override is specified
        """
        return getattr(self.dcm, attr)

    def _file_extension(self) -> str:
        _, extension = os.path.splitext(self.raw_file)
        if not extension:
            extension = '.dcm'
        return extension

    def _series_description(self):
        out = '%s_Series_%04d' % (self.dcm.SeriesDescription, self.dcm.SeriesNumber)

        # Strip so we don't have any leading/trailing spaces
        return out.strip()

    def _build_sorted_path(self) -> str:
        new_path = self.target
        if 'SeriesDescription' in self.sort_order:
            # move SeriesDescription to end of sort order
            self.sort_order.remove('SeriesDescription')
        self.sort_order.append('SeriesDescription')
        for item in self.sort_order:
            if item == 'SeriesDescription':
                value = self._series_description()
            else:
                value = getattr(self.dcm, item)
            regex = re.compile(r'[\W]+')
            cleaned_item = re.sub(regex, '_', str(value))
            new_path = os.path.join(new_path, cleaned_item)
        return new_path

    def _build_filename(self) -> str:
        value = self.recursive_replace_tokens(self.filename, self)
        ext = self._file_extension()
        filename = f'{value}{ext}'
        return filename

    def _anonymize(self) -> None:
        for key in self.anonymization.keys():
            replacement_value = self.anonymization[key] % self
            try:
                self.dcm.data_element(key).value = replacement_value
            except KeyError:
                continue

    def sort(self) -> None:
        new_path = self._build_sorted_path()
        os.makedirs(new_path, exist_ok=True)
        new_file = self._build_filename()
        self.dcm.save_as(os.path.join(new_path, new_file))

    @staticmethod
    def recursive_replace_tokens(format_string, repobj):
        max_rep = len(re.findall(r'%', format_string))
        rep = 0

        # look for an instance of '%' and capture everything in the parenthesis
        while re.search(r'%(.*)', format_string) and rep < max_rep:
            format_string = format_string % repobj
            rep = rep + 1

        regex = re.compile(r'\s')
        cleaned_string = re.sub(regex, '_', format_string)
        return cleaned_string

    def _ignore_checker(self) -> None:
        # raise exception if found to match
        try:
            for key, val in self.ignore.items():
                dicom_attribute = getattr(self.dcm, key)
                if val == dicom_attribute:
                    raise ValueError
        except AttributeError:
            # to catch if self.ignore is None
            pass

    def _ignore_all_except_checker(self) -> None:
        # raise exception if not found to match (inversion of _ignore_checker)
        for key, val in self.ignore_all_except.items():
            dicom_attribute = str(getattr(self.dcm, key))
            if isinstance(val, str):
                if val.lower() in dicom_attribute.lower():
                    return
                else:
                    raise ValueError
            elif isinstance(val, list):
                if any([item for item in val if item.lower() in dicom_attribute.lower()]):
                    return
                else:
                    raise ValueError

