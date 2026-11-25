"""Linux + AMD (ROCm) environment check: does each piece SmoovPlay needs work on this PC?

  .venv/bin/python scripts/amd_check.py

Checks, in order: PyTorch on ROCm and the card it sees, a half-precision convolution and grid_sample on the card,
a CUDA (HIP) graph capture, which hardware decoders PyAV's FFmpeg offers (VA-API), a real VA-API decode of a short
H.264/H.265 clip, and the OpenGL renderer GLFW gets. Each line says OK, WARN or FAIL; nothing here changes the PC.
"""
from __future__ import annotations

import os
import platform
import sys
import time
import traceback

RESULTS: list[tuple[str, str, str]] = []


def report(status: str, name: str, detail: str = "") -> None:
    RESULTS.append((status, name, detail))
    print(f"[{status:4}] {name}" + (f": {detail}" if detail else ""), flush=True)


def check(name: str):
    def wrap(fn):
        def run():
            try:
                fn()
            except Exception as e:  # noqa: BLE001 - each check reports its own failure and the rest go on
                report("FAIL", name, f"{type(e).__name__}: {e}")
                if os.environ.get("AMD_CHECK_TRACE"):
                    traceback.print_exc()
        return run
    return wrap


@check("system")
def system() -> None:
    report("OK", "system", f"{platform.platform()}, Python {platform.python_version()}")
    session = os.environ.get("XDG_SESSION_TYPE", "?")
    report("OK" if session == "wayland" else "WARN", "desktop session", session)
    for dev in ("/dev/kfd", "/dev/dri/renderD128"):
        if not os.path.exists(dev):
            report("FAIL", dev, "missing")
        elif not os.access(dev, os.R_OK | os.W_OK):
            report("FAIL", dev, "no read/write access (add yourself to the 'render' and 'video' groups, then log in again)")
        else:
            report("OK", dev, "readable and writable")


@check("pytorch")
def pytorch() -> None:
    import torch

    hip = getattr(torch.version, "hip", None)
    if not hip:
        report("FAIL", "pytorch", f"{torch.__version__} is not a ROCm build (torch.version.hip is empty)")
        return
    report("OK", "pytorch", f"{torch.__version__}, HIP {hip}")
    if not torch.cuda.is_available():
        report("FAIL", "gpu", "torch.cuda.is_available() is False: ROCm doesn't see the card")
        return
    props = torch.cuda.get_device_properties(0)
    arch = getattr(props, "gcnArchName", "?")
    report("OK" if arch.startswith("gfx120") else "WARN", "gpu",
           f"{props.name}, {arch}, {props.total_memory / 2**30:.1f} GiB")


@check("fp16 compute")
def compute() -> None:
    import torch
    import torch.nn.functional as F

    if not torch.cuda.is_available():
        return
    dev = torch.device("cuda")
    x = torch.randn(1, 16, 1088, 1920, device=dev, dtype=torch.half)
    conv = torch.nn.Conv2d(16, 64, 3, padding=1).to(dev, torch.half)
    grid = torch.rand(1, 1088, 1920, 2, device=dev, dtype=torch.half) * 2 - 1
    with torch.no_grad():
        for _ in range(3):  # warm-up (MIOpen picks its kernels on the first runs)
            y = conv(x)
            F.grid_sample(x, grid, mode="bilinear", padding_mode="border", align_corners=True)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(20):
            y = conv(x)
            F.grid_sample(x, grid, mode="bilinear", padding_mode="border", align_corners=True)
        torch.cuda.synchronize()
    ms = (time.perf_counter() - t0) / 20 * 1000
    if not torch.isfinite(y).all():
        report("FAIL", "fp16 compute", "result has NaN/inf")
    else:
        report("OK", "fp16 compute", f"1080p conv + grid_sample {ms:.2f} ms")


