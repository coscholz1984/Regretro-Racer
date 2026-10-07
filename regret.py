"""RETRO RACER DELUXE - regret.py
The dark story arc. Once the racing past catches up with the driver
(haunt stage 4), the mini-games are replaced by three scenes - the
courtroom, the hospital room and the nightstand - where the player
relives the aftermath of the accident. Once all three are done, the
final flashback reveals the truth, and after that only the memorial
remains.

The scenes are registered in menu.py's active_games() exactly like
mini-games, so main.py needs no changes at all."""
import math
import random

import pygame

from core import (FPS, BaseGame, VH, VW, load_skin, mark_scene,
                  mark_truth, reset_haunt)
from sprites import (MEDS, car_sprite, driver_face_surface, med_surface,
                     person_surface, player_car_surface, selected_car)
import music


WHITE = (235, 235, 235)
GRAY = (180, 180, 190)
DIM = (120, 120, 130)
GOLD = (255, 210, 74)
RED = (200, 60, 60)


# ============================================================================
# THE MESSAGE - shared by the flashback's ending and the memorial
# ============================================================================
def draw_epilogue(s, app):
    """The road-safety epilogue the whole arc has been building to."""
    s.fill((8, 8, 10))
    ttl = app.font_big.render("REGRET RACER", True, RED)
    s.blit(ttl, ttl.get_rect(center=(VW / 2, 96)))
    lines = [
        ("this is where the racing story ends.", WHITE),
        ("", WHITE),
        ("NEVER DRIVE UNDER THE INFLUENCE OF ALCOHOL OR DRUGS.", GOLD),
        ("ONE MISTAKE CAN CHANGE - OR END - MANY LIVES.", GOLD),
        ("DRIVE SAFELY. THE CONSEQUENCES STAY WITH YOU.", GOLD),
        ("", WHITE),
        ("if you or someone you know struggles with alcohol or", GRAY),
        ("drugs, please talk to a doctor. help exists.", GRAY),
        ("", WHITE),
        ("THE END", RED),
    ]
    y = 176
    for txt, col in lines:
        if txt:
            surf = app.font.render(txt, True, col)
            s.blit(surf, surf.get_rect(center=(VW / 2, y)))
        y += 34


