// AudioWorklet : extrait les échantillons PCM du graphe audio et les poste
// au thread principal (mixés en mono).

class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0] && input[0].length > 0) {
      const ch0 = input[0];
      let mono;
      if (input.length > 1) {
        const ch1 = input[1];
        mono = new Float32Array(ch0.length);
        for (let i = 0; i < ch0.length; i++) mono[i] = (ch0[i] + ch1[i]) / 2;
      } else {
        mono = ch0.slice();
      }
      this.port.postMessage(mono, [mono.buffer]);
    }
    return true; // rester actif
  }
}

registerProcessor('pcm-processor', PCMProcessor);