@check("gpu graph")
def graph() -> None:
    import torch

    if not torch.cuda.is_available():
        return
    a = torch.ones(1 << 20, device="cuda")
    b = torch.empty_like(a)
    side = torch.cuda.Stream()
    side.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(side):
        b.copy_(a * 2)
    torch.cuda.current_stream().wait_stream(side)
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g, capture_error_mode="thread_local"):
        b.copy_(a * 2)
    a.fill_(3)
    g.replay()
    torch.cuda.synchronize()
    ok = bool((b == 6).all())
    report("OK" if ok else "FAIL", "gpu graph", "capture and replay work" if ok else "replay gave a wrong result")


@check("pyav")
def pyav() -> None:
    import av
    from av.codec.hwaccel import hwdevices_available

    devs = list(hwdevices_available())
    report("OK", "pyav", f"{av.__version__}, FFmpeg {av.library_versions.get('libavcodec', '?')}, "
                         f"hardware: {', '.join(devs) or 'none'}")
    if "vaapi" not in devs:
        report("WARN", "vaapi in pyav", "PyAV's FFmpeg has no VA-API; decoding falls back to the CPU")


@check("vaapi decode")
def vaapi_decode() -> None:
    import io

    import av
    import numpy as np
    from av.codec.hwaccel import HWAccel, hwdevices_available

    if "vaapi" not in hwdevices_available():
        return
    for codec in ("hevc", "h264"):
        enc_name = {"hevc": "libx265", "h264": "libx264"}[codec]
        buf = io.BytesIO()
        try:
            with av.open(buf, "w", format="mp4") as out:
                s = out.add_stream(enc_name, rate=30)
                s.width, s.height, s.pix_fmt = 1920, 1080, "yuv420p"
                for i in range(30):
                    img = np.full((1080, 1920, 3), (i * 8) % 256, dtype=np.uint8)
                    for p in s.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
                        out.mux(p)
                for p in s.encode():
                    out.mux(p)
        except Exception as e:  # noqa: BLE001
            report("WARN", f"vaapi {codec}", f"couldn't make a test clip ({enc_name}): {e}")
            continue
        buf.seek(0)
        with av.open(buf, hwaccel=HWAccel("vaapi", allow_software_fallback=False)) as inp:
            st = inp.streams.video[0]
            t0 = time.perf_counter()
            n, fmt = 0, "?"
            for fr in inp.decode(st):
                fmt = fr.format.name
                n += 1
            ms = (time.perf_counter() - t0) / max(n, 1) * 1000
        report("OK" if fmt == "vaapi" else "WARN", f"vaapi {codec}",
               f"{n} frames, {ms:.2f} ms/frame, frames come out as {fmt}")


@check("opengl")
def opengl() -> None:
    os.environ.setdefault("PYGLFW_LIBRARY_VARIANT", "wayland" if os.environ.get("WAYLAND_DISPLAY") else "x11")
    import glfw
    from OpenGL import GL

    if not glfw.init():
        report("FAIL", "opengl", "glfw.init() failed")
        return
    try:
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        win = glfw.create_window(64, 64, "amd_check", None, None)
        if not win:
            report("FAIL", "opengl", "couldn't create a window")
            return
        glfw.make_context_current(win)
        renderer = GL.glGetString(GL.GL_RENDERER).decode()
        version = GL.glGetString(GL.GL_VERSION).decode()
        soft = any(w in renderer.lower() for w in ("llvmpipe", "software", "softpipe"))
        report("FAIL" if soft else "OK", "opengl",
               f"{renderer} | {version} | GLFW {os.environ['PYGLFW_LIBRARY_VARIANT']}")
        glfw.destroy_window(win)
    finally:
        glfw.terminate()


def main() -> int:
    for fn in (system, pytorch, compute, graph, pyav, vaapi_decode, opengl):
        fn()
    fails = sum(1 for s, _, _ in RESULTS if s == "FAIL")
    warns = sum(1 for s, _, _ in RESULTS if s == "WARN")
    print(f"\n{fails} FAIL, {warns} WARN. Copy everything above into the chat.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
