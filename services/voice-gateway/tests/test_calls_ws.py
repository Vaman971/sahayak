import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from voice_gateway.main import create_app

START = {"type": "start", "sample_rate": 16000, "encoding": "pcm_s16le", "frame_ms": 20}


def test_echo_reassembles_slit_frames() -> None:
    with TestClient(create_app()) as client, client.websocket_connect("/v1/calls/ws") as ws:
        ws.send_json(START)
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["frame_bytes"] == 640  # the amount expected in 1 frame = 20ms

        payload = bytes(range(256)) * 5  # 1280 bytes = exactly 2 frames
        ws.send_bytes(payload[:1000])  # 1 frame + 360 leftover

        assert (
            ws.receive_bytes() == payload[:640]
        )  # first 640 of what amount was sent should be recieved
        ws.send_bytes(payload[1000:])  # complete frame 2 (sending remaining 280)
        assert ws.receive_bytes() == payload[640:]  # the remaining 640 should be recieved

        ws.send_json({"type": "ping", "t": 123.0})
        assert ws.receive_json() == {"type": "pong", "t": 123.0}

        ws.send_json({"type": "stop"})
        summary = ws.receive_json()

        assert summary["type"] == "summary"
        assert summary["frames"] == 2


def test_rejects_unsupported_sample_rate() -> None:
    with TestClient(create_app()) as client, client.websocket_connect("/v1/calls/ws") as ws:
        ws.send_json(
            {**START, "sample_rate": 8000}
        )  # we can manipulate json objects directly by putting **
        err = ws.receive_json()

        assert err["code"] == "bad_start"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
        assert exc.value.code == 4400  # what we set in the api


def test_rejects_audio_before_start() -> None:
    with TestClient(create_app()) as client, client.websocket_connect("/v1/calls/ws") as ws:
        ws.send_bytes(b"\x00" * 640)
        err = ws.receive_json()
        assert err["code"] == "bad_start"
