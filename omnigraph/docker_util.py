"""
Created on 2025-05-14

@author: wf
"""

import os
import subprocess
from tempfile import NamedTemporaryFile

from omnigraph.shell import Shell


class DockerUtil:
    """
    docker utilities
    """

    def __init__(self, shell: Shell, container_name: str, debug: bool = False):
        self.shell = shell
        self.container_name = container_name
        self.debug = debug

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
