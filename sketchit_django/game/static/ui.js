/**
 * ui.js — Skribbl web client
 *
 * Connects to the Python game server via a WebSocket bridge.
 * The bridge is expected to forward JSON messages exactly as the TCP server
 * sends them, so all message types (join, welcome, new_round, draw_line, …)
 * are identical to those used by the Pygame client.
 *
 * Screens:  menu  →  lobby  →  game  ⟷  round_result (overlay)  →  game_over
 */

"use strict";

// ─── Palette & brush sizes (must match server.py / gio.py) ───────────────────
const PALETTE = [
  "#000000", "#ffffff", "#c8c8c8",
  "#ff0000", "#ff6400", "#ffdc00",
  "#00b400", "#00c8c8", "#0050ff",
  "#8c00ff", "#ff00c8", "#8c5014",
];

const BRUSH_SIZES = [3, 6, 10, 18, 30];

const CHARACTERS = {
  cat:    { icon: "🐱", color: "#f6993f" },
  dog:    { icon: "🐶", color: "#a0855b" },
  panda:  { icon: "🐼", color: "#4a5568" },
  fox:    { icon: "🦊", color: "#e05d44" },
  frog:   { icon: "🐸", color: "#38a169" },
  monkey: { icon: "🐵", color: "#b07d4f" },
};

// ─── Colour utility ───────────────────────────────────────────────────────────
/** Convert "#rrggbb" to [r, g, b] array (used when sending draw messages). */
function hexToArr(hex) {
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
}

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const screens = {
  menu:        document.getElementById("screen-menu"),
  lobby:       document.getElementById("screen-lobby"),
  game:        document.getElementById("screen-game"),
  roundResult: document.getElementById("screen-round-result"),
  gameover:    document.getElementById("screen-gameover"),
};

const menuError       = document.getElementById("menu-error");
const inputName       = document.getElementById("input-name");
const inputIp         = document.getElementById("input-ip");
const inputPort       = document.getElementById("input-port");
const btnHost         = document.getElementById("btn-host");
const btnJoin         = document.getElementById("btn-join");

const lobbyInfo       = document.getElementById("lobby-info");
const lobbyPlayerList = document.getElementById("lobby-player-list");
const btnStartGame    = document.getElementById("btn-start-game");

const roundLabel      = document.getElementById("round-label");
const wordHint        = document.getElementById("word-hint");
const timerBox        = document.getElementById("timer-box");
const panelPlayers    = document.getElementById("panel-players");
const canvasWrap      = document.getElementById("canvas-wrap");
const drawCanvas      = document.getElementById("draw-canvas");
const toolbar         = document.getElementById("toolbar");
const btnClearCanvas  = document.getElementById("btn-clear-canvas");
const chatLog         = document.getElementById("chat-log");
const chatInput       = document.getElementById("chat-input");
const btnSend         = document.getElementById("btn-send");

const resultHeading   = document.getElementById("result-heading");
const resultWord      = document.getElementById("result-word");
const resultReason    = document.getElementById("result-reason");
const resultScores    = document.getElementById("result-scores");

const finalScoreList  = document.getElementById("final-score-list");
const btnPlayAgain    = document.getElementById("btn-play-again");

// ─── Game state ───────────────────────────────────────────────────────────────
let ws            = null;
let myId          = null;
let isHost        = false;
let hostId        = null;    // actual host player ID from the server
let players       = [];      // [{id, name, score}]
let drawerId      = null;
let currentRound  = 0;
let totalRounds   = 6;
let myWord        = "";      // set for the drawer only
let guessedPlayers = new Set();
let selectedChar = "cat";

// Canvas
const ctx = drawCanvas.getContext("2d");
let drawing   = false;
let lastX     = 0;
let lastY     = 0;
let drawColor = "#000000";
let brushSize = 6;
let isDrawer  = false;

// ─── Screen helpers ───────────────────────────────────────────────────────────
function showScreen(name) {
  for (const [key, el] of Object.entries(screens)) {
    el.classList.toggle("active", key === name);
  }
}

function showOverlay(name) {
  screens.roundResult.classList.toggle("active", name === "roundResult");
}

// ─── WebSocket connection ─────────────────────────────────────────────────────
/**
 * Connect to ws://host:wsPort  (default WS port 5556 — the bridge listens there).
 * Falls back to a mock-mode if no server is reachable so the UI can be previewed.
 */
