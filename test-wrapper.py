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
g_wrap_method_env: str = 'TEST_WRAPPER_METHOD'

g_wrap_method = None


def notice(msg: str = ''):
    if g_dry_run:
        print(f'[test-wrapper dry run] {msg}')
    else:
        print(f'[test-wrapper] {msg}')


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
    
    exe_base = os.path.basename(exe)
    exe_backup = f'{exe}.perf-bin'
    out_perf_data = f'{exe_base}.perf.data'

    if g_dry_run:
        notice(f'mv {exe}')
        notice(f'to {exe_backup}\n')
    else:
        notice(f'mv {exe}')
        notice(f'to {exe_backup}\n')
        shutil.move(exe, exe_backup)

    exe_script_perf=f"""
#!/usr/bin/env bash

mkdir -p {g_perf_data_path}/errors/

/usr/bin/rvbench-tools/perf-fuzz-gen.py $RPM_PACKAGE_NAME $RPM_PACKAGE_VERSION {exe} "$@"

SUFIX=$(date +%N_%F_%T)
perf record -F 9999 -e instructions:u -g --user-callchains \\
    -o {g_perf_data_path}/{out_perf_data}.$SUFIX {exe_backup} "$@" \\
    2>> {g_perf_data_path}/errors/{out_perf_data}.$SUFIX
"""

    exe_cov_real = f'{exe}_cov.real'
    
    # exe wrapper
    exe_script_coverage=f"""
#!/usr/bin/env bash
exec fish {exe_cov_real} "$@"
"""

    # true exe wrapper, written as `exe_cov_real`
    # need this indirection because OBS uses sh only
    exe_script_coverage_real=f"""
#!/usr/bin/env fish

set ID (date +%N_%F_%T)
export LLVM_PROFILE_FILE=$TREC_PERF_DIR/{exe_base}_$ID.profraw

# If exe path is a symlink, then it's a link to a wrap script,
# just run the script to avoid generating two profile data.
file {exe_backup} | grep --quiet 'symbolic link'
if test $status -eq 0
    {exe_backup} $argv
else
    {exe_backup} $argv
    if test -e $TREC_PERF_DIR/{exe_base}_$ID.profraw
        for i in (ldd {exe_backup} | grep '=>' | cut -d ' ' -f3)
            objdump -h $i | grep --quiet -E '__llvm_prf|__llvm_cov'
            if test $status -eq 0
                objdump -h (realpath $i) >> $TREC_PERF_DIR/{exe_base}_$ID.debug
                echo (realpath $i) >> $TREC_PERF_DIR/{exe_base}_$ID.sos
                set objs $objs -object $i
            end
        end

        llvm-profdata merge -sparse $TREC_PERF_DIR/{exe_base}_$ID.profraw -o $TREC_PERF_DIR/{exe_base}_$ID.prodata
        llvm-cov show {exe_backup} -instr-profile $TREC_PERF_DIR/{exe_base}_$ID.prodata -format=html -output-dir=$TREC_PERF_DIR/{exe_base}_$ID_report $objs &> $TREC_PERF_DIR/a_cov_show.log
        llvm-cov report -instr-profile $TREC_PERF_DIR/{exe_base}_$ID.prodata {exe_backup} $objs &> $TREC_PERF_DIR/{exe_base}_$ID.report
    end
end
"""

    if g_wrap_method == 'perf':
        exe_script = exe_script_perf
    elif g_wrap_method == 'cov':
        exe_script = exe_script_coverage
    else:
        notice('Unknown wrap method')
        exit(-1)

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

        if g_wrap_method == 'cov':
            with open(exe_cov_real, 'w') as f:
                f.write(exe_script_coverage_real)

    return True


###
### start of program
###

parser = argparse.ArgumentParser(
    prog='test-wrapper',
    description='Replace executables with testing scripts.')
parser.add_argument('-p', '--package', required=True, help='package name')
parser.add_argument('-v', '--version', required=True, help='package version')
parser.add_argument('-d', '--dry', action='store_true', help='dry run, without real replacing')

args = parser.parse_args()

g_package  = args.package
g_version  = args.version
g_dataset_path = f"/usr/lib64/rvbench/{g_package}-{g_version}-perf"
g_dry_run = args.dry

if not os.path.exists(g_dataset_path):
    notice(f'Dataset {g_dataset_path} not found, quitting...')
    exit(-1)
elif os.path.isdir(g_dataset_path):
    notice(f'Dataset {g_dataset_path} is not a file, quiting...')
    exit(-1)

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

if g_wrap_method_env in os.environ.keys():
    v = os.environ[g_wrap_method_env]
    if v == 'perf':
        g_wrap_method = v
    elif v == 'cov':
        g_wrap_method = v
    else:
        notice(f'Bad {g_wrap_method_env} value')

if not g_perf_dir_env in os.environ.keys():
    notice('env TREC_PERF_DIR not set, quitting...')
    exit(-1)

g_perf_data_path = os.environ[g_perf_dir_env]
if not os.path.isdir(g_perf_data_path):
    notice(f'{g_perf_data_path} is not a dir, quiting...')
    exit(-1)

notice(f'env {g_perf_dir_env}: {g_perf_data_path}')

with open(g_dataset_path, 'r') as f:
    exes = yaml.load(f, Loader=yaml.Loader)
    true_exes = []
    for exe in exes:
        if wrap(exe):
            true_exes.append(exe)
    
    if not true_exes == []:
        with open(f'{g_perf_data_path}/{g_package}_{g_version}.refinement', 'w') as f_refine:
            yaml.dump(true_exes, f_refine)