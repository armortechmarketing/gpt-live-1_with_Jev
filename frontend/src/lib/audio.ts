const OUTPUT_RATE = 24000;

export function downsample(input: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate) return input;
  const ratio = inputRate / outputRate;
  const length = Math.floor(input.length / ratio);
  const output = new Float32Array(length);
  for (let i = 0; i < length; i += 1) {
    const position = i * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, input.length - 1);
    const mix = position - left;
    output[i] = input[left] * (1 - mix) + input[right] * mix;
  }
  return output;
}

export function floatToPcm16(samples: Float32Array): Uint8Array {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < samples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return bytes;
}

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const size = 0x8000;
  for (let i = 0; i < bytes.length; i += size) {
    binary += String.fromCharCode(...bytes.subarray(i, i + size));
  }
  return btoa(binary);
}

export function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export class PcmPlayer {
  private nextTime = 0;

  constructor(private context: AudioContext) {}

  play(pcm: Uint8Array): void {
    const length = Math.floor(pcm.byteLength / 2);
    if (length === 0) return;
    const view = new DataView(pcm.buffer, pcm.byteOffset, length * 2);
    const floats = new Float32Array(length);
    for (let i = 0; i < length; i += 1) floats[i] = view.getInt16(i * 2, true) / 32768;
    const buffer = this.context.createBuffer(1, length, OUTPUT_RATE);
    buffer.copyToChannel(floats, 0);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    const start = Math.max(this.context.currentTime + 0.08, this.nextTime);
    source.start(start);
    this.nextTime = start + buffer.duration;
  }

  reset(): void {
    this.nextTime = 0;
  }
}

export async function startMicrophone(onPcm: (audio: string) => void): Promise<() => void> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const silent = context.createGain();
  silent.gain.value = 0;
  processor.onaudioprocess = (event) => {
    const channel = event.inputBuffer.getChannelData(0);
    const pcm = floatToPcm16(downsample(channel, context.sampleRate, OUTPUT_RATE));
    if (pcm.byteLength > 0) onPcm(bytesToBase64(pcm));
  };
  source.connect(processor);
  processor.connect(silent);
  silent.connect(context.destination);
  return () => {
    processor.onaudioprocess = null;
    processor.disconnect();
    source.disconnect();
    silent.disconnect();
    stream.getTracks().forEach((track) => track.stop());
    void context.close();
  };
}
