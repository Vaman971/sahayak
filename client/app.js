const WS_URL = "ws://localhost:8000/v1/calls/ws";
const SAMPLE_RATE = 16000;
const FRAME_MS = 20;
const FRAME_SAMPLES = (SAMPLE_RATE * FRAME_MS) / 1000;

const $ = (id) => document.getElementById(id); // to get html elements
const log = (m) => {
  $("log").textContent += `${new Date().toISOString().slice(11, 23)} ${m}\n`;
  $("log").scrollTop = 1e9;
};

let ctx, ws, stream, pingTimer, gapTimer;
let lastCapture = 0;
let maxGap = 0;

/**
 Calculats the `dBFS` loudness from 640 raw bytes and moves the green <meter> bar on the screen*/
function meter(buf) {
  const s = new Int16Array(buf);
  let sum = 0;
  for (let i = 0; i < s.length; i++) {
    const x = s[i] / 32768; // normalize to value between -1 to 1 (a float 32)
    sum += x * x; // square
  }
  $("level").value = Math.max(-60, 10 * Math.log10(sum / s.length + 1e-12)); // calculating dBFS
}

async function start() {
  $("start").disabled = true; // once the audio has started to be recieved, disable start button
  const dsp = $("dsp").checked; // set browsers own echoCancellation, noise Suppresion and autoGain control
  ctx = new AudioContext({ sampleRate: SAMPLE_RATE }); // 16000 Khz (browsers internal c++ engine does the work of compression)
  await ctx.audioWorklet.addModule("./capture-worklet.js"); // load the capture workscript into background thread 
  await ctx.audioWorklet.addModule("./player-worklet.js"); // load the player workscipt into background thread

  // requesting for microphone
  // with this, the browser pops-up (allow site to access the mic), if accepted stream gives you raw access to the hardware mic
  stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,  // 1 for Mono, and 2 for sterio
      echoCancellation: dsp, // checked or unchecked
      noiseSuppression: dsp, // ""
      autoGainControl: dsp  // ""
    },
  });

  const settings = stream.getAudioTracks()[0].getSettings();
  log(`AudioContext=${ctx.sampleRate} Hz, mic=${settings.sampleRate ?? "?"} Hz, dsp=${dsp}`);

  const mic = ctx.createMediaStreamSource(stream); // The faucet where raw audio enters
  const capture = new AudioWorkletNode(ctx, "capture", {
    processorOptions: { frameSamples: FRAME_SAMPLES }, // 320
  }); // Our CaptureProcessor worklet node, it manipulates the sound
  const mute = ctx.createGain(); // to control the volume
  mute.gain.value = 0; // keeps capture in the graph without playing the mic
  mic.connect(capture).connect(mute).connect(ctx.destination); // an audio node will not execute unless it is connected all the way to ctx.destination (speakers)

  const player = new AudioWorkletNode(ctx, "player");
  player.connect(ctx.destination); // this is the seperate output pipe, whatever player-worklet.js outputs goes straight to your speaker

  player.port.onmessage = (e) => { // every 400 ms player reports how much cushion remians in the jitter buffer, wheather the resevior ran dry (underruns), and the narrowest safety margin observed (minbuf)
    $("underruns").textContent = e.data.underruns;
    $("buf").textContent = e.data.bufferMs.toFixed(0);
    $("minbuf").textContent = e.data.minBufferMs === null ? "–" : e.data.minBufferMs.toFixed(0);
  }; // setting what postMessage of player returns

  ws = new WebSocket(WS_URL); // th websocket object for connections.
  ws.binaryType = "arraybuffer"; // binary audio comes as ArrayBuffer, not Blob

  ws.onopen = () => { // opening the websocket connection
    ws.send(JSON.stringify({
      type: "start", sample_rate: SAMPLE_RATE, encoding: "pcm_s16le", frame_ms: FRAME_MS,
    })); // before sending single byte of voice the browser sends a JSON card saying, "I want to talk at 16Khz, 20 ms frames, in 16-bt PCM format"
  };

  ws.onmessage = (e) => { // this receives ready, with the server attaching call_id and sending back a response: {"type": "ready", "call_id": "ada01acfa7d9", "frame_bytes": 640}
    if (typeof e.data !== "string") {
      player.port.postMessage(e.data, [e.data]); // if the message is binary (non text), zero math is required, directly feed the e.data down to player using zero-copy memory transfer
      // player will place those bytes in its 60ms jitter buffer, pull them out at the exact 16Khz sample rate
      return;
    }
    const msg = JSON.parse(e.data);
    if (msg.type === "ready") { // here the floodgates open
      log(`ready call_id=${msg.call_id} frame_bytes=${msg.frame_bytes}`);
      // this is what happens, every 20ms you speak -> finishes packing 320 samples and fires this.port.postMessage
      capture.port.onmessage = (ev) => {
        const now = performance.now();
        if (lastCapture) maxGap = Math.max(maxGap, now - lastCapture); // if 20ms fraes are arriving every 20.1 ms, your broser's audio clock is healthy, if it jumps to 55ms, the computer's CPU is chocking
        lastCapture = now;
        meter(ev.data); // calculating the loudness
        if (ws.readyState === WebSocket.OPEN) ws.send(ev.data); // send raw 640 byte binary packet
      };
      pingTimer = setInterval(() => {
        ws.send(JSON.stringify({ type: "ping", t: performance.now() }));
      }, 2000); // every 2s cehck the server health
      gapTimer = setInterval(() => {
        $("capgap").textContent = maxGap.toFixed(1);
        maxGap = 0;
      }, 1000); // every 1s change the max gap if it changed
      $("stop").disabled = false;
    } else if (msg.type === "pong") {
      $("rtt").textContent = (performance.now() - msg.t).toFixed(1); // if server returns pong, te round trp time is set in milliseconds
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

/**This stops the timer, shuts off the browser's mic permission light, and frees the audio hardware so the system does not leak memory  */
function cleanup() {
  clearInterval(pingTimer);
  clearInterval(gapTimer);
  lastCapture = 0;
  maxGap = 0;
  stream?.getTracks().forEach((t) => t.stop()); // shuts offf red microphone light
  ctx?.close(); // Frees sound card hardware
  $("start").disabled = false;
  $("stop").disabled = true;
}

$("start").onclick = () => start().catch((err) => { log(`error: ${err}`); cleanup(); });
$("stop").onclick = stop;