# ============================================================================
# TEXT-AND-CHOICE SCENES (courtroom, hospital room, nightstand)
# ============================================================================
class BaseScene(BaseGame):
    """A scene of relived misery: beats are advanced with ENTER, and
    some beats offer choices picked with LEFT/RIGHT + ENTER. ESC backs
    out to the menu; finishing all beats marks the scene as relived."""

    KEY = ""                # haunt "scenes" key set when completed
    TITLE = ""

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def beats(self):
        """[(lines, choice), ...]: lines = [(text, color), ...],
        choice = [(label, next beat index), ...] or None."""
        return []

    def done_line(self):
        return ""

    def reset(self):
        sk = load_skin()
        self.name = sk["name"]
        self.face = driver_face_surface(sk["clothes"], sk["hair"], 0, 4,
                                        mood=4)
        self.beat = 0
        self.t = 0.0
        self.choice = 0
        self.scene_done = False
        self.stop_loops()
        music.start_music(self.app, "guilt")

    def current_beat(self):
        if self.beat < len(self.beats()):
            return self.beats()[self.beat]
        return None

    def advance(self):
        beat = self.current_beat()
        if beat is None:
            self.finish_scene()
            return
        _, choice = beat
        if choice:
            self.beat = choice[self.choice][1]
            self.choice = 0
        else:
            self.beat += 1
        if self.beat >= len(self.beats()):
            self.finish_scene()

    def finish_scene(self):
        if self.KEY and not self.scene_done:
            mark_scene(self.KEY)
            self.scene_done = True

    # --------------------------------- run ---------------------------------
    def run(self):
        while not self.exited:
            dt = min(0.05, self.app.clock.tick(FPS) / 1000)
            self.t += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.exited = True
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_m:
                        self.stop_loops()
                        music.toggle_mute(self.app)
                    elif e.key == pygame.K_F11:
                        self.app.toggle_fullscreen()
                    elif e.key == pygame.K_ESCAPE:
                        self.stop_loops()
                        return          # back to the menu
                    elif self.scene_done:
                        if e.key == pygame.K_RETURN:
                            self.stop_loops()
                            return
                    else:
                        beat = self.current_beat()
                        if beat and beat[1]:
                            if e.key in (pygame.K_LEFT, pygame.K_a):
                                self.choice = (self.choice - 1) % len(beat[1])
                                self.snd("blip", 0.5)
                            elif e.key in (pygame.K_RIGHT, pygame.K_d):
                                self.choice = (self.choice + 1) % len(beat[1])
                                self.snd("blip", 0.5)
                            elif e.key == pygame.K_RETURN:
                                self.snd("blip")
                                self.advance()
                        elif e.key == pygame.K_RETURN:
                            self.advance()
            self.update_fx(dt, active=True)     # the scenes jump too
            s = self.app.screen
            self.draw_scene(s, self.t)
            self.draw_text(s)
            self.draw_scare(s)
            pygame.display.flip()
        self.stop_loops()

    # -------------------------------- drawing -------------------------------
    def draw_scene(self, s, t):
        pass        # the background of the scene (overridden)

    def draw_text(self, s):
        beat = self.current_beat()
        if self.scene_done:
            txt = self.font_big.render(self.done_line(), True, RED)
            s.blit(txt, txt.get_rect(center=(VW / 2, VH / 2 - 40)))
            hint = "it is done. ENTER to leave."
        elif beat:
            lines, choice = beat
            h = 36 + len(lines) * 30 + (46 if choice else 0)
            box = pygame.Rect(VW / 2 - 380, VH - 56 - h, 760, h)
            pygame.draw.rect(s, (12, 12, 18), box, border_radius=8)
            pygame.draw.rect(s, (90, 90, 100), box, 2, border_radius=8)
            y = box.y + 14
            for txt, col in lines:
                surf = self.font.render(txt, True, col)
                s.blit(surf, (box.x + 24, y))
                y += 30
            if choice:
                for i, (label, _) in enumerate(choice):
                    x = box.x + 24 + i * 370
                    sel = i == self.choice
                    if sel:
                        pygame.draw.rect(s, (44, 52, 70),
                                         (x - 10, y - 6, 350, 32),
                                         border_radius=6)
                    surf = self.font.render(("+ " if sel else "  ") + label,
                                            True, GOLD if sel else DIM)
                    s.blit(surf, (x, y))
            hint = "ENTER continue" + (" - LEFT/RIGHT choose" if choice else "")
        else:
            hint = ""
        hs = self.font.render(hint, True, (120, 220, 140))
        s.blit(hs, hs.get_rect(center=(VW / 2, VH - 26)))


