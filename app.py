from flask import Flask, Response

app = Flask(__name__)

HTML = r"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Prancheta Basquete FIBA</title>
  <style>
    :root { --bg:#0f172a; --panel:#111827; --text:#e5e7eb; --muted:#9ca3af; }
    *{ box-sizing:border-box; }
    body{ margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; background:var(--bg); color:var(--text); }
    header{
      display:flex; flex-wrap:wrap; gap:10px;
      align-items:center; justify-content:space-between;
      padding:12px 16px; background:var(--panel);
      border-bottom:1px solid rgba(255,255,255,.08);
    }
    .title{ font-weight:800; }
    .controls{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; justify-content:flex-end; }
    button, select{
      padding:8px 10px; border-radius:10px;
      border:1px solid rgba(255,255,255,.15);
      background:rgba(255,255,255,.06);
      color:var(--text);
      cursor:pointer;
    }
    button:hover, select:hover{ background:rgba(255,255,255,.10); }
    .wrap{ padding:18px; display:grid; place-items:center; gap:10px; }
    canvas{
      background:#d7b07b; /* madeira */
      border-radius:18px;
      box-shadow:0 12px 40px rgba(0,0,0,.35);
      max-width:100%;
      height:auto;
      touch-action:none;
    }
    .hint{ margin:0; color:var(--muted); text-align:center; max-width:1000px; }
    .pill{
      padding:6px 10px; border-radius:999px;
      border:1px solid rgba(255,255,255,.15);
      background:rgba(255,255,255,.06);
      color:var(--muted); font-size:12px;
    }
  </style>
</head>
<body>
<header>
  <div>
    <div class="title">Prancheta — Basquete (FIBA fiel) + 10 jogadores + bola + setas</div>
    <div class="pill">Mover arrasta peças • Linha/Caneta desenha • Seta cria flecha • Desfazer remove o último desenho</div>
  </div>
  <div class="controls">
    <select id="mode">
      <option value="move">Mover</option>
      <option value="line">Linha</option>
      <option value="arrow">Seta</option>
      <option value="pen">Caneta</option>
    </select>
    <button id="undoBtn">Desfazer</button>
    <button id="clearBtn">Limpar desenhos</button>
    <button id="resetBtn">Reset peças</button>
    <button id="flipBtn">Inverter lados</button>
  </div>
</header>

<main class="wrap">
  <canvas id="board" width="1120" height="640"></canvas>
  <p class="hint">Dica: no modo Seta, clique/arraste/solte pra criar uma flecha (boa pra jogadas).</p>
</main>

<script>
const canvas = document.getElementById("board");
const ctx = canvas.getContext("2d");

const modeSel = document.getElementById("mode");
const undoBtn = document.getElementById("undoBtn");
const clearBtn = document.getElementById("clearBtn");
const resetBtn = document.getElementById("resetBtn");
const flipBtn = document.getElementById("flipBtn");

const W = canvas.width, H = canvas.height;

// Peças
const TEAM_A_COLOR = "#2E86FF";
const TEAM_B_COLOR = "#FF3B3B";
const BALL_COLOR   = "#F5F5F5";
const PLAYER_R = 18;
const BALL_R = 10;

// ====== Medidas FIBA (metros) ======
// Quadra: 28 x 15
// Linha de lance livre: 5.8m da linha de fundo
// Garrafão (retângulo): 4.9m de largura
// Círculo central: raio 1.8m
// Arco de 3: 6.75m do centro da cesta (raio)
// Canto (distância da linha lateral para início do arco): 0.90m (distância da linha lateral até a linha de 3 no canto)
const M = {
  courtL: 28.0,
  courtW: 15.0,
  ftFromBaseline: 5.8,
  keyWidth: 4.9,
  centerCircleR: 1.8,
  threeR: 6.75,
  corner3FromSideline: 0.90,
  hoopFromBaseline: 1.575, // centro da cesta a 1.575m da linha de fundo (FIBA)
  backboardFromBaseline: 1.2, // só pra desenhar marcador
  rimR: 0.225 // aro 45cm diâmetro
};

// Área desenhável no canvas (com padding)
const PAD = 40;
const court = { x: PAD, y: PAD, w: W - PAD*2, h: H - PAD*2 };

// Escala: metros -> pixels
const sX = court.w / M.courtL;
const sY = court.h / M.courtW;
// Usa escala uniforme pra não distorcer círculo/arcos
const s = Math.min(sX, sY);

// Centraliza quadra real dentro do retângulo (caso sX != sY)
const realWpx = M.courtL * s;
const realHpx = M.courtW * s;
const ox = court.x + (court.w - realWpx)/2;
const oy = court.y + (court.h - realHpx)/2;

// Conversões
function mx(m){ return ox + m * s; } // metros no eixo comprimento (0..28) -> x
function my(m){ return oy + m * s; } // metros no eixo largura (0..15) -> y

function clamp(v, min, max){ return Math.max(min, Math.min(max, v)); }
function dist2(ax,ay,bx,by){ const dx=ax-bx, dy=ay-by; return dx*dx+dy*dy; }

// Fundo madeira
function drawWood(){
  ctx.save();
  ctx.fillStyle = "#d7b07b";
  ctx.fillRect(0,0,W,H);

  ctx.globalAlpha = 0.07;
  for(let x=0;x<W;x+=30){
    ctx.fillStyle = (x/30)%2===0 ? "#000" : "#fff";
    ctx.fillRect(x, 0, 15, H);
  }
  ctx.restore();
}

// Desenha quadra FIBA fiel (geometria baseada em metros)
function drawCourtFIBA(){
  ctx.save();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(255,255,255,0.95)";
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  const x0 = mx(0),  x1 = mx(M.courtL);
  const y0 = my(0),  y1 = my(M.courtW);

  // Linhas externas
function drawPerimeter(){
 function drawPerimeter(){
  const x0 = mx(0), x1 = mx(M.courtL);
  const y0 = my(0), y1 = my(M.courtW);

  const left = Math.min(x0, x1);
  const top  = Math.min(y0, y1);
  const w    = Math.abs(x1 - x0);
  const h    = Math.abs(y1 - y0);

  ctx.save();
  ctx.strokeStyle = "rgba(255,255,255,0.98)";
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  ctx.lineWidth = 6;
  ctx.strokeRect(left + 0.5, top + 0.5, w - 1, h - 1);

  ctx.lineWidth = 3;
  ctx.strokeRect(left + 3.5, top + 3.5, w - 7, h - 7);

  ctx.restore();
}
}

  // Linha do meio
  const midX = mx(M.courtL/2);
  ctx.beginPath();
  ctx.moveTo(midX, y0);
  ctx.lineTo(midX, y1);
  ctx.stroke();

  // Círculo central
  ctx.beginPath();
  ctx.arc(midX, my(M.courtW/2), M.centerCircleR * s, 0, Math.PI*2);
  ctx.stroke();

  // Garrafão (retângulo) e lance livre (linha e semicirculo)
  const keyHalf = (M.keyWidth/2) * s;
  const yMid = my(M.courtW/2);
  const ftX_L = mx(M.ftFromBaseline);
  const ftX_R = mx(M.courtL - M.ftFromBaseline);

  // Retângulo garrafão esquerdo (da linha de fundo até FT line)
  ctx.strokeRect(mx(0), yMid - keyHalf, ftX_L - mx(0), keyHalf*2);
  // Linha FT esquerda
  ctx.beginPath();
  ctx.moveTo(ftX_L, yMid - keyHalf);
  ctx.lineTo(ftX_L, yMid + keyHalf);
  ctx.stroke();
  // Semicírculo FT esquerda (fora do garrafão)
  ctx.beginPath();
  ctx.arc(ftX_L, yMid, keyHalf, -Math.PI/2, Math.PI/2);
  ctx.stroke();

  // Retângulo garrafão direito
  ctx.strokeRect(ftX_R, yMid - keyHalf, mx(M.courtL) - ftX_R, keyHalf*2);
  // Linha FT direita
  ctx.beginPath();
  ctx.moveTo(ftX_R, yMid - keyHalf);
  ctx.lineTo(ftX_R, yMid + keyHalf);
  ctx.stroke();
  // Semicírculo FT direita
  ctx.beginPath();
  ctx.arc(ftX_R, yMid, keyHalf, Math.PI/2, -Math.PI/2);
  ctx.stroke();

  // Cestas (centro do aro)
  const hoopLx = mx(M.hoopFromBaseline);
  const hoopRx = mx(M.courtL - M.hoopFromBaseline);
  const hoopY  = yMid;

  // Marca aro (pequeno círculo)
  ctx.fillStyle = "rgba(255,255,255,0.95)";
  ctx.beginPath(); ctx.arc(hoopLx, hoopY, Math.max(3, M.rimR*s*0.35), 0, Math.PI*2); ctx.fill();
  ctx.beginPath(); ctx.arc(hoopRx, hoopY, Math.max(3, M.rimR*s*0.35), 0, Math.PI*2); ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.95)";

  // Linha de 3 pontos (FIBA): arco de raio 6.75m do centro da cesta + linhas retas nos cantos
  const threeR = M.threeR * s;

  // Canto: a linha de 3 no canto fica a 0.90m da linha lateral (sideline).
  // Então y da linha de 3 no canto:
  const cornerTopY = my(M.corner3FromSideline);
  const cornerBotY = my(M.courtW - M.corner3FromSideline);

  // Linhas retas do canto - esquerda (x constante aproximado no ponto onde arco encontraria)
  // Usa vertical em x = hoopLx + sqrt(r^2 - dy^2), com dy = distância até cornerTopY/BottomY.
  function xAtYForArc(cx, cy, r, yval, side){
    const dy = yval - cy;
    const inside = Math.max(0, r*r - dy*dy);
    const dx = Math.sqrt(inside);
    return side === "right" ? (cx + dx) : (cx - dx);
  }

  const xL_top = xAtYForArc(hoopLx, hoopY, threeR, cornerTopY, "right");
  const xL_bot = xAtYForArc(hoopLx, hoopY, threeR, cornerBotY, "right");

  ctx.beginPath();
  ctx.moveTo(mx(0), cornerTopY);
  ctx.lineTo(xL_top, cornerTopY);
  ctx.moveTo(mx(0), cornerBotY);
  ctx.lineTo(xL_bot, cornerBotY);
  ctx.stroke();

  // Arco esquerdo (somente entre os cantos)
  // Angulos calculados pelos pontos de canto
  const angL_top = Math.atan2(cornerTopY - hoopY, xL_top - hoopLx);
  const angL_bot = Math.atan2(cornerBotY - hoopY, xL_bot - hoopLx);
  ctx.beginPath();
  ctx.arc(hoopLx, hoopY, threeR, angL_top, angL_bot);
  ctx.stroke();

  // Direita (simétrico)
  const xR_top = xAtYForArc(hoopRx, hoopY, threeR, cornerTopY, "left");
  const xR_bot = xAtYForArc(hoopRx, hoopY, threeR, cornerBotY, "left");

  ctx.beginPath();
  ctx.moveTo(mx(M.courtL), cornerTopY);
  ctx.lineTo(xR_top, cornerTopY);
  ctx.moveTo(mx(M.courtL), cornerBotY);
  ctx.lineTo(xR_bot, cornerBotY);
  ctx.stroke();

  const angR_top = Math.atan2(cornerTopY - hoopY, xR_top - hoopRx);
  const angR_bot = Math.atan2(cornerBotY - hoopY, xR_bot - hoopRx);
  ctx.beginPath();  
  
  ctx.arc(hoopRx, hoopY, threeR, angR_bot, angR_top);
  ctx.stroke();

  ctx.restore();
}

