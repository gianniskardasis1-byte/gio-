import pygame
import sys
import time
import socket
import threading
import json
import queue

from server import GameServer, WebSocketBridge, get_local_ip, DEFAULT_PORT

# ──────────────── Settings ────────────────
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
DARK_GRAY = (80, 80, 80)
LIGHT_GRAY = (230, 230, 230)
BG_COLOR = (240, 240, 245)
PANEL_COLOR = (50, 55, 70)
ACCENT = (80, 140, 255)
CORRECT_GREEN = (40, 200, 80)
WRONG_RED = (220, 60, 60)

PALETTE = [
    (0, 0, 0), (255, 255, 255), (200, 200, 200),
    (255, 0, 0), (255, 100, 0), (255, 220, 0),
    (0, 180, 0), (0, 200, 200), (0, 80, 255),
    (140, 0, 255), (255, 0, 200), (140, 80, 20),
]
BRUSH_SIZES = [3, 6, 10, 18, 30]


# ──────────── Network client ────────────
class NetClient:
    def __init__(self):
        self.sock = None
        self.connected = False
        self.incoming = queue.Queue()
        self._buf = ""

    def connect(self, host, port, name):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((host, int(port)))
        self.sock.settimeout(None)
        self.connected = True
        self.send({"type": "join", "name": name})
        threading.Thread(target=self._recv, daemon=True).start()

    def _recv(self):
        while self.connected:
            try:
                data = self.sock.recv(4096)
                if not data:
                    self.connected = False
                    self.incoming.put({"type": "_dc"})
                    return
                self._buf += data.decode()
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            self.incoming.put(json.loads(line))
                        except (json.JSONDecodeError, ValueError):
                            pass
            except Exception:
                self.connected = False
                self.incoming.put({"type": "_dc"})
                return

    def send(self, msg):
        if self.connected and self.sock:
            try:
                self.sock.sendall((json.dumps(msg) + "\n").encode())
            except Exception:
                self.connected = False

    def poll(self):
        msgs = []
        try:
            while True:
                msgs.append(self.incoming.get_nowait())
        except queue.Empty:
            pass
        return msgs

    def disconnect(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass


# ──────────── Main ────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((1200, 800))
    SW, SH = screen.get_size()
    fullscreen = False

    def set_screen(full):
        nonlocal screen, SW, SH
        if full:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            screen = pygame.display.set_mode((1200, 800))
        SW, SH = screen.get_size()

    pygame.display.set_caption("Skribbl \u2014 Multiplayer Draw & Guess")
    clock = pygame.time.Clock()

    # Fonts
    font_big = pygame.font.SysFont("segoeui", 36, bold=True)
    font_med = pygame.font.SysFont("segoeui", 22)
    font_small = pygame.font.SysFont("segoeui", 18)
    font_tiny = pygame.font.SysFont("segoeui", 14)
    font_input = pygame.font.SysFont("consolas", 20)

    # ── helpers ──
    def draw_rounded_rect(surf, color, rect, r=8):
        pygame.draw.rect(surf, color, rect, border_radius=r)

    def draw_button(surf, text, rect, color=ACCENT, tc=WHITE, f=font_med):
        draw_rounded_rect(surf, color, rect, 10)
        t = f.render(text, True, tc)
        surf.blit(t, t.get_rect(center=rect.center))

    def draw_text_input(surf, text, rect, active=False, f=font_input):
        pygame.draw.rect(surf, WHITE, rect, border_radius=6)
        pygame.draw.rect(surf, ACCENT if active else GRAY, rect, 2, border_radius=6)
        t = f.render(text + ("\u2502" if active else ""), True, BLACK)
        surf.blit(t, (rect.x + 8, rect.y + (rect.h - t.get_height()) // 2))

    # ── state ──
    net = NetClient()
    server_inst = None

    phase = "menu"       # menu | joining | lobby | playing | round_result | game_over
    name_text = ""
    ip_text = ""
    active_input = "name"
    error_msg = ""
    my_id = None
    is_host = False

    # lobby / game
    players = []         # [{id, name, score}, ...]
    drawer_id = None
    drawer_name = ""
    word = ""            # only set for drawer
    hint = ""
    current_round = 0
    total_rounds = 6
    time_left = 60
    guess_text = ""
    chat_log = []        # [(text, color), ...]
    guessed_correctly = False

    # canvas
    LEFT_W = 190
    RIGHT_W = 210
    CANVAS_X = LEFT_W + 10
    CANVAS_Y = 60
    canvas_w = SW - LEFT_W - RIGHT_W - 20
    canvas_h = SH - 220
    canvas = pygame.Surface((canvas_w, canvas_h))
    canvas.fill(WHITE)
    draw_color = BLACK
    brush_size = 6
    drawing = False
    last_pos = None

    # round result
    result_word = ""
    result_reason = ""
    result_timer = 0

    def reset_canvas():
        nonlocal canvas, canvas_w, canvas_h
        canvas_w = max(200, SW - LEFT_W - RIGHT_W - 20)
        canvas_h = max(200, SH - 220)
        canvas = pygame.Surface((canvas_w, canvas_h))
        canvas.fill(WHITE)

    def recalc_layout():
        nonlocal CANVAS_X, CANVAS_Y, canvas_w, canvas_h
        CANVAS_X = LEFT_W + 10
        CANVAS_Y = 60
        canvas_w = max(200, SW - LEFT_W - RIGHT_W - 20)
        canvas_h = max(200, SH - 220)

    # ── main loop ──
    running = True
    while running:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()
        recalc_layout()

        # ── process network ──
        if net.connected:
            for msg in net.poll():
                mt = msg.get("type", "")

                if mt == "welcome":
                    my_id = msg["id"]
                    is_host = msg.get("is_host", False)
                    players = msg.get("players", [])
                    phase = "lobby"
                    error_msg = ""

                elif mt == "you_are_host":
                    is_host = True

                elif mt == "player_joined":
                    players.append({"id": msg["id"], "name": msg["name"], "score": 0})
                    chat_log.append((f"{msg['name']} joined", ACCENT))

                elif mt == "player_left":
                    players = [p for p in players if p["id"] != msg["id"]]
                    chat_log.append((f"{msg['name']} left", GRAY))

                elif mt == "new_round":
                    phase = "playing"
                    current_round = msg["round"]
                    total_rounds = msg["total_rounds"]
                    drawer_id = msg["drawer_id"]
                    drawer_name = msg["drawer_name"]
                    word = msg.get("word", "")
                    hint = msg.get("hint", "")
                    time_left = msg.get("time", 60)
                    players = msg.get("players", players)
                    guess_text = ""
                    guessed_correctly = False
                    chat_log = []
                    reset_canvas()
                    drawing = False
                    last_pos = None
                    draw_color = BLACK
                    brush_size = 6
                    if drawer_id == my_id:
                        chat_log.append((f"Your word: {word.upper()}", ACCENT))
                    else:
                        chat_log.append((f"{drawer_name} is drawing!", ACCENT))

                elif mt == "draw_line":
                    x1 = int(msg["x1"] * canvas_w)
                    y1 = int(msg["y1"] * canvas_h)
                    x2 = int(msg["x2"] * canvas_w)
                    y2 = int(msg["y2"] * canvas_h)
                    c = tuple(msg["color"])
                    s = msg["size"]
                    pygame.draw.line(canvas, c, (x1, y1), (x2, y2), s)
                    pygame.draw.circle(canvas, c, (x2, y2), s // 2)

                elif mt == "draw_dot":
                    x = int(msg["x"] * canvas_w)
                    y = int(msg["y"] * canvas_h)
                    c = tuple(msg["color"])
                    s = msg["size"]
                    pygame.draw.circle(canvas, c, (x, y), s // 2)

                elif mt == "clear_canvas":
                    canvas.fill(WHITE)

                elif mt == "correct_guess":
                    pn = msg["player_name"]
                    chat_log.append(("\u2713 " + pn + " guessed correctly!", CORRECT_GREEN))
                    if msg["player_id"] == my_id:
                        guessed_correctly = True
                    scores = msg.get("scores", {})
                    for p in players:
                        sd = scores.get(str(p["id"]))
                        if sd:
                            p["score"] = sd["score"]

                elif mt == "wrong_guess":
                    pn = msg["player_name"]
                    tx = msg["text"]
                    if msg["player_id"] == my_id:
                        chat_log.append(("\u2717 " + tx, WRONG_RED))
                    else:
                        chat_log.append(("\u2717 " + pn + ": " + tx, WRONG_RED))

                elif mt == "hint":
                    hint = msg["hint"]

                elif mt == "timer":
                    time_left = msg["time_left"]

                elif mt == "round_over":
                    phase = "round_result"
                    result_word = msg["word"]
                    result_reason = msg["reason"]
                    result_timer = time.time()
                    scores = msg.get("scores", {})
                    for p in players:
                        sd = scores.get(str(p["id"]))
                        if sd:
                            p["score"] = sd["score"]

                elif mt == "game_over":
                    phase = "game_over"
                    scores = msg.get("scores", {})
                    for p in players:
                        sd = scores.get(str(p["id"]))
                        if sd:
                            p["score"] = sd["score"]

                elif mt == "back_to_lobby":
                    phase = "lobby"
                    chat_log.append((msg.get("reason", "Back to lobby"), GRAY))

                elif mt == "_dc":
                    phase = "menu"
                    error_msg = "Disconnected from server"
                    net.disconnect()

        # ── events ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    set_screen(fullscreen)
                    reset_canvas()
                    continue
                if event.key == pygame.K_ESCAPE and fullscreen:
                    fullscreen = False
                    set_screen(fullscreen)
                    reset_canvas()
                    continue

            # ── MENU ──
            if phase == "menu":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    name_rect = pygame.Rect(SW // 2 - 150, 280, 300, 40)
                    if name_rect.collidepoint(event.pos):
                        active_input = "name"

                    host_btn = pygame.Rect(SW // 2 - 260, 380, 240, 55)
                    if host_btn.collidepoint(event.pos) and name_text.strip():
                        try:
                            server_inst = GameServer()
                            threading.Thread(target=server_inst.run, daemon=True).start()
                            WebSocketBridge(server_inst).run_in_thread()
                            time.sleep(0.4)
                            net.connect("127.0.0.1", DEFAULT_PORT, name_text.strip())
                        except Exception as e:
                            error_msg = str(e)

                    join_btn = pygame.Rect(SW // 2 + 20, 380, 240, 55)
                    if join_btn.collidepoint(event.pos) and name_text.strip():
                        phase = "joining"
                        active_input = "ip"
                        error_msg = ""

                elif event.type == pygame.KEYDOWN and active_input == "name":
                    if event.key == pygame.K_BACKSPACE:
                        name_text = name_text[:-1]
                    elif event.key == pygame.K_RETURN and name_text.strip():
                        active_input = "ip"
                    elif len(name_text) < 15 and event.unicode.isprintable():
                        name_text += event.unicode

            # ── JOINING ──
            elif phase == "joining":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    ip_rect = pygame.Rect(SW // 2 - 150, 280, 300, 40)
                    if ip_rect.collidepoint(event.pos):
                        active_input = "ip"

                    connect_btn = pygame.Rect(SW // 2 - 110, 350, 220, 50)
                    if connect_btn.collidepoint(event.pos) and ip_text.strip():
                        try:
                            net.connect(ip_text.strip(), DEFAULT_PORT, name_text.strip())
                        except Exception as e:
                            error_msg = str(e)

                    back_btn = pygame.Rect(SW // 2 - 110, 420, 220, 50)
                    if back_btn.collidepoint(event.pos):
                        phase = "menu"
                        error_msg = ""

                elif event.type == pygame.KEYDOWN:
                    if active_input == "ip":
                        if event.key == pygame.K_BACKSPACE:
                            ip_text = ip_text[:-1]
                        elif event.key == pygame.K_RETURN and ip_text.strip():
                            try:
                                net.connect(ip_text.strip(), DEFAULT_PORT, name_text.strip())
                            except Exception as e:
                                error_msg = str(e)
                        elif event.key == pygame.K_ESCAPE:
                            phase = "menu"
                            error_msg = ""
                        elif len(ip_text) < 45 and event.unicode.isprintable():
                            ip_text += event.unicode

            # ── LOBBY ──
            elif phase == "lobby":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    start_btn = pygame.Rect(SW // 2 - 120, 500, 240, 55)
                    if start_btn.collidepoint(event.pos) and is_host and len(players) >= 2:
                        net.send({"type": "start_game"})

            # ── PLAYING ──
            elif phase == "playing":
                am_drawer = (drawer_id == my_id)

                if am_drawer:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        clicked_ui = False
                        # palette
                        for i, col in enumerate(PALETTE):
                            cx = 20 + (i % 2) * 40
                            cy = 100 + (i // 2) * 40
                            if pygame.Rect(cx, cy, 34, 34).collidepoint(event.pos):
                                draw_color = col
                                clicked_ui = True
                                break
                        # brush sizes
                        if not clicked_ui:
                            for i, sz in enumerate(BRUSH_SIZES):
                                bx = 20 + i * 34
                                by = CANVAS_Y + canvas_h + 20
                                if pygame.Rect(bx, by, 30, 30).collidepoint(event.pos):
                                    brush_size = sz
                                    clicked_ui = True
                                    break
                        # clear
                        if not clicked_ui:
                            clr_btn = pygame.Rect(20, CANVAS_Y + canvas_h + 60, 160, 35)
                            if clr_btn.collidepoint(event.pos):
                                canvas.fill(WHITE)
                                net.send({"type": "clear_canvas"})
                                clicked_ui = True
                        # start draw
                        if not clicked_ui:
                            cr = pygame.Rect(CANVAS_X, CANVAS_Y, canvas_w, canvas_h)
                            if cr.collidepoint(event.pos):
                                drawing = True
                                last_pos = (mx - CANVAS_X, my - CANVAS_Y)
                                pygame.draw.circle(canvas, draw_color, last_pos, brush_size // 2)
                                net.send({
                                    "type": "draw_dot",
                                    "x": last_pos[0] / canvas_w,
                                    "y": last_pos[1] / canvas_h,
                                    "color": list(draw_color),
                                    "size": brush_size,
                                })

                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        drawing = False
                        last_pos = None

                    elif event.type == pygame.MOUSEMOTION and drawing:
                        cr = pygame.Rect(CANVAS_X, CANVAS_Y, canvas_w, canvas_h)
                        if cr.collidepoint(event.pos):
                            cur = (mx - CANVAS_X, my - CANVAS_Y)
                            if last_pos:
                                pygame.draw.line(canvas, draw_color, last_pos, cur, brush_size)
                                pygame.draw.circle(canvas, draw_color, cur, brush_size // 2)
                                net.send({
                                    "type": "draw_line",
                                    "x1": last_pos[0] / canvas_w,
                                    "y1": last_pos[1] / canvas_h,
                                    "x2": cur[0] / canvas_w,
                                    "y2": cur[1] / canvas_h,
                                    "color": list(draw_color),
                                    "size": brush_size,
                                })
                            last_pos = cur
                        else:
                            last_pos = None

                # guessing input (not drawer, not already guessed)
                if not am_drawer and not guessed_correctly:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN and guess_text.strip():
                            net.send({"type": "guess", "text": guess_text.strip()})
                            guess_text = ""
                        elif event.key == pygame.K_BACKSPACE:
                            guess_text = guess_text[:-1]
                        elif len(guess_text) < 30 and event.unicode.isprintable():
                            guess_text += event.unicode

            # ── GAME OVER ──
            elif phase == "game_over":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    lobby_btn = pygame.Rect(SW // 2 - 120, 520, 240, 55)
                    if lobby_btn.collidepoint(event.pos):
                        phase = "lobby"

        # ══════════════ RENDER ══════════════
        screen.fill(BG_COLOR)

        if phase == "menu":
            title = font_big.render("Skribbl \u2014 Draw & Guess!", True, PANEL_COLOR)
            screen.blit(title, title.get_rect(center=(SW // 2, 140)))
            sub = font_med.render("Play with friends on your network!", True, DARK_GRAY)
            screen.blit(sub, sub.get_rect(center=(SW // 2, 200)))

            lbl = font_small.render("Your Name:", True, DARK_GRAY)
            screen.blit(lbl, (SW // 2 - 150, 255))
            name_rect = pygame.Rect(SW // 2 - 150, 280, 300, 40)
            draw_text_input(screen, name_text, name_rect, active_input == "name")

            host_btn = pygame.Rect(SW // 2 - 260, 380, 240, 55)
            draw_button(screen, "HOST GAME", host_btn, ACCENT if name_text.strip() else GRAY)
            join_btn = pygame.Rect(SW // 2 + 20, 380, 240, 55)
            draw_button(screen, "JOIN GAME", join_btn, ACCENT if name_text.strip() else GRAY)

            tip = font_tiny.render("HOST starts a server. JOIN connects to a friend's game.", True, DARK_GRAY)
            screen.blit(tip, tip.get_rect(center=(SW // 2, 460)))

            if error_msg:
                err = font_small.render(error_msg, True, WRONG_RED)
                screen.blit(err, err.get_rect(center=(SW // 2, 500)))

        elif phase == "joining":
            title = font_big.render("Join Game", True, PANEL_COLOR)
            screen.blit(title, title.get_rect(center=(SW // 2, 160)))

            lbl = font_small.render("Server IP address:", True, DARK_GRAY)
            screen.blit(lbl, (SW // 2 - 150, 255))
            ip_rect = pygame.Rect(SW // 2 - 150, 280, 300, 40)
            draw_text_input(screen, ip_text, ip_rect, active_input == "ip")

            connect_btn = pygame.Rect(SW // 2 - 110, 350, 220, 50)
            draw_button(screen, "CONNECT", connect_btn, ACCENT if ip_text.strip() else GRAY)
            back_btn = pygame.Rect(SW // 2 - 110, 420, 220, 50)
            draw_button(screen, "BACK", back_btn, DARK_GRAY)

            if error_msg:
                err = font_small.render(error_msg, True, WRONG_RED)
                screen.blit(err, err.get_rect(center=(SW // 2, 500)))

        elif phase == "lobby":
            title = font_big.render("Lobby", True, PANEL_COLOR)
            screen.blit(title, title.get_rect(center=(SW // 2, 100)))

            if server_inst:
                ip = get_local_ip()
                ip_lbl = font_med.render(f"Your IP: {ip}  (share with friends!)", True, ACCENT)
                screen.blit(ip_lbl, ip_lbl.get_rect(center=(SW // 2, 160)))

            waiting = font_small.render("Waiting for players\u2026", True, DARK_GRAY)
            screen.blit(waiting, waiting.get_rect(center=(SW // 2, 210)))

            # player list
            y_off = 260
            for i, p in enumerate(players):
                tag = ""
                if p["id"] == my_id:
                    tag += " (you)"
                if is_host and p["id"] == my_id:
                    tag += " \u2605 HOST"
                txt = font_med.render(f"  {p['name']}{tag}", True, PANEL_COLOR)
                screen.blit(txt, (SW // 2 - 150, y_off))
                y_off += 35

            if is_host:
                start_btn = pygame.Rect(SW // 2 - 120, 500, 240, 55)
                can_start = len(players) >= 2
                draw_button(screen, "START GAME", start_btn, ACCENT if can_start else GRAY)
                if not can_start:
                    need = font_tiny.render("Need at least 2 players", True, DARK_GRAY)
                    screen.blit(need, need.get_rect(center=(SW // 2, 570)))
            else:
                wmsg = font_small.render("Waiting for host to start\u2026", True, DARK_GRAY)
                screen.blit(wmsg, wmsg.get_rect(center=(SW // 2, 520)))

        elif phase == "playing":
            am_drawer = (drawer_id == my_id)
            right_x = CANVAS_X + canvas_w + 10

            # ── left panel ──
            panel = pygame.Rect(0, 0, LEFT_W, SH)
            draw_rounded_rect(screen, PANEL_COLOR, panel, 0)

            r_txt = font_small.render(f"Round {current_round}/{total_rounds}", True, WHITE)
            screen.blit(r_txt, (15, 10))

            # who's drawing
            if am_drawer:
                d_txt = font_small.render("You are drawing!", True, CORRECT_GREEN)
            else:
                d_txt = font_small.render(f"{drawer_name} draws", True, ACCENT)
            screen.blit(d_txt, (15, 35))

            # palette
            p_lbl = font_tiny.render("COLORS", True, GRAY)
            screen.blit(p_lbl, (15, 83))
            for i, col in enumerate(PALETTE):
                cx = 20 + (i % 2) * 40
                cy = 100 + (i // 2) * 40
                cr = pygame.Rect(cx, cy, 34, 34)
                pygame.draw.rect(screen, col, cr, border_radius=4)
                if col == draw_color and am_drawer:
                    pygame.draw.rect(screen, WHITE, cr, 3, border_radius=4)
                else:
                    pygame.draw.rect(screen, DARK_GRAY, cr, 1, border_radius=4)

            # brush sizes
            bs_lbl = font_tiny.render("BRUSH SIZE", True, GRAY)
            screen.blit(bs_lbl, (15, CANVAS_Y + canvas_h + 3))
            for i, sz in enumerate(BRUSH_SIZES):
                bx = 20 + i * 34
                by = CANVAS_Y + canvas_h + 20
                br = pygame.Rect(bx, by, 30, 30)
                draw_rounded_rect(screen, ACCENT if sz == brush_size and am_drawer else (70, 75, 90), br, 6)
                pygame.draw.circle(screen, WHITE, br.center, min(sz // 2, 12))

            # clear button
            if am_drawer:
                clr_btn = pygame.Rect(20, CANVAS_Y + canvas_h + 60, 160, 35)
                draw_button(screen, "Clear Canvas", clr_btn, WRONG_RED, WHITE, font_small)

            # ── canvas ──
            # word / hint above canvas
            if am_drawer:
                wl = font_big.render(f"Draw: {word.upper()}", True, ACCENT)
                screen.blit(wl, (CANVAS_X, CANVAS_Y - 50))
            else:
                hl = font_med.render(f"Hint: {hint}", True, DARK_GRAY)
                screen.blit(hl, (CANVAS_X, CANVAS_Y - 40))

            # timer bar
            ratio = max(0, time_left / 60)
            bar = pygame.Rect(CANVAS_X, CANVAS_Y - 14, canvas_w, 10)
            pygame.draw.rect(screen, GRAY, bar, border_radius=4)
            fc = CORRECT_GREEN if ratio > 0.3 else (255, 180, 0) if ratio > 0.1 else WRONG_RED
            fill = pygame.Rect(CANVAS_X, CANVAS_Y - 14, int(canvas_w * ratio), 10)
            pygame.draw.rect(screen, fc, fill, border_radius=4)
            tt = font_tiny.render(f"{int(time_left)}s", True, BLACK)
            screen.blit(tt, (CANVAS_X + canvas_w - 28, CANVAS_Y - 16))

            # canvas border + surface
            pygame.draw.rect(screen, DARK_GRAY, pygame.Rect(CANVAS_X - 2, CANVAS_Y - 2, canvas_w + 4, canvas_h + 4), 2, border_radius=4)
            screen.blit(canvas, (CANVAS_X, CANVAS_Y))

            # ── guess input (below canvas) ──
            if not am_drawer and not guessed_correctly:
                inp_rect = pygame.Rect(CANVAS_X, CANVAS_Y + canvas_h + 10, canvas_w - 80, 36)
                pygame.draw.rect(screen, WHITE, inp_rect, border_radius=6)
                pygame.draw.rect(screen, ACCENT, inp_rect, 2, border_radius=6)
                gt = font_input.render(guess_text + "\u2502", True, BLACK)
                screen.blit(gt, (inp_rect.x + 8, inp_rect.y + 7))
                el = font_small.render("Enter \u21b5", True, DARK_GRAY)
                screen.blit(el, (inp_rect.right + 8, inp_rect.y + 7))
            elif not am_drawer and guessed_correctly:
                gl = font_med.render("\u2713 You guessed it!", True, CORRECT_GREEN)
                screen.blit(gl, (CANVAS_X, CANVAS_Y + canvas_h + 15))
            elif am_drawer:
                hl2 = font_small.render(f"Guessers see: {hint}", True, DARK_GRAY)
                screen.blit(hl2, (CANVAS_X, CANVAS_Y + canvas_h + 15))

            # ── right panel: players + chat ──
            rp = pygame.Rect(right_x, 0, SW - right_x, SH)
            draw_rounded_rect(screen, PANEL_COLOR, rp, 0)

            pl = font_small.render("PLAYERS", True, GRAY)
            screen.blit(pl, (right_x + 10, 10))

            sorted_players = sorted(players, key=lambda p: p["score"], reverse=True)
            py_pos = 35
            for p in sorted_players:
                suffix = ""
                if p["id"] == drawer_id:
                    suffix = " \U0001f3a8"
                nm = font_small.render(f"{p['name']}{suffix}", True, ACCENT if p["id"] == my_id else WHITE)
                sc = font_small.render(f"{p['score']}", True, GRAY)
                screen.blit(nm, (right_x + 10, py_pos))
                screen.blit(sc, (SW - 50, py_pos))
                py_pos += 28

            # chat/guess log
            cl = font_small.render("CHAT", True, GRAY)
            screen.blit(cl, (right_x + 10, py_pos + 15))
            cy_pos = py_pos + 40
            max_msgs = max(1, (SH - cy_pos - 10) // 22)
            visible = chat_log[-max_msgs:]
            for msg_text, msg_col in visible:
                ct = font_tiny.render(msg_text, True, msg_col)
                screen.blit(ct, (right_x + 10, cy_pos))
                cy_pos += 22

        elif phase == "round_result":
            box = pygame.Rect(SW // 2 - 250, SH // 2 - 140, 500, 280)
            draw_rounded_rect(screen, WHITE, box, 16)
            pygame.draw.rect(screen, DARK_GRAY, box, 2, border_radius=16)

            if result_reason == "timeout":
                t1 = font_big.render("Time's Up!", True, WRONG_RED)
            elif result_reason == "all_guessed":
                t1 = font_big.render("Everyone Guessed!", True, CORRECT_GREEN)
            elif result_reason == "drawer_left":
                t1 = font_big.render("Drawer Left", True, DARK_GRAY)
            else:
                t1 = font_big.render("Round Over", True, DARK_GRAY)
            screen.blit(t1, t1.get_rect(center=(SW // 2, SH // 2 - 90)))

            t2 = font_med.render(f'The word was: "{result_word.upper()}"', True, DARK_GRAY)
            screen.blit(t2, t2.get_rect(center=(SW // 2, SH // 2 - 30)))

            sorted_p = sorted(players, key=lambda p: p["score"], reverse=True)
            sy = SH // 2 + 10
            for p in sorted_p[:5]:
                st = font_small.render(f"{p['name']}: {p['score']} pts", True, ACCENT if p["id"] == my_id else DARK_GRAY)
                screen.blit(st, st.get_rect(center=(SW // 2, sy)))
                sy += 25

            t4 = font_tiny.render("Next round starting soon\u2026", True, GRAY)
            screen.blit(t4, t4.get_rect(center=(SW // 2, SH // 2 + 120)))

        elif phase == "game_over":
            t1 = font_big.render("Game Over!", True, PANEL_COLOR)
            screen.blit(t1, t1.get_rect(center=(SW // 2, 120)))

            sorted_p = sorted(players, key=lambda p: p["score"], reverse=True)
            if sorted_p:
                winner = font_big.render(f"\U0001f3c6 {sorted_p[0]['name']} wins!", True, ACCENT)
                screen.blit(winner, winner.get_rect(center=(SW // 2, 200)))

            sy = 270
            for i, p in enumerate(sorted_p):
                medal = ["\U0001f947", "\U0001f948", "\U0001f949"][i] if i < 3 else f"  {i+1}."
                col = ACCENT if p["id"] == my_id else DARK_GRAY
                st = font_med.render(f"{medal} {p['name']}  \u2014  {p['score']} pts", True, col)
                screen.blit(st, st.get_rect(center=(SW // 2, sy)))
                sy += 40

            lobby_btn = pygame.Rect(SW // 2 - 120, 520, 240, 55)
            draw_button(screen, "BACK TO LOBBY", lobby_btn, ACCENT)

        pygame.display.flip()

    # cleanup
    net.disconnect()
    if server_inst:
        server_inst.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
