#! /usr/bin/env python3

import yaml


F_FAIL_ARG         = 0
F_FAIL_ENV         = 1
F_FAIL_PATH        = 2
F_INCOMPLETE_ARGS  = 3
F_INCOMPLETE_ENVS  = 4

G_TRACEDATUM_TAG = u'!!bcc_trace_datum'

package = ''
version = ''

class TraceDatum(yaml.YAMLObject):
    yaml_tag = G_TRACEDATUM_TAG

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
        if self.flags & (1 << F_FAIL_ARG) == (1 << F_FAIL_ARG):
            self.fail_arg = True

        if self.flags & (1 << F_FAIL_ENV) == (1 << F_FAIL_ENV):
            self.fail_env = True

        if self.flags & (1 << F_FAIL_PATH) == (1 << F_FAIL_PATH):
            self.fail_path = True

        if self.flags & (1 << F_INCOMPLETE_ARGS) == (1 << F_INCOMPLETE_ARGS):
            self.incomplete_args = True

        if self.flags & (1 << F_INCOMPLETE_ENVS) == (1 << F_INCOMPLETE_ENVS):
            self.incomplete_envs = True


    def prepare(self):
        self.parse_flags()
        self.assemble_working_dir()


def trace_datum_constructor(loader, node):
    value = loader.construct_mapping(node)

    d = TraceDatum()
    d.pid_tgid = value['pid_tgid']
    d.comm = value['comm']
    d.file_path = value['file_path']
    d.args = value['args']
    d.envs = value['envs']
    d.working_dir = value['working_dir']
    d.flags = value['flags']
    d.fail_arg = value['fail_arg']
    d.fail_env = value['fail_env']
    d.fail_path = value['fail_path']
    d.incomplete_args = value['incomplete_args']
    d.incomplete_envs = value['incomplete_envs']
    d.path_parts = []
    d.creator = ''

    return d


yaml.add_constructor(G_TRACEDATUM_TAG, trace_datum_constructor)