# ------------------------------- the courtroom -------------------------------
class CourtScene(BaseScene):
    KEY = "court"
    TITLE = "THE COURTROOM"

    def done_line(self):
        return "CASE CLOSED"

    def beats(self):
        return [
            ([("THE PEOPLE vs. " + self.name, WHITE),
              ("case 11-07: the bypass, that night.", GRAY),
              ("illegal street racing.", WHITE),
              ("driving under the influence.", WHITE),
              ("hit and run. grievous bodily harm.", WHITE),
              ("and one count the clerk cannot read out loud.", RED)], None),
            ([("the room is very quiet.", WHITE),
              ("your trophies are on the evidence table.", GRAY),
              ("they have never looked so small.", GRAY)], None),
            ([("how do you plead?", GOLD)],
             [("NOT GUILTY", 3), ("GUILTY", 4)]),
            ([("'not guilty.'", WHITE),
              ("the judge looks at you for a long time.", WHITE),
              ("then she looks at the photographs.", GRAY),
              ("the room stops breathing.", GRAY)],
             [("go on", 4)]),
            ([("'guilty. on all counts.'", WHITE),
              ("the gavel falls. it sounds like a door.", GRAY)], None),
            ([("there is no prize money for this one.", RED)], None),
        ]

    def draw_scene(self, s, t):
        s.fill((24, 19, 14))
        for x in range(0, VW + 90, 90):           # dark wood paneling
            pygame.draw.rect(s, (33, 26, 18), (x, 0, 4, VH))
            pygame.draw.rect(s, (28, 22, 16), (x + 45, 0, 2, VH))
        # a cone of light onto the dock
        pygame.draw.polygon(s, (40, 38, 30),
                            [(VW / 2 - 40, 0), (VW / 2 + 40, 0),
                             (VW / 2 + 240, VH - 120), (VW / 2 - 240, VH - 120)])
        # the judge's bench and a silhouette behind it
        pygame.draw.rect(s, (58, 44, 28), (VW / 2 - 280, 96, 560, 84))
        pygame.draw.rect(s, (78, 60, 38), (VW / 2 - 280, 96, 560, 22))
        pygame.draw.rect(s, (14, 12, 10),
                         (VW / 2 - 30, 46, 60, 50), border_radius=10)
        # a gavel that never stops swinging
        swing = math.sin(t * 3) * 6
        pygame.draw.rect(s, (120, 82, 40), (VW / 2 + 210, 66 + swing, 70, 10))
        pygame.draw.rect(s, (90, 62, 30), (VW / 2 + 150, 92, 60, 18), 2)
        # the dock: where the driver used to wave from the podium
        dock = pygame.Rect(VW / 2 - 90, 310, 180, 26)
        pygame.draw.rect(s, (58, 44, 28), dock)
        s.blit(self.face, self.face.get_rect(midbottom=(VW / 2, dock.top - 4)))
        ttl = self.font_big.render(self.TITLE, True, RED)
        s.blit(ttl, ttl.get_rect(center=(VW / 2, 36)))


