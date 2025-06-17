"""
Created on 2025-05-14

@author: wf
"""

import json
import os
import subprocess
from tempfile import NamedTemporaryFile
import traceback
from typing import Any, Dict, Optional

from basemkit.persistent_log import Log
from basemkit.shell import Shell, ShellResult


class DockerUtil:
    """
    docker utilities
    """

    def __init__(self,
        shell: Shell,
        container_name: str,
        log:Log,
        verbose: bool = False,
        debug: bool = False):
        self.shell = shell
        self.container_name = container_name
        self.log=log
        self.verbose = verbose
        self.debug = debug

    def handle_exception(self, context: str, ex: Exception):
        """
        handle the given exception
        """
        container_name = self.container_name
        self.log.log("❌", container_name, f"Exception {context}: {ex}")
        if self.debug:
            # extract exception type, and trace back
            ex_type = type(ex)
            ex_tb = ex.__traceback__
            # print exception stack details
            traceback.print_exception(ex_type, ex, ex_tb)

    def patch_file(self, file_path: str, callback, push_back: bool = True):
        """
        Copy a file from the container, apply a patch callback, and optionally copy it back.

        Args:
            file_path (str): Absolute path to the file inside the container.
            callback (Callable[[str], None]): Function to apply changes to the local copy.
            push_back (bool): If True, copy the modified file back to the container.
        """

        with NamedTemporaryFile(delete=False) as tmp:
            local_path = tmp.name

        # Copy file from container
        result = self.shell.run(
            f"docker cp {self.container_name}:{file_path} {local_path}",
            tee=self.debug,
        )
        if result.returncode != 0:
            raise RuntimeError(f"docker cp from {file_path} failed")

        # Apply patch callback
        callback(local_path)

        # Copy file back to container
        if push_back:
            result = self.shell.run(
                f"docker cp {local_path} {self.container_name}:{file_path}",
                tee=self.debug,
            )
            if result.returncode != 0:
                raise RuntimeError(f"docker cp back to {file_path} failed")

        # Clean up
        try:
            os.unlink(local_path)
        except Exception:
            pass

    def line_patch(self, path: str, line_callback, title: str, msg: str):
        """
        Patch a file in the container line-by-line via callback and check in using RCS.

        Args:
            path (str): Path to file inside container.
            line_callback (Callable[[str], Tuple[str, bool]]): Function to patch a line. Returns (line, found).
            title (str): What is being patched, used for error message.
            msg (str): RCS check-in message.
        """

        def patch_callback(local_path):
            with open(local_path, "r") as f:
                lines = f.readlines()
            found = False
            with open(local_path, "w") as f:
                for line in lines:
                    patched_line, was_found = line_callback(line)
                    f.write(patched_line)
                    found = found or was_found
            if not found:
                raise RuntimeError(f"⚠️  No matching line found for {title} in {path}")

        self.patch_file(path, patch_callback)
        self.run(f"""ci -l -m"{msg}" {path}""")

    def run_script(self, name: str, script_content: str, tee: bool = False, *args):
        """Run a script in the container with parameters"""
        with NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as tmp:
            tmp.write(script_content)
            tmp_file = tmp.name

        os.chmod(tmp_file, 0o755)

        # Copy script to container
        container_script_path = f"/tmp/{name}.sh"
        self.run_local(f"docker cp {tmp_file} {self.container_name}:{container_script_path}")

        # Execute script in container with args
        args_str = " ".join(args)
        process = self.run_local(
            cmd=f"docker exec -i {self.container_name} bash {container_script_path} {args_str}",
            tee=tee,
        )

        # Clean up local temporary file
        try:
            os.unlink(tmp_file)
        except Exception:
            pass

        return process

    def run(self, command):
        """Run a command in the container"""
        # use single quotes
        cmd = f"docker exec -i {self.container_name} bash -c '{command}'"
        return self.run_local(cmd)

    def run_local(self, cmd: str, tee: bool = False) -> subprocess.CompletedProcess:
        """
        Run a command with sourced profile

        Args:
            cmd: The command to run
            tree: if true show stdout/stderr while running the command

        Returns:
            subprocess.CompletedProcess: The result of the command
        """
        process = self.shell.run(cmd, tee=tee, debug=self.debug)
        return process

    def inspect(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve full .State of the Docker container.

        Returns:
            dict: parsed .State structure or None on error
        """
        inspect_dict = None
        cmd = f'docker inspect -f "{{{{json .State}}}}" {self.container_name}'
        result = self.shell.run(cmd, debug=self.debug)
        if result.returncode == 0:
            try:
                json_text = result.stdout.strip()
                inspect_dict = json.loads(json_text)
            except Exception as ex:
                if self.debug:
                    print(f"Failed to parse Docker state JSON: {ex}")
        return inspect_dict

    def run_shell_command(self, command: str, success_msg: str = None, error_msg: str = None) -> ShellResult:
        """
        Helper function for running shell commands with consistent error handling.

        Args:
            command: Shell command to run
            success_msg: Message to log on success
            error_msg: Message to log on error

        Returns:
            shell_result: a shell result
        """
        container_name = self.container_name
        command_success = False
        proc = None
        try:
            proc = self.shell.run(command, debug=self.debug, tee=self.verbose)
            if proc.returncode == 0:
                if success_msg:
                    self.log.log("✅", container_name, success_msg)
                command_success = True
            else:
                error_detail = error_msg or f"Command failed: {command}"
                if proc.stderr:
                    error_detail += f" - {proc.stderr}"
                self.log.log("❌", container_name, error_detail)
                command_success = False
        except Exception as ex:
            self.handle_exception(f"command '{command}'", ex)
            command_success = False
        shell_result = ShellResult(proc, command_success)
        return shell_result

    def docker_cmd(self, cmd: str, options: str = "", args: str = "") -> str:
        """
        create the given docker command with the given options
        """
        container_name = "" if cmd == "info" else self.container_name
        if options:
            options = f" {options}"
        if args:
            args = f" {args}"
        full_cmd = f"docker {cmd}{options} {container_name}{args}"
        return full_cmd

    def run_docker_cmd(self, cmd: str, options: str = "", args: str = "") -> ShellResult:
        """
        run the given docker commmand with the given options
        """
        container_name = self.container_name
        full_cmd = self.docker_cmd(cmd, options, args)
        shell_result = self.run_shell_command(
            full_cmd,
            success_msg=f"{cmd} container {container_name}",
            error_msg=f"Failed to {cmd} container {container_name}",
        )
        return shell_result

    def logs(self) -> ShellResult:
        """show the logs of the container"""
        logs_result = self.run_docker_cmd("logs")
        return logs_result

    def docker_info(self) -> ShellResult:
        """
        Check if Docker is responsive on the host system.
        """
        info_result = self.run_docker_cmd("info")
        return info_result

    def stop(self) -> ShellResult:
        """stop the server container"""
        stop_result = self.run_docker_cmd("stop")
        return stop_result

    def rm(self) -> ShellResult:
        """remove the server container."""
        rm_result = self.run_docker_cmd("rm")
        return rm_result

    def bash(self) -> bool:
        """bash into the server container."""
        bash_cmd = self.docker_cmd("exec", "-it", "/bin/bash")
        print(bash_cmd)
        return True
