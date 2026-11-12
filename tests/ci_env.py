"""Print and record the runner, OS, CPU architecture, Python and uv versions."""

import json
import os
import platform
import subprocess


def main():
    try:
        uv_version = subprocess.check_output(["uv", "--version"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        uv_version = "unavailable"
    info = {
        "runner_os": os.environ.get("RUNNER_OS"),
        "runner_arch": os.environ.get("RUNNER_ARCH"),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER"),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "uv": uv_version,
        "ci": os.environ.get("CI", "false"),
    }
    print(json.dumps(info, indent=2))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(f"### {info['system']} / {info['machine']}\n\n")
            summary.write("```json\n")
            summary.write(json.dumps(info, indent=2))
            summary.write("\n```\n\n")


if __name__ == "__main__":
    main()