# ------------------------------ the hospital room ----------------------------
class HospitalScene(BaseScene):
    KEY = "hospital"
    TITLE = "ROOM 214"

    def done_line(self):
        return "VISITING HOURS ARE OVER"

    def reset(self):
        super().reset()
        sk = load_skin()
        self.body = person_surface(sk["clothes"], sk["hair"], 0, 5, mood=4)
        self.lying = pygame.transform.rotate(self.body, 90)

    def beats(self):
        return [
            ([("you do not remember the crash.", WHITE),
              ("you remember the sirens, the lights,", WHITE),
              ("the rain on the windshield. always the rain.", GRAY)], None),
            ([("a nurse asks how you are feeling.", WHITE)],
             [("I'M FINE", 2), ("WHERE IS MY CAR?", 3)]),
            ([("'fine.' the word tastes like a lie.", WHITE),
              ("she writes something down.", GRAY),
              ("the pen sounds like a gavel.", GRAY)],
             [("go on", 4)]),
            ([("she does not answer that.", WHITE),
              ("no one has answered that for weeks.", GRAY)],
             [("go on", 4)]),
            ([("on the tray: your phone, your keys,", WHITE),
              ("and a small paper cup with two pills.", WHITE)],
             [("SWALLOW", 5), ("REFUSE", 6)]),
            ([("the ceiling softens. the dream comes back.", WHITE)],
             [("go on", 7)]),
            ([("the nurse nods and quietly writes more down.", WHITE)],
             [("go on", 7)]),
            ([("the monitor beeps politely.", WHITE),
              ("you sleep. you dream of the bypass.", WHITE),
              ("in the dream, you never hit the brakes.", RED)], None),
        ]

    def draw_scene(self, s, t):
        s.fill((26, 30, 36))
        # the window: rain, and one streetlight that never goes out
        win = pygame.Rect(VW - 300, 60, 220, 200)
        pygame.draw.rect(s, (18, 20, 26), win, border_radius=6)
        pygame.draw.rect(s, (70, 76, 88), win, 4, border_radius=6)
        pygame.draw.rect(s, (70, 76, 88), (win.centerx - 2, win.y, 4, win.h))
        rng = random.Random(int(t * 20))
        for _ in range(26):
            rx = rng.uniform(win.x + 6, win.right - 6)
            ry = (rng.uniform(0, win.h) + t * 160) % win.h
            pygame.draw.line(s, (110, 130, 150), (rx, win.y + ry),
                             (rx - 2, win.y + ry + 12))
        pygame.draw.rect(s, (255, 210, 74), (win.x + 24, win.bottom - 54, 22, 8))
        # the bed, the pillow, the blanket, and you
        pygame.draw.rect(s, (150, 150, 158), (60, 372, 360, 22),
                         border_radius=6)
        pygame.draw.rect(s, (210, 210, 216), (66, 352, 120, 26),
                         border_radius=8)
        s.blit(self.lying, self.lying.get_rect(center=(320, 344)))
        pygame.draw.rect(s, (60, 90, 140), (150, 322, 240, 56),
                         border_radius=8)
        # the IV drip, ticking
        drip = 2 * int(1 + math.sin(t * 1.2))
        pygame.draw.rect(s, (170, 170, 180), (500, 130, 8, 200))
        pygame.draw.line(s, (170, 170, 180), (504, 130), (560, 190), 2)
        pygame.draw.rect(s, (210, 230, 240), (552, 190 + drip, 16, 34),
                         border_radius=6)
        pygame.draw.rect(s, (56, 189, 248), (556, 206 + drip, 8, 14),
                         border_radius=3)
        # the monitor: a polite green line that is lying to everyone
        mon = pygame.Rect(600, 120, 300, 150)
        pygame.draw.rect(s, (14, 16, 14), mon, border_radius=8)
        pygame.draw.rect(s, (60, 70, 60), mon, 3, border_radius=8)
        pts = []
        for i in range(150):
            x = mon.x + 20 + i * (260 / 150.0)
            ph = ((i / 150.0) * 2.0 + t * 0.7) % 1.0
            yv = mon.y + 75
            if ph < 0.06:
                yv = mon.y + 75 - 42 * math.sin(ph / 0.06 * math.pi)
            pts.append((x, yv))
        pygame.draw.lines(s, (74, 222, 128), False, pts, 2)
        ttl = self.font_big.render(self.TITLE, True, RED)
        s.blit(ttl, ttl.get_rect(center=(VW / 2, 36)))