// Perímetro por cima (duplo) pra nunca “falhar”
function drawPerimeter(){
  // garante que w e h são sempre positivos
  const xA = mx(0), xB = mx(M.courtL);
  const yA = my(0), yB = my(M.courtW);

  const x0 = Math.min(xA, xB);
  const y0 = Math.min(yA, yB);
  const w  = Math.abs(xB - xA);
  const h  = Math.abs(yB - yA);

  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = "rgba(255,255,255,0.98)";

  // Traço externo
  ctx.lineWidth = 6;
  ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, h - 1);

  // Traço interno (acabamento)
  ctx.lineWidth = 3;
  ctx.strokeRect(x0 + 3.5, y0 + 3.5, w - 7, h - 7);

  ctx.restore();
}

// ===== Peças =====
function makeInitialPieces(){
  const midX = mx(M.courtL/2);
  const midY = my(M.courtW/2);

  const ys = [
    midY - 160, midY - 80, midY, midY + 80, midY + 160
  ].map(v => clamp(v, my(0)+60, my(M.courtW)-60));

  const leftX  = mx(6.5);
  const rightX = mx(M.courtL - 6.5);

  const pieces = [];
  for(let i=0;i<5;i++){
    pieces.push({type:"A", x:leftX, y:ys[i], r:PLAYER_R, fill:TEAM_A_COLOR, stroke:"white", label:String(i+1), labelColor:"white"});
  }
  for(let i=0;i<5;i++){
    pieces.push({type:"B", x:rightX, y:ys[i], r:PLAYER_R, fill:TEAM_B_COLOR, stroke:"white", label:String(i+1), labelColor:"white"});
  }
  pieces.push({type:"ball", x:midX, y:midY, r:BALL_R, fill:BALL_COLOR, stroke:"black", label:"", labelColor:""});
  return pieces;
}

