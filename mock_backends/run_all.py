"""Run all three mock backends in separate processes for local dev."""
from __future__ import annotations

import multiprocessing

import uvicorn


def run(mod: str, port: int) -> None:
    """Boot a uvicorn worker for the given app module and port."""
    uvicorn.run(mod, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    procs = [
        multiprocessing.Process(target=run, args=("mock_backends.echo.main:app", 9001)),
        multiprocessing.Process(target=run, args=("mock_backends.slow.main:app", 9002)),
        multiprocessing.Process(target=run, args=("mock_backends.flaky.main:app", 9003)),
    ]
    for p in procs:
        p.start()
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()