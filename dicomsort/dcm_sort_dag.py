from airflow import DAG
from datetime import datetime
from operators.dicom_operator import DicomSortOperator


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['schragelab@education.wisc.edu'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    # 'retry_delay': timedelta(minutes=5),
    # 'queue': 'bash_queue',
    # 'pool': 'backfill',
    # 'priority_weight': 10,
    # 'end_date': datetime(2016, 1, 1),
    # 'wait_for_downstream': False,
    # 'dag': dag,
    # 'sla': timedelta(hours=2),
    # 'execution_timeout': timedelta(seconds=300),
    # 'on_failure_callback': some_function,
    # 'on_success_callback': some_other_function,
    # 'on_retry_callback': another_function,
    # 'sla_miss_callback': yet_another_function,
    # 'trigger_rule': 'all_success'
}
with DAG('DICOM_Sort', default_args=default_args, schedule_interval=None, start_date=datetime(2021, 8, 1), catchup=False) as DAG:
    dicom_sort = DicomSortOperator(
        task_id='dicom-sort',
        source='/media/schragelab/CDROM/a',
        target='/mnt/hgfs/bucket/asl/raw',
        ignore_all_except={
            'SeriesDescription': [
                '3D ASL',
                'UW eASL',
                'Ax T1',
                'mADNI'
            ]
        }
    )