# ------------------------------ the nightstand -------------------------------
class MedsScene(BaseScene):
    KEY = "drugs"
    TITLE = "THE NIGHTSTAND"

    def done_line(self):
        return "THE DRAWER IS STILL OPEN"

    def reset(self):
        super().reset()
        sk = load_skin()
        self.body = person_surface(sk["clothes"], sk["hair"], 0, 6, mood=4)

    def beats(self):
        return [
            ([("the drawer of the nightstand has been open for weeks.",
               WHITE),
              ("it is easier than remembering.", GRAY)], None),
            ([("uppers to stay awake. downers to sleep it off.", WHITE),
              ("anything to keep the hands from shaking.", WHITE),
              ("anything to keep the bypass quiet.", GRAY)], None),
            ([("you remember the night now.", WHITE),
              ("you took something to stay awake.", WHITE),
              ("something to go faster.", RED)],
             [("TAKE ONE", 3), ("CLOSE THE DRAWER", 4)]),
            ([("the pill does not help. it never does.", WHITE),
              ("the sirens sound closer tonight.", GRAY)],
             [("go on", 5)]),
            ([("you close the drawer.", WHITE),
              ("your hands open it again before you notice.", GRAY)],
             [("go on", 5)]),
            ([("there is no leaderboard for this.", WHITE),
              ("there is only the road.", WHITE),
              ("and the road remembers.", RED)], None),
        ]

    def draw_scene(self, s, t):
        s.fill((16, 14, 20))
        # a pale moon through the window
        moon = pygame.Rect(VW - 210, 70, 70, 70)
        pygame.draw.rect(s, (12, 12, 16), (VW - 240, 50, 150, 130),
                         border_radius=8)
        pygame.draw.rect(s, (70, 70, 84), (VW - 240, 50, 150, 130), 4,
                         border_radius=8)
        pygame.draw.circle(s, (200, 210, 230), moon.center, 34)
        # the bed, with the driver hunched on the edge of it
        pygame.draw.rect(s, (40, 36, 50), (60, 330, 330, 60), border_radius=8)
        s.blit(self.body, self.body.get_rect(midbottom=(170, 334)))
        # the nightstand and its bottles, breathing slightly
        stand = pygame.Rect(470, 300, 330, 90)
        pygame.draw.rect(s, (60, 44, 30), stand, border_radius=6)
        pygame.draw.rect(s, (40, 30, 22), (480, 330, 60, 50), border_radius=4)
        for i in range(len(MEDS)):
            spr = med_surface(i, 4)
            bob = math.sin(t * 1.4 + i) * 3
            s.blit(spr, (stand.x + 60 + i * 66,
                        stand.y - spr.get_height() + 20 + bob))
        ttl = self.font_big.render(self.TITLE, True, RED)
        s.blit(ttl, ttl.get_rect(center=(VW / 2, 36)))


