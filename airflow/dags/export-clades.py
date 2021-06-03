import yaml
import datetime

# The DAG object; we'll need this to instantiate a DAG
from airflow import DAG

# Operators; we need this to operate!
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.hooks.base import BaseHook
from airflow.models import Variable

# These args will get passed on to each operator
# You can override them on a per-task basis during operator initialization

from airflow.contrib.operators.slack_webhook_operator import SlackWebhookOperator

import os
import sys
import pathlib

p = os.path.abspath(str(pathlib.Path(__file__).parent.absolute()) + '/../../python/')
if p not in sys.path:
    sys.path.append(p)

from export_sequences import export_sequences
from export_meta import export_meta

WORKING_DIR = Variable.get("WORKING_DIR")

SLACK_CONN_ID = 'slack'

default_args = {
    'owner': 'sweaver',
    'depends_on_past': False,
    'email': ['sweaver@temple.edu'],
    'email_on_failure': False,
    'email_on_retry': False,
    'params' : {
        'working_dir' : WORKING_DIR,
        'region_cfg' : "/data/shares/veg/SARS-CoV-2/SARS-CoV-2-devel/airflow/libs/regions.yaml",
        'date' : datetime.date.today().strftime('%Y-%m-%d')
    },
    'retries': 1,
    'retry_delay': datetime.timedelta(minutes=5)
}

with DAG(
    'export_clades',
    default_args=default_args,
    description='exports clades',
    schedule_interval='@weekly',
    start_date=datetime.datetime(2021, 6, 2),
    on_failure_callback=dag_fail_slack_alert,
    on_success_callback=dag_success_slack_alert,
    tags=['export'],
    ) as dag:

    with open(dag.params["region_cfg"], 'r') as stream:
        regions = yaml.safe_load(stream)

    last_exec_date = dag.get_latest_execution_date()

    if last_exec_date is None:
        last_exec_date = datetime.datetime(year=1970, month=1, day=1)

    unique_id = str(round(last_exec_date.timestamp()))
    directory_output = WORKING_DIR + "/data/exports/whole-genome-clades/" + unique_id + "/"

    default_args['meta-output'] = directory_output + '/master-no-fasta.json'

    mk_dir_task = BashOperator(
        task_id='make_directory',
        bash_command='mkdir -p {{params.directory_output}}',
        params={"directory_output": directory_output},
        dag=dag,
    )

    export_meta_task = PythonOperator(
            task_id='export_meta',
            python_callable=export_meta,
            op_kwargs={ "config" : default_args['params'] },
            dag=dag,
        )

    export_meta_task.set_upstream(mk_dir_task)

    clades = [
        "B.1.2",
        "B.1.596",
        "B.1",
        "B.1.1.519",
        "B.1.243",
        "B.1.234",
        "B.1.526.1",
        "B.1.1",
        "B.1.526.2",
        "B.1.575",
        "R.1",
        "B.1.1.7",
        "B.1.429",
        "B.1.427",
        "B.1.351",
        "P.1",
        "B.1.526",
        "P.2",
        "B.1.525",
        "B.1.617"
        ]

    for clade in clades:

        params = {}

        params["sequence-output"] = directory_output + '/' + clade + '.fas'
        params['only-uniques'] = False
        params["clades"] = [clade]

        export_sequences_task = PythonOperator(
                task_id=f'export_sequences_{clade}',
                python_callable=export_sequences,
                op_kwargs={ "config" : params },
                dag=dag,
            )

        export_sequences_task.set_upstream(mk_dir_task)

