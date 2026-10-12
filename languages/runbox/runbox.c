/*
 * runbox: runs one program inside a sandbox container and reports how it went.
 *
 * Usage: runbox <cpu_ms> <wall_ms> <output_bytes> <file_bytes> -- <command> [args...]
 *
 * The child inherits stdin. Its stdout and stderr go to temp files. Every file
 * it writes, those two included, is capped at file_bytes (RLIMIT_FSIZE, so
 * writing more fails with EFBIG or kills it with SIGXFSZ). At most
 * output_bytes of each stream are reported back.
 * When the child exits, runbox prints one header line followed by the raw
 * stdout bytes and then the raw stderr bytes:
 *
 *   RUNBOX exit=0 signal=0 cpu_ms=12 wall_ms=15 mem_kb=9000 timed_out=0 stdout=3 stderr=0
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static long now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

static int open_capture(const char *tmpl, char *path) {
    strcpy(path, tmpl);
    int fd = mkstemp(path);
    if (fd < 0) {
        perror("runbox: mkstemp");
        exit(2);
    }
    return fd;
}

static long copy_out(int fd, long limit) {
    char buf[8192];
    long total = 0;
    lseek(fd, 0, SEEK_SET);
    while (total < limit) {
        long want = limit - total < (long)sizeof buf ? limit - total : (long)sizeof buf;
        ssize_t n = read(fd, buf, want);
        if (n <= 0) break;
        fwrite(buf, 1, n, stdout);
        total += n;
    }
    return total;
}

static long file_size(int fd, long limit) {
    struct stat st;
    if (fstat(fd, &st) != 0) return 0;
    return st.st_size < limit ? st.st_size : limit;
}

int main(int argc, char **argv) {
    if (argc < 7 || strcmp(argv[5], "--") != 0) {
        fprintf(stderr, "usage: runbox <cpu_ms> <wall_ms> <output_bytes> <file_bytes> -- <command> [args...]\n");
        return 2;
    }
    long cpu_ms = atol(argv[1]);
    long wall_ms = atol(argv[2]);
    long output_bytes = atol(argv[3]);
    long file_bytes = atol(argv[4]);

    char out_path[64], err_path[64];
    int out_fd = open_capture("/tmp/runbox-out-XXXXXX", out_path);
    int err_fd = open_capture("/tmp/runbox-err-XXXXXX", err_path);

    long start = now_ms();
    pid_t pid = fork();
    if (pid < 0) {
        perror("runbox: fork");
        return 2;
    }
    if (pid == 0) {
        setpgid(0, 0);
        struct rlimit cpu = {(cpu_ms + 999) / 1000 + 1, (cpu_ms + 999) / 1000 + 2};
        setrlimit(RLIMIT_CPU, &cpu);
        struct rlimit fsize = {file_bytes, file_bytes};
        setrlimit(RLIMIT_FSIZE, &fsize);
        dup2(out_fd, STDOUT_FILENO);
        dup2(err_fd, STDERR_FILENO);
        close(out_fd);
        close(err_fd);
        execvp(argv[6], &argv[6]);
        fprintf(stderr, "runbox: cannot execute %s: %s\n", argv[6], strerror(errno));
        _exit(127);
    }
    setpgid(pid, pid);

    int status = 0, timed_out = 0;
    struct rusage ru;
    memset(&ru, 0, sizeof ru);
    for (;;) {
        pid_t r = wait4(pid, &status, WNOHANG, &ru);
        if (r == pid) break;
        if (r < 0 && errno != EINTR) break;
        if (now_ms() - start > wall_ms) {
            timed_out = 1;
            kill(-pid, SIGKILL);
            kill(pid, SIGKILL);
            wait4(pid, &status, 0, &ru);
            break;
        }
        usleep(2000);
    }
    long wall = now_ms() - start;
    /* Take down anything the program left running. */
    kill(-pid, SIGKILL);

    long used_cpu = ru.ru_utime.tv_sec * 1000L + ru.ru_utime.tv_usec / 1000L +
                    ru.ru_stime.tv_sec * 1000L + ru.ru_stime.tv_usec / 1000L;
    int exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
    int sig = WIFSIGNALED(status) ? WTERMSIG(status) : 0;

    printf("RUNBOX exit=%d signal=%d cpu_ms=%ld wall_ms=%ld mem_kb=%ld timed_out=%d stdout=%ld stderr=%ld\n",
           exit_code, sig, used_cpu, wall, ru.ru_maxrss, timed_out,
           file_size(out_fd, output_bytes), file_size(err_fd, output_bytes));
    fflush(stdout);
    copy_out(out_fd, output_bytes);
    copy_out(err_fd, output_bytes);
    fflush(stdout);
    unlink(out_path);
    unlink(err_path);
    return 0;
}
