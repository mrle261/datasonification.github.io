"""
Protein Synth 2.0 — Bradley Lab
Streamlit app with real-time audio via Tone.js

Features:
  - Paste or upload FASTA (multiple sequences supported)
  - Batch mutations via standard notation (e.g. L11K, V3A, G7R)
  - Compare unlimited sequences vs WT — mutations play as dissonant piano key offset
  - Vibraphone / Piano (Salamander samples) / Harp voices per chemical group

Run with: streamlit run protein_synth_app.py
"""

import streamlit as st
import re
import json

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Protein Synth 2.0 · Bradley Lab",
    page_icon="🧬",
    layout="wide",
)

# ── Amino acid map — hydrophobicity-based ────────────────────────────────────
# Group 1  Hydrophobic   → Vibraphone  (sky blue)
# Group 2  Polar         → Piano       (green)
# Group 3  Pos. charged  → Harp warm   (amber)
# Group 4  Neg. charged  → Harp bright (red)
AMINO_MAP = {
    'A': {'s': 1, 'n': 'C'}, 'V': {'s': 1, 'n': 'D'}, 'I': {'s': 1, 'n': 'E'},
    'L': {'s': 1, 'n': 'F'}, 'M': {'s': 1, 'n': 'G'}, 'F': {'s': 1, 'n': 'A'},
    'W': {'s': 1, 'n': 'B'}, 'P': {'s': 1, 'n': 'C'}, 'C': {'s': 1, 'n': 'D'},
    'G': {'s': 2, 'n': 'E'}, 'S': {'s': 2, 'n': 'F'}, 'T': {'s': 2, 'n': 'G'},
    'Y': {'s': 2, 'n': 'A'}, 'H': {'s': 2, 'n': 'B'}, 'Q': {'s': 2, 'n': 'C'},
    'N': {'s': 2, 'n': 'D'},
    'K': {'s': 3, 'n': 'E'}, 'R': {'s': 3, 'n': 'G'},
    'D': {'s': 4, 'n': 'F'}, 'E': {'s': 4, 'n': 'A'},
}

# ── Pure Python helpers ───────────────────────────────────────────────────────

def clean_sequence(raw: str) -> str:
    lines = raw.strip().splitlines()
    seq_lines = [l for l in lines if not l.startswith(">")]
    return re.sub(r"[^A-Z]", "", "".join(seq_lines).upper())


def validate_sequence(seq: str) -> tuple:
    valid, unknown = "", []
    for ch in seq:
        if ch in AMINO_MAP:
            valid += ch
        else:
            unknown.append(ch)
    return valid, list(set(unknown))


def parse_fasta(text: str) -> dict:
    """Parse FASTA into {name: sequence}. Falls back to single unnamed seq."""
    sequences = {}
    current_name, current_seq = None, []

    for line in text.strip().splitlines():
        line = line.strip()
        if line.startswith(">"):
            if current_name is not None:
                seq, _ = validate_sequence(clean_sequence("\n".join(current_seq)))
                if seq:
                    sequences[current_name] = seq
            current_name = line[1:].split()[0] or f"Seq{len(sequences)+1}"
            current_seq = []
        else:
            current_seq.append(line)

    if current_name is not None and current_seq:
        seq, _ = validate_sequence(clean_sequence("\n".join(current_seq)))
        if seq:
            sequences[current_name] = seq

    if not sequences:
        seq, _ = validate_sequence(clean_sequence(text))
        if seq:
            sequences["Sequence"] = seq

    return sequences


def apply_single_mutation(seq: str, pos: int, new_aa: str) -> str:
    if 1 <= pos <= len(seq) and new_aa in AMINO_MAP:
        return seq[: pos - 1] + new_aa + seq[pos:]
    return seq


def apply_global_swap(seq: str, target: str, replacement: str) -> str:
    if target in AMINO_MAP and replacement in AMINO_MAP:
        return seq.replace(target, replacement)
    return seq


