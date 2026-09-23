# HOT
import numpy as np
import wave
import os
from datetime import datetime

def save_wav(filename, data, sample_rate=44100):
    """Save numpy array as WAV file."""
    # Ensure data is in the correct range and format
    if data.dtype != np.int16:
        # Normalize to [-1, 1] and convert to 16-bit PCM
        data = np.clip(data, -1.0, 1.0)
        data = (data * 32767).astype(np.int16)
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())

def generate_ambient(duration=60, sample_rate=44100):
    """Generate ambient drone: low frequency with slow modulation."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Base frequency: 110 Hz (A2)
    base = 110.0
    # Slow modulation: 0.1 Hz
    mod = 0.1 * np.sin(2 * np.pi * 0.1 * t)
    # Generate tone with frequency modulation
    freq = base * (1.0 + 0.1 * mod)
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate
    wave_data = np.sin(phase)
    # Add some noise for texture
    noise = 0.05 * np.random.normal(size=len(t))
    wave_data += noise
    # Apply envelope to avoid clicks
    envelope = np.ones_like(t)
    attack = int(0.1 * sample_rate)
    release = int(0.1 * sample_rate)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-release:] = np.linspace(1, 0, release)
    wave_data *= envelope
    return wave_data

def generate_battle(duration=30, sample_rate=44100):
    """Generate battle theme: rhythmic bass and drum-like hits."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Bass line: 80 Hz with a driving rhythm
    bass_freq = 80.0
    # Rhythm: 4 beats per second (120 BPM)
    beat = 4.0
    # Create a pulse for each beat
    bass_env = np.zeros_like(t)
    for i in range(int(duration * beat)):
        start = int(i * sample_rate / beat)
        end = int((i + 0.3) * sample_rate / beat)  # 30% of beat for note
        if end < len(t):
            bass_env[start:end] = np.linspace(0, 1, end-start)
            bass_env[start:end] *= np.linspace(1, 0, end-start)
    bass_wave = np.sin(2 * np.pi * bass_freq * t) * bass_env
    # Drum-like hits: snare on 2 and 4, kick on 1 and 3
    # We'll generate noise bursts for snare and low thump for kick
    drum = np.zeros_like(t)
    for i in range(int(duration * beat)):
        t_start = i * sample_rate / beat
        # Kick on beats 0 and 2 (1 and 3)
        if i % 2 == 0:
            start = int(t_start)
            end = int(t_start + 0.05 * sample_rate)  # 50ms
            if end < len(t):
                # Low frequency thump
                kick = np.sin(2 * np.pi * 60 * np.linspace(0, 1, end-start)) * np.linspace(1, 0, end-start)
                drum[start:end] += kick * 0.5
        # Snare on beats 1 and 3 (2 and 4)
        else:
            start = int(t_start)
            end = int(t_start + 0.1 * sample_rate)  # 100ms
            if end < len(t):
                # Noise burst
                snare = np.random.normal(size=end-start) * np.linspace(1, 0, end-start)
                drum[start:end] += snare * 0.3
    # Combine bass and drums
    wave_data = bass_wave + drum
    # Apply envelope
    envelope = np.ones_like(t)
    attack = int(0.05 * sample_rate)
    release = int(0.05 * sample_rate)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-release:] = np.linspace(1, 0, release)
    wave_data *= envelope
    return wave_data