function connect(host, port, playerName) {
  const wsPort = parseInt(port, 10) + 1; // convention: WS bridge = TCP port + 1
  const url    = `ws://${host || "localhost"}:${wsPort}`;

  try {
    ws = new WebSocket(url);
  } catch (e) {
    setError(`Cannot open WebSocket: ${e.message}`);
    return;
  }

  ws.onopen = () => {
    send({ type: "join", name: playerName, character: selectedChar });
  };

  ws.onmessage = (evt) => {
    let msg;
    try { msg = JSON.parse(evt.data); } catch { return; }
    handleMessage(msg);
  };

  ws.onerror = () => {
    setError("Connection error — is the server running?");
  };

  ws.onclose = () => {
    if (screens.game.classList.contains("active") ||
        screens.lobby.classList.contains("active")) {
      setError("Disconnected from server.");
      showScreen("menu");
    }
  };
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}

function disconnect() {
  if (ws) { ws.close(); ws = null; }
}

// ─── Message handler ──────────────────────────────────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {

    case "welcome":
      myId    = msg.id;
      isHost  = msg.is_host;
      hostId  = isHost ? myId : (msg.players?.[0]?.id ?? null);
      players = (msg.players || []).map(p => ({ ...p, character: p.character || "cat" }));
      showScreen("lobby");
      renderLobby();
      break;

    case "you_are_host":
      isHost = true;
      hostId = myId;
      renderLobby();
      break;

    case "player_joined":
      players.push({ id: msg.id, name: msg.name, score: 0, character: msg.character || "cat" });
      appendChat(`${msg.name} joined`, "info");
      renderLobby();
      break;

    case "player_left":
      players = players.filter(p => p.id !== msg.id);
      appendChat(`${msg.name} left`, "info");
      renderLobby();
      break;

    case "new_round":
      currentRound  = msg.round;
      totalRounds   = msg.total_rounds;
      drawerId      = msg.drawer_id;
      isDrawer      = drawerId === myId;
      myWord        = msg.word || "";
      players       = (msg.players || players).map(p => ({ ...p, character: p.character || "cat" }));
      guessedPlayers.clear();
      showOverlay(null);
      showScreen("game");
      startRound(msg);
      break;

    case "draw_line":
      if (!isDrawer) remoteDrawLine(msg);
      break;

    case "draw_dot":
      if (!isDrawer) remoteDrawDot(msg);
      break;

    case "clear_canvas":
      clearCanvas();
      break;

    case "hint":
      updateHint(msg.hint);
      break;

    case "timer":
      updateTimer(msg.time_left);
      break;

    case "correct_guess": {
      const pName = msg.player_name;
      appendChat(`✓ ${pName} guessed correctly!`, "correct");
      guessedPlayers.add(msg.player_id);
      applyScores(msg.scores);
      renderScorePanel();
      if (msg.player_id === myId && !isDrawer) {
        chatInput.disabled = true;
        chatInput.placeholder = "You guessed it! 🎉";
      }
      break;
    }

    case "wrong_guess":
      if (msg.player_id === myId) {
        appendChat(`✗ ${msg.text}`, "wrong");
      } else {
        appendChat(`✗ ${msg.player_name}: ${msg.text}`, "wrong");
      }
      break;

    case "round_over":
      applyScores(msg.scores);
      showRoundResult(msg);
      break;

    case "game_over":
      applyScores(msg.scores);
      showOverlay(null);
      showGameOver();
      break;

    case "back_to_lobby":
      appendChat(msg.reason || "Back to lobby", "info");
      showScreen("lobby");
      renderLobby();
      break;

    default:
      break;
  }
}

// ─── Lobby rendering ──────────────────────────────────────────────────────────
function renderLobby() {
  lobbyPlayerList.innerHTML = "";
  for (const p of players) {
    const div = document.createElement("div");
    div.className = "lobby-player";
    const ch = CHARACTERS[p.character] || CHARACTERS.cat;
    div.innerHTML = `
      <div class="player-avatar" style="background:${ch.color}">${ch.icon}</div>
      <span class="lobby-player-name">${escHtml(p.name)}</span>
      ${p.id === hostId ? '<span class="host-badge">HOST</span>' : ""}
    `;
    lobbyPlayerList.appendChild(div);
  }
  const countEl = document.getElementById("lobby-player-count");
  if (countEl) countEl.textContent = `${players.length} player${players.length !== 1 ? "s" : ""} in lobby`;
  btnStartGame.style.display = isHost ? "block" : "none";
}

