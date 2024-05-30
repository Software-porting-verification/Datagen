#! /usr/bin/env python3

####################################################
#
#
# fuzz dataset generator (per package)
#
# Author: Mao Yifu, maoif@ios.ac.cn
#
#
####################################################


import os
import sys
import argparse
import yaml
import socket
import time
import shutil


g_script_name = 'perf-fuzz-gen'
g_package: str = ''
g_version: str = ''
g_exe: str = ''
g_perf_dir_env: str = 'TREC_PERF_DIR'
g_perf_data_path = os.environ[g_perf_dir_env]
g_files_path = f'{g_perf_data_path}/fuzz/files'

ARG_FLAG    = 'op_flag'   # -v, --help
# TODO -I../lib
# ARG_OP     = 'op'     # --input bla, --files f1 f2
ARG_OP_ARG  = 'op_arg' # --quality=9, if=/dev/null
ARG_NUMBER  = 'op_num'
ARG_STRING  = 'op_str'
ARG_FILE    = 'op_file'
ARG_DIR     = 'op_dir'
ARG_URL     = 'op_url'
ARG_IP      = 'op_ip'
ARG_UNKNOWN = 'op_unknown'


def notice(msg: str = ''):
    print(f'[{g_script_name}] {msg}')


def is_number(n):
    is_number = True
    try:
        num = float(n)
    except ValueError:
        is_number = False
    return is_number


def is_url(s):
    for prefix in ['http://', 'https://', 'ftp://', 'file://', 'data://', 'ws://',
                   'socks4://', 'socks4a://', 'socks5://', 'socks5h://']:
        if s.startswith(prefix):
            return True
    return False


def is_ip(s):
    parts = s.split(':')
    if len(parts) <= 2:
        try:
            ignore = socket.inet_aton(parts[0])
            return True
        except OSError:
            return False

    return False


def is_file(s):
    if os.path.isfile(s):
        shutil.copy(s, g_files_path)
        return True
    
    return False


def is_dir(s):
    return os.path.isdir(s)


def classify_args(args: list[str]):
    results = []
    length = len(args)

    for i in range(length):
        arg = args[i]
        
        try:
            if arg.startswith('--') or arg.startswith('-'):
                if '=' in arg:
                    results.append({ ARG_OP_ARG : arg })
                else:
                    results.append({ ARG_FLAG : arg })
            elif is_url(arg):
                results.append({ ARG_URL : arg })
            elif is_number(arg):
                results.append({ ARG_NUMBER : arg })
            elif '=' in arg:
                # dd if=/dev/zero
                results.append({ ARG_OP_ARG : arg })
            elif is_ip(arg):
                results.append({ ARG_IP : arg })
            elif is_file(arg):
                results.append({ ARG_FILE : arg })
            elif is_dir(arg):
                results.append({ ARG_DIR : arg })
            else:
                # TODO maybe subcommands like `perf report`
                results.append({ ARG_UNKNOWN : arg })
        except TypeError:
            notice(f'classify_args error: {arg}')
            notice(f'in \n {args}')
            
    return results
            

def analyze_envs():
    pass


def analyze(args: list[str]):
    args_classified = classify_args(args[1:])
    fuzz = { 'package': g_package, 'version': g_version, 'exe': g_exe,
             'raw_args' : args, 'classified_args' : args_classified }

    return fuzz


###
### start of program
###

args = sys.argv

if len(args) < 3:
    print(f'Args length less than 3, need at least package name, version and exe path')
    exit(-1)

g_package = args[1]
g_version = args[2]
g_exe = args[3]
all_args = args[3:]

try:
    os.makedirs(g_files_path, exist_ok=True)
except OSError:
    notice(f'failed to create {g_files_path}')

fuzz = analyze(all_args)
fuzz_path = f'{g_perf_data_path}/fuzz/fuzz-{str(time.time())}'
with open(fuzz_path, 'w') as f_fuzz:
    yaml.dump(fuzz, f_fuzz)
    notice(f'fuzz dataset at {fuzz_path}')

