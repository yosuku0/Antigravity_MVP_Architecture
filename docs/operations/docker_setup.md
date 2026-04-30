# Docker GPU Setup

Docker is optional for this Windows-first project. Use it for local isolation
and GPU workloads only when the host supports WSL2 + NVIDIA Container Toolkit.

## Validation

```powershell
docker info
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
python scripts/monitor_gpu.py --count 1
```

If `nvidia-smi` is unavailable, `monitor_gpu.py` exits successfully and writes no
metrics. This is expected on CPU-only machines.

## Metrics

`scripts/monitor_gpu.py` writes `logs/gpu_metrics.csv` with:

- `ts`
- `index`
- `name`
- `utilization_gpu_percent`
- `memory_used_mib`
- `memory_total_mib`
- `temperature_gpu_c`
- `power_draw_w`

Do not store `NGC_API_KEY` or other secrets in logs, JOB files, wiki files, or
artifacts.