// ─── Game round setup ─────────────────────────────────────────────────────────
function startRound(msg) {
  roundLabel.textContent = `Round ${msg.round} / ${msg.total_rounds}`;
  updateHint(msg.hint || "");
  updateTimer(msg.time || 60);

  clearCanvas();
  chatLog.innerHTML = "";
  chatInput.disabled = false;
  chatInput.placeholder = isDrawer ? "You are drawing!" : "Guess the word…";

  if (isDrawer) {
    appendChat(`✏️ Your word: ${myWord.toUpperCase()}`, "correct");
  } else {
    appendChat(`🖊 ${msg.drawer_name} is drawing!`, "info");
  }

  renderScorePanel();
  resizeCanvas();

  toolbar.style.display = isDrawer ? "flex" : "none";
  canvasWrap.style.cursor = isDrawer ? "crosshair" : "default";
}

function updateHint(hint) {
  wordHint.textContent = hint || "";
}

function updateTimer(t) {
  timerBox.textContent = t;
  timerBox.classList.toggle("urgent", t <= 15);
}

// ─── Score panel ──────────────────────────────────────────────────────────────
function renderScorePanel() {
  panelPlayers.innerHTML = "";
  const sorted = [...players].sort((a, b) => b.score - a.score);
  for (const p of sorted) {
    const div = document.createElement("div");
    div.className = "score-player";
    if (p.id === drawerId)   div.classList.add("drawing");
    if (guessedPlayers.has(p.id)) div.classList.add("guessed");
    const ch = CHARACTERS[p.character] || CHARACTERS.cat;
    div.innerHTML = `
      <div class="player-avatar" style="background:${ch.color}">${ch.icon}</div>
      <span>${escHtml(p.name)}</span>
      <span class="score-val">${p.score}</span>
    `;
    panelPlayers.appendChild(div);
  }
}

function applyScores(scoresDict) {
  if (!scoresDict) return;
  for (const p of players) {
    const sd = scoresDict[String(p.id)];
    if (sd) p.score = sd.score;
  }
}

// ─── Round result overlay ─────────────────────────────────────────────────────
const REASON_LABELS = {
  timeout:     "⏱ Time ran out",
  all_guessed: "🎉 Everyone guessed it!",
  drawer_left: "🚪 The drawer disconnected",
};

function showRoundResult(msg) {
  resultHeading.textContent = `Round ${msg.round} / ${msg.total_rounds}`;
  resultWord.textContent    = msg.word;
  resultReason.textContent  = REASON_LABELS[msg.reason] || msg.reason;

  resultScores.innerHTML = "";
  const sorted = [...players].sort((a, b) => b.score - a.score);
  for (const p of sorted) {
    const row = document.createElement("div");
    row.className = "result-score-row";
    row.innerHTML = `<span>${escHtml(p.name)}</span><span class="result-score-val">${p.score}</span>`;
    resultScores.appendChild(row);
  }

  showOverlay("roundResult");
}

// ─── Game over screen ─────────────────────────────────────────────────────────
function showGameOver() {
  finalScoreList.innerHTML = "";
  const sorted = [...players].sort((a, b) => b.score - a.score);
  const rankClass = ["gold", "silver", "bronze"];
  sorted.forEach((p, i) => {
    const row = document.createElement("div");
    row.className = "final-score-row";
    const rc = rankClass[i] || "";
    const ch = CHARACTERS[p.character] || CHARACTERS.cat;
    row.innerHTML = `
      <span class="final-rank ${rc}">${i + 1}</span>
      <div class="player-avatar" style="background:${ch.color};width:28px;height:28px;font-size:.95rem">
        ${ch.icon}
      </div>
      <span>${escHtml(p.name)}</span>
      <span class="final-score-pts">${p.score}</span>
    `;
    finalScoreList.appendChild(row);
  });
  showScreen("gameover");
}

