"""
Script for submitting stochastic release model jobs to Moab
"""
import os, subprocess

from aisynphys.database import default_db as db


qsub_template = """#!/bin/bash
#PBS -q {queue_name}
#PBS -N {job_id}
#PBS -r n
#PBS -l ncpus=88,mem=32g,walltime=04:00:00
#PBS -o {log_path}/{job_id}.out
#PBS -j oe
source {conda_path}/bin/activate {conda_env}
python {aisynphys_path}/tools/stochastic_release_model.py --cache-path={cache_path} --no-gui {expt_id} {pre_cell_id} {post_cell_id} > {log_path}/{job_id}.log 2>&1
"""

base_path = os.getcwd()
conda_path = base_path + '/miniconda3'
cache_path = base_path + '/cache'
log_path = base_path + '/log'
aisynphys_path = base_path + '/aisynphys'
for d in [cache_path, log_path, aisynphys_path, conda_path]:
    assert os.path.isdir(d), f'Missing path: {d}'

job_id = 'synphys_model_test'
#queue_name = 'aibs_dbg'
queue_name = 'celltypes'

pairs = db.pair_query(synapse=True).all()

for pair in pairs:
    expt_id = pair.experiment.ext_id
    pre_cell_id = pair.pre_cell.ext_id
    post_cell_id = pair.post_cell.ext_id

    job_id = f'{expt_id}_{pre_cell_id}_{post_cell_id}'

    if os.path.exists(f'{cache_path}/{job_id}.pkl'):
        print(f'{job_id} => SKIP')
        continue

    qsub = qsub_template.format(
        queue_name=queue_name,
        job_id=job_id,
        base_path=base_path,
        log_path=log_path,
        cache_path=cache_path,
        conda_path=conda_path,
        aisynphys_path=aisynphys_path,
        conda_env='aisynphys',
        expt_id=expt_id,
        pre_cell_id=pre_cell_id,
        post_cell_id=post_cell_id,
    )

    qsub_file = f'{log_path}/{job_id}.qsub'
    open(qsub_file, 'w').write(qsub)

    sub_id = subprocess.check_output(f'qsub {qsub_file}', shell=True).decode().strip()
    open(qsub_file, 'a').write(f"\n# {sub_id}\n")

    print(f"{job_id} => {sub_id}")
