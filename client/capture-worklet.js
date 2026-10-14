// Audio thread. Receives 128-sample float32 blocks at the context rate (16Khz)
class CaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super(); // initialize all the attributes
    this.frameSamples = options.processorOptions.frameSamples; // 320
    this.buf = new Int16Array(this.frameSamples); // a pre-allocated memory buffer holding ip to 320 16 bit numbers
    this.n = 0; // pointer to how many samples we have filled into this.buf
  }

  process(inputs) {
    // ch is a Float32Array storing the 128 (8ms) audio chunk (in decimals) between [-1 to 1]
    const ch = inputs[0][0]; // first 0 -> input device (microphone), and second for channel (mono(0) or sterio)
    if (!ch) return true; // if mic disconnected, keep it alive
    for (let i = 0; i < ch.length; i++) {
      const s = Math.max(-1, Math.min(1, ch[i])); // safety check to keep number betweem -1 and 1
      this.buf[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff; // hexadecimal for 16 bit integer limits
      if (this.n === this.frameSamples) {
        this.port.postMessage(this.buf.buffer, [this.buf.buffer]); // transfer, no copy
        this.buf = new Int16Array(this.frameSamples); //reset to start collecting the next 320 samples
        this.n = 0; // reset
      }
    }
    return true;
  }
}

registerProcessor("capture", CaptureProcessor); // tell browser audio engin to register this class under the name capture, so app.js can attach it to microphone
