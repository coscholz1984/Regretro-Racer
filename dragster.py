"""RETRO RACER DELUXE - dragster.py
Mini-game: quarter-mile drag race, a tribute to Atari's Dragster.

Hold UP for gas, SPACE shifts up through the four gears. The RPM
climbs in every gear: shift near the redline for maximum speed.
Shifting too early bogs the engine, screaming in the redline too
long blows it, and hitting the gas before the green light is a
foul start. First one over 402 m wins."""
import math
import random
import time

import pygame

from core import (FPS, LB_DRAGSTER, BaseGame, VH, VW,
                  add_cash, load_board, note_finish,
                  note_play, play_haunt, reward_multiplier, save_board)
from sprites import body_surface, dragster_surface, selected_car, \
    wreck_surface
import music


# ----------------------------- configuration -------------------------------
QM_D = 4020            # quarter mile: 402 m at 10 px per meter
REDLINE = 0.90         # rpm fraction where the engine starts screaming
BLOW_T = 1.1           # seconds in the redline before the engine blows
PAR = 7.0              # par time for the reward multiplier

# (min speed, max speed) window of each of the four gears
GEARS = [(0, 140), (100, 300), (240, 540), (440, 900)]

RIVAL_Y = 238          # rival lane (upper strip)
PLAYER_Y = 362         # player lane (lower strip)

# haunt stage 2+: the car demands its own controls each race (shown in
# the HUD) - and at stage 3 it silently changes them mid-run
KEY_NAMES = {pygame.K_UP: "UP", pygame.K_i: "I", pygame.K_k: "K",
             pygame.K_SPACE: "SPACE", pygame.K_j: "J", pygame.K_l: "L"}
GAS_KEYS = [pygame.K_UP, pygame.K_i, pygame.K_k]
SHIFT_KEYS = [pygame.K_SPACE, pygame.K_j, pygame.K_l]

