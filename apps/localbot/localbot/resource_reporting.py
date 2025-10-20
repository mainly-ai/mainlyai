import logging
from mirmod import miranda

import os
import subprocess
import platform


def update_crg_maximum_resources(
    sctx: miranda.Security_context, crg: miranda.Compute_resource_group
):
    crg.cpu_capacity = os.cpu_count() or 0
    crg.gpu_capacity = _get_cuda_gpu_count()
    crg.ram_capacity = _get_ram_capacity_gb()

    logging.info(
        f"Updating CRG maximum resource specifications: CPU={crg.cpu_capacity}, GPU={crg.gpu_capacity}, RAM={crg.ram_capacity}GB"
    )

    crg.update(sctx)


def _get_cuda_gpu_count() -> int:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=count", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # nvidia-smi returns the count for each gpu
            # so we just count the lines
            gpu_count = len(result.stdout.strip().split("\n"))
            return gpu_count
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        logging.warning(
            "nvidia-smi not found or failed, could not detect any cuda capable gpus"
        )
        pass
    return 0


def _get_ram_capacity_gb() -> int:
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                total_ram_bytes = int(result.stdout.strip())
                return int(total_ram_bytes / (1024**3))

        elif system == "Linux":
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        # MemTotal is in KB
                        mem_kb = int(line.split()[1])
                        return int(mem_kb / (1024**2))

        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "computersystem", "get", "totalphysicalmemory"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    total_ram_bytes = int(lines[1].strip())
                    return int(total_ram_bytes / (1024**3))

    except Exception as e:
        logging.warning(f"Failed to get RAM capacity: {e}")

    return 0
