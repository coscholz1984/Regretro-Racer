"""RETRO RACER DELUXE - music.py
Background music: procedurally synthesized looping tracks, one per
screen or mini-game. Each track is 4 bars (32 eighth notes); the tail
of every loop contains a short pausing motif (lead rests over the
bass) so the loops breathe instead of repeating mechanically.

Track format (all lengths in eighth notes):
    "tempo":     seconds per eighth note
    "lead":      one midi note per eighth, played staccato;
                 None = rest (silence for one eighth)
    "bass":      list of (midi note, length in eighths) notes;
                 midi None = rest of that length
    "wave":      lead waveform: "square" (bleepy) or "triangle" (soft)
    "lead_vol" / "bass_vol": mix levels
"""
import array
import math

import pygame

RATE = 22050


def _note_freq(m):
    """Midi note number -> frequency in Hz."""
    return 440.0 * 2 ** ((m - 69) / 12)


# ============================================================================
# MUSIC REGISTRY - add a track by appending one entry here
# ============================================================================
TRACKS = {
    # the classic menu arpeggio: C - Am - F - G over a soft bass;
    # second half pauses for two beats, then rises back to the start
    "menu": {
        "tempo": 0.15,
        "lead": [72, 76, 79, 76, 69, 72, 76, 72,
                 65, 69, 72, 69, 67, 71, 74, 71,
                 72, 76, 79, 76, 69, 72, 76, 72,
                 65, 69, 72, 69, None, None, 67, 71],
        "bass": [(48, 2), (55, 2), (45, 2), (52, 2),
                 (41, 2), (48, 2), (43, 2), (50, 2),
                 (48, 2), (55, 2), (45, 2), (52, 2),
                 (41, 2), (48, 2), (43, 2), (50, 2)],
        "wave": "square", "lead_vol": 0.30, "bass_vol": 0.22,
    },
    # circuit: fast minor rock riff (Em - Em - C - D);
    # the riff falls silent for two beats before slamming back in
    "circuit": {
        "tempo": 0.12,
        "lead": [64, 67, 71, 67, 64, 67, 71, 74,
                 60, 64, 67, 64, 62, 66, 69, 66,
                 64, 67, 71, 67, 64, 67, 71, 74,
                 60, 64, 67, 64, 62, 66, None, None],
        "bass": [(40, 2), (40, 2), (36, 2), (36, 2),
                 (38, 2), (38, 2), (38, 2), (38, 2),
                 (40, 2), (40, 2), (36, 2), (36, 2),
                 (38, 2), (38, 2), (38, 2), (38, 2)],
        "wave": "square", "lead_vol": 0.30, "bass_vol": 0.26,
    },
    # scroll: laid-back highway cruise in A major (A - Bm - D - E);
    # the lead takes a soft breath before the loop drifts back in
    "scroll": {
        "tempo": 0.14,
        "lead": [69, 73, 76, 73, 71, 74, 78, 74,
                 66, 69, 73, 69, 64, 68, 71, 68,
                 69, 73, 76, 73, 71, 74, 78, 74,
                 66, 69, 73, 69, 66, 69, None, None],
        "bass": [(45, 2), (45, 2), (47, 2), (47, 2),
                 (38, 2), (38, 2), (40, 2), (40, 2),
                 (45, 2), (45, 2), (47, 2), (47, 2),
                 (38, 2), (38, 2), (40, 2), (40, 2)],
        "wave": "triangle", "lead_vol": 0.32, "bass_vol": 0.22,
    },
    # dragster: slow, dark and heavy (Dm - Dm - Bb - C);
    # the end idles on a single low thud between two rests
    "dragster": {
        "tempo": 0.17,
        "lead": [50, 53, 57, 53, 50, 53, 58, 53,
                 46, 50, 53, 50, 48, 52, 55, 52,
                 50, 53, 57, 53, 50, 53, 58, 53,
                 46, 50, 53, 50, None, 48, None, None],
        "bass": [(38, 2), (38, 2), (34, 2), (34, 2),
                 (36, 2), (36, 2), (36, 2), (36, 2),
                 (38, 2), (38, 2), (34, 2), (34, 2),
                 (36, 2), (36, 2), (36, 2), (36, 2)],
        "wave": "square", "lead_vol": 0.28, "bass_vol": 0.30,
    },
    # guilt: the court/hospital/meds scenes and the final flashback;
    # a slow minor-key lament that never quite resolves
    "guilt": {
        "tempo": 0.34,
        "lead": [69, None, 72, None, 76, None, 72, None,
                 68, None, 71, None, 64, None, None, None,
                 69, None, 72, None, 77, None, 76, None,
                 74, None, 71, None, 69, None, None, None],
        "bass": [(45, 4), (41, 4), (44, 4), (40, 4),
                 (45, 4), (41, 4), (43, 4), (45, 4)],
        "wave": "triangle", "lead_vol": 0.24, "bass_vol": 0.28,
    },
}