let pieces = makeInitialPieces();

// ===== Desenhos =====
// stroke: {type:"line"|"pen"|"arrow", points:[{x,y},...]}
let strokes = [];
let tempStroke = null;
let isDrawing = false;

// Drag
let draggingIndex = -1;
let dragOffX = 0, dragOffY = 0;

// Pointer
function getPointerPos(evt){
  const rect = canvas.getBoundingClientRect();
  const clientX = evt.touches ? evt.touches[0].clientX : evt.clientX;
  const clientY = evt.touches ? evt.touches[0].clientY : evt.clientY;
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return { x:(clientX-rect.left)*scaleX, y:(clientY-rect.top)*scaleY };
}

function pickPiece(px,py){
  for(let i=pieces.length-1;i>=0;i--){
    const p=pieces[i];
    if(dist2(px,py,p.x,p.y) <= p.r*p.r) return i;
  }
  return -1;
}

function drawPiece(p){
  ctx.save();
  ctx.beginPath();
  ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
  ctx.fillStyle=p.fill;
  ctx.fill();
  ctx.lineWidth=2;
  ctx.strokeStyle=p.stroke;
  ctx.stroke();

  if(p.label){
    ctx.fillStyle=p.labelColor;
    ctx.font="bold 12px Arial";
    ctx.textAlign="center";
    ctx.textBaseline="middle";
    ctx.fillText(p.label,p.x,p.y);
  }
  ctx.restore();
}

