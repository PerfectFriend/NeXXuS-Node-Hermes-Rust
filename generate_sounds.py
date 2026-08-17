import numpy as np
from scipy.io import wavfile
import os

output_dir = "/home/thomas/LivingCode/CompleteProjects/superguard_20260816_232832/assets/sounds"
os.makedirs(output_dir, exist_ok=True)

sample_rate = 44100

def generate_tone(frequency, duration, sample_rate=44100, volume=0.5, wave_type='sine'):
    """Generate a tone of given frequency and duration."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    if wave_type == 'sine':
        wave = np.sin(2 * np.pi * frequency * t)
    elif wave_type == 'square':
        wave = np.sign(np.sin(2 * np.pi * frequency * t))
    elif wave_type == 'sawtooth':
        wave = 2 * (t * frequency - np.floor(0.5 + t * frequency))
    else:
        wave = np.sin(2 * np.pi * frequency * t)
    return (wave * volume * 32767).astype(np.int16)

def apply_envelope(audio, attack=0.01, decay=0.1, sustain=0.7, release=0.1, sample_rate=44100):
    """Apply ADSR envelope to audio."""
    total_samples = len(audio)
    attack_samples = int(attack * sample_rate)
    decay_samples = int(decay * sample_rate)
    release_samples = int(release * sample_rate)
    sustain_samples = total_samples - attack_samples - decay_samples - release_samples
    
    if sustain_samples < 0:
        release_samples = max(0, total_samples - attack_samples - decay_samples)
        sustain_samples = 0
    
    envelope = np.ones(total_samples)
    if attack_samples > 0:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    if decay_samples > 0:
        envelope[attack_samples:attack_samples+decay_samples] = np.linspace(1, sustain, decay_samples)
    if sustain_samples > 0:
        envelope[attack_samples+decay_samples:attack_samples+decay_samples+sustain_samples] = sustain
    if release_samples > 0:
        envelope[-release_samples:] = np.linspace(sustain, 0, release_samples)
    
    return (audio * envelope).astype(np.int16)

# 1. Alarm sound - urgent, pulsing
def create_alarm():
    duration = 3.0
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    freq1 = 880  # A5
    freq2 = 698  # F5
    pulse = 0.5 * (1 + np.sign(np.sin(2 * np.pi * 2 * t)))
    wave1 = np.sin(2 * np.pi * freq1 * t) * pulse
    wave2 = np.sin(2 * np.pi * freq2 * t) * (1 - pulse)
    wave = wave1 + wave2
    wave = apply_envelope(wave, attack=0.05, decay=0.1, sustain=0.8, release=0.2, sample_rate=sample_rate)
    return (wave * 0.6 * 32767).astype(np.int16)

# 2. Notification - gentle, pleasant
def create_notification():
    duration = 1.5
    notes = [523.25, 659.25, 783.99, 1046.50]
    note_duration = duration / len(notes)
    audio = np.array([], dtype=np.int16)
    for freq in notes:
        tone = generate_tone(freq, note_duration, sample_rate, volume=0.4, wave_type='sine')
        tone = apply_envelope(tone, attack=0.02, decay=0.05, sustain=0.6, release=0.15, sample_rate=sample_rate)
        audio = np.concatenate([audio, tone])
    return audio

# 3. Startup sound - ascending, confident
def create_startup():
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    freqs = [261.63, 329.63, 392.00, 523.25]
    wave = np.zeros_like(t)
    for i, freq in enumerate(freqs):
        start = i * 0.15
        mask = t >= start
        note_t = t[mask] - start
        note_wave = np.sin(2 * np.pi * freq * note_t)
        env = np.exp(-note_t * 3) * (1 - np.exp(-note_t * 50))
        wave[mask] += note_wave * env * 0.3
    wave = apply_envelope(wave, attack=0.05, decay=0.2, sustain=0.5, release=0.4, sample_rate=sample_rate)
    return (wave * 0.5 * 32767).astype(np.int16)

# 4. Detection sound - subtle, technical
def create_detection():
    duration = 0.8
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    freq_start = 1000
    freq_end = 400
    phase = 2 * np.pi * (freq_start * t + (freq_end - freq_start) * t**2 / (2 * duration))
    wave = np.sin(phase)
    wave = apply_envelope(wave, attack=0.005, decay=0.1, sustain=0.3, release=0.2, sample_rate=sample_rate)
    return (wave * 0.3 * 32767).astype(np.int16)

# 5. Error/failure sound - dissonant, descending
def create_error():
    duration = 1.5
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    freq1 = 440 * 2**(6/12)  # F#4
    freq2 = 440  # A4
    wave = np.sin(2 * np.pi * freq1 * t) * np.exp(-t * 2) + np.sin(2 * np.pi * freq2 * t) * np.exp(-t * 3)
    wave = apply_envelope(wave, attack=0.01, decay=0.1, sustain=0.2, release=0.5, sample_rate=sample_rate)
    return (wave * 0.4 * 32767).astype(np.int16)

# Generate all sounds
sounds = {
    'alarm.wav': create_alarm(),
    'notification.wav': create_notification(),
    'startup.wav': create_startup(),
    'detection.wav': create_detection(),
    'error.wav': create_error(),
}

for filename, audio_data in sounds.items():
    filepath = os.path.join(output_dir, filename)
    wavfile.write(filepath, sample_rate, audio_data)
    print(f"Created: {filepath} ({len(audio_data)/sample_rate:.2f}s)")

print(f"\nAll sounds saved to {output_dir}")
print("Files:", os.listdir(output_dir))