# ------------------------------ the game -----------------------------------
class DragsterGame(BaseGame):
    """Quarter-mile drag race against one rival dragster."""

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        # the player drags the car selected in the garage
        self.car_spec = selected_car()
        self.player_surf = dragster_surface(self.car_spec["body"],
                                            self.car_spec["dark"])
        self.rival_surf = dragster_surface((232, 232, 232), (154, 154, 154))
        # race state
        self.started = False
        self.green = False           # False during the countdown lights
        self.over = False
        self.reason = ""
        self.won = False
        self.cd_t = 0.0              # countdown clock
        self.race_time = 0.0
        self.dist = 0.0
        self.speed = 0.0
        self.gear = 1
        self.rpm = 0.0
        self.overrev = 0.0
        self.bog_t = 0.0
        self.gassing = False
        self.space_prev = False
        # the haunt: how far the story has crept in, and (stage 2+) the
        # controls the car demands tonight - at stage 3 they even
        # silently change mid-run
        self.haunt = play_haunt()
        if self.haunt >= 2:
            self.gas_key, self.shift_key = self._pick_keys()
        else:
            self.gas_key, self.shift_key = pygame.K_UP, pygame.K_SPACE
        self.remap_t = random.uniform(4.0, 6.0)
        self.remap_msg_t = 0.0       # big on-screen key banner timer
        self.stuck_t = 0.0           # going nowhere: nudge the driver
        # the haunt: burnt-out wrecks behind the guardrails - and from
        # stage 3, silhouettes that never got across in time
        self.body_surf = body_surface()
        self.spooks = []
        if self.haunt >= 2:
            rng = random.Random(21)
            d = 500
            while d < QM_D - 200:
                side = rng.choice((-1, 1))
                body = self.haunt >= 3 and rng.random() < 0.35
                self.spooks.append({
                    "d": d,
                    "y": 172 if side < 0 else 414,
                    "kind": "body" if body else "wreck",
                    "spr": (self.body_surf if body else
                            pygame.transform.rotate(
                                wreck_surface(rng.choice(
                                    ["white", "teal", "purple"])),
                                rng.uniform(-40, 40)))})
                d += rng.randrange(650, 1100)
        self.reset_fx()
        # the rival: smooth launch curve with a per-race skill factor
        self.rival_dist = 0.0
        self.rival_done = 0.0        # time the rival crossed (0.0 = not yet)
        self.rival_tau = 2.4 * random.uniform(0.9, 1.12)
        self.smoke = []
        self.board = load_board(LB_DRAGSTER)
        self.new_lb = None
        self.cash_won = 0
        self.stop_loops()
        music.start_music(self.app, "dragster",
                          haunt=min(self.haunt, 3))
        # static star field for the night sky
        rng = random.Random(99)
        self.stars = [(rng.uniform(0, VW), rng.uniform(0, 180))
                      for _ in range(40)]

    def _pick_keys(self):
        """The controls the car demands this run (haunt stage 2+)."""
        return random.choice(GAS_KEYS), random.choice(SHIFT_KEYS)

    # ------------------------------- update --------------------------------
    def update(self, dt, keys):
        if keys[pygame.K_q]:
            self.exited = True
            return
        if not self.started:
            if keys[pygame.K_RETURN]:
                self.started = True
                self.snd("blip")
            return
        if self.over:
            if keys[pygame.K_r]:
                self.reset()
            self.update_fx(dt, active=False)     # the fireball burns out
            return
        self.update_fx(dt, active=True)

        # countdown: three amber lights, then the green light
        if not self.green:
            self.cd_t += dt
            if keys[self.gas_key]:
                self.game_over("FOUL START")      # jumped the green light
                return
            if self.cd_t >= 3.2:
                self.green = True
                self.snd("go")
                self.driver_hud_say(self.race_start_line())
            self._engine_sound(idle=True)
            return

        # ------------------------------ racing ------------------------------
        self.race_time += dt
        self.driver_cheer(dt)
        self.remap_msg_t = max(0.0, self.remap_msg_t - dt)
        # stage 3: the car rewrites its own controls mid-run
        if self.haunt >= 3:
            self.remap_t -= dt
            if self.remap_t <= 0:
                self.gas_key, self.shift_key = self._pick_keys()
                self.remap_t = random.uniform(4.0, 6.0)
                self.remap_msg_t = 3.0        # LOUD - the driver must see it
                self.snd("warn", 0.5)
                self.driver_hud_say("the controls have changed.")
        # stage 3: sometimes the car simply decides to explode
        if (self.haunt >= 3 and self.race_time > 12.0
                and random.random() < dt * 0.022):
            self.explode_at(170, PLAYER_Y)
            self.game_over("THE CAR EXPLODED")
            for _ in range(14):
                self.smoke.append((170 + random.uniform(-16, 16),
                                   PLAYER_Y + random.uniform(-14, 10),
                                   random.uniform(0.5, 1.0)))
            return
        gas = keys[self.gas_key]
        self.gassing = gas
        # the haunt hides the keys - but it must never strand the
        # driver: after 2s of going nowhere the car whispers what it
        # wants, big and unmissable
        self.stuck_t = self.stuck_t + dt if self.speed < 5 else 0.0
        if self.stuck_t > 2.0 and self.haunt >= 2:
            self.stuck_t = 0.0
            self.remap_msg_t = max(self.remap_msg_t, 2.0)
            self.driver_hud_say(f"it wants {KEY_NAMES[self.gas_key]}."
                                f" give it {KEY_NAMES[self.gas_key]}.")

        lo, hi = GEARS[self.gear - 1]
        if self.gear == len(GEARS):       # garage car adds top speed in 4th
            hi += self.car_spec["max"]
        self.rpm = max(0.0, min(1.0, (self.speed - lo) / max(1.0, hi - lo)))

        if gas and self.bog_t <= 0:
            self.speed += 260 * (0.5 + 0.6 * self.rpm) * dt
        else:
            self.speed *= 1 - 0.55 * dt   # lift off the gas
        self.speed = max(0.0, min(hi, self.speed))

        # redline: screaming engine wears towards a blow-up (not in top gear)
        if (self.gear < len(GEARS) and self.rpm >= REDLINE and gas):
            self.overrev += dt
            if random.random() < dt * 20:
                self.smoke.append((170 + random.uniform(-14, 4), PLAYER_Y - 4,
                                   random.uniform(0.3, 0.6)))
        else:
            self.overrev = max(0.0, self.overrev - dt * 0.7)
        if self.overrev >= BLOW_T:
            self.game_over("ENGINE BLOWN")
            return

        # the mapped key shifts up (too early = engine bogs down)
        space = keys[self.shift_key]
        if space and not self.space_prev and self.gear < len(GEARS):
            if self.rpm < 0.5:
                self.bog_t = 0.8
                self.speed *= 0.82
                self.snd("warn", 0.6)
            else:
                self.gear += 1
                self.snd("blip", 0.7)
        self.space_prev = space
        self.bog_t = max(0.0, self.bog_t - dt)

        # drive + rival
        self.dist += self.speed * dt
        if self.rival_done == 0.0:
            rspeed = 830 * (1 - math.exp(-self.race_time / self.rival_tau))
            self.rival_dist += rspeed * dt
            if self.rival_dist >= QM_D:
                self.rival_done = self.race_time
        if self.dist >= QM_D:
            self.finish_race(self.rival_done == 0.0)
            return

        self.smoke = [(x, y, l - dt) for (x, y, l) in self.smoke if l - dt > 0]
        self._engine_sound()

    def _engine_sound(self, idle=False):
        """Engine loop: pitch follows the rpm needle."""
        if self.sfx.ok and not self.app.muted:
            idx = 0 if idle else min(9, int(self.rpm * 9.99))
            if idx != self._eng_idx:
                if self.engine_ch:
                    self.engine_ch.stop()
                self._eng_idx = idx
                self.engine_ch = self.sfx.engines[idx].play(loops=-1)
                self.engine_ch.set_volume(0.14)
            if self.engine_ch:
                self.engine_ch.set_volume(
                    0.16 if (not idle and self.speed > 5) else 0.08)

    # --------------------------- finish / fail ----------------------------
    def finish_race(self, win):
        self.over = True
        self.won = win
        self.reason = "YOU WIN!" if win else "YOU LOSE"
        self.stop_loops()
        self.snd("ding")
        mult = reward_multiplier(self.race_time, par=PAR)
        base = 120 + (80 if win else 0)
        self.cash_won = int(round(base * mult))
        add_cash(self.cash_won)
        note_finish()
        note_play(self.race_time)
        entry = {"time": round(self.race_time, 1),
                 "when": time.strftime("%Y-%m-%d %H:%M")}
        self.board = load_board(LB_DRAGSTER)
        self.board.append(entry)
        self.board.sort(key=lambda e: e["time"])
        self.board = self.board[:10]
        save_board(LB_DRAGSTER, self.board)
        self.new_lb = entry

    def game_over(self, reason):
        self.over = True
        self.reason = reason
        self.stop_loops()
        self.snd("thud")

    def lb_lines(self, rows=5):
        lines = [("LEADERBOARD (best times)", self.font, (255, 210, 74))]
        if not self.board:
            lines.append(("no runs yet - set the first one!", self.font,
                          (180, 180, 180)))
            return lines
        for i, e in enumerate(self.board[:rows]):
            txt = f"{i + 1}.  {e['time']:.1f}s    {e['when']}"
            color = (255, 50, 50) if e is self.new_lb else (255, 255, 255)
            lines.append((txt, self.font, color))
        return lines

    # ------------------------------- draw ---------------------------------
    def draw_world(self):
        s = self.screen
        s.fill((16, 20, 34))                      # night sky
        for (sx, sy) in self.stars:
            pygame.draw.rect(s, (60, 70, 100), (sx, sy, 2, 2))

        camx = self.dist - 170                   # player stays at x = 170

        # roadside billboards in the sky, above the guardrails
        for wx in range(int(camx // 500) * 500 + 250, int(camx) + VW + 500, 500):
            x = wx - camx
            pygame.draw.rect(s, (34, 40, 58), (x, 148, 90, 46))
            pygame.draw.rect(s, (60, 70, 100), (x, 148, 90, 46), 2)
            s.blit(self.font.render("RETRO", True, (120, 200, 255)),
                   (x + 16, 160))

        # two lanes: rival strip on top, player strip below
        pygame.draw.rect(s, (68, 68, 74), (0, 210, VW, 56))
        pygame.draw.rect(s, (52, 52, 58), (0, 262, VW, 4))
        pygame.draw.rect(s, (68, 68, 74), (0, 330, VW, 56))
        pygame.draw.rect(s, (52, 52, 58), (0, 382, VW, 4))
        for wx in range(int(camx // 40) * 40, int(camx) + VW + 40, 40):
            x = wx - camx
            pygame.draw.rect(s, (255, 255, 255), (x, 236, 22, 4))
            pygame.draw.rect(s, (255, 255, 255), (x, 356, 22, 4))
        # red/white guardrails
        for wx in range(int(camx // 30) * 30, int(camx) + VW + 30, 30):
            x = wx - camx
            c = (224, 90, 26) if (wx // 30) % 2 == 0 else (235, 235, 235)
            pygame.draw.rect(s, c, (x, 202, 30, 6))
            pygame.draw.rect(s, c, (x, 388, 30, 6))

        # start and finish lines (checkers spanning both lanes)
        for wx in (0, QM_D):
            x = wx - camx
            if -20 < x < VW + 20:
                for wy in (210, 330):
                    for j in range(14):
                        c = (245, 245, 245) if j % 2 == 0 else (20, 20, 20)
                        pygame.draw.rect(s, c, (x, wy + j * 4, 12, 4))
                if wx == QM_D:
                    sign = self.font.render("FINISH", True, (255, 210, 74))
                    s.blit(sign, (x - sign.get_width() / 2, 172))

        # lane labels
        s.blit(self.font_small.render("RIVAL", True, (150, 150, 160)), (12, 214))
        s.blit(self.font_small.render("YOU", True, (150, 150, 160)), (12, 334))

        # the haunt: what the guardrails are guarding - burnt-out
        # wrecks, and from stage 3 the people who never got across
        for sp in self.spooks:
            x = sp["d"] - camx
            if -60 < x < VW + 60:
                y = sp["y"]
                if sp["kind"] == "body":
                    pygame.draw.ellipse(s, (46, 10, 12),
                                       (int(x - 24), int(y - 5), 48, 11))
                    s.blit(sp["spr"], (int(x - 18), int(y - 12)))
                else:
                    s.blit(sp["spr"], sp["spr"].get_rect(center=(x, y)))
                    if random.random() < 0.35:     # embers still glow
                        pygame.draw.circle(
                            s, (255, 120 + random.randint(0, 80), 30),
                            (int(x + random.uniform(-14, 14)),
                             int(y + random.uniform(-8, 8))), 3)

        # rival dragster (upper lane)
        rx = self.rival_dist - camx
        if -80 < rx < VW + 80:
            s.blit(self.rival_surf, self.rival_surf.get_rect(
                center=(rx, RIVAL_Y)))

        # exhaust flame while on the gas
        if self.gassing and not self.over and self.green:
            l = random.uniform(8, 20)
            pygame.draw.rect(s, (255, 210, 74),
                             (143 - int(l), PLAYER_Y - 2, int(l), 6))
        s.blit(self.player_surf, self.player_surf.get_rect(
            center=(170, PLAYER_Y)))

        # smoke puffs (redline stress)
        for (x, y, l) in self.smoke:
            r = int((1 - l) * 8) + 3
            pygame.draw.circle(s, (150, 150, 150),
                               (int(x), int(y - (0.5 - l) * 24)), r)

    def draw_hud(self):
        s = self.screen
        # the driver cheers from the night sky, clear of both lanes
        self.draw_driver_hud((10, 14))

        # top-right: distance + race time + best (same style as scroll)
        top = pygame.Rect(VW - 320, 10, 300, 66)
        self.panel_rect(top)
        best = f"{self.board[0]['time']:.1f}s" if self.board else "-"
        s.blit(self.font.render(
            f"DIST {int(self.dist / 10):4d} / {QM_D // 10} m", True,
            (255, 255, 255)), (top.x + 12, 16))
        s.blit(self.font.render(f"TIME {self.race_time:5.1f}s  BEST {best}", True,
                                (255, 210, 74)), (top.x + 12, 38))

        # bottom-left: gear + rpm needle + speed bar (below the lanes)
        panel = pygame.Rect(10, VH - 130, 250, 120)
        self.panel_rect(panel)
        s.blit(self.font_big.render(f"GEAR {self.gear}", True, (255, 210, 74)),
               (panel.x + 16, panel.y + 12))
        bx, bw = panel.x + 130, 100
        s.blit(self.font.render("RPM", True, (255, 255, 255)),
               (bx, panel.y + 16))
        pygame.draw.rect(s, (68, 68, 68), (bx, panel.y + 38, bw, 12))
        col = (239, 68, 68) if self.rpm >= REDLINE else (74, 222, 128)
        pygame.draw.rect(s, col, (bx, panel.y + 38, int(bw * self.rpm), 12))
        pygame.draw.rect(s, (90, 90, 90), (bx, panel.y + 38, bw, 12), 1)
        pygame.draw.rect(s, (255, 210, 74),
                         (bx + int(bw * REDLINE), panel.y + 34, 2, 20))
        if self.overrev > 0 and pygame.time.get_ticks() // 200 % 2 == 0:
            s.blit(self.font.render("OVERREV!", True, (239, 68, 68)),
                   (bx, panel.y + 54))
        s.blit(self.font.render(f"SPD {int(self.speed):3d}", True,
                                (255, 255, 255)), (panel.x + 16, panel.y + 74))
        top_spd = GEARS[-1][1] + self.car_spec["max"]
        pygame.draw.rect(s, (68, 68, 68), (panel.x + 16, panel.y + 96, 218, 10))
        pygame.draw.rect(s, (74, 222, 128),
                         (panel.x + 16, panel.y + 96, int(218 * self.speed / top_spd), 10))
        # haunt stage 2+: the controls the car demands right now
        if self.haunt >= 2:
            hint = (f"GAS {KEY_NAMES[self.gas_key]} - "
                    f"SHIFT {KEY_NAMES[self.shift_key]}")
            hcol = (239, 68, 68) if self.haunt >= 3 else (255, 210, 74)
            if (self.haunt >= 3
                    and pygame.time.get_ticks() // 300 % 2 == 0):
                hint = hint.replace("GAS", "GAS?")
            hs = self.font.render(hint, True, hcol)
            s.blit(hs, (panel.x, panel.y - 24))

        # countdown lights / green flash (top center, clear of the lanes)
        if self.started and not self.green:
            for i in range(3):
                on = self.cd_t > 0.8 + i * 0.8
                col = (255, 210, 74) if on else (60, 60, 70)
                pygame.draw.circle(s, col, (int(VW / 2 - 60 + i * 60), 92), 16)
            if self.cd_t < 0.8:
                rd = self.font_big.render("READY", True, (255, 255, 255))
                s.blit(rd, rd.get_rect(center=(VW / 2, 124)))
        elif self.green and self.race_time < 1.0:
            pygame.draw.circle(s, (74, 222, 128), (int(VW / 2), 92), 16)
            go = self.font_big.render("GO!", True, (74, 222, 128))
            s.blit(go, go.get_rect(center=(VW / 2, 124)))

        # horizontal race progress bar (between the lanes and the HUD):
        # green marker = you, red marker = rival, ticks every 50 m
        px0, px1, py = 300, VW - 40, 428
        pygame.draw.rect(s, (20, 20, 30, 110),
                         (px0 - 16, py - 22, px1 - px0 + 32, 44),
                         border_radius=6)
        pygame.draw.rect(s, (68, 68, 68), (px0, py, px1 - px0, 6))
        for i in range(QM_D // 500):
            mx = px0 + (px1 - px0) * ((i + 1) * 500 / QM_D)
            pygame.draw.rect(s, (90, 90, 100), (int(mx), py - 4, 2, 14))
        ry_ = px0 + (px1 - px0) * min(1.0, self.rival_dist / QM_D)
        pygame.draw.rect(s, (239, 68, 68), (int(ry_) - 8, py - 2, 16, 10))
        fy_ = px0 + (px1 - px0) * min(1.0, self.dist / QM_D)
        pygame.draw.rect(s, (74, 222, 128), (int(fy_) - 8, py - 2, 16, 10))
        s.blit(self.font_small.render("YOU", True, (74, 222, 128)),
               (px0, py - 18))
        s.blit(self.font_small.render("RIVAL", True, (239, 68, 68)),
               (px0 + 40, py - 18))
        s.blit(self.font_small.render("0", True, (255, 255, 255)),
               (px0 - 4, py + 8))
        s.blit(self.font_small.render(f"{QM_D // 10} m", True, (255, 255, 255)),
               (px1 - 34, py + 8))

    def draw(self):
        self.draw_world()
        self.draw_hud()
        if not self.started:
            lines = [
                ("DRUGSTER - QUARTER MILE" if self.haunt >= 2
                 else "DRAG RACE - QUARTER MILE",
                 self.font_big, (255, 210, 74)),
                (f"tonight the car demands: {KEY_NAMES[self.gas_key]} ="
                 f" gas, {KEY_NAMES[self.shift_key]} = shift"
                 if self.haunt >= 2 else
                 "hold UP for gas - SPACE shifts up through 4 gears",
                 self.font,
                 (239, 68, 68) if self.haunt >= 2 else (255, 255, 255)),
                ("shift near the redline - too early bogs the engine",
                 self.font, (255, 255, 255)),
                ("screaming at the redline too long blows the engine",
                 self.font, (255, 255, 255)),
                ("gas before the green light is a FOUL START",
                 self.font, (255, 255, 255)),
            ]
            if self.haunt >= 1:
                lines.append(("the exhaust smells like old smoke"
                              if self.haunt == 1
                              else "the tree blinks like a bad memory",
                              self.font, (180, 180, 190)))
            lines.append(("ENTER start - R repeat after race - ESC menu",
                          self.font, (74, 222, 128)))
            lines.append(("M toggles sound - Q quits",
                          self.font, (74, 222, 128)))
            self.overlay(*lines, *self.lb_lines())
        elif self.over:
            head_col = (74, 222, 128) if self.won else (239, 68, 68)
            lines = [(self.reason, self.font_big, head_col)]
            if self.reason == "THE CAR EXPLODED":
                lines.append(("no warning. no reason. it has happened before.",
                              self.font, (239, 68, 68)))
            if self.reason in ("YOU WIN!", "YOU LOSE"):
                lines.append((f"TIME {self.race_time:.1f}s", self.font,
                              (255, 255, 255)))
                lines.append((f"CASH +${self.cash_won}", self.font,
                              (74, 222, 128)))
                if self.haunt >= 1:
                    lines.append(("the prize money feels like evidence",
                                  self.font, (180, 180, 190)))
            lines.append(("press R to repeat - ESC for the menu", self.font,
                          (74, 222, 128)))
            self.overlay(*lines, *self.lb_lines())
        # haunt stage 2+: the keys the car demands, big and central
        # while they matter - during the countdown, for the first
        # seconds after the green, and LOUDLY after every mid-run change
        if (self.haunt >= 2 and self.started and not self.over
                and (not self.green or self.remap_msg_t > 0
                     or self.race_time < 2.5)):
            s = self.screen
            l1 = ("THE KEYS HAVE CHANGED" if self.remap_msg_t > 0
                  else "TONIGHT THE CAR DEMANDS")
            l2 = (f"GAS {KEY_NAMES[self.gas_key]}"
                  f"   SHIFT {KEY_NAMES[self.shift_key]}")
            col = ((239, 68, 68) if pygame.time.get_ticks() // 200 % 2
                   else (255, 255, 255))
            t1 = self.font_big.render(l1, True, col)
            t2 = self.font_big.render(l2, True, col)
            s.blit(t1, t1.get_rect(center=(VW / 2, 156)))
            s.blit(t2, t2.get_rect(center=(VW / 2, 198)))
        self.draw_boom(self.screen)
        self.draw_scare(self.screen)

    # -------------------------------- run ----------------------------------
    def run(self):
        while not self.exited:
            dt = min(0.05, self.app.clock.tick(FPS) / 1000)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.exited = True
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                    self.stop_loops()
                    music.toggle_mute(self.app)
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    self.app.toggle_fullscreen()
            keys = pygame.key.get_pressed()
            if keys[pygame.K_ESCAPE]:
                self.stop_loops()
                return          # back to the menu
            self.update(dt, keys)
            self.draw()
            pygame.display.flip()
        self.stop_loops()