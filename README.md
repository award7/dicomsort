DICOM Sort
================

[![CircleCI](https://circleci.com/gh/suever/dicomsort.svg?style=svg)](https://circleci.com/gh/suever/dicomsort)
[![Maintainability](https://api.codeclimate.com/v1/badges/0113af254aa8a5e7afa4/maintainability)](https://codeclimate.com/github/suever/dicomSort/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/0113af254aa8a5e7afa4/test_coverage)](https://codeclimate.com/github/suever/dicomSort/test_coverage)

DicomSort is a utility that takes a series of DICOM images and sorts them into
a directory tree based upon the header fields selected.

This software has the following dependencies:

* [wxPython 4.0.7](http://www.wxpython.org/download.php)
* [pydicom 1.3.0](https://github.com/pydicom/pydicom)

Windows binaries are available at [the project website](http://www.dicomsort.com).

To install from source, first clone the git repository

```
$ git clone https://github.com/suever/dicomSort.git
```

Install dependencies (if you haven't already)

```
$ pip install -r requirements.txt
```

Then you should be able to launch the software using the `DicomSort.pyw` file.

```
$ python DicomSort.pyw 
```

If you have any questions or would like to request a feature, feel free to 
provide feedback.