function drawArrowHead(x1,y1,x2,y2){
  // seta na ponta (x2,y2)
  const ang = Math.atan2(y2-y1, x2-x1);
  const headLen = 14;
  const a1 = ang - Math.PI/7;
  const a2 = ang + Math.PI/7;

  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - headLen*Math.cos(a1), y2 - headLen*Math.sin(a1));
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - headLen*Math.cos(a2), y2 - headLen*Math.sin(a2));
  ctx.stroke();
}

function drawStrokes(){
  ctx.save();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(20,20,20,0.95)";
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  const all = tempStroke ? [...strokes, tempStroke] : strokes;

  for(const s of all){
    const pts = s.points;
    if(!pts || pts.length < 2) continue;

    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for(let i=1;i<pts.length;i++) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.stroke();

    if(s.type === "arrow"){
      const p1 = pts[pts.length-2];
      const p2 = pts[pts.length-1];
      drawArrowHead(p1.x,p1.y,p2.x,p2.y);
    }
  }
  ctx.restore();
}

function drawTopBarText(){
  ctx.save();
  ctx.fillStyle="rgba(0,0,0,0.35)";
  ctx.fillRect(0, 0, W, 34);
  ctx.fillStyle="rgba(255,255,255,0.95)";
  ctx.font="bold 14px Arial";
  ctx.textAlign="center";
  const label = modeSel.value === "move" ? "Mover" :
                modeSel.value === "line" ? "Linha" :
                modeSel.value === "arrow" ? "Seta" : "Caneta";
  ctx.fillText(`Modo: ${label}`, W/2, 22);
  ctx.restore();
}

