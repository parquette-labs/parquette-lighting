#!/usr/bin/env python3
"""Deploy local changes to the live parquette-mm machine.

Workflow:
  1. Inspect the remote working tree over ssh. If it's dirty:
     - For layout/params files, prompt to (a) scp them down into the local
       working tree, (b) discard them on the remote, or (c) abort.
     - For any other dirty files, abort with a clear message.
     (Doing this BEFORE the local commit lets any scp'd files land in the
     same commit alongside whatever the user was already editing locally.)
  2. If the local working tree is now dirty (either from existing edits or
     from the scp step), drop into `git commit -a` so the user can write a
     commit message; abort if still dirty afterwards.
  3. Push the current branch to origin.
  4. Fetch + checkout the local branch on the remote and `git pull`.
  5. Run `./launchd/install.sh -y` on the remote to reinstall and restart
     the launchd agents.

Run with:
    cd python/parquette-lights
    poetry run poe deploy
"""

import shlex
import subprocess
import sys
from pathlib import Path

import click


REMOTE_HOST = "parquette-mm"
REMOTE_PATH = "/Users/pq/parquette/parquette-lighting"

# Repo-relative paths whose modifications on the remote we are willing to
# pull back to local rather than abort. Anything outside this set on a
# dirty remote means abort.
SYNCABLE_PATHS = {
    "open-stage-control/layout-config.json",
    "python/parquette-lights/params.pickle",
}

# Toggled by the --verbose/-v flag. When True, every shell command (local
# git/scp and remote ssh wrapper) is echoed before it runs.
VERBOSE = False


def repo_root() -> Path:
    """Resolve the git repo root from this script's location."""
    return Path(__file__).resolve().parents[3]


