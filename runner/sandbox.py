"""A locked-down Docker container that compiles and runs one submission.

One container is started per submission and kept alive while each scenario
runs inside it through `runbox`, which enforces CPU time, wall time and
output limits and reports what happened. The container has no network,
a read-only root filesystem, a memory cap and no Linux capabilities, and it
is removed when the sandbox closes.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass

import docker
from docker.utils.socket import STDOUT, frames_iter

from core.languages import Language

SANDBOX_USER = "65534:65534"  # nobody
PIDS_LIMIT = 64
# Compilers need more memory than many programs are allowed (g++ with
# <bits/stdc++.h> peaks around 250 MB), so compiled languages start with at
# least this much and drop to the program's limit before it runs.
COMPILE_MEMORY_MB = 768
TMPFS = {
    "/tmp": "rw,exec,nosuid,size=256m,mode=1777",
    "/code": "rw,exec,nosuid,size=64m,mode=1777",
}


class SandboxError(Exception):
    """The sandbox itself failed; not the submitted program's fault."""


@dataclass
class ProcessResult:
    exit_code: int
    signal: int
    cpu_ms: int
    wall_ms: int
    memory_kb: int
    timed_out: bool
    stdout: bytes
    stderr: bytes


class Sandbox:
    def __init__(self, language: Language, memory_mb: int, client: docker.DockerClient | None = None):
        self.language = language
        self.memory_mb = memory_mb + language.extra_memory_mb
        self.start_memory_mb = max(self.memory_mb, COMPILE_MEMORY_MB) if language.compile else self.memory_mb
        self.client = client or docker.from_env()
        self.container = None

    def __enter__(self) -> "Sandbox":
        try:
            self.container = self.client.containers.run(
                self.language.image,
                ["sleep", "infinity"],
                detach=True,
                network_mode="none",
                read_only=True,
                tmpfs=TMPFS,
                mem_limit=f"{self.start_memory_mb}m",
                memswap_limit=f"{self.start_memory_mb}m",
                nano_cpus=1_000_000_000,
                pids_limit=PIDS_LIMIT,
                user=SANDBOX_USER,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                working_dir="/code",
                labels={"codeplay.sandbox": "1"},
            )
        except docker.errors.DockerException as exc:
            raise SandboxError(f"could not start sandbox: {exc}") from exc
        return self

    def __exit__(self, *exc_info) -> None:
        if self.container is not None:
            try:
                self.container.remove(force=True)
            except docker.errors.DockerException:
                pass
            self.container = None

    def restrict_memory(self) -> None:
        """Lower the memory cap from the compile allowance to the program's limit."""
        if self.start_memory_mb == self.memory_mb:
            return
        try:
            self.container.update(mem_limit=f"{self.memory_mb}m", memswap_limit=f"{self.memory_mb}m")
        except docker.errors.DockerException as exc:
            raise SandboxError(f"could not set the memory limit: {exc}") from exc

    def write_file(self, name: str, content: bytes) -> None:
        exit_code, _ = self._exec(["sh", "-c", f'cat > "/code/{name}"'], stdin=content, timeout=30)
        if exit_code != 0:
            raise SandboxError(f"could not write {name} into the sandbox")

    def prepare(self) -> None:
        if self.language.prepare:
            exit_code, output = self._exec(self.language.prepare, timeout=60)
            if exit_code != 0:
                raise SandboxError(f"prepare step failed: {output[-500:]!r}")

    def execute(
        self, command: list[str], stdin: bytes, cpu_ms: int, wall_ms: int, output_bytes: int, file_bytes: int
    ) -> ProcessResult:
        """Run a command under runbox with the given limits.

        file_bytes caps every file the command writes, stdout and stderr
        included; output_bytes is how much of each stream comes back.
        """
        runbox = ["runbox", str(cpu_ms), str(wall_ms), str(output_bytes), str(file_bytes), "--", *command]
        # Leave room for docker exec overhead on top of runbox's own wall limit.
        _, raw = self._exec(runbox, stdin=stdin, timeout=wall_ms / 1000 + 30)
        return parse_runbox_output(raw)

    def _exec(self, command: list[str], stdin: bytes = b"", timeout: float = 30) -> tuple[int, bytes]:
        api = self.client.api
        try:
            exec_id = api.exec_create(
                self.container.id, command, stdin=True, stdout=True, stderr=True, user=SANDBOX_USER
            )["Id"]
            sock = api.exec_start(exec_id, socket=True)
            raw_sock = getattr(sock, "_sock", sock)
            raw_sock.settimeout(timeout)
            if stdin:
                raw_sock.sendall(stdin)
            raw_sock.shutdown(socket.SHUT_WR)
            stdout, stderr = bytearray(), bytearray()
            for stream, data in frames_iter(sock, tty=False):
                (stdout if stream == STDOUT else stderr).extend(data)
            # Close the HTTP response before its socket, or urllib3 later
            # tries to flush the closed socket and logs an ignored error.
            response = getattr(sock, "_response", None)
            if response is not None:
                response.close()
            raw_sock.close()
            exit_code = api.exec_inspect(exec_id)["ExitCode"]
        except (docker.errors.DockerException, OSError) as exc:
            raise SandboxError(f"exec failed: {exc}") from exc
        return exit_code if exit_code is not None else -1, bytes(stdout + stderr)


def parse_runbox_output(raw: bytes) -> ProcessResult:
    header, sep, body = raw.partition(b"\n")
    if not sep or not header.startswith(b"RUNBOX "):
        raise SandboxError(f"runbox did not report a result: {raw[:300]!r}")
    fields = dict(item.split("=", 1) for item in header.decode().split()[1:])
    out_len, err_len = int(fields["stdout"]), int(fields["stderr"])
    return ProcessResult(
        exit_code=int(fields["exit"]),
        signal=int(fields["signal"]),
        cpu_ms=int(fields["cpu_ms"]),
        wall_ms=int(fields["wall_ms"]),
        memory_kb=int(fields["mem_kb"]),
        timed_out=fields["timed_out"] == "1",
        stdout=body[:out_len],
        stderr=body[out_len : out_len + err_len],
    )
