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


F_FAIL_ARG         = 0
F_FAIL_ENV         = 1
F_FAIL_PATH        = 2
F_INCOMPLETE_ARGS  = 3
F_INCOMPLETE_ENVS  = 4


class TraceDatum:
    def __init__(self):
        self.pid_tgid = False
        self.comm = False
        self.file_path = False
        self.args = []
        self.envs = []
        self.path_parts = []
        self.working_dir = False
        self.creator = ""
        self.flags = 0
        self.fail_arg = False
        self.fail_env = False
        self.fail_path = False
        self.incomplete_args = False
        self.incomplete_envs = False


    def __str__(self):
        return f"""
flags:     {bin(self.flags)}
fail_arg:  {self.fail_arg}
fail_env:  {self.fail_env}
fail_path: {self.fail_path}
incomplete_args: {self.incomplete_args}
incomplete_envs: {self.incomplete_envs}
pid_tgid: {self.pid_tgid}
caller:   {self.comm}
callee:   {self.file_path}
args:     {self.args}
envs:     {self.envs}
dir:      {self.working_dir}
        """


    def has_no(self, what):
        pass
        # print(f"One TraceDatum has no {what}")


    def check_fields(self):
        if not self.pid_tgid:
            self.has_no("pid_tgid")
            return False

        if not self.comm:
            self.has_no("comm")
            return False

        if not self.file_path:
            self.has_no("file_path")
            return False

        if self.args == []:
            self.has_no("args")
            return False

        # if self.envs == []:
        #     self.has_no("envs")
        #     return False

        if self.path_parts == []:
            self.has_no("working_dir")
            return False

        return True


    def assemble_working_dir(self):
        self.path_parts.reverse()
        self.working_dir = "/" + "/".join(self.path_parts)


    def parse_flags(self):
        if self.flags & (1 << F_FAIL_ARG) == F_FAIL_ARG:
            self.fail_arg = True

        if self.flags & (1 << F_FAIL_ENV) == F_FAIL_ENV:
            self.fail_env = True

        if self.flags & (1 << F_FAIL_PATH) == F_FAIL_PATH:
            self.fail_path = True

        if self.flags & (1 << F_INCOMPLETE_ARGS) == F_INCOMPLETE_ARGS:
            self.incomplete_args = True

        if self.flags & (1 << F_INCOMPLETE_ENVS) == F_INCOMPLETE_ENVS:
            self.incomplete_envs = True


    def prepare(self):
        self.parse_flags()
        self.assemble_working_dir()


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
    env = event.envs.decode('utf-8')

    d = get_trace_datum(ids, 'record_env')
    d.envs.append(env)


def record_path_part(ctx, data, size):
    event = b['events_path_part'].event(data)
    ids = event.pid_tgid
    path = event.path.decode('utf-8')

    d = get_trace_datum(ids, 'record_path_part')
    d.path_parts.append(path)


def skip_result(datum: TraceDatum):
    filter_prefixes = ['/bin/', '/usr/', '/sbin/']
    callee = datum.file_path
    for p in filter_prefixes:
       if callee.startswith(p):
            return True

    return False


def write_results(output_file):
    with open(output_file, 'w') as f:
        for d in g_trace_data.values():
            if skip_result(d):
                continue

            if d.check_fields():
                d.prepare()
                f.write(str(d))


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
parser.add_argument('-o', '--output', help='save the traces to file')

args = parser.parse_args()
output_file = ''
if args.output != None:
    output_file = args.output


# load BPF program
b = BPF(src_file="bcc-execve.c")

# register callbacks
# If things go well, this is the last callback in a sequence of events during an execve().
b["events_basic"].open_ring_buffer(record_basic)
b["events_arg"].open_ring_buffer(record_arg)
b["events_env"].open_ring_buffer(record_env)
b["events_path_part"].open_ring_buffer(record_path_part)

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
