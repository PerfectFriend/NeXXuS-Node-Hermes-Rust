/**
 * Sound system for Elemental Life — 15-min procedural soundtrack + ambient SFX.
 * Uses Web Audio API with proper autoplay handling.
 */

type SoundName = 
  | 'ambient' 
  | 'transition' 
  | 'click' 
  | 'elemental-fire' 
  | 'elemental-water' 
  | 'elemental-earth' 
  | 'elemental-air'
  | 'waterfall'
  | 'campfire'
  | 'seagulls'
  | 'crows'
  | 'bard-song';

interface AudioBufferMap {
  [key: string]: AudioBuffer;
}

interface AmbientLayer {
  name: string;
  buffer: AudioBuffer;
  gain: GainNode;
  source: AudioBufferSourceNode | null;
  enabled: boolean;
  baseVolume: number;
}

class SoundSystem {
  private ctx: AudioContext | null = null;
  private buffers: AudioBufferMap = {};
  private sources: Map<string, AudioBufferSourceNode> = new Map();
  private gainNodes: Map<string, GainNode> = new Map();
  private masterGain: GainNode | null = null;
  private musicGain: GainNode | null = null;
  private sfxGain: GainNode | null = null;
  private loaded = false;
  private musicEnabled = true;
  private sfxEnabled = true;
  
  // Ambient layers for the 15-min soundtrack
  private ambientLayers: AmbientLayer[] = [];

  private async ensureContext(): Promise<AudioContext> {
    if (!this.ctx) {
      this.ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      this.masterGain = this.ctx.createGain();
      this.musicGain = this.ctx.createGain();
      this.sfxGain = this.ctx.createGain();
      
      this.musicGain.connect(this.masterGain);
      this.sfxGain.connect(this.masterGain);
      this.masterGain.connect(this.ctx.destination);
      
      this.masterGain.gain.value = 0.5;
      this.musicGain.gain.value = 0.4;
      this.sfxGain.gain.value = 0.6;
    }
    if (this.ctx.state === 'suspended') {
      await this.ctx.resume();
    }
    return this.ctx;
  }

  /** Generate 15-minute procedural ambient soundtrack (900 seconds) */
  private generateSoundtrack(duration = 900): AudioBuffer {
    const ctx = this.ctx!;
    const sampleRate = ctx.sampleRate;
    const length = sampleRate * duration;
    const buffer = ctx.createBuffer(2, length, sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      
      // Pre-calculate some slow modulators for the entire track
      const modulators = {
        verySlow: new Float32Array(length),
        slow: new Float32Array(length),
        med: new Float32Array(length),
      };
      
      for (let i = 0; i < length; i++) {
        const t = i / sampleRate;
        modulators.verySlow[i] = Math.sin(t * 0.0005) * 0.5 + 0.5; // 33 min cycle
        modulators.slow[i] = Math.sin(t * 0.002 + channel * 100) * 0.5 + 0.5; // 8 min cycle
        modulators.med[i] = Math.sin(t * 0.01 + channel * 200) * 0.5 + 0.5; // 1.6 min cycle
      }

      for (let i = 0; i < length; i++) {
        const t = i / sampleRate;
        const vSlow = modulators.verySlow[i];
        const slow = modulators.slow[i];
        const med = modulators.med[i];

        // === DEEP DRONE LAYER (always present) ===
        const drone1 = Math.sin(t * 41.2 * 2 * Math.PI) * 0.12; // E1
        const drone2 = Math.sin(t * 55 * 2 * Math.PI) * 0.1;    // A1
        const drone3 = Math.sin(t * 82.41 * 2 * Math.PI) * 0.08; // E2
        const droneMod = Math.sin(t * 0.001) * 0.3 + 0.7;

        // === EVOLVING PAD LAYER ===
        const padFreq1 = 110 * (1 + slow * 0.15); // A2 with slow drift
        const padFreq2 = 164.81 * (1 + med * 0.1); // E3
        const padFreq3 = 220 * (1 + vSlow * 0.05); // A3
        const pad1 = Math.sin(t * padFreq1 * 2 * Math.PI + Math.sin(t * 0.05) * 0.8) * 0.06 * slow;
        const pad2 = Math.sin(t * padFreq2 * 2 * Math.PI + Math.sin(t * 0.08) * 0.5) * 0.04 * med;
        const pad3 = Math.sin(t * padFreq3 * 2 * Math.PI) * 0.03 * vSlow;

        // === SUBTLE ARPEGGIO (comes and goes) ===
        const arpActive = vSlow > 0.6;
        let arp = 0;
        if (arpActive) {
          const arpSpeed = 0.25;
          const arpNotes = [110, 130.81, 146.83, 164.81, 196, 220, 246.94, 293.66];
          const arpIndex = Math.floor(t * arpSpeed) % arpNotes.length;
          const arpEnv = Math.max(0, Math.sin(t * 0.3)) * 0.5 + 0.5;
          arp = Math.sin(t * arpNotes[arpIndex] * 2 * Math.PI) * 0.015 * arpEnv * (vSlow - 0.5) * 2;
        }

        // === WATER SHIMMER (periodic) ===
        const shimmerActive = med > 0.4;
        let shimmer = 0;
        if (shimmerActive) {
          shimmer = Math.sin(t * 880 * 2 * Math.PI + Math.sin(t * 1.5) * 2) * 0.01 * (med - 0.3) * 1.4;
        }

        // === VINYL TEXTURE (very subtle) ===
        const noise = (Math.random() * 2 - 1) * 0.003 * Math.max(0, Math.sin(t * 0.02));

        // === COMBINE WITH STEREO SPREAD ===
        let sample = (drone1 + drone2 + drone3) * droneMod + pad1 + pad2 + pad3 + arp + shimmer + noise;

        // Stereo width
        if (channel === 0) sample *= 0.9 + Math.sin(t * 0.06) * 0.1;
        else sample *= 1.1 - Math.sin(t * 0.06) * 0.1;

        // Gentle limiter
        sample = Math.tanh(sample * 1.2) * 0.6;

        data[i] = sample;
      }
    }
    return buffer;
  }

