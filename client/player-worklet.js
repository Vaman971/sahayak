// Audio thread. Ring buffer + jitter buffer for smooth playback.
const PREBUFFER = 960; // 60 ms at 16 kHz
const STATS_EVERY = 50; // process() calls; 50 x 8 ms = 400 ms

class PlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.capacity = 16000 * 5; // 5 s a fixed array of 80000 float slots
    this.ring = new Float32Array(this.capacity);
    this.read = 0; // marks where the speaker reads sample from
    this.write = 0; // marks where the incoming network samples get written
    this.size = 0; // currently how any unplayed samples sit in the buffer
    this.started = false;
    this.underruns = 0; // counts how many times the buffer ran completely dry while the agent was supposed to be talking
    this.minSize = Infinity;
    this.calls = 0;

    // whenever audio arrives over websocket, it forwards the bytes to the worklets
    this.port.onmessage = (e) => {
      if (e.data === "clear") { // barge-in will use this later
        this.read = this.write = this.size = 0; // clear the buffer in 0 milliseconds
        this.started = false; // cutting off playback without waiting for old queued sentences to finish
        return;
      }
      const pcm = new Int16Array(e.data);
      for (let i = 0; i < pcm.length; i++) {
        // if the network delivers faster then the speaker can play and the 5 second buffer fills up
        if (this.size === this.capacity) { // full: drop oldest samples rather than crashing
          this.read = (this.read + 1) % this.capacity; //circular queue
          this.size--;
        }
        this.ring[this.write] = pcm[i] / 0x8000;
        this.write = (this.write + 1) % this.capacity; // circular queue
        this.size++;
      }
    };
  }

  // every 8 ms, the audio sound hardware requests 128 audio samples
  process(_inputs, outputs) {
    const out = outputs[0][0]; // channel 0 output buffer (128 samles)
    if (!this.started && this.size < PREBUFFER) { // still waiting for the prebuffer to fill atleast 60ms of audio
      out.fill(0); // echo silence (that is what 0 means)
    } else {
      this.started = true;
      for (let i = 0; i < out.length; i++) {
        if (this.size > 0) {
          out[i] = this.ring[this.read];
          this.read = (this.read + 1) % this.capacity;
          this.size--;
        } else {
          out[i] = 0; // silence
        }
      }
      // minSize records the lowest sample count observed during this window, if this.size hit zero the buffer ran out of audio
      this.minSize = Math.min(this.minSize, this.size);
      if (this.size === 0) {
        this.underruns++; // amount of times the system had to speack but did not increased
        this.started = false; // forcing the system to wait for another 60 ms pre-buffer before resuming
      }
    }

    if (++this.calls % STATS_EVERY === 0) {
      this.port.postMessage({
        underruns: this.underruns, // total times the audio starved
        bufferMs: this.size / 16, // current buffer headroom in milliseconds
        minBufferMs: this.minSize === Infinity ? null : this.minSize / 16, // The narrowest margin the buffer exerienced in the last 400 ms, if this dips near 0 ms, network jitter is threatening to cause crackling
      });
      this.minSize = Infinity;
    }
    return true;
  }
}
registerProcessor("player", PlayerProcessor);