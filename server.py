"""Skribbl multiplayer game server.

Run standalone:  python server.py
Or started automatically when a player clicks HOST GAME in the client.
"""

import socket
import threading
import json
import random
import time

WORDS = [
    "cat", "dog", "house", "tree", "sun", "moon", "car", "fish",
    "bird", "flower", "star", "heart", "boat", "plane", "apple",
    "banana", "pizza", "guitar", "camera", "clock", "umbrella",
    "rainbow", "mountain", "beach", "robot", "rocket", "dragon",
    "castle", "butterfly", "snowman", "bicycle", "bridge", "diamond",
    "elephant", "fire", "ghost", "hat", "ice cream", "jungle",
    "key", "lamp", "mushroom", "ocean", "penguin", "queen",
    "snake", "tornado", "volcano", "waterfall", "zebra", "sword",
    "crown", "skull", "cactus", "donut", "egg", "frog", "grapes",
    "helicopter", "island", "jellyfish", "kite", "lion", "mermaid",
    "ninja", "octopus", "pirate", "rose", "spider", "treasure",
    "unicorn", "wizard", "angel", "bomb", "candle", "dice",
]

DEFAULT_PORT = 5555
ROUND_TIME = 60
TOTAL_ROUNDS = 6


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class GameServer:
    def __init__(self, host="0.0.0.0", port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(8)

        self.lock = threading.Lock()
        self.players = {}          # id -> {socket, name, score}
        self.next_id = 1
        self.host_id = None
        self.phase = "lobby"       # lobby | playing
        self.current_round = 0
        self.drawer_id = None
        self.drawer_order = []
        self.word = ""
        self.hint = ""
        self.hints_given = 0
        self.round_start = 0
        self.time_left = ROUND_TIME
        self.guessed_players = set()
        self.running = True

    # ── networking helpers ──

    def _send(self, sock, msg):
        try:
            sock.sendall((json.dumps(msg) + "\n").encode())
        except Exception:
            pass

    def _broadcast(self, msg, exclude=None):
        """Send to all players. Must hold self.lock."""
        for pid, p in list(self.players.items()):
            if pid != exclude:
                self._send(p["socket"], msg)

    def _player_list(self):
        return [
            {"id": pid, "name": p["name"], "score": p["score"]}
            for pid, p in self.players.items()
        ]

    def _scores_dict(self):
        return {
            str(pid): {"name": p["name"], "score": p["score"]}
            for pid, p in self.players.items()
        }

    # ── hint ──

    def _build_hint(self):
        chars = list(self.word)
        hidden = list(self.hint.replace(" ", ""))
        unrevealed = [i for i, c in enumerate(chars) if c != " " and hidden[i] == "_"]
        if unrevealed:
            idx = random.choice(unrevealed)
            hidden[idx] = chars[idx]
            self.hints_given += 1
        self.hint = " ".join(hidden)

    # ── connection handling ──

    def run(self):
        print(f"Server listening on {self.host}:{self.port}")
        self.sock.settimeout(1.0)
        while self.running:
            try:
                client, addr = self.sock.accept()
                t = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break
        try:
            self.sock.close()
        except Exception:
            pass

    def stop(self):
        self.running = False

    def _handle_client(self, client_socket):
        buf = ""
        pid = None
        try:
            client_socket.settimeout(1.0)
            while self.running:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    buf += data.decode()
                except socket.timeout:
                    continue
                except Exception:
                    break
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if msg.get("type") == "join" and pid is None:
                        pid = self._add_player(client_socket, msg.get("name", "Player"))
                    elif pid is not None:
                        self._process(pid, msg)
        except Exception:
            pass
        finally:
            if pid is not None:
                self._remove_player(pid)
            try:
                client_socket.close()
            except Exception:
                pass

    # ── player management ──

    def _add_player(self, sock, name):
        with self.lock:
            pid = self.next_id
            self.next_id += 1
            self.players[pid] = {"socket": sock, "name": name, "score": 0}
            if self.host_id is None:
                self.host_id = pid

            self._send(sock, {
                "type": "welcome",
                "id": pid,
                "is_host": pid == self.host_id,
                "players": self._player_list(),
                "phase": self.phase,
            })
            self._broadcast({"type": "player_joined", "id": pid, "name": name}, exclude=pid)
            print(f"+ {name} (id={pid})")
            return pid

    def _remove_player(self, pid):
        with self.lock:
            if pid not in self.players:
                return
            name = self.players[pid]["name"]
            del self.players[pid]
            print(f"- {name} (id={pid})")

            if pid == self.host_id and self.players:
                self.host_id = next(iter(self.players))
                self._send(self.players[self.host_id]["socket"], {"type": "you_are_host"})

            self._broadcast({"type": "player_left", "id": pid, "name": name})

            if self.phase == "playing" and pid == self.drawer_id:
                self._end_round("drawer_left")

            if self.phase == "playing" and len(self.players) < 1:
                self.phase = "lobby"
                self.current_round = 0
                self._broadcast({"type": "back_to_lobby", "reason": "Not enough players"})

    # ── message processing ──

    def _process(self, pid, msg):
        t = msg.get("type", "")

        if t == "start_game":
            with self.lock:
                if pid != self.host_id or len(self.players) < 1 or self.phase != "lobby":
                    return
                self.phase = "playing"
                self.current_round = 0
                for p in self.players.values():
                    p["score"] = 0
                self.drawer_order = list(self.players.keys())
                random.shuffle(self.drawer_order)
                self._start_next_round()

        elif t in ("draw_line", "draw_dot", "clear_canvas"):
            with self.lock:
                if self.phase == "playing" and pid == self.drawer_id:
                    self._broadcast(msg, exclude=pid)

        elif t == "guess":
            with self.lock:
                if self.phase != "playing" or pid == self.drawer_id or pid in self.guessed_players:
                    return
                text = msg.get("text", "").strip()
                if not text:
                    return
                # Prevent the guess text from containing the actual word
                # (only check exact match for scoring)
                if text.lower() == self.word.lower():
                    self.guessed_players.add(pid)
                    bonus = max(10, int(self.time_left * 2))
                    self.players[pid]["score"] += bonus
                    if self.drawer_id in self.players:
                        self.players[self.drawer_id]["score"] += max(5, int(self.time_left))
                    self._broadcast({
                        "type": "correct_guess",
                        "player_id": pid,
                        "player_name": self.players[pid]["name"],
                        "scores": self._scores_dict(),
                    })
                    guessers = [p for p in self.players if p != self.drawer_id]
                    if all(g in self.guessed_players for g in guessers):
                        self._end_round("all_guessed")
                else:
                    self._broadcast({
                        "type": "wrong_guess",
                        "player_id": pid,
                        "player_name": self.players[pid]["name"],
                        "text": text,
                    })

    # ── round lifecycle ──

    def _start_next_round(self):
        """Must hold self.lock."""
        self.current_round += 1
        if self.current_round > TOTAL_ROUNDS:
            self._end_game()
            return

        # pick drawer
        self.drawer_order = [p for p in self.drawer_order if p in self.players]
        if not self.drawer_order:
            self.drawer_order = list(self.players.keys())
            random.shuffle(self.drawer_order)
        self.drawer_id = self.drawer_order[(self.current_round - 1) % len(self.drawer_order)]
        if self.drawer_id not in self.players:
            self.drawer_id = next(iter(self.players))

        self.word = random.choice(WORDS)
        self.hint = "_ " * len(self.word.replace(" ", ""))
        self.hints_given = 0
        self.guessed_players = set()
        self.round_start = time.time()
        self.time_left = ROUND_TIME

        drawer_name = self.players[self.drawer_id]["name"]

        # tell the drawer (includes word)
        self._send(self.players[self.drawer_id]["socket"], {
            "type": "new_round",
            "round": self.current_round,
            "total_rounds": TOTAL_ROUNDS,
            "drawer_id": self.drawer_id,
            "drawer_name": drawer_name,
            "word": self.word,
            "hint": self.hint,
            "time": ROUND_TIME,
            "players": self._player_list(),
        })
        # tell guessers (no word)
        for pid in self.players:
            if pid != self.drawer_id:
                self._send(self.players[pid]["socket"], {
                    "type": "new_round",
                    "round": self.current_round,
                    "total_rounds": TOTAL_ROUNDS,
                    "drawer_id": self.drawer_id,
                    "drawer_name": drawer_name,
                    "hint": self.hint,
                    "time": ROUND_TIME,
                    "players": self._player_list(),
                })

        # start timer
        threading.Thread(target=self._round_timer, args=(self.current_round,), daemon=True).start()

    def _round_timer(self, round_num):
        while True:
            time.sleep(1)
            with self.lock:
                if not self.running or self.phase != "playing" or self.current_round != round_num:
                    return
                self.time_left = max(0, ROUND_TIME - (time.time() - self.round_start))
                self._broadcast({"type": "timer", "time_left": int(self.time_left)})
                if self.time_left < ROUND_TIME * 0.5 and self.hints_given == 0:
                    self._build_hint()
                    self._broadcast({"type": "hint", "hint": self.hint})
                if self.time_left < ROUND_TIME * 0.25 and self.hints_given <= 1:
                    self._build_hint()
                    self._broadcast({"type": "hint", "hint": self.hint})
                if self.time_left <= 0:
                    self._end_round("timeout")
                    return

    def _end_round(self, reason):
        """Must hold self.lock."""
        self._broadcast({
            "type": "round_over",
            "word": self.word,
            "reason": reason,
            "round": self.current_round,
            "total_rounds": TOTAL_ROUNDS,
            "scores": self._scores_dict(),
        })
        round_num = self.current_round
        threading.Timer(4.0, self._after_round_delay, args=[round_num]).start()

    def _after_round_delay(self, expected_round):
        with self.lock:
            if self.phase != "playing" or self.current_round != expected_round:
                return
            if len(self.players) < 1:
                self.phase = "lobby"
                self._broadcast({"type": "back_to_lobby", "reason": "Not enough players"})
                return
            self._start_next_round()

    def _end_game(self):
        """Must hold self.lock."""
        self.phase = "lobby"
        self.current_round = 0
        self._broadcast({"type": "game_over", "scores": self._scores_dict()})


if __name__ == "__main__":
    ip = get_local_ip()
    print(f"Your local IP: {ip}")
    srv = GameServer()
    try:
        srv.run()
    except KeyboardInterrupt:
        srv.stop()
        print("\nServer stopped.")
