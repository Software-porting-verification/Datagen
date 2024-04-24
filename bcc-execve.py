#! /usr/bin/env python3

####################################################
#
#
# execve() tracing facility
#
# Author: Mao Yifu, maoif@ios.ac.cn
#
#
####################################################


from bcc import BPF
import time
import argparse
import yaml
from trace_datum import *


g_trace_data: dict[int, TraceDatum] = {}

def get_trace_datum(pid_tgid, creator) -> TraceDatum:
    if pid_tgid in g_trace_data.keys():
        return g_trace_data[pid_tgid]
    else:
        d = TraceDatum()
        d.pid_tgid = pid_tgid
        d.creator = creator
        g_trace_data[pid_tgid] = d
        return d


def record_basic(ctx, data, size):
    event = b['events_basic'].event(data)
    ids = event.pid_tgid
    comm = event.comm.decode('utf-8')
    filename = event.filename.decode('utf-8')

    d = get_trace_datum(ids, 'record_basic')
    d.comm = comm
    d.file_path = filename
    d.flags = event.flags


def record_arg(ctx, data, size):
    event = b['events_arg'].event(data)
    ids = event.pid_tgid
    arg = ""
    try:
        arg = event.args.decode('utf-8')
    except UnicodeDecodeError:
        arg = event.args

    d = get_trace_datum(ids, 'record_arg')
    d.args.append(arg)


def record_env(ctx, data, size):
    event = b['events_env'].event(data)
    ids = event.pid_tgid
    env = ""
    try:
        env = event.envs.decode('utf-8')
    except UnicodeDecodeError:
        env = event.envs

    d = get_trace_datum(ids, 'record_env')
    d.envs.append(env)


def record_path_part(ctx, data, size):
    event = b['events_path_part'].event(data)
    ids = event.pid_tgid
    path = event.path.decode('utf-8')

    d = get_trace_datum(ids, 'record_path_part')
    d.path_parts.append(path)


def write_results(output_file):
    for d in g_trace_data.values():
        d.prepare()

    with open(output_file, 'w') as f:
        result = {'package' : package, 
                  'version' : version, 
                  'data'    : list(filter(lambda d: d.check_fields(), g_trace_data.values())) }
        yaml.dump(result, f)


def print_results():
    pass


###
### start of program
###

# TODO check sudo
# TODO store received data
# TODO parse results

parser = argparse.ArgumentParser(
    prog='bcc-execve',
    description='Analyze bpftrace data and generate dataset.')
parser.add_argument('-o', '--output', required=True, help='save the traces to file')
parser.add_argument('-p', '--package', required=True, help='package name')
parser.add_argument('-v', '--version', required=True, help='package version')

args = parser.parse_args()
output_file = ''
if args.output != None:
    output_file = args.output

package  = args.package
version  = args.version

# load BPF program
b = BPF(src_file="bcc-execve.c")

# register callbacks
# If things go well, this is the last callback in a sequence of events during an execve().
b["events_basic"].open_ring_buffer(record_basic)
b["events_arg"].open_ring_buffer(record_arg)
b["events_env"].open_ring_buffer(record_env)
b["events_path_part"].open_ring_buffer(record_path_part)

yaml.add_constructor(G_TRACEDATUM_TAG, trace_datum_constructor)

while True:
    try:
        b.ring_buffer_poll()
        time.sleep(0.1)
    except KeyboardInterrupt:
        if output_file == '':
            print_results()
        else:
            write_results(output_file)
        exit()
