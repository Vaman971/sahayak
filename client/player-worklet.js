// Audio thread. Ring buffer + jitter buffer for smooth playback.
const PREBUFFER = 960; // 60 ms at 16 kHz

class PlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.capacity = 16000 * 5; // 5 s
    this.ring = new Float32Array(this.capacity);
    this.read = 0;
    this.write = 0;
    this.size = 0;
    this.started = false;
    this.underruns = 0;

    this.port.onmessage = (e) => {
      if (e.data === "clear") { // barge-in will use this later
        this.read = this.write = this.size = 0;
        this.started = false;
        return;
      }
      const pcm = new Int16Array(e.data);
      for (let i = 0; i < pcm.length; i++) {
        if (this.size === this.capacity) { // full: drop oldest
          this.read = (this.read + 1) % this.capacity;
          this.size--;
        }
        this.ring[this.write] = pcm[i] / 0x8000;
        this.write = (this.write + 1) % this.capacity;
        this.size++;
      }
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    if (!this.started && this.size < PREBUFFER) {
      out.fill(0);
      return true;
    }
    this.started = true;
    for (let i = 0; i < out.length; i++) {
      if (this.size > 0) {
        out[i] = this.ring[this.read];
        this.read = (this.read + 1) % this.capacity;
        this.size--;
      } else {
        out[i] = 0;
      }
    }
    if (this.size === 0) {
      this.underruns++;
      this.started = false;
      this.port.postMessage({ underruns: this.underruns });
    }
    return true;
  }
}
registerProcessor("player", PlayerProcessor);