// ─── Chat log ─────────────────────────────────────────────────────────────────
function appendChat(text, cls = "") {
  const div = document.createElement("div");
  div.className = `chat-msg ${cls}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

// ─── Canvas drawing ───────────────────────────────────────────────────────────
function resizeCanvas() {
  const rect = canvasWrap.getBoundingClientRect();
  drawCanvas.width  = rect.width  || canvasWrap.offsetWidth;
  drawCanvas.height = rect.height || canvasWrap.offsetHeight;
  drawCanvas.style.width  = drawCanvas.width  + "px";
  drawCanvas.style.height = drawCanvas.height + "px";
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, drawCanvas.width, drawCanvas.height);
}

function clearCanvas() {
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, drawCanvas.width, drawCanvas.height);
}

function normX(x) { return x / drawCanvas.width;  }
function normY(y) { return y / drawCanvas.height; }
function denormX(nx) { return Math.round(nx * drawCanvas.width);  }
function denormY(ny) { return Math.round(ny * drawCanvas.height); }

function localDraw(x1, y1, x2, y2) {
  ctx.strokeStyle = drawColor;
  ctx.lineWidth   = brushSize;
  ctx.lineCap     = "round";
  ctx.lineJoin    = "round";
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x2, y2, brushSize / 2, 0, Math.PI * 2);
  ctx.fillStyle = drawColor;
  ctx.fill();
}

function remoteDrawLine(msg) {
  const x1 = denormX(msg.x1), y1 = denormY(msg.y1);
  const x2 = denormX(msg.x2), y2 = denormY(msg.y2);
  const color = `rgb(${msg.color[0]},${msg.color[1]},${msg.color[2]})`;
  ctx.strokeStyle = color;
  ctx.lineWidth   = msg.size;
  ctx.lineCap     = "round";
  ctx.lineJoin    = "round";
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x2, y2, msg.size / 2, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

function remoteDrawDot(msg) {
  const x = denormX(msg.x), y = denormY(msg.y);
  const color = `rgb(${msg.color[0]},${msg.color[1]},${msg.color[2]})`;
  ctx.beginPath();
  ctx.arc(x, y, msg.size / 2, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

// Canvas pointer events (drawer only)
function canvasPos(e) {
  const rect = drawCanvas.getBoundingClientRect();
  const src  = e.touches ? e.touches[0] : e;
  return {
    x: src.clientX - rect.left,
    y: src.clientY - rect.top,
  };
}

drawCanvas.addEventListener("mousedown",  onPointerDown);
drawCanvas.addEventListener("mousemove",  onPointerMove);
drawCanvas.addEventListener("mouseup",    onPointerUp);
drawCanvas.addEventListener("mouseleave", onPointerUp);
drawCanvas.addEventListener("touchstart", (e) => { e.preventDefault(); onPointerDown(e); }, { passive: false });
drawCanvas.addEventListener("touchmove",  (e) => { e.preventDefault(); onPointerMove(e); }, { passive: false });
drawCanvas.addEventListener("touchend",   onPointerUp);

function onPointerDown(e) {
  if (!isDrawer) return;
  drawing = true;
  const { x, y } = canvasPos(e);
  lastX = x; lastY = y;
  // draw a dot
  ctx.beginPath();
  ctx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
  ctx.fillStyle = drawColor;
  ctx.fill();
  send({ type: "draw_dot", x: normX(x), y: normY(y), color: hexToArr(drawColor), size: brushSize });
}

function onPointerMove(e) {
  if (!isDrawer || !drawing) return;
  const { x, y } = canvasPos(e);
  localDraw(lastX, lastY, x, y);
  send({
    type: "draw_line",
    x1: normX(lastX), y1: normY(lastY),
    x2: normX(x),     y2: normY(y),
    color: hexToArr(drawColor),
    size: brushSize,
  });
  lastX = x; lastY = y;
}

function onPointerUp() {
  drawing = false;
}

window.addEventListener("resize", () => {
  if (screens.game.classList.contains("active")) {
    resizeCanvas();
  }
});

// ─── Toolbar setup ────────────────────────────────────────────────────────────
function buildToolbar() {
  // colour swatches
  for (const hex of PALETTE) {
    const sw = document.createElement("div");
    sw.className = "color-swatch";
    sw.style.background = hex;
    if (hex === drawColor) sw.classList.add("selected");
    sw.title = hex;
    sw.addEventListener("click", () => {
      drawColor = hex;
      document.querySelectorAll(".color-swatch").forEach(s => s.classList.remove("selected"));
      sw.classList.add("selected");
    });
    toolbar.insertBefore(sw, toolbar.querySelector(".toolbar-sep"));
  }

  // size buttons
  const sep = toolbar.querySelector(".toolbar-sep");
  for (const sz of BRUSH_SIZES) {
    const btn = document.createElement("button");
    btn.className = "size-btn" + (sz === brushSize ? " selected" : "");
    btn.title = `Size ${sz}`;
    const dot = document.createElement("div");
    dot.className = "size-dot";
    dot.style.width  = Math.min(sz, 22) + "px";
    dot.style.height = Math.min(sz, 22) + "px";
    btn.style.width  = "30px";
    btn.style.height = "30px";
    btn.appendChild(dot);
    btn.addEventListener("click", () => {
      brushSize = sz;
      document.querySelectorAll(".size-btn").forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
    });
    sep.after(btn);
  }
}

btnClearCanvas.addEventListener("click", () => {
  if (!isDrawer) return;
  clearCanvas();
  send({ type: "clear_canvas" });
});

// ─── Chat / guess ─────────────────────────────────────────────────────────────
function sendGuess() {
  const text = chatInput.value.trim();
  if (!text) return;
  if (isDrawer) {
    // drawers can't guess, just clear input
    chatInput.value = "";
    return;
  }
  send({ type: "guess", text });
  chatInput.value = "";
}

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendGuess();
});
btnSend.addEventListener("click", sendGuess);

// ─── Menu buttons ─────────────────────────────────────────────────────────────
function setError(msg) {
  menuError.textContent = msg;
}

const joinFields = document.getElementById("join-fields");
const btnConnect = document.getElementById("btn-connect");

// Restore saved settings from localStorage
(function loadSaved() {
  const saved = localStorage.getItem("skribbl_settings");
  if (saved) {
    try {
      const s = JSON.parse(saved);
      if (s.name) inputName.value = s.name;
      if (s.ip)   inputIp.value = s.ip;
      if (s.port) inputPort.value = s.port;
    } catch {}
  }
})();

function saveSettings(name, ip, port) {
  localStorage.setItem("skribbl_settings", JSON.stringify({ name, ip, port }));
}

function validateName() {
  const name = inputName.value.trim();
  if (!name) { setError("Please enter your name."); return null; }
  setError("");
  return name;
}

btnHost.addEventListener("click", () => {
  const name = validateName();
  if (!name) return;
  joinFields.classList.remove("visible");
  saveSettings(name, "", "5555");
  lobbyInfo.textContent = "Hosting on localhost:5555  (share your IP with friends)";
  connect("localhost", "5555", name);
});

btnJoin.addEventListener("click", () => {
  joinFields.classList.toggle("visible");
});

btnConnect.addEventListener("click", () => {
  const name = validateName();
  if (!name) return;
  const ip   = inputIp.value.trim();
  const port = inputPort.value.trim() || "5555";
  if (!ip) { setError("Please enter the server IP."); return; }
  if (isNaN(parseInt(port, 10))) { setError("Port must be a number."); return; }
  setError("");
  saveSettings(name, ip, port);
  lobbyInfo.textContent = `Connecting to ${ip}:${port}…`;
  connect(ip, port, name);
});

// Quick play — host + auto start
document.getElementById("btn-play").addEventListener("click", () => {
  const name = validateName();
  if (!name) return;
  joinFields.classList.remove("visible");
  saveSettings(name, "", "5555");
  lobbyInfo.textContent = "Hosting on localhost:5555";
  connect("localhost", "5555", name);
  // Auto-start once connected
  const origHandler = handleMessage;
  handleMessage = function(msg) {
    origHandler(msg);
    if (msg.type === "welcome") {
      handleMessage = origHandler;
      setTimeout(() => send({ type: "start_game" }), 300);
    }
  };
});

// Start game (host only)
btnStartGame.addEventListener("click", () => {
  send({ type: "start_game" });
});

// Play again
btnPlayAgain.addEventListener("click", () => {
  disconnect();
  players = [];
  myId    = null;
  isHost  = false;
  hostId  = null;
  showScreen("menu");
});

// ─── Helpers ─────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Deterministic avatar colour based on player id */
function avatarColor(id) {
  const COLORS = ["#508cff","#48bb78","#f0b429","#fc8181","#9f7aea","#ed64a6","#38b2ac","#ed8936"];
  return COLORS[((id || 0) - 1) % COLORS.length];
}
// ─── Character selection ──────────────────────────────────────────────────────
document.querySelectorAll(".char-card").forEach(card => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".char-card").forEach(c => c.classList.remove("selected"));
    card.classList.add("selected");
    selectedChar = card.dataset.char;
  });
});
// ─── Init ─────────────────────────────────────────────────────────────────────
(function init() {
  buildToolbar();
  showScreen("menu");
  resizeCanvas();
})();