  /** Generate waterfall ambient (continuous) */
  private generateWaterfall(): AudioBuffer {
    const ctx = this.ctx!;
    const duration = 30; // 30 sec loop
    const sampleRate = ctx.sampleRate;
    const length = sampleRate * duration;
    const buffer = ctx.createBuffer(2, length, sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      for (let i = 0; i < length; i++) {
        const t = i / sampleRate;
        // Multi-layered water noise
        let sample = 0;
        // Low rumble
        sample += (Math.random() * 2 - 1) * 0.08 * Math.max(0, Math.sin(t * 0.5));
        // Mid splash
        sample += (Math.random() * 2 - 1) * 0.12 * Math.max(0, Math.sin(t * 2.3));
        // High spray
        sample += (Math.random() * 2 - 1) * 0.06 * Math.max(0, Math.sin(t * 7.1));
        // Periodic droplets
        const droplet = Math.sin(t * 800 * 2 * Math.PI) * Math.exp(-(t % 0.5) * 20) * 0.03;
        sample += droplet;
        // Stereo
        data[i] = Math.tanh(sample) * 0.4 * (channel === 0 ? 0.9 : 1.1);
      }
    }
    return buffer;
  }

  /** Generate campfire ambient (continuous) */
  private generateCampfire(): AudioBuffer {
    const ctx = this.ctx!;
    const duration = 20;
    const sampleRate = ctx.sampleRate;
    const length = sampleRate * duration;
    const buffer = ctx.createBuffer(2, length, sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      for (let i = 0; i < length; i++) {
        const t = i / sampleRate;
        let sample = 0;
        // Crackling embers
        for (let j = 0; j < 8; j++) {
          const seed = t * 50 + j * 500;
          const crackle = Math.sin(seed * 12.9898) * 43758.5453;
          if (crackle % 1 < 0.0008) {
            sample += Math.exp(-(t - Math.floor(t * 20) * 0.05) * 30) * 0.15;
          }
        }
        // Low fire roar
        sample += (Math.random() * 2 - 1) * 0.05 * Math.max(0, Math.sin(t * 1.7));
        // Occasional pop
        if (Math.random() < 0.0002) sample += (Math.random() * 2 - 1) * 0.2 * Math.exp(-t * 5);
        
        data[i] = Math.tanh(sample) * 0.35 * (channel === 0 ? 1 : 1.05);
      }
    }
    return buffer;
  }

