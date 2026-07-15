import subprocess
import sys
import os


def _find_pip():
    if sys.platform == "win32":
        candidates = ["py -m pip", "python -m pip", "pip", "pip3"]
    else:
        candidates = ["python3 -m pip", "pip3", "pip", "python -m pip"]
    for c in candidates:
        try:
            subprocess.run(c.split() + ["--version"], capture_output=True, check=True)
            return c
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return None


def _install_instructions(package):
    system = sys.platform
    print(f"\n  Could not find pip. Install it manually:")
    if system == "win32":
        print(f"    1. Download get-pip.py from https://bootstrap.pypa.io/get-pip.py")
        print(f"    2. Run: python get-pip.py")
        print(f"    3. Then: pip install {package}")
    elif system == "darwin":
        print(f"    brew install python   # if Python not installed")
        print(f"    python3 -m pip install {package}")
    else:
        print(f"    # Debian/Ubuntu: sudo apt install python3-pip")
        print(f"    # RHEL/Fedora:   sudo dnf install python3-pip")
        print(f"    python3 -m pip install {package}")
    print()


def prompt_install(package):
    print(f"\n  Missing required library: {package}")
    try:
        resp = input("  Install it now? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        resp = "n"
        print()
    if resp not in ("y", "yes"):
        print(f"  Aborted. Run: pip install {package}")
        sys.exit(1)
    pip_cmd = _find_pip()
    if pip_cmd is None:
        _install_instructions(package)
        sys.exit(1)
    print(f"  Installing {package}...")
    result = subprocess.run(
        pip_cmd.split() + ["install", package],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Installation failed:\n{result.stderr}")
        _install_instructions(package)
        sys.exit(1)
    print(f"  Successfully installed {package}")
