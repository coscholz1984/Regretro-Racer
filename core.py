"""RETRO RACER DELUXE - core.py
Shared engine, no game code: window/App shell, synthesized sounds,
save files (leaderboards + cash wallet) and the BaseGame class that
every mini-game builds on."""
import array
import json
import math
import os
import random

import pygame

import music


# ------------------------------ configuration ------------------------------
VW, VH = 960, 600          # window size
FPS = 60
PIX = 3                     # sprite pixel scale

LB_CIRCUIT = "leaderboard_circuit.json"    # circuit mode: best 3-lap times
LB_SCROLL = "leaderboard_scroll.json"    # scroll mode: best 3000 m times
LB_DRAGSTER = "leaderboard_dragster.json"    # dragster: best quarter-mile times


def lb_path(name):
    try:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    except NameError:
        return name


def load_board(name):
    """Top-10 fastest times for a mode, persisted next to the script.
    Entries without a 'time' field are ignored."""
    try:
        with open(lb_path(name)) as f:
            board = [e for e in json.load(f) if "time" in e]
        return sorted(board, key=lambda e: e["time"])[:10]
    except (OSError, ValueError):
        return []


def save_board(name, board):
    try:
        with open(lb_path(name), "w") as f:
            json.dump(board, f)
    except OSError:
        pass  # read-only filesystem: leaderboard stays session-only


# ------------------------------ cash rewards --------------------------------
CASH_FILE = "cash.json"
CASH_BILL = 20          # value of one cash bill pickup


def load_profile():
    """(cash, owned car indices, selected car) persisted in cash.json."""
    try:
        with open(lb_path(CASH_FILE)) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            d = {}
        owned = d.get("owned", [0])
        if not isinstance(owned, list) or not owned:
            owned = [0]
        sel = d.get("selected", 0)
        if sel not in owned:
            sel = owned[0]
        return int(d.get("cash", 0)), owned, int(sel)
    except (OSError, ValueError):
        return 0, [0], 0


def save_profile(cash, owned, selected):
    """Merge wallet/car data into cash.json (keeps other keys, e.g.
    the player profile, so nothing overwrites its sibling data)."""
    try:
        with open(lb_path(CASH_FILE)) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            d = {}
    except (OSError, ValueError):
        d = {}
    d.update({"cash": cash, "owned": owned, "selected": selected})
    try:
        with open(lb_path(CASH_FILE), "w") as f:
            json.dump(d, f)
    except OSError:
        pass


def load_skin():
    """Player skin (name, clothes, hair, hats) persisted in cash.json
    under the "profile" key."""
    try:
        with open(lb_path(CASH_FILE)) as f:
            d = json.load(f)
        sk = d.get("profile", {}) if isinstance(d, dict) else {}
    except (OSError, ValueError):
        sk = {}
    hats = sk.get("hats", [0])
    if not isinstance(hats, list) or not hats:
        hats = [0]
    meds = sk.get("meds", [])
    if not isinstance(meds, list):
        meds = []
    return {"name": str(sk.get("name", "CHAMP"))[:12] or "CHAMP",
            "clothes": int(sk.get("clothes", 0)),
            "hair": int(sk.get("hair", 0)),
            "hats": hats, "hat": int(sk.get("hat", 0)),
            "meds": [m for m in meds if isinstance(m, int)],
            "med": int(sk.get("med", 0))}


def save_skin(skin):
    """Merge the player skin into cash.json (keeps cash/owned/selected)."""
    try:
        with open(lb_path(CASH_FILE)) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            d = {}
    except (OSError, ValueError):
        d = {}
    d["profile"] = skin
    try:
        with open(lb_path(CASH_FILE), "w") as f:
            json.dump(d, f)
    except OSError:
        pass  # read-only filesystem: skin stays session-only


def load_cash():
    return load_profile()[0]