function render(){
  ctx.clearRect(0,0,W,H);
  drawWood();
  drawCourtFIBA();
  drawStrokes();
  drawPerimeter();
  drawTopBarText();
  for(const p of pieces) drawPiece(p);
}

// ===== Interação =====
function pointerDown(evt){
  evt.preventDefault();
  const mode = modeSel.value;
  const {x,y} = getPointerPos(evt);

  if(mode === "move"){
    const idx = pickPiece(x,y);
    if(idx === -1) return;

    draggingIndex = idx;
    dragOffX = x - pieces[idx].x;
    dragOffY = y - pieces[idx].y;

    const picked = pieces.splice(idx,1)[0];
    pieces.push(picked);
    draggingIndex = pieces.length - 1;

    render();
    return;
  }

  isDrawing = true;
  if(mode === "line"){
    tempStroke = { type:"line", points:[{x,y},{x,y}] };
  } else if(mode === "arrow"){
    tempStroke = { type:"arrow", points:[{x,y},{x,y}] };
  } else { // pen
    tempStroke = { type:"pen", points:[{x,y}] };
  }
  render();
}

function pointerMove(evt){
  if(draggingIndex === -1 && !isDrawing) return;
  evt.preventDefault();

  const mode = modeSel.value;
  const {x,y} = getPointerPos(evt);

  if(mode === "move" && draggingIndex !== -1){
    const p = pieces[draggingIndex];
    p.x = clamp(x - dragOffX, 10, W - 10);
    p.y = clamp(y - dragOffY, 10, H - 10);
    render();
    return;
  }

  if(isDrawing && tempStroke){
    if(tempStroke.type === "line" || tempStroke.type === "arrow"){
      tempStroke.points[1] = {x,y};
    } else {
      tempStroke.points.push({x,y});
    }
    render();
  }
}

function pointerUp(evt){
  if(draggingIndex !== -1){
    evt.preventDefault();
    draggingIndex = -1;
    return;
  }

  if(isDrawing){
    evt.preventDefault();
    isDrawing = false;

    if(tempStroke && tempStroke.points.length >= 2){
      strokes.push(tempStroke);
    }
    tempStroke = null;
    render();
  }
}

// Mouse + Touch
canvas.addEventListener("mousedown", pointerDown);
window.addEventListener("mousemove", pointerMove);
window.addEventListener("mouseup", pointerUp);

canvas.addEventListener("touchstart", pointerDown, {passive:false});
window.addEventListener("touchmove", pointerMove, {passive:false});
window.addEventListener("touchend", pointerUp, {passive:false});

// Botões
undoBtn.addEventListener("click", ()=>{
  strokes.pop();
  render();
});
clearBtn.addEventListener("click", ()=>{
  strokes = [];
  tempStroke = null;
  isDrawing = false;
  render();
});
resetBtn.addEventListener("click", ()=>{
  pieces = makeInitialPieces();
  render();
});
flipBtn.addEventListener("click", ()=>{
  // espelha peças
  pieces.forEach(p => { p.x = W - p.x; });

  // espelha desenhos
  strokes = strokes.map(s => ({
    ...s,
    points: s.points.map(pt => ({ x: W - pt.x, y: pt.y }))
  }));

  render();
});

render();
</script>
</body>
</html>
"""

@app.get("/")
def home():
    return Response(HTML, mimetype="text/html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