def _to_sound(samples):
    data = array.array("h",
                       [max(-32768, min(32767, int(s * 32767)))
                        for s in samples])
    return pygame.mixer.Sound(buffer=data.tobytes())


def _render(track, haunt=0):
    """Render one track spec into a loopable Sound. haunt (0-3) drags
    the tune: slower, slightly flat, with notes that go missing - and
    from level 2 an actual horror mix: a dread pulse throbs under
    everything and at level 3 a dissonant tritone wail slides on top."""
    h = min(max(int(haunt), 0), 3)
    slow = 1.0 + 0.10 * h              # guilt is heavy: the beat drags
    detune = 2 ** (-0.035 * h)         # ...and the pitch sags
    step = int(RATE * track["tempo"] * slow)
    beats = len(track["lead"])
    buf = [0.0] * (step * beats)
    for i, m in enumerate(track["lead"]):
        if not m:                        # None = rest (pausing motif)
            continue
        if h >= 2 and i % 5 == 3:        # memory lapses: notes go missing
            continue
        n = int(step * 0.9)          # 10% gap -> bleepy staccato
        for k in range(n):
            p = (_note_freq(m) * detune * k / RATE) % 1.0
            if track["wave"] == "triangle" or h >= 3:
                # haunt 3: even the bright tracks sing soft and hollow
                v = 4 * abs(p - 0.5) - 1
            else:
                v = 1.0 if p < 0.5 else -1.0
            buf[i * step + k] += v * track["lead_vol"] * (1 - k / n) ** 1.5
    pos = 0
    for m, eighths in track["bass"]:
        n = int(step * eighths * 0.9)
        if m:                          # midi None = rest of that length
            freq = _note_freq(m) * (0.5 if h >= 3 else 1.0)
            for k in range(n):
                p = (freq * k / RATE) % 1.0
                v = 4 * abs(p - 0.5) - 1          # triangle wave
                buf[pos + k] += v * track["bass_vol"] * (1 - k / n) ** 1.2
        pos += step * eighths
    # the horror layer: at haunt 2+ a slow dread pulse throbs under the
    # tune; at haunt 3 a dissonant tritone wail slides over everything
    if h >= 2:
        pf = _note_freq(31) * (0.5 if h >= 3 else 1.0)
        period = max(1, step * 2)
        for k in range(len(buf)):
            ph = (k % period) / period
            if ph < 0.5:
                buf[k] += 0.20 * math.sin(math.pi * ph * 2) \
                    * math.sin(2 * math.pi * pf * k / RATE)
    if h >= 3:
        wf = _note_freq(75) * 2 ** 0.5            # a bare tritone
        for k in range(len(buf)):
            vib = 1.0 + 0.012 * math.sin(2 * math.pi * 0.7 * k / RATE)
            sw = 0.6 + 0.4 * math.sin(2 * math.pi * 0.21 * k / RATE)
            buf[k] += 0.05 * sw * math.sin(2 * math.pi * wf * vib * k / RATE)
    return _to_sound(buf)


_sounds = {}          # name -> Sound cache (built lazily on first use)
_channel = None       # channel of the currently looping track
_current = None       # name of the currently looping track
_cur_haunt = 0        # haunt level of the currently looping track
_wanted = None        # track the caller asked for (kept across mutes)
_wanted_haunt = 0     # ...and its haunt level


def start_music(app, name, volume=0.45, haunt=0):
    """Loop the named track; switching tracks stops the previous one.
    haunt (0-3) renders a sadder, slower, slightly flat variant - the
    same tune, the way memory plays it back. Does nothing while muted
    or without a working mixer - the track restarts automatically when
    toggle_mute() unmutes."""
    global _channel, _current, _cur_haunt, _wanted, _wanted_haunt
    if name not in TRACKS:
        return
    _wanted, _wanted_haunt = name, min(max(int(haunt), 0), 3)
    if not app.sfx.ok or app.muted:
        return
    if (_channel is not None and _current == name
            and _cur_haunt == _wanted_haunt):
        return                       # already playing exactly this track
    stop_music()
    key = name if not _wanted_haunt else f"{name}#{_wanted_haunt}"
    if key not in _sounds:
        _sounds[key] = _render(TRACKS[name], _wanted_haunt)
    snd = _sounds[key]
    snd.set_volume(volume)
    _channel = snd.play(loops=-1)
    _current = name
    _cur_haunt = _wanted_haunt


def stop_music():
    """Stop whatever track is playing (the request is remembered)."""
    global _channel, _current, _cur_haunt
    if _channel is not None:
        _channel.stop()
        _channel = None
    _current = None
    _cur_haunt = 0


def toggle_mute(app):
    """The M key: mute (stop the music) or unmute (restart the track
    that was last requested)."""
    app.muted = not app.muted
    if app.muted:
        stop_music()
    elif _wanted is not None:
        start_music(app, _wanted, haunt=_wanted_haunt)