# --------------------------- the haunt (story arc) ----------------------------
# Retro Racer Deluxe slowly reveals its dark backstory: after a couple
# of races the game "remembers" an illegal street-racing past that
# ended in a drugged, fatal crash. Progress is persisted in cash.json
# under the "haunt" key and merges like everything else:
#   finishes - races completed (all mini-games combined)
#   play     - seconds actually spent racing
#   scenes   - court/hospital/meds scenes already relived
#   truth    - 1 after the final flashback has been seen
# Stages: 0 innocent, 1 echoes, 2 corruption, 3 haunting,
#         4 collapse (races replaced by scenes), 5 aftermath.
HAUNT_FINISH_STAGES = [2, 5, 8, 11]       # finishes that trigger stages 1-4
HAUNT_PLAY_STAGES = [150, 400, 700, 1000]  # ...or this many raced seconds
HAUNT_TITLES = ["RETRO RACER DELUXE", "REGRETRO RACER", "REGRET RACER",
                "REGRET RACER", "REGRET RACER", "REGRET RACER"]


def load_haunt():
    try:
        with open(lb_path(CASH_FILE)) as f:
            d = json.load(f)
        h = d.get("haunt", {}) if isinstance(d, dict) else {}
    except (OSError, ValueError):
        h = {}
    if not isinstance(h, dict):
        h = {}
    scenes = h.get("scenes", [])
    if not isinstance(scenes, list):
        scenes = []
    return {"finishes": max(0, int(h.get("finishes", 0))),
            "play": max(0.0, float(h.get("play", 0.0))),
            "scenes": [s for s in scenes if isinstance(s, str)],
            "truth": 1 if h.get("truth") else 0,
            "arcade": 1 if h.get("arcade") else 0}


def save_haunt(h):
    """Merge the haunt progress into cash.json (keeps all sibling keys)."""
    try:
        with open(lb_path(CASH_FILE)) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            d = {}
    except (OSError, ValueError):
        d = {}
    d["haunt"] = h
    try:
        with open(lb_path(CASH_FILE), "w") as f:
            json.dump(d, f)
    except OSError:
        pass


def note_finish():
    """A race was completed: the story creeps one step further."""
    h = load_haunt()
    h["finishes"] += 1
    save_haunt(h)


def note_play(secs):
    """Add raced seconds to the haunt clock (finishes count too)."""
    if secs <= 0:
        return
    h = load_haunt()
    h["play"] += float(secs)
    save_haunt(h)


def mark_scene(key):
    """One of the court/hospital/meds scenes has been relived."""
    h = load_haunt()
    if key not in h["scenes"]:
        h["scenes"].append(key)
        save_haunt(h)


def mark_truth():
    """The final flashback has been seen: only the memorial remains."""
    h = load_haunt()
    h["truth"] = 1
    save_haunt(h)


def reset_haunt():
    """Forget the whole arc (the memorial's BACKSPACE): fresh story."""
    try:
        with open(lb_path(CASH_FILE)) as f:
            d = json.load(f)
        if isinstance(d, dict) and "haunt" in d:
            del d["haunt"]
            with open(lb_path(CASH_FILE), "w") as f:
                json.dump(d, f)
    except (OSError, ValueError):
        pass


def haunt_stage():
    """0 innocent ... 4 collapse, 5 aftermath (after the truth)."""
    h = load_haunt()
    if h["truth"]:
        return 5
    st = 0
    for i in range(len(HAUNT_FINISH_STAGES)):
        if (h["finishes"] >= HAUNT_FINISH_STAGES[i]
                or h["play"] >= HAUNT_PLAY_STAGES[i]):
            st = i + 1
    return st


def arcade_mode():
    """True once the story is finished and the player switched to
    arcade mode: the normal mini-games, just for cash."""
    return bool(load_haunt()["arcade"])


def set_arcade(on):
    """Switch between the story and arcade mode. Cash, records and
    story progress are all kept - only the mode flag changes."""
    h = load_haunt()
    h["arcade"] = 1 if on else 0
    save_haunt(h)


