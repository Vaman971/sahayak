const WS_URL = "ws://localhost:8000/v1/calls/ws";
const SAMPLE_RATE = 16000;
const FRAME_MS = 20;
const FRAME_SAMPLES = (SAMPLE_RATE * FRAME_MS) / 1000;

const $ = (id) => document.getElementById(id);
const log = (m) => {
  $("log").textContent += `${new Date().toISOString().slice(11, 23)} ${m}\n`;
  $("log").scrollTop = 1e9;
};

let ctx, ws, stream, pingTimer;

function meter(buf) {
  const s = new Int16Array(buf);
  let sum = 0;
  for (let i = 0; i < s.length; i++) {
    const x = s[i] / 32768;
    sum += x * x;
  }
  $("level").value = Math.max(-60, 10 * Math.log10(sum / s.length + 1e-12));
}

async function start() {
  $("start").disabled = true;
  ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
  await ctx.audioWorklet.addModule("./capture-worklet.js");
  await ctx.audioWorklet.addModule("./player-worklet.js");

  stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  log(`AudioContext sampleRate=${ctx.sampleRate}`);

  const mic = ctx.createMediaStreamSource(stream);
  const capture = new AudioWorkletNode(ctx, "capture", {
    processorOptions: { frameSamples: FRAME_SAMPLES },
  });
  const mute = ctx.createGain();
  mute.gain.value = 0; // keeps capture in the graph without playing the mic
  mic.connect(capture).connect(mute).connect(ctx.destination);

  const player = new AudioWorkletNode(ctx, "player");
  player.connect(ctx.destination);
  player.port.onmessage = (e) => ($("underruns").textContent = e.data.underruns);

  ws = new WebSocket(WS_URL);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    ws.send(JSON.stringify({
      type: "start", sample_rate: SAMPLE_RATE, encoding: "pcm_s16le", frame_ms: FRAME_MS,
    }));
  };

  ws.onmessage = (e) => {
    if (typeof e.data !== "string") {
      player.port.postMessage(e.data, [e.data]);
      return;
    }
    const msg = JSON.parse(e.data);
    if (msg.type === "ready") {
      log(`ready call_id=${msg.call_id} frame_bytes=${msg.frame_bytes}`);
      capture.port.onmessage = (ev) => {
        meter(ev.data);
        if (ws.readyState === WebSocket.OPEN) ws.send(ev.data);
      };
      pingTimer = setInterval(() => {
        ws.send(JSON.stringify({ type: "ping", t: performance.now() }));
      }, 2000);
      $("stop").disabled = false;
    } else if (msg.type === "pong") {
      $("rtt").textContent = (performance.now() - msg.t).toFixed(1);
    } else {
      log(JSON.stringify(msg));
    }
  };

  ws.onclose = (e) => {
    log(`ws closed code=${e.code}`);
    cleanup();
  };
}

function stop() {
  $("stop").disabled = true;
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "stop" }));
}

function cleanup() {
  clearInterval(pingTimer);
  stream?.getTracks().forEach((t) => t.stop());
  ctx?.close();
  $("start").disabled = false;
  $("stop").disabled = true;
}

$("start").onclick = () => start().catch((err) => { log(`error: ${err}`); cleanup(); });
$("stop").onclick = stop;