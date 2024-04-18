//===----------------------------------------------------------------------===//
//
// Author: Mao Yifu, maoif@ios.ac.cn
//
// BPF program for execve() tracing.
//
//===----------------------------------------------------------------------===//

#include <linux/sched.h>
#include <linux/path.h>
#include <linux/fs_struct.h>
#include <linux/dcache.h>

#define MAX_STR_SIZE   (4096 - sizeof(u64))
#define PATH_SIZE      256
#define MAX_ARGS       32
#define MAX_ENVS       64
#define MAX_PATH_DEPTH 20

#define MAX_PATH_READ 32

#define F_FAIL_ARG        0
#define F_FAIL_ENV        1
#define F_FAIL_PATH       2
#define F_INCOMPLETE_ARGS 3
#define F_INCOMPLETE_ENVS 4

// Creates a ringbuf called events with N pages of space, shared across all CPUs
BPF_RINGBUF_OUTPUT(events_basic, 512);
BPF_RINGBUF_OUTPUT(events_arg, 512);
BPF_RINGBUF_OUTPUT(events_env, 512);
BPF_RINGBUF_OUTPUT(events_path_part, 512);

struct data_basic {
    u64  pid_tgid;
    u32 flags;
    char comm[TASK_COMM_LEN];
    char filename[PATH_SIZE];
};

// Each arg, env and path component is submitted to userspace individually
// to avoid having to track the char index into a single buffer,
// which would lead to boasted program size and verification failure.

struct data_arg {
    u64  pid_tgid;
    char args[MAX_STR_SIZE];
};

struct data_env {
    u64  pid_tgid;
    char envs[MAX_STR_SIZE];
};

struct data_path_part {
    u64  pid_tgid;
    char path[MAX_PATH_READ];
};

// From BCC virtiostat
/* local strcmp function, max length 8 to protect instruction loops */
#define CMPMAX	8

static int local_strcmp(const char *cs, const char *ct)
{
    int len = 0;
    unsigned char c1, c2;

    while (len++ < CMPMAX) {
        c1 = *cs++;
        c2 = *ct++;
        if (c1 != c2)
            return c1 < c2 ? -1 : 1;
        if (!c1)
            break;
    }
    return 0;
}

static void set_flag(u32 * flags, int flag) {
    u32 fgs = *flags;
    *flags = ((1 << flag) | fgs);
}

// Convenience macro for auto-attaching probes.
TRACEPOINT_PROBE(syscalls, sys_enter_execve) {
    struct data_basic * data_b = events_basic.ringbuf_reserve(sizeof(struct data_basic));
    if (data_b == NULL) {
        data_b = events_basic.ringbuf_reserve(sizeof(struct data_basic));
        if (data_b == NULL) {
            return 0;
        }
    }

    // need sudo to access `args` structure
    char ** arguments = args->argv;
    char ** envvars = args->envp;
    struct task_struct * t  = (struct task_struct *)bpf_get_current_task();
    struct fs_struct   * fs = (struct fs_struct *)(t->fs);

    bpf_get_current_comm(data_b->comm, sizeof(data_b->comm));
    bpf_probe_read_user_str(data_b->filename, sizeof(data_b->filename), args->filename);

    u64 pid_tgid = bpf_get_current_pid_tgid() ^ bpf_ktime_get_ns();
    data_b->pid_tgid = pid_tgid;
    data_b->flags = 0ul;

    // read commandline arguments
    int c = MAX_ARGS;
    while (c > 0) {
        if (*arguments == NULL) break;

        // Cannot reuse the same struct by reserving it outside the loop,
        // cause the verifier drops the reference of the buffer after ringbuf_submit().
        struct data_arg * data_a = events_arg.ringbuf_reserve(sizeof(struct data_arg));
        if (data_a == NULL) {
            // Need this to pass the verifier, otherwise there is dangling reference.
            // events_basic.ringbuf_discard(data_b, 0);
            data_a = events_arg.ringbuf_reserve(sizeof(struct data_arg));
            if (data_a == NULL) {
                set_flag(&data_b->flags, F_FAIL_ARG);
                events_basic.ringbuf_submit(data_b, 0 /* flags */);
                return 0;
            }
        }

        data_a->pid_tgid = pid_tgid;
        // bpf_probe_read_user_str() calls __builtin_memset() automatically,
        // hence no need to zero-init
        bpf_probe_read_user_str(data_a->args, sizeof(data_a->args), *arguments);

        arguments++;
        c--;
        events_arg.ringbuf_submit(data_a, 0);
    }

    if (c == 0 && *arguments != NULL) {
        set_flag(&data_b->flags, F_INCOMPLETE_ARGS);
    }

    // read environment variables
    c = MAX_ENVS;
    while (c > 0) {
        if (*envvars == NULL) break;

        struct data_env * data_e = events_env.ringbuf_reserve(sizeof(struct data_env));
        if (data_e == NULL) {
            data_e = events_env.ringbuf_reserve(sizeof(struct data_env));
            if (data_e == NULL) {
                set_flag(&data_b->flags, F_FAIL_ENV);
                events_basic.ringbuf_submit(data_b, 0 /* flags */);
                return 0;
            }
        }

        data_e->pid_tgid = pid_tgid;
        bpf_probe_read_user_str(data_e->envs, sizeof(data_e->envs), *envvars);

        envvars++;
        c--;
        events_env.ringbuf_submit(data_e, 0);
    }

    if (c == 0 && *envvars != NULL) {
        set_flag(&data_b->flags, F_INCOMPLETE_ENVS);
    }

    // read working dir
    c = MAX_PATH_DEPTH;
    struct dentry * d = fs->pwd.dentry;
    struct dentry * d_root = fs->root.dentry;
    while (c > 0) {
        // From Linux src dcache.h:
        //     #define IS_ROOT(x) ((x) == (x)->d_parent)
        // Also respect chroot by comparing with `d_root`.
        if (d == d_root || d == d->d_parent) break;
        // this is kernel data!
        const char * p = d->d_name.name;
        char buf[MAX_PATH_READ];
        bpf_probe_read_kernel_str(buf, MAX_PATH_READ, p);

        struct data_path_part * data_p = events_path_part.ringbuf_reserve(sizeof(struct data_path_part));
        if (data_p == NULL) {
            // events_basic.ringbuf_discard(data_b, 0);
            data_p = events_path_part.ringbuf_reserve(sizeof(struct data_path_part));
            if (data_p == NULL) {
                set_flag(&data_b->flags, F_FAIL_PATH);
                events_basic.ringbuf_submit(data_b, 0 /* flags */);
                return 0;
            }
        }

        data_p->pid_tgid = pid_tgid;
        bpf_probe_read_kernel_str(data_p->path, sizeof(data_p->path), p);

        d = d->d_parent;
        c--;
        events_path_part.ringbuf_submit(data_p, 0);
    }

    events_basic.ringbuf_submit(data_b, 0 /* flags */);

    return 0;
}