# ============================================================================
# THE FLASHBACK - the truth about that night on the bypass
# ============================================================================
class FlashbackGame(BaseGame):
    """The scripted cutscene that plays once the three scenes have been
    relived. It ends with the road-safety epilogue and the aftermath."""

    PHASES = [
        (7.0, "NOVEMBER. THE OLD BYPASS. NO STREETLIGHTS."),
        (7.0, "he had taken something to stay awake."
              " something to go faster."),
        (5.0, "the figure stepped into the headlights."
              " he did not brake. he could not."),
        (7.0, "he turned the wheel - into the opposite lane."
              " into the oncoming lights."),
        (7.0, "five cars. eleven people. one mistake."),
        (7.0, "three people never went home that night."),
        (7.0, "he kept driving. he is still driving."),
    ]

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        sk = load_skin()
        self.name = sk["name"]
        self.t = 0.0
        self.phase = 0
        self.phase_t = 0.0
        self.flash = 0.0
        self.epilogue = False
        self.car = player_car_surface(selected_car(), 4)
        self.figure = person_surface(7, 1, 0, 4)     # a dark silhouette
        self.fallen = pygame.transform.rotate(self.figure, 90)
        self.oncoming = [pygame.transform.rotate(car_sprite(c, 4), 180)
                         for c in ("white", "teal", "purple", "white")]
        self.drops = [(random.uniform(0, VW), random.uniform(0, VH))
                      for _ in range(80)]
        self.crash_at = None          # y where the multi-car pile-up froze
        self.stop_loops()
        music.start_music(self.app, "guilt")

    def _next(self):
        """Move to the next beat of the truth (ENTER skips ahead)."""
        self.phase += 1
        self.phase_t = 0.0
        if self.phase == 2:
            self.flash = 1.0
            self.snd("thud")
        elif self.phase == 4:
            self.flash = 1.0
            self.snd("crash", 1.0)
        if self.phase >= len(self.PHASES):
            self.phase = len(self.PHASES) - 1
            self.phase_t = 0.0
            if not self.epilogue:
                self.epilogue = True
                mark_truth()
                self.stop_loops()         # silence, for the message

    # --------------------------------- run ---------------------------------
    def run(self):
        while not self.exited:
            dt = min(0.05, self.app.clock.tick(FPS) / 1000)
            self.t += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.exited = True
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_m:
                        self.stop_loops()
                        music.toggle_mute(self.app)
                    elif e.key == pygame.K_F11:
                        self.app.toggle_fullscreen()
                    elif e.key == pygame.K_ESCAPE:
                        self.stop_loops()
                        return          # back to the menu
                    elif e.key == pygame.K_RETURN:
                        if self.epilogue:
                            self.stop_loops()
                            return      # the aftermath
                        self._next()
            self.phase_t += dt
            self.flash = max(0.0, self.flash - dt * 1.2)
            if not self.epilogue and self.phase_t >= self.PHASES[self.phase][0]:
                self._next()
            self.draw()
            pygame.display.flip()
        self.stop_loops()

    # -------------------------------- drawing -------------------------------
    def draw(self):
        s = self.app.screen
        if self.epilogue:
            draw_epilogue(s, self.app)
            hs = self.font.render("ENTER to leave", True, (120, 220, 140))
            s.blit(hs, hs.get_rect(center=(VW / 2, VH - 40)))
            return

        s.fill((10, 10, 14))
        cx = VW / 2
        road_w = 380
        car_y = VH - 150
        # the car's lane: it swerves into the oncoming lane in phase 3
        if self.phase >= 3:
            frac = min(1.0, self.phase_t / 2.5) if self.phase == 3 else 1.0
            car_x = cx + 95 - 190 * frac
        else:
            car_x = cx + 95
        # two-lane road at night
        pygame.draw.rect(s, (40, 40, 46), (cx - road_w / 2, 0, road_w, VH))
        off = (self.t * 320) % 80
        for y in range(-80 + int(off), VH, 80):
            pygame.draw.rect(s, (200, 200, 190), (cx - 3, y, 6, 34))
        # the rain
        for (x0, y0) in self.drops:
            ry = (y0 + self.t * 460) % VH
            pygame.draw.line(s, (150, 160, 180), (x0, ry),
                             (x0 - 5, ry + 16))
        # the headlights sweep the road ahead
        pygame.draw.polygon(s, (60, 58, 40),
                            [(car_x - 22, car_y - 10), (car_x + 22, car_y - 10),
                             (car_x + 110, 0), (car_x - 110, 0)])
        # the figure: crossing in phase 1, down and still from phase 2 on
        if self.phase == 1:
            frac = min(1.0, self.phase_t / self.PHASES[1][0])
            fx = cx - 240 + 220 * frac
            s.blit(self.figure, self.figure.get_rect(midbottom=(fx, car_y + 60)))
        elif self.phase >= 2:
            s.blit(self.fallen, self.fallen.get_rect(midbottom=(cx + 30, car_y + 64)))
            pool = pygame.Surface((120, 20), pygame.SRCALPHA)
            pygame.draw.ellipse(pool, (120, 20, 24, 170), pool.get_rect())
            s.blit(pool, (cx + 30 - 60, car_y + 52))
        # oncoming headlights in the swerve phases: the pile-up
        if self.phase >= 4:
            if self.crash_at is None:
                oy = self.phase_t * 300 - 60
                if oy >= car_y - 130:
                    self.crash_at = car_y - 130
                    self.flash = max(self.flash, 0.8)
            base = self.crash_at if self.crash_at is not None \
                else self.phase_t * 300 - 60
            for i, spr in enumerate(self.oncoming):
                x = cx - 95 + (i - 1.5) * 60
                ang = 18 if (self.crash_at is not None and i == 0) else 0
                spr2 = pygame.transform.rotate(spr, ang)
                s.blit(spr2, spr2.get_rect(center=(x, base - i * 80)))
            if self.crash_at is not None:
                for _ in range(2):
                    self.smoke_fx(s, cx - 95 + random.uniform(-60, 60),
                                  self.crash_at - random.uniform(0, 60))
        # the car
        tilt = -14 if self.phase == 3 else 0
        spr = pygame.transform.rotate(self.car, tilt)
        s.blit(spr, spr.get_rect(center=(car_x, car_y)))
        # impact flash
        if self.flash > 0:
            shade = pygame.Surface((VW, VH), pygame.SRCALPHA)
            shade.fill((255, 60, 40, int(150 * self.flash)))
            s.blit(shade, (0, 0))
        # the phase text
        if self.phase >= 5:            # fading to black: text centred
            a = min(255, int(self.phase_t * 80) * 3)
            shade = pygame.Surface((VW, VH), pygame.SRCALPHA)
            shade.fill((0, 0, 0, min(235, a)))
            s.blit(shade, (0, 0))
            txt = self.font.render(self.PHASES[self.phase][1], True, WHITE)
            s.blit(txt, txt.get_rect(center=(VW / 2, VH / 2)))
        else:
            txt = self.font.render(self.PHASES[self.phase][1], True, WHITE)
            pygame.draw.rect(s, (0, 0, 0, 160), (0, car_y + 60, VW, 46))
            s.blit(txt, txt.get_rect(center=(VW / 2, car_y + 83)))
        # a small prompt so the player knows ENTER skips
        hs = self.font_small.render("ENTER next beat - ESC back",
                                   True, (100, 100, 110))
        s.blit(hs, (12, VH - 24))

    def smoke_fx(self, s, x, y):
        """A puff of crash smoke (draw-only, no state kept)."""
        r = random.randint(6, 14)
        col = (150, 150, 150) if r % 2 else (90, 90, 90)
        pygame.draw.circle(s, col, (int(x), int(y - random.uniform(0, 20))), r)


