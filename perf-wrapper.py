#! /usr/bin/env python3

####################################################
#
#
# perf command wrapper
#
# Author: Mao Yifu, maoif@ios.ac.cn
#
#
####################################################

import shutil
import os
import subprocess
import yaml
import argparse

g_package: str = ''
g_version: str = ''
g_dataset_path: str = ''
g_perf_data_path: str = ''
g_perf_dir_env: str = 'TREC_PERF_DIR'
g_perf_dry_run_env: str = 'PERF_WRAPPER_DRY_RUN'
g_dry_run: bool = False


def notice(msg: str = ''):
    if g_dry_run:
        print(f'[perf-wrapper dry run] {msg}')
    else:
        print(f'[perf-wrapper] {msg}')


def wrap(exe: str) -> bool:
    # check existence, is binary, etc.
    if not os.path.exists(exe):
        notice(f'{exe} not found, skipping')
        return False
    elif not os.path.isfile(exe):
        return False
    else:
        # check 'ASCII text' or 'ELF'
        res = subprocess.run(["file", exe], capture_output=True, text=True)
        res.check_returncode()
        if 'ASCII text' in res.stdout:
            # skip non-binaries
            notice(f'{exe} is not binary, skipping')
            # subprocess.run(["cat", exe])
            notice()
            return False
    
    base_exe = os.path.basename(exe)
    backup = f'{exe}.perf-bin'
    out = f'{base_exe}.perf.data'

    if g_dry_run:
        notice(f'mv {exe}')
        notice(f'to {backup}\n')
    else:
        notice(f'mv {exe}')
        notice(f'to {backup}\n')
        shutil.move(exe, backup)
    
    # TODO parameterize more? e.g., by reading envs
    exe_script=f"""
#!/usr/bin/env bash

SUFIX=$(date +%N_%F_%T)
perf record -F 999 -e instructions:u -ag --user-callchains \\
    -o {g_perf_data_path}/{out}.$SUFIX {backup} "$@" 2>> {g_perf_data_path}/errors.{out}.$SUFIX
"""

    if g_dry_run:
        notice(f'writing {exe} as\n{exe_script}')
        notice()
    else:
        with open(exe, 'w') as f:
            f.write(exe_script)
            notice(f'writing {exe} as\n{exe_script}')
            notice()

        res = subprocess.run(["chmod", "+x", exe])
        res.check_returncode()
        notice(f'written wrapper {exe}')

    return True


###
### start of program
###

parser = argparse.ArgumentParser(
    prog='perf-wrapper',
    description='Replace executables with perf testing scripts.')
parser.add_argument('-p', '--package', required=True, help='package name')
parser.add_argument('-v', '--version', required=True, help='package version')
parser.add_argument('-d', '--dry', action='store_true', help='dry run, without real replacing')

args = parser.parse_args()

g_package  = args.package
g_version  = args.version
g_dataset_path = f"/usr/lib64/rvbench/{g_package}-{g_version}-perf"
g_dry_run = args.dry

if g_perf_dry_run_env in os.environ.keys():
    v = os.environ[g_perf_dry_run_env]
    if v == 'ON':
        g_dry_run = True
    elif v == 'OFF':
        g_dry_run = False
    else:
        notice(f'Bad {g_perf_dry_run_env} value, default to OFF')

if g_dry_run:
    notice('running in dry run mode')

# look for dataset in appropriate location
# search for each executable in the dataset
# rename and replace

# 1. rename: mv exe exe.perf-bin
# 2. wrap: 
# exe.perf-bin -> 
# #!/bin/env bash
# perf record ... exe.perf-bin -o perf.data

# TODO check package name and version

if not os.path.exists(g_dataset_path):
    notice(f'Dataset {g_dataset_path} not found, quitting...')
    exit(-1)
elif os.path.isdir(g_dataset_path):
    notice(f'Dataset {g_dataset_path} is not a file, quiting...')
    exit(-1)

if not g_perf_dir_env in os.environ.keys():
    notice('env TREC_PERF_DIR not set, quitting...')
    exit(-1)

g_perf_data_path = os.environ[g_perf_dir_env]
if not os.path.isdir(g_perf_data_path):
    notice(f'{g_perf_data_path} is not a dir, quiting...')
    exit(-1)

notice(f'perf data will be stored in {g_perf_data_path}')

with open(g_dataset_path, 'r') as f:
    exes = yaml.load(f, Loader=yaml.Loader)
    true_exes = []
    for exe in exes:
        if wrap(exe):
            true_exes.append(exe)
    
    if not true_exes == []:
        with open(f'{g_perf_data_path}/{g_package}_{g_version}.refinement', 'w') as f_refine:
            yaml.dump(true_exes, f_refine)