  /** Generate seagulls (sporadic) */
  private generateSeagulls(): AudioBuffer {
    const ctx = this.ctx!;
    const duration = 60;
    const sampleRate = ctx.sampleRate;
    const length = sampleRate * duration;
    const buffer = ctx.createBuffer(2, length, sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      for (let i = 0; i < length; i++) data[i] = 0;

      // Place 8-12 gull calls randomly
      const numCalls = 8 + Math.floor(Math.random() * 5);
      for (let c = 0; c < numCalls; c++) {
        const startTime = Math.random() * (duration - 2);
        const startSample = Math.floor(startTime * sampleRate);
        const callDuration = 0.8 + Math.random() * 1.2;
        const callSamples = Math.floor(callDuration * sampleRate);
        
        const baseFreq = 800 + Math.random() * 600;
        const freqMod = 1 + (Math.random() - 0.5) * 0.3;
        
        for (let s = 0; s < callSamples && startSample + s < length; s++) {
          const t = s / sampleRate;
          const progress = t / callDuration;
          const env = Math.sin(progress * Math.PI) * Math.exp(-progress * 2);
          const freq = baseFreq * freqMod * (1 + Math.sin(t * 5) * 0.15);
          const sample = Math.sin(2 * Math.PI * freq * t) * env * 0.15;
          const idx = startSample + s;
          data[idx] = (data[idx] || 0) + sample * (channel === 0 ? 1 : 0.8);
        }
      }
      // Apply tanh limiter
      for (let i = 0; i < length; i++) {
        data[i] = Math.tanh(data[i] * 1.5) * 0.5;
      }
    }
    return buffer;
  }

  /** Generate crows (sporadic) */
  private generateCrows(): AudioBuffer {
    const ctx = this.ctx!;
    const duration = 45;
    const sampleRate = ctx.sampleRate;
    const length = sampleRate * duration;
    const buffer = ctx.createBuffer(2, length, sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      for (let i = 0; i < length; i++) data[i] = 0;

      const numCalls = 5 + Math.floor(Math.random() * 4);
      for (let c = 0; c < numCalls; c++) {
        const startTime = Math.random() * (duration - 1.5);
        const startSample = Math.floor(startTime * sampleRate);
        const callDuration = 0.4 + Math.random() * 0.6;
        const callSamples = Math.floor(callDuration * sampleRate);
        
        // Caw: harsh, descending frequency
        for (let s = 0; s < callSamples && startSample + s < length; s++) {
          const t = s / sampleRate;
          const progress = t / callDuration;
          const env = Math.exp(-progress * 3) * (1 - progress * 0.5);
          const freq = 400 * (1.5 - progress * 0.8);
          const sample = Math.sin(2 * Math.PI * freq * t) * env * 0.12;
          const idx = startSample + s;
          data[idx] = (data[idx] || 0) + sample * (channel === 0 ? 1 : 0.7);
        }
      }
      for (let i = 0; i < length; i++) data[i] = Math.tanh(data[i] * 2) * 0.5;
    }
    return buffer;
  }

