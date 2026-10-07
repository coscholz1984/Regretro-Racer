"""RETRO RACER DELUXE - main.py (entry point)

Run with:  python main.py     (all nine files in one folder)

Project layout:
    main.py     this file - menu/garage/race dispatch loop
    core.py     shared engine: window/App, sounds, save files, BaseGame
    sprites.py  pixel-art sprites, palettes, garage car catalogue
    music.py    background music: looping synth tracks (TRACKS registry)
    circuit.py  mini-game: 3-lap circuit race against AI cars
    scroll.py   mini-game: 3000 m vertical dash with traffic
    dragster.py mini-game: quarter-mile drag race (Atari Dragster)
    menu.py     main menu, mini-game picker + garage screens
    regret.py   the dark story arc: court/hospital/meds scenes,
                the final flashback and the memorial

Save files (leaderboard_circuit.json, leaderboard_scroll.json,
leaderboard_dragster.json, cash.json) are written next to the other
.py files - drop your old ones in the same folder to keep your
records and cash. The "haunt" key inside cash.json tracks how far
the dark backstory has crept in (see core.py) - it also stores the
"arcade" flag. BACKSPACE on the memorial (or deleting the key)
resets the arc; cash and records survive.

Menu flow:
    main menu (PLAY / GARAGE / PROFILE, + ARCADE/STORY after the
    truth has been relived)
        PLAY    -> mini-game picker -> the selected game; from haunt
                  stage 4 the picker shows the regret scenes instead
        ARCADE  -> toggle arcade mode: the clean versions of the three
                  races return, playable just for cash and progress
                  (no haunt effects, no scenes); STORY switches back
        CTRL+R  -> in the aftermath story menu: erase the whole arc
                  and start the story over (asked twice; cash and
                  records are kept)
        GARAGE  -> car showroom, ESC returns to the main menu
        PROFILE -> driver profile: name, clothes, hair and a hat shop
                   (medicine, once the story turns), ESC returns to
                   the main menu

Music: the menu tune keeps playing in the menus and the garage (the
deeper the haunt, the slower and flatter it plays); each mini-game
starts its own track in its reset() via music.start_music.

Adding a new mini-game:
    1. write a new module, e.g. drift.py, with a class
       DriftGame(core.BaseGame) - copy the run() pattern from
       circuit.py or scroll.py (event loop, update, draw, ESC to menu)
    2. add one entry to the GAMES registry in menu.py
       (card name, game class, leaderboard file - use a new .json)
    3. optional: add a "drift" entry to TRACKS in music.py and start
       it with music.start_music(self.app, "drift") in reset()
    main.py needs no changes: the dispatch loop reads the registry.
"""
import pygame

import music
from core import App, haunt_title, play_haunt, reset_haunt, set_arcade
from menu import (active_games, run_game_select, run_garage, run_menu,
                  run_profile)


def main():
    app = App()
    while True:
        pygame.display.set_caption(haunt_title())
        music.start_music(app, "menu", haunt=min(play_haunt(), 3))
        mode = run_menu(app)               # "play", "garage", "profile",
        if mode is None:                   # "arcade"/"story"/"reset" or None
            music.stop_music()
            pygame.quit()
            return
        if mode in ("arcade", "story"):    # toggle, then re-read the menu
            set_arcade(mode == "arcade")   # (title, music, cards change)
            continue
        if mode == "reset":                # forget the whole arc: the
            reset_haunt()                  # menu re-reads the (empty)
            continue                       # haunt - fresh story, same cash
        if mode == "garage":
            result = run_garage(app)       # the menu tune keeps playing
            if result == "quit":
                music.stop_music()
                pygame.quit()
                return
            continue
        if mode == "profile":
            result = run_profile(app)      # the menu tune keeps playing
            if result == "quit":
                music.stop_music()
                pygame.quit()
                return
            continue
        # mode == "play": mini-game picker (menu tune keeps playing)
        games = active_games()             # races, or the regret scenes
        idx = run_game_select(app)
        if idx is None:                    # ESC back to the main menu
            continue
        game = games[idx]["cls"](app)      # its reset() starts its track
        game.run()
        if game.exited:
            pygame.quit()
            return


if __name__ == "__main__":
    main()