def generate_menu(duration=30, sample_rate=44100):
    """Generate menu theme: gentle arpeggio in major key."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Notes in C major: C4, E4, G4, C5 (arpeggio)
    notes = [261.63, 329.63, 392.00, 523.25]  # Hz
    note_duration = 0.5  # seconds per note
    wave_data = np.zeros_like(t)
    for i, note in enumerate(notes):
        start = int(i * note_duration * sample_rate)
        end = int((i + 1) * note_duration * sample_rate)
        if end > len(t):
            end = len(t)
        if start >= len(t):
            break
        # Sine wave for the note
        local_t = np.linspace(0, note_duration, end-start, False)
        wave = np.sin(2 * np.pi * note * local_t)
        # Apply ADSR envelope
        attack = int(0.01 * sample_rate)
        decay = int(0.1 * sample_rate)
        sustain_level = 0.7
        release = int(0.05 * sample_rate)
        if len(local_t) > attack + decay + release:
            env = np.ones_like(local_t)
            env[:attack] = np.linspace(0, 1, attack)
            env[attack:attack+decay] = np.linspace(1, sustain_level, decay)
            env[attack+decay:-release] = sustain_level
            env[-release:] = np.linspace(sustain_level, 0, release)
            wave *= env
        wave_data[start:end] += wave * 0.3  # Reduce volume to avoid clipping
    # Loop the arpeggio
    # We'll repeat the pattern for the duration
    pattern_length = int(len(notes) * note_duration * sample_rate)
    if pattern_length > 0:
        repeats = int(len(t) / pattern_length) + 1
        for r in range(1, repeats):
            start = r * pattern_length
            end = min(start + pattern_length, len(t))
            if start >= len(t):
                break
            wave_data[start:end] = wave_data[0:end-start]
    # Apply overall envelope to avoid clicks at start/end
    envelope = np.ones_like(t)
    attack = int(0.1 * sample_rate)
    release = int(0.1 * sample_rate)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-release:] = np.linspace(1, 0, release)
    wave_data *= envelope
    return wave_data

def generate_victory(duration=30, sample_rate=44100):
    """Generate victory fanfare: uplifting major key melody."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Simple fanfare: C4, E4, G4, C5, G4, E4, C4 (quarter notes)
    notes = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63, 261.63]
    note_duration = 0.5  # seconds per note (120 BPM)
    wave_data = np.zeros_like(t)
    for i, note in enumerate(notes):
        start = int(i * note_duration * sample_rate)
        end = int((i + 1) * note_duration * sample_rate)
        if end > len(t):
            end = len(t)
        if start >= len(t):
            break
        # Sine wave for the note
        local_t = np.linspace(0, note_duration, end-start, False)
        wave = np.sin(2 * np.pi * note * local_t)
        # Apply ADSR envelope (quick attack, medium decay, sustain, release)
        attack = int(0.01 * sample_rate)
        decay = int(0.1 * sample_rate)
        sustain_level = 0.7
        release = int(0.05 * sample_rate)
        if len(local_t) > attack + decay + release:
            env = np.ones_like(local_t)
            env[:attack] = np.linspace(0, 1, attack)
            env[attack:attack+decay] = np.linspace(1, sustain_level, decay)
            env[attack+decay:-release] = sustain_level
            env[-release:] = np.linspace(sustain_level, 0, release)
            wave *= env
        wave_data[start:end] += wave * 0.4  # Slightly louder
    # Loop the fanfare
    pattern_length = int(len(notes) * note_duration * sample_rate)
    if pattern_length > 0:
        repeats = int(len(t) / pattern_length) + 1
        for r in range(1, repeats):
            start = r * pattern_length
            end = min(start + pattern_length, len(t))
            if start >= len(t):
                break
            wave_data[start:end] = wave_data[0:end-start]
    # Apply overall envelope
    envelope = np.ones_like(t)
    attack = int(0.1 * sample_rate)
    release = int(0.1 * sample_rate)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-release:] = np.linspace(1, 0, release)
    wave_data *= envelope
    return wave_data

def main():
    project = "elemental-life"
    track_types = ["ambient", "battle", "menu", "victory"]
    base_dir = os.path.join("/home/thomas/LivingCode", "Projects", project, "assets", "music")
    os.makedirs(base_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for track_type in track_types:
        print(f"Generating {track_type}...")
        if track_type == "ambient":
            data = generate_ambient(duration=60)
        elif track_type == "battle":
            data = generate_battle(duration=30)
        elif track_type == "menu":
            data = generate_menu(duration=30)
        elif track_type == "victory":
            data = generate_victory(duration=30)
        filename = os.path.join(base_dir, f"{track_type}_{timestamp}.wav")
        save_wav(filename, data)
        print(f"Saved to {filename}")
    # Generate a simple TTS placeholder using a beep? We'll skip TTS for now.
    print("Music generation complete.")

if __name__ == "__main__":
    main()