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


class TraceDatum:
    def __init__(self):
        self.pid_tgid = False
        self.comm = False
        self.file_path = False
        self.args = []
        self.envs = []
        self.path_parts = []
        self.working_dir = False


    def __str__(self):
        return f"""
caller: {self.comm}
callee: {self.file_path}
args:   {self.args}
envs:   {self.envs}
dir:    {self.working_dir}
        """


    def has_no(self, what):
        print(f"One TraceDatum has no {what}")


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


g_trace_data: dict[int, TraceDatum] = {}

def get_trace_datum(pid_tgid) -> TraceDatum:
    if pid_tgid in g_trace_data.keys():
        return g_trace_data[pid_tgid]
    else:
        d = TraceDatum()
        d.pid_tgid = pid_tgid
        g_trace_data[pid_tgid] = d
        return d


def record_basic(ctx, data, size):
    event = b['events_basic'].event(data)
    ids = event.pid_tgid
    comm = event.comm.decode('utf-8')
    filename = event.filename.decode('utf-8')

    d = get_trace_datum(ids)
    d.comm = comm
    d.file_path = filename
    # TODO check and parse data, working dir

    if not d.check_fields():
        print(f"Bad TraceDatum: {d}")
        del g_trace_data[ids]
        return

    d.assemble_working_dir()

    print(f"ids: {ids}, comm: {comm}, callee: {filename}")


def record_arg(ctx, data, size):
    event = b['events_arg'].event(data)
    ids = event.pid_tgid
    arg = event.args.decode('utf-8')

    d = get_trace_datum(ids)
    d.args.append(arg)

    print(f"ids: {ids}, arg: {arg}")


def record_env(ctx, data, size):
    event = b['events_env'].event(data)
    ids = event.pid_tgid
    env = event.envs.decode('utf-8')

    d = get_trace_datum(ids)
    d.envs.append(env)

    print(f"ids: {ids}, env: {env}")


def record_path_part(ctx, data, size):
    event = b['events_path_part'].event(data)
    ids = event.pid_tgid
    path = event.path.decode('utf-8')

    d = get_trace_datum(ids)
    d.path_parts.append(path)

    print(f"ids: {ids}, path: {path}")


def write_out():
    with open('execve-data.txt', 'w') as f:
        for d in g_trace_data.values():
            f.write(str(d))

# TODO check sudo
# TODO store received data


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
        write_out()
        exit()
