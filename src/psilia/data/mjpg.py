"""Reader for `.mjpg` recordings (concatenated JPEG frames + sidecars).

A recording directory looks like:

    recording_dir/
    ├── {stem}.mjpg        # concatenated JPEG frames, one after another
    ├── timestamps.jsonl   # optional: {seq, t_capture, bytes} per frame
    └── metadata.yaml      # optional: frames, fps, width, height, t_start, ...

Two ways to figure out where each frame lives in the .mjpg:

1. Sidecar path (preferred). `timestamps.jsonl` gives us the exact byte size
   of every frame, so the offset of frame i is just the cumulative sum of all
   `bytes` fields up to i. Capture times come straight from the sidecar.

2. Legacy fallback. Old recordings have no sidecar. We scan for JPEG SOI
   markers (the 3-byte `FF D8 FF` signature that starts every JPEG) and treat
   each marker as the start of a frame. Capture times are synthesised from
   `metadata['fps']` if available, otherwise left as None.

The file is mmap'd so reading a single frame is just a slice — no full-file
load up front, the OS pages in what we touch.
"""

from __future__ import annotations

import json
import mmap
from pathlib import Path

import cv2
import numpy as np

from psilia.utils import read_yaml


class MjpgReader:
    """Random-access reader for a single `.mjpg` recording.

    Usage:
        with MjpgReader("path/to/recording_dir") as r:
            t, frame = r[0]              # one frame
            ts, frames = r[10:20]        # a range
            ts, frames = r[[0, 5, 9]]    # arbitrary indices
            r.set_decoded(False)         # return raw JPEG bytes instead
            r.set_channel_order("RGB")   # default is 'BGR' (cv2-native)

    Attributes:
        path:       The .mjpg file being read.
        dir:        Directory containing the .mjpg (and sidecars, if any).
        metadata:   Contents of metadata.yaml, or {} if absent.
        timestamps: list[float | None], one entry per frame. Real capture
                    times from the sidecar when available; otherwise i/fps
                    derived from metadata; otherwise all None.
    """

    def __init__(self, path: str | Path):
        # Accept either the recording directory or the .mjpg file directly.
        # The directory form is the common case (matches how lite.py writes).
        path = Path(path)
        if path.is_dir():
            candidates = sorted(path.glob("*.mjpg"))
            if not candidates:
                raise FileNotFoundError(f"no .mjpg file in {path}")
            self.path = candidates[0]
        elif path.is_file():
            self.path = path
        else:
            raise FileNotFoundError(path)
        self.dir = self.path.parent

        # mmap the file so we can slice frame bytes without loading the
        # whole recording into memory. ACCESS_READ keeps it read-only.
        self._fp = open(self.path, "rb")
        self._mm = mmap.mmap(self._fp.fileno(), 0, access=mmap.ACCESS_READ)

        # Optional metadata sidecar — used for fps fallback and exposed
        # to the user via `self.metadata`.
        meta_path = self.dir / "metadata.yaml"
        self.metadata: dict = read_yaml(meta_path) or {} if meta_path.exists() else {}

        # Build the frame index: byte offset + size for each frame, plus a
        # capture time. Two paths depending on whether the sidecar exists.
        ts_path = self.dir / "timestamps.jsonl"
        offsets: list[int] = []
        sizes: list[int] = []
        timestamps: list[float | None] = []

        if ts_path.exists():
            # Preferred path: walk the sidecar, accumulating offsets from
            # the `bytes` field. Order in the sidecar matches order in the
            # .mjpg, so a running sum gives correct offsets.
            off = 0
            with open(ts_path) as f:
                for line in f:
                    rec = json.loads(line)
                    offsets.append(off)
                    sizes.append(rec["bytes"])
                    timestamps.append(float(rec["t_capture"]))
                    off += rec["bytes"]
        else:
            # Legacy path: no sidecar, so scan the file for JPEG start-of-
            # image markers. Every JPEG begins with FF D8 FF, so each match
            # is (most likely) the start of a frame.
            soi = b"\xff\xd8\xff"
            n = len(self._mm)
            scan: list[int] = []
            i = 0
            while True:
                j = self._mm.find(soi, i)
                if j < 0:
                    break
                scan.append(j)
                i = j + 1  # advance one byte so we don't rematch the same SOI

            # A frame runs from one SOI to the next (or to EOF for the last).
            # The < 1000 byte filter drops spurious SOI matches inside JPEG
            # payloads — real frames from a camera are always much larger.
            # This matches the heuristic used by lite.py's legacy playback.
            for k, s in enumerate(scan):
                e = scan[k + 1] if k + 1 < len(scan) else n
                if e - s < 1000:
                    continue
                offsets.append(s)
                sizes.append(e - s)

            # Synthesise per-frame timestamps from fps if we have it.
            # Otherwise the user gets None and has to live without timing.
            fps = self.metadata.get("fps")
            if fps:
                timestamps = [i / float(fps) for i in range(len(offsets))]
            else:
                timestamps = [None] * len(offsets)

        self._offsets = offsets
        self._sizes = sizes
        self.timestamps = timestamps
        # Default: __getitem__ returns decoded HxWx3 BGR arrays. Flip with
        # set_decoded(False) to get the raw JPEG bytes (e.g. for fast
        # streaming, or to decode with a different library).
        self._decoded = True
        # cv2.imdecode returns BGR. Users who want RGB (matplotlib, PIL,
        # most ML pipelines) can flip this with set_channel_order("RGB").
        self._channel_order = "BGR"

    def set_decoded(self, flag: bool) -> None:
        """Choose what __getitem__ returns for each frame.

        True (default): HxWx3 uint8 ndarray (decoded via cv2.imdecode).
        False:          raw JPEG bytes, exactly as stored in the .mjpg.
        """
        self._decoded = bool(flag)

    def set_channel_order(self, order: str) -> None:
        """Channel order for decoded frames: 'BGR' (default) or 'RGB'.

        cv2.imdecode natively returns BGR — that's the cheap path. 'RGB'
        adds a per-frame `[:, :, ::-1]` view-reversal (no copy), which is
        what matplotlib / PIL / most ML pipelines expect.

        No-op when set_decoded(False): raw JPEG bytes have no channel order.
        """
        order = order.upper()
        if order not in ("BGR", "RGB"):
            raise ValueError(f"channel_order must be 'BGR' or 'RGB', got {order!r}")
        self._channel_order = order

    def __len__(self) -> int:
        """Number of frames in the recording."""
        return len(self._offsets)

    def close(self) -> None:
        """Release the mmap and file handle. Safe to call multiple times via the context manager."""
        self._mm.close()
        self._fp.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _norm(self, i: int) -> int:
        """Normalise an integer index: support negative indexing, bounds-check."""
        if i < 0:
            i += len(self._offsets)
        if not 0 <= i < len(self._offsets):
            raise IndexError(i)
        return i

    def _frame(self, i: int):
        """Return frame i, decoded or raw depending on `self._decoded`. No bounds check (caller does it)."""
        off = self._offsets[i]
        # Slice the mmap to get the JPEG bytes for this frame. `bytes(...)`
        # copies out of the memory map so the result is a regular bytes
        # object — safe to hand back to the caller.
        jpeg = bytes(self._mm[off : off + self._sizes[i]])
        if not self._decoded:
            return jpeg
        # cv2.imdecode wants a 1-D uint8 array; np.frombuffer gives that
        # as a zero-copy view over the bytes. Result is HxWx3 BGR uint8.
        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        # Flip channels to RGB if requested. `[:, :, ::-1]` is a view, not
        # a copy — cheap, but the returned array isn't C-contiguous. Call
        # `.copy()` downstream if a library needs contiguous memory.
        if self._channel_order == "RGB":
            frame = frame[:, :, ::-1]
        return frame

    def __getitem__(self, idx):
        """Look up frame(s) by index.

        - int (incl. negative):   returns (timestamp, frame)
        - slice:                  returns (list[timestamp], list[frame])
        - list/tuple/ndarray:     returns (list[timestamp], list[frame])
        """
        if isinstance(idx, slice):
            indices = list(range(*idx.indices(len(self))))
        elif isinstance(idx, (list, tuple, np.ndarray)):
            indices = [self._norm(int(i)) for i in idx]
        else:
            # Scalar index — single (t, frame) tuple.
            i = self._norm(int(idx))
            return self.timestamps[i], self._frame(i)
        # Multi-index branch — two parallel lists.
        return (
            [self.timestamps[i] for i in indices],
            [self._frame(i) for i in indices],
        )

    def __iter__(self):
        """Yield (timestamp, frame) for every frame in order."""
        for i in range(len(self)):
            yield self[i]
