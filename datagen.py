#! /usr/bin/env python3

####################################################
#
#
# dataset generator
#
# Author: Mao Yifu, maoif@ios.ac.cn
#
#
####################################################

import sys
import argparse
import yaml
import trace_datum
from trace_datum import *


g_package: str = ''
g_version: str = ''

def analyze_args():
    pass


def analyze_envs():
    pass


def filter_result(datum: TraceDatum):
    # TODO filter .sh?

    filter_prefixes = ['/bin/', '/usr/', '/sbin/', '/snap/', '/opt/', '/tmp/', '/etc/']
    callee = datum.file_path
    for p in filter_prefixes:
       if callee.startswith(p):
            return False

    filter_suffixes = ['./conftest', './configure', '.build.command', '/bin/sh', '/.', '.sh']
    for p in filter_suffixes:
       if callee.endswith(p):
            return False

    filter_infixes = ['./exec.cmd']
    for p in filter_infixes:
       if p in callee:
            return False

    return datum.check_fields()


def analyze_for_perf(data: list[TraceDatum]):
    # TODO need manual filtering of scripts/binaries? Maybe do this later
    for d in data:
        exe = d.file_path
        # caller's working dir
        pwd = d.working_dir

        # convert to absolute path
        if not exe.startswith('/'):
            exe = pwd + '/' + exe

        d.file_path = exe


def analyzer_for_fuzz(data: list[TraceDatum]):
    # fuzz data should not be deduplicated
    return []


def analyze(data: list[TraceDatum]):
    filtered = list(filter(lambda d: filter_result(d), data))
    analyze_for_perf(filtered)
    fuzz = analyzer_for_fuzz(filtered)
    
    perf = list(set([d.file_path for d in filtered]))

    return fuzz, perf



###
### start of program
###

parser = argparse.ArgumentParser(
    prog='datagen',
    description='Analyze bpftrace data and generate dataset.')
parser.add_argument('-f', '--files', nargs='+', required=True, help='trace files in yaml format')

args = parser.parse_args()

trace_files = args.files
for tf in trace_files:
    with open(tf, 'r') as f:
        print(f'loading {tf}')
        data = yaml.load(f, Loader=yaml.Loader)
        print(f'loading {tf} done')
        g_package = data['package']
        g_version = data['version']
        fuzz, perf = analyze(data['data'])
        # TODO format of fuzz and perf dataset
        
        fuzz_path = f'{g_package}-{g_version}-fuzz'
        perf_path = f'{g_package}-{g_version}-perf'
        # with open(fuzz_path, 'w') as f_fuzz:
            # print(f'{tf} fuzz dataset at {fuzz_path}')
            # pass
        with open(perf_path, 'w') as f_perf:
            yaml.dump(perf, f_perf)
            print(f'{tf} perf dataset at {perf_path}')

            
        # print(f"{len(data['data'])}")