def run(
    cmd: list[str],
    *,
    capture: bool = False,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run a local command. Streams to terminal unless capture=True."""
    if VERBOSE:
        click.secho("$ " + " ".join(shlex.quote(c) for c in cmd), dim=True)
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=capture,
        text=True,
    )


def ssh(
    remote_cmd: str, *, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command on the remote inside the project dir."""
    full = f"cd {shlex.quote(REMOTE_PATH)} && {remote_cmd}"
    return run(["ssh", REMOTE_HOST, full], capture=capture, check=check)


def git_porcelain(cwd: Path) -> list[tuple[str, str]]:
    """Return [(status_code, path), ...] for `git status --porcelain`."""
    cp = run(
        ["git", "-C", str(cwd), "status", "--porcelain"],
        capture=True,
    )
    out = []
    for line in cp.stdout.splitlines():
        if not line.strip():
            continue
        out.append((line[:2], line[3:]))
    return out


def current_branch(cwd: Path) -> str:
    return run(
        ["git", "-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"],
        capture=True,
    ).stdout.strip()


def step(msg: str) -> None:
    click.echo()
    click.secho(f"==> {msg}", fg="green", bold=True)


def fail(msg: str, code: int = 1) -> "None":
    click.secho(f"ERROR: {msg}", fg="red", err=True)
    sys.exit(code)


def classify_remote_dirty(
    entries: list[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    """Return (syncable_paths, blocking_paths)."""
    syncable: list[str] = []
    blocking: list[str] = []
    for _code, path in entries:
        if path in SYNCABLE_PATHS:
            syncable.append(path)
        else:
            blocking.append(path)
    return syncable, blocking


def handle_remote_dirty(root: Path) -> None:
    """If the remote tree is dirty, decide what to do.

    Runs BEFORE the local commit so that any files we scp down land in the
    local working tree and get folded into the next commit naturally.
    """
    step("Checking remote working tree")
    cp = ssh("git status --porcelain", capture=True)
    entries = []
    for line in cp.stdout.splitlines():
        if not line.strip():
            continue
        entries.append((line[:2], line[3:]))

    if not entries:
        click.echo("clean.")
        return

    syncable, blocking = classify_remote_dirty(entries)

    if blocking:
        click.secho("Remote has uncommitted changes outside layout/params:", fg="red")
        for path in blocking:
            click.echo(f"  {path}")
        fail("Resolve manually on the remote before deploying.")

    click.secho("Remote has uncommitted changes in syncable files:", fg="yellow")
    for path in syncable:
        click.echo(f"  {path}")
    click.echo()
    click.echo("Choose how to handle them:")
    click.echo("  a) scp them down into the local working tree")
    click.echo("  b) discard them on the remote (git checkout --)")
    click.echo("  c) abort the deploy")
    choice = click.prompt(
        "Action",
        type=click.Choice(["a", "b", "c"], case_sensitive=False),
        show_choices=True,
    )

    if choice == "c":
        fail("Deploy aborted by user.", code=2)

    if choice == "b":
        for path in syncable:
            ssh(f"git checkout -- {shlex.quote(path)}")
        return

    # choice == "a": scp each file from remote → local. The local commit
    # step that runs next will pick them up alongside any existing edits.
    for path in syncable:
        local_dest = root / path
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        run(
            [
                "scp",
                f"{REMOTE_HOST}:{REMOTE_PATH}/{path}",
                str(local_dest),
            ]
        )


def ensure_local_clean(root: Path) -> None:
    step("Checking local working tree")
    dirty = git_porcelain(root)
    if not dirty:
        click.echo("clean.")
        return

    click.secho("Local changes:", fg="yellow")
    for code, path in dirty:
        click.echo(f"  {code} {path}")
    click.echo("\nLaunching `git commit -a` so you can stage and write a message.")
    click.secho("(close the editor without saving to abort)", dim=True)
    cp = run(["git", "-C", str(root), "commit", "-a"], check=False)
    if cp.returncode != 0:
        fail("git commit -a failed or was aborted; nothing pushed.")

    leftover = git_porcelain(root)
    if leftover:
        click.secho("Still dirty after commit:", fg="red")
        for code, path in leftover:
            click.echo(f"  {code} {path}")
        fail("Local working tree is still dirty; aborting deploy.")


def push_local(root: Path, branch: str) -> None:
    step(f"Pushing {branch} → origin")
    run(["git", "-C", str(root), "push", "origin", branch])


def remote_pull(branch: str) -> None:
    step(f"Remote: fetch + checkout {branch} + pull")
    ssh("git fetch --all --prune")
    ssh(f"git checkout {shlex.quote(branch)}")
    ssh(f"git pull --ff-only origin {shlex.quote(branch)}")


def remote_install() -> None:
    step("Remote: launchd/install.sh -y")
    ssh("./launchd/install.sh -y")


@click.command()
@click.option(
    "--skip-install",
    is_flag=True,
    help="Sync code only, don't run launchd install.sh on the remote.",
)
@click.option(
    "--remote-host",
    default=REMOTE_HOST,
    show_default=True,
    help="SSH host of the deployment machine.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Echo every shell command (local + remote) before it runs.",
)
def main(skip_install: bool, remote_host: str, verbose: bool) -> None:
    """Deploy local changes to the live parquette-mm machine."""
    global REMOTE_HOST, VERBOSE  # pylint: disable=global-statement
    REMOTE_HOST = remote_host
    VERBOSE = verbose

    root = repo_root()
    click.echo(f"Repo root: {root}")
    click.echo(f"Remote:    {REMOTE_HOST}:{REMOTE_PATH}")

    branch = current_branch(root)
    click.echo(f"Branch:    {branch}")

    handle_remote_dirty(root)
    ensure_local_clean(root)
    push_local(root, branch)
    remote_pull(branch)

    if skip_install:
        click.secho("--skip-install set; not running launchd/install.sh", fg="yellow")
    else:
        remote_install()

    step("Deploy complete.")


if __name__ == "__main__":
    try:
        main()  # pylint: disable=no-value-for-parameter
    except KeyboardInterrupt:
        click.echo()
        fail("Interrupted.", code=130)
