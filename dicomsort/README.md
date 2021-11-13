# DICOM Sort: Non-GUI use and Airflow integration

This tool was adapted from https://github.com/dicomsort/dicomsort to allow integration with other programs via import, 
including Airflow. 


## Requirements

`pydicom`

`airflow` (if using the operator)

## Usage

Clone the repo and add the repo path to your `PYTHONPATH`.

### Import

Import the class

`from dicomsorter import DicomSorter`

Instantiate the class

`dcm = DicomSorter(source=source, target=target)`

Call the sort method

`dcm.sort()`

### Airflow

Copy the `dicom_operator.py` file to your `AIRFLOW_HOME/plugins` directory. In your DAG, import the operator. Use
keyword arguments in the DicomSortOperator instantiation. See `dcm_sort_dag.py` for an example DAG using the operator.


## Parameters

`source` (str): the path to unsorted DICOM files.

`target` (str): the destination path to land the sorted DICOM files.

`filename` (str): the filename to apply to the files as they are sorted. Can use DICOM attributes in name by specifying
the attribute name in `printf`-style string. Default = 'Image_(%(InstanceNumber)04d)'.

`sort_order` (List[str]): the order in which to sort the raw DICOM files. Can be any DICOM attribute. Note: 
'SeriesDescription' will always be the final sorting criteria to avoid ambiguity in the sorting process and therefore it 
is not necessary to specify. Default = ['PatientName'].

`anonymization` (dict): key-value pairs of DICOM attributes and the new values to apply to the sorted files. 
Default = None.

`keep_original` (bool): specification as to deleting the original, unsorted DICOM files in the `source` directory. 
Default = False. 

`ignore` (dict): key-value pairs of DICOM attributes to ignore with the given value. Default = None.