// Audio thread. Receives 128-sample float32 blocks at the context rate (16 kHz).
class CaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.frameSamples = options.processorOptions.frameSamples; // 320
    this.buf = new Int16Array(this.frameSamples);
    this.n = 0;
  }

  process(inputs) {
    const ch = inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      const s = Math.max(-1, Math.min(1, ch[i]));
      this.buf[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      if (this.n === this.frameSamples) {
        this.port.postMessage(this.buf.buffer, [this.buf.buffer]); // transfer, no copy
        this.buf = new Int16Array(this.frameSamples);
        this.n = 0;
      }
    }
    return true;
  }
}
registerProcessor("capture", CaptureProcessor);