#
# Copyright (c) 2023,2024,2025 MainlyAI - contact@mainly.ai
#
import subprocess
import os
from typing import Dict, Tuple, Optional
from .failure_mode import FailureMode, FailureModeHandler, RecoveryStrategy
from typing import Callable
import pexpect
import json
import sys


def read_secret_wrapper(sc, key):
    # This wrapper function allows us to pass the read_secret function
    # without circular imports
    from .miranda import read_secret

    return read_secret(sc, key)


def run_subprocess_command(command: list) -> Tuple[bool, str, str]:
    """
    Run a git command and return the result.

    :param command: List of command parts
    :return: Tuple of (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def run_command(cmd, expecting=[], timeout=5):
    c = pexpect.spawn(cmd, encoding="utf-8")
    c.logfile = sys.stdout
    if len(expecting) == 0:
        i = c.expect([pexpect.EOF, "Press RETURN"], timeout=timeout)
    else:
        i = c.expect(expecting, timeout=timeout)
    if i == 1:
        c.sendline("\n")
    c.expect([pexpect.EOF, "Press RETURN"])
    c.close()


def identify_git_failure_mode(stderr: str) -> Optional[str]:
    """
    Identify the failure mode based on the git error message.

    :param stderr: Error output from git command
    :return: Identified failure mode or None
    """
    error_lower = stderr.lower()

    if "permission denied" in error_lower:
        return "permission_denied"
    elif "repository not found" in error_lower:
        return "repo_not_found"
    elif "network error" in error_lower or "could not resolve host" in error_lower:
        return "network_error"
    elif "authentication failed" in error_lower:
        return "authentication_failed"
    elif "not a git repository" in error_lower:
        return "not_a_git_repo"
    elif "fatal: could not read from remote repository" in error_lower:
        return "remote_read_error"
    # Add more failure mode identifications as needed
    return None


# The rest of the code (FailureModeHandler, recovery strategies, etc.) remains the same
class GitFailureRecovery:
    @staticmethod
    def ssh_key_missing(sc, ko, wob, enter_interactive, soft=True, push=False):
        print("|=> SSH key missing. Attempting to clone without authentication.")
        if wob.git.startswith("ssh://"):
            # replace ssh:// with https://
            wob.git = wob.git.replace("ssh://", "https://")
            print(f"|=> Retrying with HTTPS: {wob.git}")
        return git_clone_impl(
            sc, ko, wob, enter_interactive, soft=soft, push=push, use_ssh=False
        )

    @staticmethod
    def git_not_installed(sc, ko, wob, enter_interactive, soft=True, push=False):
        print("Git is not installed. Attempting to install git...")
        os.system("apt install git -y")
        return git_clone_impl(sc, ko, wob, enter_interactive, soft=soft, use_ssh=False)

    @staticmethod
    def network_error(sc, ko, wob, enter_interactive, soft=True, push=False):
        print("|=> Network error. Retrying after 5 seconds...")
        import time

        time.sleep(5)
        return git_clone_impl(sc, ko, wob, enter_interactive, soft=soft, push=push)

    @staticmethod
    def repo_not_found(sc, ko, wob, enter_interactive, soft=True, push=False):
        print(f"|=> Repository not found: {wob.git}")
        raise Exception("|=> Repository not found")

    @staticmethod
    def wrong_directory_structure(
        sc, ko, wob, enter_interactive, soft=True, push=False
    ):
        print("|=> Wrong directory structure. Missing WOB file.")
        # TODO
        raise Exception("Failed to clone in a different location.")

    @staticmethod
    def git_error_128(sc, ko, wob, enter_interactive, soft=True, push=False):
        print("|=> Git command failed: Public key denied.")
        raise Exception("Git command failed: Public key denied.")

    @staticmethod
    def git_error(sc, ko, wob, enter_interactive, soft=True, push=False):
        print("|=> Git command failed.")
        raise Exception("Git command failed.")

    @staticmethod
    def git_timeout(sc, ko, wob, enter_interactive, soft=True, push=False):
        print("|=> Git operation timed out. Check the URL and try again.")
        raise Exception("Git operation timed out.")

    @staticmethod
    def git_no_upstream_branch(sc, ko, wob, enter_interactive, soft=True, push=False):
        print(
            "|=> No upstream branch named {}. Boldly attempting to push with default branch name main instead.".format(
                wob.git_branch
            )
        )
        wob.git_branch = "main"
        return git_clone_impl(sc, ko, wob, enter_interactive, soft=soft, push=push)


git_failure_modes: Dict[str, RecoveryStrategy] = {
    "ssh key": RecoveryStrategy(GitFailureRecovery.ssh_key_missing),
    "Secret not found": RecoveryStrategy(GitFailureRecovery.ssh_key_missing),
    "git: command not found": RecoveryStrategy(GitFailureRecovery.git_not_installed),
    "network error": RecoveryStrategy(GitFailureRecovery.network_error),
    "repo_not_found": RecoveryStrategy(GitFailureRecovery.repo_not_found),
    "no_wob_file": RecoveryStrategy(GitFailureRecovery.wrong_directory_structure),
    "git_error_128": RecoveryStrategy(GitFailureRecovery.git_error_128),
    "git_error_": RecoveryStrategy(GitFailureRecovery.git_error),
    "git_timeout": RecoveryStrategy(GitFailureRecovery.git_timeout),
    "no_upstream_branch": RecoveryStrategy(GitFailureRecovery.git_no_upstream_branch),
}


@FailureModeHandler(git_failure_modes)
def git_clone_impl(
    sc,
    ko,
    wob,
    enter_interactive: Callable,
    soft=False,
    use_ssh=True,
    push=False,
    enable_log=False,
):
    # setup identification
    with sc.connect() as con:
        sql = "SELECT username,email,first_name,last_name from v_user_detail"
        with con.cursor(dictionary=True) as cur:
            cur.execute(sql)
            for r in cur:
                email = r["email"]
                user = "{} {}".format(r["first_name"], r["last_name"])
                print("Setting gitconfig user.name = ", user)
                print("Setting gitconfig user.email = ", email)
                run_command("git config --global --unset-all user.name")
                run_command("git config --global --unset-all user.email")
                run_command(f'git config --global --add user.name "{user}"')
                run_command(f'git config --global --add user.email "{email}"')

    repo_url = wob.git
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    branch = wob.git_branch if wob.git_branch and wob.git_branch != "None" else None

    # Determine if we should use SSH
    if use_ssh:
        ssh_key_json = read_secret_wrapper(sc, "$git_ssh_key")
        # Set up SSH key if it exists
        if ssh_key_json:
            try:
                ssh_key_json = json.loads(ssh_key_json)
            except json.JSONDecodeError:
                raise FailureMode(
                    "invalid_ssh_key", Exception("Invalid JSON format for SSH key.")
                )
            ssh_key = ssh_key_json["ssh_key"]
            with open("git_ssh_key", "w") as f:
                f.write(ssh_key)
            os.chmod("git_ssh_key", 0o600)
            os.environ["GIT_SSH_COMMAND"] = "ssh -i {}".format(os.path.abspath(f.name))

    # Check if repository is already cloned
    if os.path.exists(repo_name):
        print(f"|=> Repository {repo_name} already exists.")
        cmd = f"git -C {repo_name} pull"
    else:
        print(f"|=> Cloning {repo_name}.")
        cmd = f"git clone {repo_url}"

    git_command(cmd, enter_interactive, enable_log=enable_log)

    # Checkout specific branch if specified
    if branch:
        try:
            child = pexpect.spawn(
                f"git -C {repo_name} checkout {branch}", encoding="utf-8"
            )
            child.expect(pexpect.EOF, timeout=30)
            child.close()
            if child.exitstatus != 0:
                raise FailureMode(
                    "git_checkout_error",
                    Exception(
                        f"Git checkout failed with exit status {child.exitstatus}"
                    ),
                )
        except pexpect.ExceptionPexpect as e:
            failure_mode = identify_git_failure_mode(str(e))
            if failure_mode:
                raise FailureMode(failure_mode, e)
            else:
                raise FailureMode("unknown_git_error", e)
    # Verify structure and read WOB file (same as before)
    # Find the WOB-xxxxxx.py file. Since this is executed from the processor the working directory will be the
    # just the home directory.
    wob_file = "{}.py".format(wob.name.lower().replace(" ", "_"))
    if push and not soft:
        # Push code to git
        with open("{}/{}".format(repo_name, wob_file), "w+") as f:
            f.write(wob.body)

        git_command(
            "git -C {} add {}".format(repo_name, wob_file),
            enter_interactive,
            enable_log=enable_log,
        )
        git_command(
            "git -C {} commit -m 'Changed in Mainly Designer'".format(repo_name),
            enter_interactive,
            enable_log=enable_log,
        )
        git_command(
            "git -C {} push origin {}".format(repo_name, branch),
            enter_interactive,
            enable_log=enable_log,
        )

    else:
        named_wob_file = None
        for root, dirs, files in os.walk(repo_name, topdown=False):
            for name in files:
                if name == wob_file:
                    named_wob_file = os.path.join(root, name)
                    break
        if named_wob_file is None:
            # The reposity doesn't contain any WOB file and it might be because we haven't pushed the node to the repository.
            code = ""  # Assume the git repo is empty
        else:
            with open(named_wob_file, "r") as f:
                code = f.read()
        # Ignore the node header if there is one.
        if "# ------------------- Code block -------------------" in code:
            header, code = code.split(
                "# ------------------- Code block -------------------"
            )
            code = code.strip()

        wob.body = code
        if not soft and not push:
            # Pull code from git.
            wob.write_diff(code)
            wob.update(sc)
    return wob


def git_command(cmd, enter_interactive, enable_log=False):
    try:
        # Use pexpect to spawn the git process
        custom_env = os.environ.copy()
        if "GIT_SSH_COMMAND" not in custom_env:
            custom_env["GIT_SSH_COMMAND"] = "ssh -i /miranda/git_ssh_key"
        child = pexpect.spawn(cmd, encoding="utf-8", echo=True, env=custom_env)
        if enable_log:
            child.logfile = sys.stdout

        # Define patterns to expect
        patterns = [
            "Enter passphrase for key",
            "Are you sure you want to continue connecting",
            "Repository not found.",
            "no upstream branch",
            "Press RETURN",
            pexpect.EOF,
            pexpect.TIMEOUT,
        ]

        while True:
            index = child.expect(patterns, timeout=30)

            if index == 0:  # Passphrase prompt
                passphrase = enter_interactive("Enter passphrase for SSH key: ")
                # print ("DEBUG: passphrase: ",passphrase)
                child.sendline(passphrase)
            elif index == 1:  # SSH host authenticity prompt
                # TODO save authenticated hosts on permantent storage
                child.sendline("yes")
            elif index == 2:  # Repository not found
                raise FailureMode("repo_not_found", Exception("Repository not found"))
            elif index == 3:  # No upstream branch
                raise FailureMode("no_upstream_branch", Exception("No upstream branch"))
            elif index == 4:
                child.send("\n")
            elif index == 5:  # EOF (process completed)
                break
            elif index == 6:  # Timeout
                raise FailureMode("git_timeout", Exception("Git operation timed out"))

        # Check the exit status
        child.close()
        if (
            child.exitstatus != 0 and child.exitstatus != 1
        ):  # 1 is for git pull when there are no changes
            raise FailureMode(
                f"git_error_{child.exitstatus}",
                Exception(f"Git command failed with exit status {child.exitstatus}"),
            )

    except pexpect.ExceptionPexpect as e:
        failure_mode = identify_git_failure_mode(str(e))
        if failure_mode:
            raise FailureMode(failure_mode, e)
        else:
            raise FailureMode("unknown_git_error", e)