def play_haunt():
    """The haunt level the games and menus should USE: the story
    stage - or 0 in arcade mode, where the past no longer leaks into
    the races. The story itself keeps its own stage (haunt_stage)."""
    return 0 if arcade_mode() else haunt_stage()


def haunt_title():
    """The game's name: it rots from RETRO RACER to REGRET RACER (and
    is innocent again in arcade mode)."""
    return HAUNT_TITLES[min(play_haunt(), 5)]


def add_cash(amount):
    """Credit cash to the persistent wallet; returns the new total."""
    cash, owned, sel = load_profile()
    cash += amount
    save_profile(cash, owned, sel)
    return cash


def reward_multiplier(race_time, par):
    """Faster than par pays up to 2x, slower than par always 1x."""
    return max(1.0, min(2.0, par / max(1.0, race_time)))


# --------------------------------- sound ------------------------------------
class SFX:
    """Procedurally synthesized sound effects shared by both modes."""

    def __init__(self):
        self.ok = True
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(22050, -16, 1)
        except pygame.error:
            self.ok = False
            return

        def to_sound(samples):
            data = array.array("h",
                               [max(-32768, min(32767, int(s * 32767))) for s in samples])
            return pygame.mixer.Sound(buffer=data.tobytes())

        # engine loops: 10 pitch steps, low rumbly tone
        self.engines = []
        rng = random.Random(3)
        for i in range(10):
            f = 26 * (2 ** (i * 0.22))          # 26 Hz .. ~106 Hz
            n = int(22050 * 0.3)
            self.engines.append(to_sound(
                [0.55 * math.sin(2 * math.pi * f * k / 22050)
                 + 0.35 * math.sin(math.pi * f * k / 22050)
                 + 0.12 * math.sin(6 * math.pi * f * k / 22050)
                 + 0.05 * rng.uniform(-1, 1)
                 for k in range(n)]))
        # off-road rumble: low-passed noise loop (circuit mode)
        n = int(22050 * 0.25)
        rng = random.Random(7)
        lp, prev = [], 0.0
        for _ in range(n):
            prev = prev * 0.9 + rng.uniform(-1, 1) * 0.1
            lp.append(prev * 3)
        self.offroad = to_sound(lp)
        # crash: decaying noise burst
        n = int(22050 * 0.2)
        self.crash = to_sound([(random.random() * 2 - 1) * (1 - k / n) ** 2
                               for k in range(n)])
        # pickup / refuel blip
        n = int(22050 * 0.06)
        self.blip = to_sound([math.sin(2 * math.pi * 1300 * k / 22050) * 0.6
                              for k in range(n)])
        # low-fuel warning (scroll mode)
        n = int(22050 * 0.12)
        self.warn = to_sound([math.sin(2 * math.pi * 520 * k / 22050) * 0.5
                              for k in range(n)])
        # game over thud (scroll mode)
        n = int(22050 * 0.5)
        self.thud = to_sound([math.sin(2 * math.pi * 70 * k / 22050)
                              * 0.8 * (1 - k / n) for k in range(n)])
        # lap / finish ding
        n = int(22050 * 0.4)
        self.ding = to_sound([math.sin(2 * math.pi * 880 * k / 22050) * 0.5
                              * (1 - k / n) for k in range(n)])
        # start beep
        n = int(22050 * 0.3)
        self.go = to_sound([math.sin(2 * math.pi * 660 * k / 22050) * 0.5
                            * (1 - k / n) for k in range(n)])
        # scare sting: a short falling, beating shriek (the jump frames)
        n = int(22050 * 0.45)
        self.scare = to_sound([
            (math.sin(2 * math.pi * 640 * (1 - 0.5 * k / n) * k / 22050)
             + math.sin(2 * math.pi * 676 * (1 - 0.5 * k / n) * k / 22050))
            * 0.55 * (1 - k / n) ** 1.3
            for k in range(n)])

        # looping background music lives in music.py (TRACKS registry)


