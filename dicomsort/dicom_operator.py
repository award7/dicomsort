from airflow.models.baseoperator import BaseOperator
from dicomsort.dicomsorter import DicomSorter
from typing import Any


class DicomSortOperator(BaseOperator):
    def __init__(
            self,
            *,
            source: str,
            target: str,
            filename: str = 'Image_(%(InstanceNumber)04d)',
            sort_order: list = ['ProtocolName', 'PatientName'],
            anonymization: dict = {},
            keep_original=True,
            **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.source = source
        self.target = target
        self.filename = filename
        self.sort_order = sort_order
        self.anonymization = anonymization
        self.keep_original = keep_original

    def execute(self, context: Any) -> None:
        dcm = DicomSorter(
            source=self.source,
            target=self.target,
            filename=self.filename,
            sort_order=self.sort_order,
            anonymization=self.anonymization,
            keep_original=self.keep_original
        )
        dcm.sort()