  /** Generate bard song with guitar (melodic, 2-3 min loop) */
  private generateBardSong(): AudioBuffer {
    const ctx = this.ctx!;
    const duration = 180; // 3 min loop
    const sampleRate = ctx.sampleRate;
    const length = sampleRate * duration;
    const buffer = ctx.createBuffer(2, length, sampleRate);

    // Simple "unknown language" vocal melody + guitar
    const melodyNotes = [
      220, 246.94, 261.63, 293.66, 329.63, 349.23, 392, 440, // A3..A4
      392, 349.23, 329.63, 293.66, 261.63, 246.94, 220, 196  // descending
    ];
    const noteDuration = duration / melodyNotes.length;

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      
      for (let i = 0; i < length; i++) {
        const t = i / sampleRate;
        const noteIndex = Math.floor(t / noteDuration) % melodyNotes.length;
        const noteFreq = melodyNotes[noteIndex];
        const noteProgress = (t % noteDuration) / noteDuration;
        
        // Guitar: plucked string simulation
        const guitarEnv = Math.exp(-noteProgress * 8) * Math.max(0, Math.cos(noteProgress * Math.PI * 0.5));
        const guitar = Math.sin(t * noteFreq * 2 * Math.PI) * guitarEnv * 0.08;
        
        // Vocal: formant-like synthesis
        const vocalEnv = Math.sin(noteProgress * Math.PI) * 0.5;
        const f1 = noteFreq * 2.5; // Formant 1
        const f2 = noteFreq * 4.2; // Formant 2
        const vocal = (Math.sin(t * f1 * 2 * Math.PI) * 0.6 + Math.sin(t * f2 * 2 * Math.PI) * 0.4) * vocalEnv * 0.05;
        
        // Occasional harmony
        const harmony = Math.sin(noteProgress * Math.PI * 2) > 0.5 ? 
          Math.sin(t * noteFreq * 1.5 * 2 * Math.PI) * guitarEnv * 0.03 : 0;

        let sample = guitar + vocal + harmony;
        
        // Stereo
        if (channel === 0) sample *= 1.1;
        else sample *= 0.9;
        
        data[i] = Math.tanh(sample) * 0.4;
      }
    }
    return buffer;
  }

  async loadAll(): Promise<void> {
    if (this.loaded) return;
    await this.ensureContext();

    // Main 15-min soundtrack
    this.buffers.soundtrack = this.generateSoundtrack(900);
    
    // Ambient layers
    this.buffers.waterfall = this.generateWaterfall();
    this.buffers.campfire = this.generateCampfire();
    this.buffers.seagulls = this.generateSeagulls();
    this.buffers.crows = this.generateCrows();
    this.buffers.bardSong = this.generateBardSong();

    // SFX
    this.buffers.transition = this.generateTransition();
    this.buffers.click = this.generateClick();
    this.buffers['elemental-fire'] = this.generateElemental('fire');
    this.buffers['elemental-water'] = this.generateElemental('water');
    this.buffers['elemental-earth'] = this.generateElemental('earth');
    this.buffers['elemental-air'] = this.generateElemental('air');

    this.loaded = true;
  }

  /** Start the 15-min soundtrack with ambient layers */
  startSoundtrack(): void {
    if (!this.ctx || !this.buffers.soundtrack || !this.musicEnabled) return;
    
    // Main soundtrack
    const mainSrc = this.ctx.createBufferSource();
    mainSrc.buffer = this.buffers.soundtrack;
    mainSrc.loop = true;
    const mainGain = this.ctx.createGain();
    mainGain.gain.value = 0.35;
    mainGain.connect(this.musicGain!);
    mainSrc.connect(mainGain);
    mainSrc.start(this.ctx.currentTime);
    
    this.ambientLayers.push({
      name: 'soundtrack',
      buffer: this.buffers.soundtrack,
      gain: mainGain,
      source: mainSrc,
      enabled: true,
      baseVolume: 0.35,
    });

    // Waterfall (always on if enabled)
    if (this.buffers.waterfall) {
      const wfSrc = this.ctx.createBufferSource();
      wfSrc.buffer = this.buffers.waterfall;
      wfSrc.loop = true;
      const wfGain = this.ctx.createGain();
      wfGain.gain.value = 0.15;
      wfGain.connect(this.musicGain!);
      wfSrc.connect(wfGain);
      wfSrc.start(this.ctx.currentTime + Math.random() * 5);
      
      this.ambientLayers.push({
        name: 'waterfall',
        buffer: this.buffers.waterfall,
        gain: wfGain,
        source: wfSrc,
        enabled: true,
        baseVolume: 0.15,
      });
    }

    // Campfire
    if (this.buffers.campfire) {
      const cfSrc = this.ctx.createBufferSource();
      cfSrc.buffer = this.buffers.campfire;
      cfSrc.loop = true;
      const cfGain = this.ctx.createGain();
      cfGain.gain.value = 0.12;
      cfGain.connect(this.musicGain!);
      cfSrc.connect(cfGain);
      cfSrc.start(this.ctx.currentTime + 2 + Math.random() * 3);
      
      this.ambientLayers.push({
        name: 'campfire',
        buffer: this.buffers.campfire,
        gain: cfGain,
        source: cfSrc,
        enabled: true,
        baseVolume: 0.12,
      });
    }

    // Seagulls (sporadic - restart periodically)
    this.scheduleSporadic('seagulls', 0.1, 30, 80);
    this.scheduleSporadic('crows', 0.08, 45, 120);
    this.scheduleSporadic('bardSong', 0.12, 180, 240);
  }

  private scheduleSporadic(name: string, volume: number, minInterval: number, maxInterval: number): void {
    if (!this.ctx || !this.buffers[name]) return;
    
    const playOnce = () => {
      if (!this.musicEnabled) return;
      const src = this.ctx!.createBufferSource();
      src.buffer = this.buffers[name];
      const gain = this.ctx!.createGain();
      gain.gain.value = volume;
      gain.connect(this.musicGain!);
      src.connect(gain);
      src.start(this.ctx!.currentTime);
      
      src.onended = () => {
        const nextDelay = minInterval + Math.random() * (maxInterval - minInterval);
        setTimeout(playOnce, nextDelay * 1000);
      };
    };
    
    // Start after random initial delay
    setTimeout(playOnce, (5 + Math.random() * 15) * 1000);
  }

  stopSoundtrack(): void {
    for (const layer of this.ambientLayers) {
      if (layer.source) {
        try { layer.source.stop(); } catch {}
      }
    }
    this.ambientLayers = [];
  }

  toggleMusic(enabled: boolean): void {
    this.musicEnabled = enabled;
    if (this.musicGain) {
      this.musicGain.gain.value = enabled ? 0.4 : 0;
    }
    if (!enabled) this.stopSoundtrack();
    else if (this.ctx && this.loaded) this.startSoundtrack();
  }

  isMusicEnabled(): boolean { return this.musicEnabled; }

  toggleSfx(enabled: boolean): void {
    this.sfxEnabled = enabled;
    if (this.sfxGain) this.sfxGain.gain.value = enabled ? 0.6 : 0;
  }

  isSfxEnabled(): boolean { return this.sfxEnabled; }

  play(name: SoundName, options: { loop?: boolean; volume?: number; delay?: number } = {}): void {
    if (!this.ctx || !this.buffers[name] || !this.sfxEnabled) return;
    if (name.startsWith('elemental-') || name === 'click' || name === 'transition') {
      // These go through SFX bus
    } else {
      // Ambient layers handled separately
      return;
    }

    const buffer = this.buffers[name];
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = options.loop ?? false;

    const gain = this.ctx.createGain();
    gain.gain.value = options.volume ?? 1;
    gain.connect(this.sfxGain!);

    source.connect(gain);
    const startTime = this.ctx.currentTime + (options.delay ?? 0);
    source.start(startTime);

    const key = `${name}-${Date.now()}`;
    this.sources.set(key, source);
    this.gainNodes.set(key, gain);

    source.onended = () => {
      this.sources.delete(key);
      this.gainNodes.delete(key);
    };
  }

  stop(name?: SoundName): void {
    if (name) {
      for (const [key, source] of this.sources) {
        if (key.startsWith(name)) {
          try { source.stop(); } catch {}
          this.sources.delete(key);
          this.gainNodes.delete(key);
        }
      }
    } else {
      for (const source of this.sources.values()) {
        try { source.stop(); } catch {}
      }
      this.sources.clear();
      this.gainNodes.clear();
    }
  }

  setMasterVolume(volume: number): void {
    if (this.masterGain) this.masterGain.gain.value = Math.max(0, Math.min(1, volume));
  }

  getMasterVolume(): number { return this.masterGain?.gain.value ?? 0.5; }

  setMusicVolume(volume: number): void {
    if (this.musicGain) this.musicGain.gain.value = Math.max(0, Math.min(1, volume));
    for (const layer of this.ambientLayers) {
      layer.gain.gain.value = layer.baseVolume * volume / 0.4;
    }
  }

  setSfxVolume(volume: number): void {
    if (this.sfxGain) this.sfxGain.gain.value = Math.max(0, Math.min(1, volume));
  }

  isLoaded(): boolean { return this.loaded; }

  // Private generators (unchanged from before)
  private generateTransition(): AudioBuffer { /* ... */ const ctx=this.ctx!; const d=1.5; const sr=ctx.sampleRate; const l=sr*d; const b=ctx.createBuffer(2,l,sr); for(let ch=0;ch<2;ch++){const d2=b.getChannelData(ch); for(let i=0;i<l;i++){const t=i/sr; const p=t/d; const f=100+p*2000; d2[i]=Math.tanh((Math.sin(2*Math.PI*f*t)*Math.pow(1-p,2)*0.3+Math.sin(2*Math.PI*60*t)*Math.exp(-t*10)*0.4+Math.sin(2*Math.PI*2000*t)*Math.exp(-t*5)*0.15))*0.6;}} return b; }
  private generateClick(): AudioBuffer { const ctx=this.ctx!; const d=0.1; const sr=ctx.sampleRate; const l=sr*d; const b=ctx.createBuffer(2,l,sr); for(let ch=0;ch<2;ch++){const d2=b.getChannelData(ch); for(let i=0;i<l;i++){const t=i/sr; d2[i]=Math.tanh(Math.sin(2*Math.PI*(800+Math.sin(t*1000)*200)*t)*Math.exp(-t*50)*0.2);}} return b; }
  private generateElemental(type: 'fire'|'water'|'earth'|'air'): AudioBuffer { const ctx=this.ctx!; const d=2; const sr=ctx.sampleRate; const l=sr*d; const b=ctx.createBuffer(2,l,sr); for(let ch=0;ch<2;ch++){const d2=b.getChannelData(ch); for(let i=0;i<l;i++){const t=i/sr; let s=0; switch(type){case 'fire': for(let j=0;j<5;j++){const sd=t*100+j*1000; if(Math.sin(sd*12.9898)*43758.5453%1<0.001)s+=Math.exp(-(t-Math.floor(t*10)*0.1)*50)*0.3;} s+=Math.sin(t*80*2*Math.PI)*0.1*Math.exp(-t); break; case 'water': s=(Math.random()*2-1)*0.15+Math.sin(t*220*2*Math.PI+Math.sin(t*2))*0.08+Math.sin(t*800*2*Math.PI)*Math.exp(-t*3)*0.05; break; case 'earth': s=Math.sin(t*40*2*Math.PI)*0.2*Math.exp(-t*0.5)+Math.sin(t*120*2*Math.PI)*Math.exp(-t*8)*0.3+(Math.random()*2-1)*0.05*Math.exp(-t*2); break; case 'air': s=(Math.random()*2-1)*0.1*Math.max(0,Math.sin(t*0.5))+Math.sin(t*523.25*2*Math.PI)*Math.exp(-t*1.5)*0.15+Math.sin(t*659.25*2*Math.PI)*Math.exp(-t*2)*0.1+Math.sin(t*783.99*2*Math.PI)*Math.exp(-t*2.5)*0.08; break;} d2[i]=Math.tanh(s)*0.5;}} return b; }
}

export const soundSystem = new SoundSystem();

export function useSound() {
  return {
    play: (name: SoundName, options?: { loop?: boolean; volume?: number; delay?: number }) => soundSystem.play(name, options),
    stop: (name?: SoundName) => soundSystem.stop(name),
    setMasterVolume: (vol: number) => soundSystem.setMasterVolume(vol),
    setMusicVolume: (vol: number) => soundSystem.setMusicVolume(vol),
    setSfxVolume: (vol: number) => soundSystem.setSfxVolume(vol),
    getMasterVolume: () => soundSystem.getMasterVolume(),
    toggleMusic: (enabled: boolean) => soundSystem.toggleMusic(enabled),
    toggleSfx: (enabled: boolean) => soundSystem.toggleSfx(enabled),
    isMusicEnabled: () => soundSystem.isMusicEnabled(),
    isSfxEnabled: () => soundSystem.isSfxEnabled(),
    startSoundtrack: () => soundSystem.startSoundtrack(),
    stopSoundtrack: () => soundSystem.stopSoundtrack(),
    loadAll: () => soundSystem.loadAll(),
    isLoaded: () => soundSystem.isLoaded(),
  };
}