# --------------------------------- shell ------------------------------------
class App:
    """Shared window, fonts, sounds and mute state."""

    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self.fullscreen = False
        self.screen = pygame.display.set_mode((VW, VH))
        pygame.display.set_caption("RETRO RACER DELUXE")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 18, bold=True)
        self.font_big = pygame.font.SysFont("monospace", 42, bold=True)
        self.font_small = pygame.font.SysFont("monospace", 14)
        self.sfx = SFX()
        self.muted = False

    def toggle_fullscreen(self):
        """F11: switch between window and fullscreen.

        pygame.SCALED keeps the internal 960x600 surface and stretches it
        to the monitor (letterboxed), so all drawing code works unchanged."""
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            try:
                self.screen = pygame.display.set_mode(
                    (VW, VH), pygame.FULLSCREEN | pygame.SCALED)
            except pygame.error:
                # older pygame without SCALED: switch resolution directly
                self.screen = pygame.display.set_mode(
                    (VW, VH), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((VW, VH))


def play(app, name, volume=1.0):
    if app.sfx.ok and not app.muted:
        snd = getattr(app.sfx, name)
        snd.set_volume(volume)
        snd.play()


# random encouragement the corner driver shouts during a race
DRIVER_CHEERS = ["Go! Go! Go!", "You can do it!", "Nice driving!",
                 "Keep pushing!", "Full speed ahead!", "You're on fire!",
                 "Smooth moves!", "Watch the corners!"]

# what the driver says once the suppressed memories start leaking
# through (haunt_stage is the key: 1 unease, 2 guilt, 3 terror)
HAUNT_CHEERS = {
    1: ["did the radio say our name?", "i know this road...",
        "someone waved at us. i waved back.",
        "the dashboard smells like rain.",
        "that billboard wasn't there yesterday.",
        "we raced here once. at night."],
    2: ["why are the mirrors full of red?",
        "don't look at the roadside crosses.",
        "my hands remember this wheel.",
        "the engine hums a funeral song.",
        "we shouldn't have raced that night.",
        "the seatbelt is still sticky."],
    3: ["they're following us. don't slow down.",
        "it wasn't the engine that screamed.",
        "i never stopped. i never stopped.",
        "the same headlights. always the same.",
        "don't close your eyes. don't."],
}
HAUNT_STARTS = {1: "let's go. again.",
                2: "one more. like that night.",
                3: "they let us race. why?"}

# words that flash across the screen for a heartbeat when the haunt
# jumps (drawn by BaseGame.draw_scare): stages 2-3 inside the races,
# stage 4 inside the court / hospital / nightstand scenes
HAUNT_SCARE_WORDS = {
    2: ["REMEMBER", "NOVEMBER", "THE BYPASS", "WATCH THE ROAD",
        "TOO FAST", "WHO IS THAT?", "SLOW DOWN"],
    3: ["YOU DID NOT BRAKE", "HE IS STILL DRIVING",
        "THE FIGURE STEPPED OUT", "FIVE CARS. ELEVEN PEOPLE.",
        "THEY ARE IN THE ROAD", "TURN BACK"],
    4: ["GUILTY", "ON ALL COUNTS", "ROOM 214", "SWALLOW",
        "THE DRAWER IS OPEN", "THEY NEVER WENT HOME"],
}

# pygame 2.1.3+ can invert a surface in one call; older versions fall
# back to a sickly dim instead (see BaseGame.draw_scare)
_INVERT_OK = hasattr(pygame.transform, "invert")


class BaseGame:
    """Things both game modes share: HUD panels, overlays, sound helpers."""

    def __init__(self, app):
        self.app = app
        self.font = app.font
        self.font_big = app.font_big
        self.font_small = app.font_small
        self.sfx = app.sfx
        self.exited = False          # True -> quit the whole application
        self.engine_ch = None
        self.offroad_ch = None
        self._eng_idx = -1
        # how far the dark backstory has crept in (0..5, see the haunt)
        # - in arcade mode the races are always innocent
        self.haunt = play_haunt()
        # driver-in-the-corner HUD (face + speech bubble)
        self.driver_surf = None
        self.driver_msg = ""
        self.driver_msg_t = 0.0
        self.driver_next = random.uniform(9.0, 16.0)
        # shared haunt fx: sudden scare frames + explosion fireballs
        self.scare = 0.0            # seconds of scare frame left (0 = none)
        self.scare_kind = 0
        self.scare_msg = ""
        self.scare_t = random.uniform(8.0, 20.0)
        self.boom = []              # explosion fireballs: [(age, x, y)]

    @property
    def screen(self):
        # always the current window surface, even after a fullscreen toggle
        return self.app.screen

    def snd(self, name, volume=1.0):
        play(self.app, name, volume)

    def stop_loops(self):
        if self.engine_ch:
            self.engine_ch.stop()
            self.engine_ch = None
        if self.offroad_ch:
            self.offroad_ch.stop()
            self.offroad_ch = None
        self._eng_idx = -1
        music.stop_music()          # background music is stopped too

    # ------------------- driver HUD (cheering co-driver) --------------------
    def driver_hud_say(self, msg, dur=2.5):
        """Show a short comment in the driver's speech bubble."""
        self.driver_msg = msg
        self.driver_msg_t = dur

    def race_start_line(self):
        """What the driver says at the green light - it changes as the
        guilt surfaces."""
        return HAUNT_STARTS.get(getattr(self, "haunt", 0), "Go! Go! Go!")

    def driver_cheer(self, dt):
        """Tick the bubble timer and shout encouragement now and then."""
        self.driver_msg_t = max(0.0, self.driver_msg_t - dt)
        self.driver_next -= dt
        if self.driver_next <= 0:
            self.driver_next = random.uniform(9.0, 16.0)
            pool = HAUNT_CHEERS.get(getattr(self, "haunt", 0)) or DRIVER_CHEERS
            self.driver_hud_say(random.choice(pool))

    # ------------------- shared haunt fx (scares + booms) -------------------
    def reset_fx(self):
        """Fresh scare/explosion state (each game's reset() calls this)."""
        self.scare = 0.0
        self.scare_kind = 0
        self.scare_msg = ""
        self.scare_t = random.uniform(8.0, 20.0)
        self.boom = []

    def update_fx(self, dt, active=True):
        """Tick the shared haunt fx: explosion fireballs always burn
        out; and at haunt stage 2+ the picture suddenly jumps now and
        then - then flips back to normal as if nothing happened."""
        self.boom = [(a + dt, x, y) for (a, x, y) in self.boom
                    if a + dt < 1.8]
        if self.scare > 0:
            self.scare -= dt
            return
        if not active or self.haunt < 2:
            return
        self.scare_t -= dt
        if self.scare_t <= 0:
            self.scare = random.uniform(0.16, 0.4)
            self.scare_kind = random.randrange(3)
            words = HAUNT_SCARE_WORDS.get(min(self.haunt, 4))
            self.scare_msg = random.choice(words) if words else ""
            self.scare_t = random.uniform(10.0, 30.0)
            self.snd("scare", 0.7)

    def explode_at(self, x, y, big=True):
        """Spawn the fireball that replaces a car that exploded (or
        crashed head-on somewhere it never should have been)."""
        for _ in range(3 if big else 1):
            self.boom.append((random.uniform(-0.2, 0.0),
                              x + random.uniform(-24, 24),
                              y + random.uniform(-16, 16)))

    def draw_boom(self, s):
        """Explosion fireballs: white-hot flash, fireball, dying red,
        then a dark smoke stain that lingers over everything."""
        for a, x, y in self.boom:
            if a < 0:
                continue
            if a < 0.12:                    # white-hot flash
                col, rad = (255, 255, 225), int(10 + 260 * a)
            elif a < 0.5:                   # fireball
                col, rad = (255, 170, 40), int(58 + 60 * a)
            elif a < 1.0:                   # dying red
                col, rad = (200, 60, 25), int(88 - 20 * a)
            else:                           # smoke
                col, rad = (70, 62, 60), int(68 + 40 * (a - 1.0))
            pygame.draw.circle(s, col, (int(x), int(y)), rad)

    def draw_scare(self, s):
        """The jump frame: the whole picture twists for a heartbeat -
        blood wash, inverted contrast or a blackout, plus one word
        from the past - then the game continues as if nothing happened."""
        if self.scare <= 0:
            return
        if self.scare_kind == 0:            # everything washes blood red
            s.fill((150, 20, 20), special_flags=pygame.BLEND_RGB_MULT)
        elif self.scare_kind == 1:          # contrast inverted
            if _INVERT_OK:
                s.blit(pygame.transform.invert(s), (0, 0))
            else:                           # older pygame: sickly dim
                s.fill((140, 130, 110), special_flags=pygame.BLEND_RGB_MULT)
        else:                               # the lights go out
            s.fill((36, 36, 42), special_flags=pygame.BLEND_RGB_MULT)
        if self.scare_msg:
            col = (20, 20, 24) if self.scare_kind == 1 else (255, 46, 40)
            txt = self.font_big.render(self.scare_msg, True, col)
            s.blit(txt, txt.get_rect(center=(VW / 2, VH / 2)))

    def draw_driver_hud(self, pos=(12, 12)):
        """Small face + torso of the player's driver in a corner, with a
        semi-transparent speech bubble - kept tiny so it never blocks
        the view of the race."""
        if self.driver_surf is None:
            from sprites import driver_face_surface   # local import:
            sk = load_skin()                          # sprites -> core
            self.driver_surf = driver_face_surface(
                sk["clothes"], sk["hair"], sk["hat"], 4,
                mood=min(4, getattr(self, "haunt", 0)))
        x, y = pos
        self.screen.blit(self.driver_surf, (x, y))
        if self.driver_msg_t > 0 and self.driver_msg:
            txt = self.font_small.render(self.driver_msg, True,
                                         (255, 255, 255))
            bx = x + self.driver_surf.get_width() + 4
            by = y + 4
            box = pygame.Rect(0, 0, txt.get_width() + 16,
                              txt.get_height() + 10)
            panel = pygame.Surface((box.w + 10, box.h), pygame.SRCALPHA)
            pygame.draw.rect(panel, (20, 20, 30, 150),
                            (10, 0, box.w, box.h), border_radius=8)
            pygame.draw.rect(panel, (255, 210, 74, 200),
                            (10, 0, box.w, box.h), 2, border_radius=8)
            pygame.draw.polygon(panel, (20, 20, 30, 150),      # tail
                                [(10, box.h // 2 - 5),
                                 (10, box.h // 2 + 5),
                                 (0, box.h // 2)])
            self.screen.blit(panel, (bx - 10, by))
            self.screen.blit(txt, (bx + 6, by + 5))

    def panel_rect(self, rect):
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (20, 20, 30, 110), surf.get_rect(), border_radius=6)
        pygame.draw.rect(surf, (136, 136, 136, 160), surf.get_rect(), 2, border_radius=6)
        self.screen.blit(surf, rect.topleft)

    def overlay(self, *lines):
        shade = pygame.Surface((VW, VH), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        self.screen.blit(shade, (0, 0))
        n = len(lines)
        for i, (text, font, color) in enumerate(lines):
            surf = font.render(text, True, color)
            self.screen.blit(surf, surf.get_rect(
                center=(VW / 2, VH / 2 + (i - n / 2) * 40 + 20)))