def parse_batch_mutations(text: str) -> list:
    """
    Parse standard mutation notation: 'L11K, V3A, G7R'
    Returns list of (1-indexed position, new_aa) tuples.
    """
    mutations = []
    tokens = [t.strip() for t in re.split(r"[,;\s]+", text.strip()) if t.strip()]
    for token in tokens:
        m = re.fullmatch(r"([A-Za-z])(\d+)([A-Za-z])", token)
        if not m:
            raise ValueError(f"Cannot parse '{token}' — expected format like L11K")
        new = m.group(3).upper()
        if new not in AMINO_MAP:
            raise ValueError(f"'{new}' is not a valid amino acid code")
        mutations.append((int(m.group(2)), new))
    return mutations


def apply_batch_mutations(seq: str, mutations: list) -> str:
    result = list(seq)
    for pos, new_aa in mutations:
        if 1 <= pos <= len(result):
            result[pos - 1] = new_aa
    return "".join(result)


def count_mutations(wt: str, mut: str) -> int:
    return sum(a != b for a, b in zip(wt, mut))


# ── HTML / Tone.js audio component ───────────────────────────────────────────

def build_audio_component(sequences: dict, wt_name: str, bpm: int) -> str:
    wt_seq    = sequences[wt_name]
    amino_json = json.dumps({k: {"s": v["s"], "n": v["n"]} for k, v in AMINO_MAP.items()})

    seqs_js      = "{\n" + "".join(
        f"  {json.dumps(n)}: {json.dumps(list(s))},\n" for n, s in sequences.items()
    ) + "}"
    seq_names_js = json.dumps(list(sequences.keys()))
    wt_name_js   = json.dumps(wt_name)

    options_html = "\n".join(
        f'    <option value="{n}">{n}{"  [WT]" if n == wt_name else ""}</option>'
        for n in sequences
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/tone/14.8.49/Tone.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@600;800&display=swap');
  :root {{
    --bg:#080d14; --card:#0f1923; --line:#1e2d3d;
    --s1:#38bdf8; --s2:#4ade80; --s3:#fbbf24; --s4:#f87171;
    --text:#e2e8f0; --dim:#64748b;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Space Mono',monospace; background:var(--bg); color:var(--text); padding:14px; font-size:12px; }}

  .controls {{
    display:flex; flex-wrap:wrap; gap:8px; align-items:center;
    padding:12px 14px; background:var(--card); border:1px solid var(--line);
    border-radius:10px; margin-bottom:14px;
  }}
  button {{
    font-family:'Space Mono',monospace; font-size:11px; font-weight:700;
    padding:7px 14px; border:none; border-radius:6px; cursor:pointer;
    transition:opacity .15s,transform .1s;
  }}
  button:hover {{ opacity:.85; transform:translateY(-1px); }}
  .btn-init  {{ background:#e11d48; color:#fff; }}
  .btn-init.ready {{ background:#059669; color:#fff; }}
  .btn-play  {{ background:#3b82f6; color:#fff; }}
  .btn-stop  {{ background:#475569; color:#fff; }}
  .btn-beep  {{ background:#1e293b; color:var(--s1); border:1px solid var(--s1); }}
  label {{ color:var(--dim); font-size:10px; }}
  input[type=range] {{ cursor:pointer; width:100px; }}
  .val {{ font-weight:700; min-width:28px; }}
  select {{
    font-family:'Space Mono',monospace; font-size:11px; background:var(--card);
    color:var(--text); border:1px solid var(--line); border-radius:6px; padding:6px 10px; cursor:pointer;
  }}
  #status {{ color:var(--s2); font-size:11px; font-weight:700; margin-left:auto; }}

  .grids-outer {{ display:flex; flex-direction:column; gap:12px; }}
  .seq-panel {{
    background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px;
    transition: border-color .2s, box-shadow .2s;
  }}
  .seq-panel.is-playing {{ border-color:#3b82f6; box-shadow:0 0 0 1px #3b82f688; }}
  .panel-title {{
    font-family:'Syne',sans-serif; font-size:13px; font-weight:800;
    letter-spacing:.07em; text-transform:uppercase;
    display:flex; align-items:center; gap:8px; margin-bottom:10px;
  }}
  .badge {{
    font-family:'Space Mono',monospace; font-size:10px; font-weight:400;
    background:var(--line); padding:2px 8px; border-radius:99px; color:var(--dim);
  }}
  .wt-badge  {{ background:#0a1f0a; color:#4ade80; border:1px solid #22c55e44; }}
  .mut-badge {{ background:#1e0a3c; color:#a78bfa; border:1px solid #7c3aed44; }}

  .grid {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .tile {{
    width:30px; height:30px; border-radius:4px;
    display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:10px; color:#0f172a;
    transition:transform .1s,box-shadow .1s; position:relative; cursor:default;
  }}
  .s1 {{ background:var(--s1); }} .s2 {{ background:var(--s2); }}
  .s3 {{ background:var(--s3); }} .s4 {{ background:var(--s4); }}
  .tile.mutated {{ outline:2px solid #a78bfa; outline-offset:1px; }}
  .tile.active  {{ transform:scale(1.25); box-shadow:0 0 12px 4px rgba(255,255,255,.55); z-index:10; }}
  .tile[title]:hover::after {{
    content:attr(title); position:absolute; bottom:110%; left:50%;
    transform:translateX(-50%); background:#1e293b; color:white;
    padding:2px 6px; border-radius:4px; font-size:10px; white-space:nowrap;
    pointer-events:none; z-index:20;
  }}
  .diff-bar {{
    margin-top:8px; padding:8px 12px; background:#1e0a3c;
    border:1px solid #7c3aed44; border-radius:6px;
    font-size:10px; color:#c4b5fd; line-height:1.8; word-break:break-all;
  }}

  .legend {{
    display:flex; gap:12px; flex-wrap:wrap;
    margin-top:14px; padding-top:12px; border-top:1px solid var(--line);
  }}
  .legend-item {{ display:flex; align-items:center; gap:5px; font-size:10px; color:var(--dim); }}
  .legend-dot {{ width:10px; height:10px; border-radius:2px; }}
</style>
</head>
<body>

<div class="controls">
  <button class="btn-init" id="initBtn" onclick="initAudio()">▶ ENABLE AUDIO</button>
  <button class="btn-beep" id="beepBtn" onclick="testBeep()" disabled>♪ TEST</button>

  <label>BPM</label>
  <input type="range" id="bpmSlider" min="60" max="450" value="{bpm}"
    oninput="updateBpm(this.value)" disabled style="accent-color:#38bdf8;">
  <span class="val" id="bpmVal">{bpm}</span>

  <label style="color:#a78bfa;">KEY OFFSET</label>
  <input type="range" id="keyOffset" min="-12" max="12" value="5"
    oninput="updateKeyOffset(this.value)" disabled style="accent-color:#a78bfa;width:80px;">
  <span class="val" id="keyOffsetVal" style="color:#a78bfa;">+5</span>

  <label>SEQUENCE</label>
  <select id="seqSelect" onchange="onSeqChange()" disabled>
{options_html}
  </select>

  <button class="btn-play" id="playBtn" onclick="togglePlay()" disabled>▶ PLAY</button>
  <button class="btn-stop" onclick="stopAll()">■ STOP</button>
  <span id="status">— audio off —</span>
</div>

<div class="grids-outer" id="grids-outer"></div>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:var(--s1)"></div>Hydrophobic — vibraphone</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--s2)"></div>Polar — piano</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--s3)"></div>Pos. charged — harp (warm)</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--s4)"></div>Neg. charged — harp (bright)</div>
  <div class="legend-item"><div class="legend-dot" style="background:transparent;border:2px solid #a78bfa;"></div>Mutated vs WT — piano + key offset</div>
</div>

<script>
const SEQS      = {seqs_js};
const SEQ_NAMES = {seq_names_js};
const WT_NAME   = {wt_name_js};
const AM        = {amino_json};

// Pre-compute which indices differ from WT for each sequence
const wtArr  = SEQS[WT_NAME];
const MUT_IDX = {{}};
for (const name of SEQ_NAMES) {{
  const s = new Set(), arr = SEQS[name];
  for (let i = 0; i < Math.max(wtArr.length, arr.length); i++) {{
    if ((wtArr[i]||'?') !== (arr[i]||'?')) s.add(i);
  }}
  MUT_IDX[name] = s;
}}

// ── Render all grids ──────────────────────────
function renderAllGrids() {{
  const outer = document.getElementById('grids-outer');
  outer.innerHTML = '';
  for (const name of SEQ_NAMES) {{
    const seq = SEQS[name], isWT = name === WT_NAME, mutSet = MUT_IDX[name];

    const panel = document.createElement('div');
    panel.className = 'seq-panel'; panel.id = `panel-${{name}}`;

    const nMut = mutSet.size;
    panel.innerHTML = `
      <div class="panel-title">
        ${{isWT ? '🧬' : '⚗️'}} ${{name}}
        <span class="badge ${{isWT ? 'wt-badge' : 'mut-badge'}}">
          ${{isWT ? seq.length + ' aa · Wild-Type' : nMut + ' mutation' + (nMut===1?'':'s')}}
        </span>
      </div>
      <div class="grid" id="grid-${{name}}"></div>
      ${{!isWT && nMut > 0 ? '<div class="diff-bar" id="diff-' + name + '"></div>' : ''}}
    `;
    outer.appendChild(panel);

    const grid = document.getElementById(`grid-${{name}}`);
    seq.forEach((aa, i) => {{
      const d = AM[aa] || {{s:1}};
      const isMut = !isWT && mutSet.has(i);
      const t = document.createElement('div');
      t.className = `tile s${{d.s}}${{isMut ? ' mutated' : ''}}`;
      t.id = `tile-${{name}}-${{i}}`;
      t.textContent = aa;
      t.title = `#${{i+1}} ${{aa}}${{isMut ? ' (WT: ' + (wtArr[i]||'?') + ')' : ''}}`;
      grid.appendChild(t);
    }});

    if (!isWT && nMut > 0) {{
      const diffs = [];
      for (const i of [...mutSet].sort((a,b) => a-b))
        diffs.push(`#${{i+1}} ${{wtArr[i]||'?'}}→${{seq[i]||'?'}}`);
      document.getElementById(`diff-${{name}}`).textContent = '⚗ ' + diffs.join('  ·  ');
    }}
  }}
}}

// ── Audio engine ──────────────────────────────
let vibraSynth, pianoSampler, pianoLoaded = false;
let masterComp, room, part, playing = false;
let keyOffsetSemitones = 5;

function semitoneShift(note, n) {{
  const ns = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
  const m = note.match(/^([A-G]#?)(\d+)$/);
  if (!m) return note;
  let idx = ns.indexOf(m[1]), oct = parseInt(m[2]);
  idx += n;
  while (idx >= 12) {{ idx -= 12; oct++; }}
  while (idx  < 0)  {{ idx += 12; oct--; }}
  return ns[idx] + oct;
}}

function updateKeyOffset(val) {{
  keyOffsetSemitones = parseInt(val);
  document.getElementById('keyOffsetVal').textContent = (val >= 0 ? '+' : '') + val;
}}

function updateBpm(val) {{
  Tone.Transport.bpm.value = val;
  document.getElementById('bpmVal').textContent = val;
}}

async function initAudio() {{
  await Tone.start();
  masterComp = new Tone.Compressor({{ threshold:-18, ratio:3.5, attack:0.05, release:0.3, knee:8 }}).toDestination();
  room = new Tone.Reverb({{ decay:1.6, wet:0.25, preDelay:0.015 }}).connect(masterComp);

  vibraSynth = new Tone.PolySynth(Tone.FMSynth, {{
    harmonicity:1, modulationIndex:2.5,
    oscillator:{{ type:'sine' }},
    envelope:{{ attack:0.001, decay:0.8, sustain:0.3, release:1.6 }},
    modulation:{{ type:'sine' }},
    modulationEnvelope:{{ attack:0.001, decay:0.5, sustain:0.1, release:0.8 }}
  }}).connect(room);
  vibraSynth.volume.value = -6;

  document.getElementById('status').textContent = '⏳ loading piano…';
  pianoSampler = new Tone.Sampler({{
    urls:{{
      A0:'A0.mp3',C1:'C1.mp3','D#1':'Ds1.mp3','F#1':'Fs1.mp3',
      A1:'A1.mp3',C2:'C2.mp3','D#2':'Ds2.mp3','F#2':'Fs2.mp3',
      A2:'A2.mp3',C3:'C3.mp3','D#3':'Ds3.mp3','F#3':'Fs3.mp3',
      A3:'A3.mp3',C4:'C4.mp3','D#4':'Ds4.mp3','F#4':'Fs4.mp3',
      A4:'A4.mp3',C5:'C5.mp3','D#5':'Ds5.mp3','F#5':'Fs5.mp3',
      A5:'A5.mp3',C6:'C6.mp3','D#6':'Ds6.mp3','F#6':'Fs6.mp3',
      A6:'A6.mp3',C7:'C7.mp3','D#7':'Ds7.mp3','F#7':'Fs7.mp3',
      A7:'A7.mp3',C8:'C8.mp3'
    }},
    release:1.2,
    baseUrl:'https://tonejs.github.io/audio/salamander/',
    onload:() => {{
      pianoLoaded = true;
      document.getElementById('status').textContent = '— ready —';
    }}
  }}).connect(room);
  pianoSampler.volume.value = -4;

  const btn = document.getElementById('initBtn');
  btn.textContent = '✓ AUDIO READY'; btn.className = 'btn-init ready';
  ['playBtn','beepBtn','bpmSlider','seqSelect','keyOffset'].forEach(id =>
    document.getElementById(id).disabled = false
  );
}}

function pluckHarp(note, time, bright) {{
  const h = new Tone.PluckSynth({{
    attackNoise: bright ? 0.8 : 0.4, dampening: bright ? 4200 : 2800, resonance:0.96
  }}).connect(room);
  h.volume.value = bright ? -5 : -4;
  h.triggerAttackRelease(note, '8n', time);
}}

function playNote(group, note, dur, time) {{
  if      (group===1) vibraSynth.triggerAttackRelease(note, dur, time);
  else if (group===2) (pianoLoaded?pianoSampler:vibraSynth).triggerAttackRelease(note, dur, time);
  else if (group===3) pluckHarp(note, time, false);
  else if (group===4) pluckHarp(note, time, true);
}}

function playMutNote(note, time) {{
  const shifted = semitoneShift(note, keyOffsetSemitones);
  (pianoLoaded?pianoSampler:vibraSynth).triggerAttackRelease(shifted, '2n', time);
}}

function testBeep() {{
  if (!vibraSynth) return;
  const t = Tone.now();
  playNote(1,'C4','4n',t);
  playNote(2,'E4','4n',t+0.3);
  playNote(3,'G3','4n',t+0.6);
  playNote(4,'C5','4n',t+0.9);
  playMutNote('E4', t+1.5);
}}

// ── Sequencer ─────────────────────────────────
const octaves   = {{1:3, 2:4, 3:4, 4:5}};
const durations = {{1:'4n', 2:'4n', 3:'8n', 4:'16n'}};

function setupPart() {{
  Tone.Transport.cancel();
  if (part) part.dispose();
  const seqName = document.getElementById('seqSelect').value;
  const seq     = SEQS[seqName];
  const mutSet  = MUT_IDX[seqName];
  const isWT    = seqName === WT_NAME;

  const events = seq.map((aa, i) => {{
    const d = AM[aa]; if (!d) return null;
    const isMut = !isWT && mutSet.has(i);
    return {{ time:i*0.25, note:`${{d.n}}${{octaves[d.s]}}`, group:d.s, i, isMut, seqName }};
  }}).filter(Boolean);

  part = new Tone.Part((time, val) => {{
    val.isMut ? playMutNote(val.note, time) : playNote(val.group, val.note, durations[val.group], time);
    Tone.Draw.schedule(() => {{
      document.querySelectorAll('.tile').forEach(t => t.classList.remove('active'));
      const el = document.getElementById(`tile-${{val.seqName}}-${{val.i}}`);
      if (el) el.classList.add('active');
    }}, time);
  }}, events).start(0);

  Tone.Transport.loop = true;
  Tone.Transport.loopEnd = events.length * 0.25;
}}

function onSeqChange() {{
  document.querySelectorAll('.seq-panel').forEach(p => p.classList.remove('is-playing'));
  const name = document.getElementById('seqSelect').value;
  const panel = document.getElementById(`panel-${{name}}`);
  if (panel) panel.classList.add('is-playing');
  if (Tone.Transport.state === 'started') setupPart();
}}

function togglePlay() {{
  const btn = document.getElementById('playBtn');
  if (Tone.Transport.state === 'started') {{
    Tone.Transport.pause(); playing = false;
    btn.textContent = '▶ PLAY';
    document.getElementById('status').textContent = '— paused —';
  }} else {{
    setupPart();
    Tone.Transport.bpm.value = parseInt(document.getElementById('bpmSlider').value);
    Tone.Transport.start(); playing = true;
    btn.textContent = '⏸ PAUSE';
    onSeqChange();
    document.getElementById('status').textContent =
      `♪ playing ${{document.getElementById('seqSelect').value}}…`;
  }}
}}

function stopAll() {{
  Tone.Transport.stop(); Tone.Transport.seconds = 0; playing = false;
  document.getElementById('playBtn').textContent = '▶ PLAY';
  document.getElementById('status').textContent = '— stopped —';
  document.querySelectorAll('.tile').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.seq-panel').forEach(p => p.classList.remove('is-playing'));
}}

renderAllGrids();
</script>
</body>
</html>"""


# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("sequences", {}),
    ("wt_name",   ""),
    ("loaded",    False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Space+Mono:wght@400;700&display=swap');
html, body, [class*="css"] { font-family: 'Space Mono', monospace; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }
section[data-testid="stSidebar"] { background: #0f1923; border-right: 1px solid #1e2d3d; }
.block-container { padding-top: 2rem; max-width: 1200px; }
div[data-testid="stTextArea"] textarea {
    font-family: 'Space Mono', monospace !important; font-size: 12px !important;
    background: #0f1923 !important; border: 1px solid #1e2d3d !important; color: #60a5fa !important;
}
div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input {
    font-family: 'Space Mono', monospace !important; background: #0f1923 !important; color: white !important;
}
.info-box {
    background: #0f1923; border: 1px solid #1e2d3d; border-radius: 8px;
    padding: 10px 14px; font-family: 'Space Mono', monospace;
    font-size: 12px; color: #64748b; margin-top: 6px;
}
.info-box .hi { color: #a78bfa; font-weight: bold; }
.info-box .gr { color: #4ade80; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🧬 Protein Synth 2.0")
st.markdown(
    "<p style='color:#64748b;font-family:Space Mono,monospace;font-size:13px;margin-top:-10px;'>"
    "Bradley Lab · Sequence Sonification</p>",
    unsafe_allow_html=True,
)
st.divider()


# ── Sidebar — Mutation tools ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚗️ Mutation Tools")

    if not st.session_state.loaded:
        st.info("Load a WT sequence first.")
    else:
        wt_seq = st.session_state.sequences[st.session_state.wt_name]
        variant_names = list(st.session_state.sequences.keys())

        # Which sequence to base the mutation on
        st.markdown("---")
        target_name = st.selectbox(
            "Base mutations on",
            options=variant_names,
            index=len(variant_names) - 1,
            key="mut_target",
        )
        base_seq = st.session_state.sequences[target_name]

        # ── Batch mutations ───────────────────────────────────────────────────
        st.markdown("**Batch Mutations**")
        st.caption("e.g. `L11K, V3A, G7R`")
        batch_input    = st.text_input("Mutations", placeholder="L11K, V3A, G7R", key="batch_input")
        new_var_name   = st.text_input("Save variant as", placeholder="Mutant-2", key="new_var_name")

        if st.button("Apply Batch & Save", use_container_width=True):
            if not new_var_name.strip():
                st.error("Please name the new variant.")
            elif not batch_input.strip():
                st.error("Enter at least one mutation.")
            else:
                try:
                    muts    = parse_batch_mutations(batch_input)
                    new_seq = apply_batch_mutations(base_seq, muts)
                    name    = new_var_name.strip()
                    st.session_state.sequences[name] = new_seq
                    n = count_mutations(wt_seq, new_seq)
                    st.success(f"Saved '{name}' — {n} mutation(s) vs WT.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

        # ── Single residue ────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Single Residue**")
        c1, c2 = st.columns(2)
        with c1:
            mut_pos = st.number_input("Pos #", min_value=1, max_value=max(len(base_seq), 1), value=1, step=1)
        with c2:
            mut_aa  = st.text_input("New AA", value="K", max_chars=1).upper().strip()
        s_name = st.text_input("Save as", placeholder="Mutant-1", key="single_name")

        if st.button("Apply Single & Save", use_container_width=True):
            if not s_name.strip():
                st.error("Please name the new variant.")
            elif mut_aa not in AMINO_MAP:
                st.error(f"'{mut_aa}' is not a valid amino acid.")
            else:
                new_seq = apply_single_mutation(base_seq, mut_pos, mut_aa)
                st.session_state.sequences[s_name.strip()] = new_seq
                st.success(f"Saved '{s_name.strip()}'.")
                st.rerun()

        # ── Global swap ───────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Global Swap**")
        c3, c4 = st.columns(2)
        with c3:
            swap_from = st.text_input("Replace ALL", value="L", max_chars=1, key="sf").upper().strip()
        with c4:
            swap_to   = st.text_input("With", value="K", max_chars=1, key="sw").upper().strip()
        gs_name = st.text_input("Save as", placeholder="SwapVariant", key="gs_name")

        if st.button("Apply Swap & Save", use_container_width=True):
            if not gs_name.strip():
                st.error("Please name the new variant.")
            elif swap_from not in AMINO_MAP or swap_to not in AMINO_MAP:
                st.error("Both must be valid amino acid codes.")
            else:
                new_seq = apply_global_swap(base_seq, swap_from, swap_to)
                st.session_state.sequences[gs_name.strip()] = new_seq
                st.success(f"Saved '{gs_name.strip()}'.")
                st.rerun()

        # ── Remove variant ────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Remove Variant**")
        non_wt = [n for n in st.session_state.sequences if n != st.session_state.wt_name]
        if non_wt:
            to_remove = st.selectbox("Variant to remove", non_wt, key="to_remove")
            if st.button("🗑 Remove", use_container_width=True):
                del st.session_state.sequences[to_remove]
                st.rerun()
        else:
            st.caption("No variants loaded yet.")

        # ── Stats readout ─────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Loaded Sequences**")
        for name, seq in st.session_state.sequences.items():
            is_wt  = (name == st.session_state.wt_name)
            n_mut  = 0 if is_wt else count_mutations(wt_seq, seq)
            cls    = "gr" if is_wt else "hi"
            label  = "Wild-Type" if is_wt else f"{n_mut} mut vs WT"
            st.markdown(
                f'<div class="info-box"><span class="{cls}">{name}</span>'
                f' · {len(seq)} aa · {label}</div>',
                unsafe_allow_html=True,
            )


# ── Main: Step 1 — Load sequences ────────────────────────────────────────────
st.markdown("### 1 · Load Wild-Type Sequence")

paste_tab, upload_tab = st.tabs(["📋 Paste sequence", "📁 Upload FASTA"])

with paste_tab:
    raw_input = st.text_area(
        "WT sequence",
        height=90,
        placeholder=">MyProtein\nMKTAYIAKQRQISFVKSHFSRQTEAERNKHHSSLLTAYGNSQ...",
        label_visibility="collapsed",
    )
    wt_label = st.text_input("Name this sequence", value="Wild-Type", key="wt_label_paste")

    if st.button("🔬 Load as Wild-Type", type="primary", use_container_width=True, key="load_paste"):
        parsed = parse_fasta(raw_input) if raw_input.strip() else {}
        if not parsed:
            st.error("No valid sequence found.")
        else:
            name_list = list(parsed.keys())
            wt_seq_name = wt_label.strip() or name_list[0]
            new_seqs = {wt_seq_name: list(parsed.values())[0]}
            for n, s in list(parsed.items())[1:]:
                new_seqs[n] = s
            st.session_state.sequences = new_seqs
            st.session_state.wt_name   = wt_seq_name
            st.session_state.loaded    = True
            st.success(f"Loaded WT '{wt_seq_name}' — {len(list(parsed.values())[0])} residues.")
            st.rerun()

with upload_tab:
    st.caption(
        "Upload a FASTA file. Multiple sequences are supported — "
        "the first becomes WT, the rest become variants automatically."
    )
    uploaded    = st.file_uploader("FASTA file", type=["fasta","fa","txt"], label_visibility="collapsed")
    wt_label_up = st.text_input("Name for first sequence (WT)", value="Wild-Type", key="wt_label_upload")

    if uploaded and st.button("🔬 Load FASTA", type="primary", use_container_width=True, key="load_upload"):
        text   = uploaded.read().decode("utf-8", errors="ignore")
        parsed = parse_fasta(text)
        if not parsed:
            st.error("No valid sequences found in the file.")
        else:
            new_seqs = {}
            for i, (n, s) in enumerate(parsed.items()):
                label = (wt_label_up.strip() or n) if i == 0 else n
                new_seqs[label] = s
            wt_seq_name = list(new_seqs.keys())[0]
            st.session_state.sequences = new_seqs
            st.session_state.wt_name   = wt_seq_name
            st.session_state.loaded    = True
            st.success(f"Loaded {len(parsed)} sequence(s). WT = '{wt_seq_name}'.")
            st.rerun()

st.markdown("---")

# ── Main: Step 2 — Visualise & Play ──────────────────────────────────────────
if st.session_state.loaded and st.session_state.sequences:
    st.markdown("### 2 · Visualize & Play")

    col_l, col_r = st.columns([1, 4])
    with col_l:
        st.markdown(
            "<div style='padding-top:8px;font-size:12px;color:#64748b;'>Tempo (BPM)</div>",
            unsafe_allow_html=True,
        )
    with col_r:
        bpm = st.slider("BPM", 60, 450, 120, label_visibility="collapsed")

    component_html = build_audio_component(
        sequences=st.session_state.sequences,
        wt_name=st.session_state.wt_name,
        bpm=bpm,
    )

    longest  = max(len(s) for s in st.session_state.sequences.values())
    n_seqs   = len(st.session_state.sequences)
    tile_rows = (longest // 22) + 1
    height   = min(220 + n_seqs * (tile_rows * 38 + 90), 1600)

    st.components.v1.html(component_html, height=height, scrolling=True)
    st.caption(
        "💡 Click **ENABLE AUDIO** first — piano samples take ~5 sec to load. "
        "Use the **SEQUENCE** dropdown to switch what plays. "
        "Purple outlines = mutated vs WT. Adjust **KEY OFFSET** to control how dissonant mutations sound."
    )

else:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;border:2px dashed #1e2d3d;
                border-radius:12px;margin-top:20px;">
        <div style="font-size:3rem;">🧬</div>
        <div style="font-family:'Space Mono',monospace;font-size:13px;margin-top:10px;color:#334155;">
            Paste or upload a sequence above to begin.
        </div>
    </div>
    """, unsafe_allow_html=True)