# ============================================================================
# THE MEMORIAL - what remains after the truth
# ============================================================================
class MemorialScene(BaseGame):
    """Stage 5: the epilogue stays on screen, and with BACKSPACE the
    player may forget the whole arc and start fresh (cash and records
    are kept - only the story is erased)."""

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.t = 0.0
        self.stop_loops()
        music.start_music(self.app, "guilt", volume=0.25)

    def run(self):
        while not self.exited:
            dt = min(0.05, self.app.clock.tick(FPS) / 1000)
            self.t += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.exited = True
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_m:
                        self.stop_loops()
                        music.toggle_mute(self.app)
                    elif e.key == pygame.K_F11:
                        self.app.toggle_fullscreen()
                    elif e.key in (pygame.K_ESCAPE, pygame.K_q):
                        self.stop_loops()
                        return          # back to the menu
                    elif e.key == pygame.K_RETURN:
                        self.stop_loops()
                        return
                    elif e.key == pygame.K_BACKSPACE:
                        reset_haunt()
                        self.snd("ding")
                        self.stop_loops()
                        return          # the story starts over
            s = self.app.screen
            draw_epilogue(s, self.app)
            # the memorial line, under the message
            mem = self.font.render(
                "in memory of everyone who never got home from a race.",
                True, GRAY)
            s.blit(mem, mem.get_rect(center=(VW / 2, VH - 120)))
            candle = 4 + int(math.sin(self.t * 9) * 1.5)
            cx, cy = VW / 2, VH - 74
            pygame.draw.rect(s, (60, 52, 40), (cx - 3, cy, 6, 26))
            pygame.draw.circle(s, (255, 210, 74), (cx, cy - 6), candle)
            pygame.draw.circle(s, (255, 160, 40), (cx, cy - 4), candle // 2)
            hint = self.font.render(
                "ENTER menu - BACKSPACE forget the story, start over",
                True, (120, 220, 140))
            s.blit(hint, hint.get_rect(center=(VW / 2, VH - 26)))
            pygame.display.flip()
        self.stop_loops()


# ============================================================================
# PICKER PREVIEWS - one small animated scene per regret entry
# ============================================================================
def preview_court(s, rect, t):
    pygame.draw.rect(s, (24, 19, 14), rect, border_radius=10)
    for x in range(rect.x, rect.right, 36):
        pygame.draw.rect(s, (33, 26, 18), (x, rect.y, 3, rect.h))
    pygame.draw.rect(s, (58, 44, 28), (rect.centerx - 90, rect.y + 34, 180, 44))
    pygame.draw.rect(s, (78, 60, 38), (rect.centerx - 90, rect.y + 34, 180, 12))
    swing = math.sin(t * 3) * 4
    pygame.draw.rect(s, (120, 82, 40),
                     (rect.centerx + 64, rect.y + 26 + swing, 40, 6))


def preview_hospital(s, rect, t):
    pygame.draw.rect(s, (26, 30, 36), rect, border_radius=10)
    mon = pygame.Rect(rect.centerx - 90, rect.y + 24, 180, 80)
    pygame.draw.rect(s, (14, 16, 14), mon, border_radius=6)
    pts = []
    for i in range(60):
        x = mon.x + 10 + i * (160 / 60.0)
        ph = ((i / 60.0) * 2.0 + t * 0.8) % 1.0
        y = mon.y + 50 - (20 * math.sin(ph / 0.08 * math.pi)
                          if ph < 0.08 else 0)
        pts.append((x, y))
    pygame.draw.lines(s, (74, 222, 128), False, pts, 2)
    pygame.draw.rect(s, (150, 150, 158),
                     (rect.x + 26, rect.centery + 44, 120, 12), border_radius=4)
    pygame.draw.rect(s, (60, 90, 140),
                     (rect.x + 40, rect.centery + 16, 90, 30), border_radius=6)


def preview_meds(s, rect, t):
    pygame.draw.rect(s, (16, 14, 20), rect, border_radius=10)
    pygame.draw.circle(s, (200, 210, 230), (rect.right - 50, rect.y + 40), 22)
    stand = pygame.Rect(rect.centerx - 100, rect.centery - 6, 200, 60)
    pygame.draw.rect(s, (60, 44, 30), stand, border_radius=6)
    for i in range(len(MEDS)):
        spr = med_surface(i, 3)
        bob = math.sin(t * 1.4 + i) * 2
        s.blit(spr, (stand.x + 10 + i * 46, stand.y - spr.get_height() + 10 + bob))


def preview_truth(s, rect, t):
    pygame.draw.rect(s, (10, 10, 14), rect, border_radius=10)
    cx = rect.centerx
    pygame.draw.rect(s, (40, 40, 46), (cx - 90, rect.y, 180, rect.h))
    off = (t * 200) % 50
    for y in range(rect.y - 50 + int(off), rect.bottom, 50):
        pygame.draw.rect(s, (200, 200, 190), (cx - 2, y, 4, 20))
    for i in range(14):
        rx = rect.x + 16 + (i * 131) % (rect.w - 32)
        ry = (t * 130 + i * 60) % rect.h
        pygame.draw.line(s, (150, 160, 180), (rx, ry), (rx - 3, ry + 10))
    for dy in (18, 40):
        y = rect.centery - ((t * 60 + dy * 20) % 120)
        pygame.draw.rect(s, (200, 60, 60), (cx - 26, y, 10, 6))
        pygame.draw.rect(s, (200, 60, 60), (cx + 16, y, 10, 6))


def preview_memorial(s, rect, t):
    pygame.draw.rect(s, (8, 8, 10), rect, border_radius=10)
    cx, cy = rect.center
    flick = 4 + int(math.sin(t * 9) * 1.5)
    pygame.draw.rect(s, (60, 52, 40), (cx - 3, cy + 6, 6, 28))
    pygame.draw.circle(s, (255, 210, 74), (cx, cy), flick)
    pygame.draw.circle(s, (255, 160, 40), (cx, cy + 2), flick // 2)