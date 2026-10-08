class FrameAssembler:
    """Re-slices an arbitrary byte stream into exact fixed-size frames.

    WebSocket messages can split or merge frames. This guarantees every frame
    handed downstream is exactly `frame_bytes` long; leftovers wait for more data.
    """

    def __init__(self, frame_bytes: int) -> None:
        if frame_bytes <= 0:
            raise ValueError("frame_bytes can not be negative")
        self._frame_bytes = frame_bytes
        self._buf = bytearray()  # an empty buffer for extra or incomplete bytes

    def push(self, data: bytes) -> list[bytes]:
        self._buf.extend(data)

        n = len(self._buf) // self._frame_bytes  # no. of full frames avaiable

        if n == 0:
            return []  # wait for remaining bytes to complete one frame

        cut = n * self._frame_bytes

        frames = [
            bytes(self._buf[i : i + self._frame_bytes]) for i in range(0, cut, self._frame_bytes)
        ]

        del self._buf[:cut]  # remove the processed frames
        return frames

    @property
    def pending(self) -> int:
        return len(self._buf)
