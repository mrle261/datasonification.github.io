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

# ── Amino acid map — pentatonic scale, ordered by hydrophobicity ─────────────
# All WT notes are in C major pentatonic (C D E G A) — impossible to sound bad.
# Groups stay in their own register so you can hear the chemical texture.
# Mutations get a tritone shift (+6 semitones) landing outside the pentatonic.
#
# Group 1  Hydrophobic   → Vibraphone  low register  (sky blue)
# Group 2  Polar         → Piano       mid register  (green)
# Group 3  Pos. charged  → Harp warm   low-mid       (amber)
# Group 4  Neg. charged  → Harp bright high          (red)
#
# Ordered within each group by Kyte-Doolittle hydrophobicity score
AMINO_MAP = {
    # Hydrophobic (9 AAs) — vibraphone, octave 3, pentatonic C D E G A × 2
    'I': {'s': 1, 'n': 'C'}, 'V': {'s': 1, 'n': 'D'}, 'L': {'s': 1, 'n': 'E'},
    'F': {'s': 1, 'n': 'G'}, 'C': {'s': 1, 'n': 'A'}, 'M': {'s': 1, 'n': 'C'},
    'A': {'s': 1, 'n': 'D'}, 'W': {'s': 1, 'n': 'E'}, 'P': {'s': 1, 'n': 'G'},
    # Polar uncharged (7 AAs) — piano, octave 4, pentatonic
    'G': {'s': 2, 'n': 'A'}, 'T': {'s': 2, 'n': 'C'}, 'S': {'s': 2, 'n': 'D'},
    'Y': {'s': 2, 'n': 'E'}, 'H': {'s': 2, 'n': 'G'}, 'Q': {'s': 2, 'n': 'A'},
    'N': {'s': 2, 'n': 'C'},
    # Positively charged (2 AAs) — warm harp, octave 3
    'K': {'s': 3, 'n': 'G'}, 'R': {'s': 3, 'n': 'E'},
    # Negatively charged (2 AAs) — bright harp, octave 4
    'D': {'s': 4, 'n': 'A'}, 'E': {'s': 4, 'n': 'E'},
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

  /* Grids wrapper — side by side, wraps if more than 2 sequences */
  .grids-outer {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }}
  .seq-panel {{
    background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px;
    transition: border-color .2s, box-shadow .2s;
    min-width: 0; /* prevent overflow in grid */
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
    width:24px; height:24px; border-radius:3px;
    display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:9px; color:#0f172a;
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
  <input type="range" id="keyOffset" min="-12" max="12" value="6"
    oninput="updateKeyOffset(this.value)" disabled style="accent-color:#a78bfa;width:80px;">
  <span class="val" id="keyOffsetVal" style="color:#a78bfa;">+6</span>

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
let keyOffsetSemitones = 6;  // tritone — most dissonant interval, always lands outside pentatonic

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
  // Tritone shift lands outside the pentatonic — maximally dissonant
  // Played as a half note at +3dB so it rings out and is impossible to miss
  const shifted = semitoneShift(note, keyOffsetSemitones);
  const sampler = pianoLoaded ? pianoSampler : vibraSynth;
  sampler.volume.value = -1;   // louder than normal piano (-4dB)
  sampler.triggerAttackRelease(shifted, '2n', time);
  // Reset volume after the note
  setTimeout(() => {{ if (pianoLoaded) pianoSampler.volume.value = -4; }}, 600);
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
// All WT notes in pentatonic → pleasant, coherent melody
// Octave registers keep groups sonically distinct:
//   Group 1 (hydrophobic)  → octave 3  vibraphone, low & warm
//   Group 2 (polar)        → octave 4  piano, main melody register
//   Group 3 (pos charged)  → octave 3  harp warm, supportive low
//   Group 4 (neg charged)  → octave 5  harp bright, high sparkle
// Consistent quarter-note durations so the melody flows evenly
const octaves   = {{1:3, 2:4, 3:3, 4:5}};
const durations = {{1:'4n', 2:'4n', 3:'4n', 4:'8n'}};

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
section[data-testid="stSidebar"] * { color: white !important; }
section[data-testid="stSidebar"] .hi { color: #a78bfa !important; }
section[data-testid="stSidebar"] .gr { color: #4ade80 !important; }

/* Expander label, summary, and inner text */
section[data-testid="stSidebar"] details summary p { color: white !important; }
section[data-testid="stSidebar"] details summary span { color: white !important; }
section[data-testid="stSidebar"] details > div * { color: white !important; }
section[data-testid="stSidebar"] [data-testid="stExpanderToggleIcon"] { color: white !important; }

/* Selectbox, text input, number input labels and values */
section[data-testid="stSidebar"] label { color: white !important; }
section[data-testid="stSidebar"] input { color: white !important; }
section[data-testid="stSidebar"] [data-baseweb="select"] * { color: white !important; }
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color: white !important; }
section[data-testid="stSidebar"] small { color: white !important; }
section[data-testid="stSidebar"] .stCaption p { color: white !important; }

/* Fix buttons — dark bg, white text (including inside expanders) */
section[data-testid="stSidebar"] button[kind="secondary"],
section[data-testid="stSidebar"] button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button,
section[data-testid="stSidebar"] details .stButton > button,
section[data-testid="stSidebar"] details div .stButton > button,
section[data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button {
    background-color: #1e3a5f !important;
    color: white !important;
    border: 1px solid #334155 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover,
section[data-testid="stSidebar"] details .stButton > button:hover,
section[data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button:hover {
    background-color: #2a4a6f !important;
    color: white !important;
}
section[data-testid="stSidebar"] .stButton > button p,
section[data-testid="stSidebar"] details .stButton > button p,
section[data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button p {
    color: white !important;
}

/* Make placeholder text visible */
section[data-testid="stSidebar"] input::placeholder {
    color: #94a3b8 !important;
    opacity: 1 !important;
}
section[data-testid="stSidebar"] textarea::placeholder {
    color: #94a3b8 !important;
    opacity: 1 !important;
}
section[data-testid="stSidebar"] [data-baseweb="input"] {
    background-color: #1e2d3d !important;
    border-color: #334155 !important;
}
section[data-testid="stSidebar"] [data-baseweb="input"] input {
    background-color: #1e2d3d !important;
    color: white !important;
}
section[data-testid="stSidebar"] [data-testid="stNumberInputStepDown"],
section[data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] {
    background-color: #1e2d3d !important;
    color: white !important;
}
section[data-testid="stSidebar"] [data-testid="stNumberInputStepDown"] svg,
section[data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] svg {
    fill: white !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div { 
    background-color: #1e2d3d !important; 
    border-color: #334155 !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stSelectboxValue"],
section[data-testid="stSidebar"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] [data-baseweb="select"] div { 
    color: white !important; 
}
section[data-testid="stSidebar"] [role="listbox"] { 
    background-color: #1e2d3d !important; 
}
section[data-testid="stSidebar"] [role="option"] { 
    background-color: #1e2d3d !important; 
    color: white !important; 
}

.block-container { padding-top: 2rem; max-width: 1200px; }
div[data-testid="stTextArea"] textarea {
    font-family: 'Space Mono', monospace !important; font-size: 12px !important;
    background: #0f1923 !important; border: 1px solid #1e2d3d !important; color: #60a5fa !important;
}
div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input {
    font-family: 'Space Mono', monospace !important; background: #0f1923 !important; color: white !important;
}

/* ── Sidebar section headers ── */
.sidebar-section {
    display: flex; align-items: center; gap: 8px;
    padding: 7px 10px; border-radius: 6px; margin-bottom: 4px;
    font-family: 'Space Mono', monospace; font-size: 11px; font-weight: 700;
    letter-spacing: .06em; text-transform: uppercase;
}
.section-batch   { background: #1e1040; color: #a78bfa; border-left: 3px solid #7c3aed; }
.section-single  { background: #0a1f30; color: #38bdf8; border-left: 3px solid #0284c7; }
.section-swap    { background: #0a2010; color: #4ade80; border-left: 3px solid #16a34a; }
.section-remove  { background: #200a0a; color: #f87171; border-left: 3px solid #dc2626; }
.section-seqs    { background: #101010; color: #94a3b8; border-left: 3px solid #475569; }

/* ── Info boxes ── */
.info-box {
    background: #0f1923; border: 1px solid #1e2d3d; border-radius: 8px;
    padding: 10px 14px; font-family: 'Space Mono', monospace;
    font-size: 12px; color: white; margin-top: 6px;
}
.info-box .hi { color: #a78bfa; font-weight: bold; }
.info-box .gr { color: #4ade80; font-weight: bold; }

/* ── Expander polish ── */
section[data-testid="stSidebar"] div[data-testid="stExpander"] {
    border: 1px solid #1e2d3d !important;
    border-radius: 8px !important;
    background: #0c1520 !important;
    margin-bottom: 8px !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] summary {
    background-color: #0c1520 !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] summary:hover {
    background-color: #1e2d3d !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] details {
    background-color: #0c1520 !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] > details > div {
    background-color: #0c1520 !important;
}
/* All buttons inside expanders */
section[data-testid="stSidebar"] div[data-testid="stExpander"] button {
    background-color: #1e3a5f !important;
    color: white !important;
    border: 1px solid #334155 !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] button:hover {
    background-color: #2a4a6f !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] button * {
    color: white !important;
}
/* All inputs inside expanders */
section[data-testid="stSidebar"] div[data-testid="stExpander"] input {
    background-color: #1e2d3d !important;
    color: white !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] [data-baseweb="input"] {
    background-color: #1e2d3d !important;
}
section[data-testid="stSidebar"] div[data-testid="stExpander"] [data-baseweb="base-input"] {
    background-color: #1e2d3d !important;
}
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
        st.info("Load a WT sequence first to use mutation tools.")
    else:
        wt_seq        = st.session_state.sequences[st.session_state.wt_name]
        variant_names = list(st.session_state.sequences.keys())

        # ── Base sequence selector — always visible ───────────────────────────
        st.markdown(
            '<div class="sidebar-section section-seqs">🔬 Working Sequence</div>',
            unsafe_allow_html=True,
        )
        target_name = st.selectbox(
            "Base mutations on",
            options=variant_names,
            index=len(variant_names) - 1,
            key="mut_target",
            label_visibility="collapsed",
            help="Mutations will be applied starting from this sequence.",
        )
        base_seq = st.session_state.sequences[target_name]
        st.caption(f"{len(base_seq)} aa · mutations saved as new variants, WT never modified")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Batch mutations ───────────────────────────────────────────────────
        with st.expander("🟣  Batch Mutations  —  e.g. L11K, V3A"):
            st.markdown(
                '<div class="sidebar-section section-batch">Apply multiple at once</div>',
                unsafe_allow_html=True,
            )
            st.caption("Standard notation: `OriginalAA · Position · NewAA`")
            batch_input  = st.text_input("Mutations", placeholder="L11K, V3A, G7R", key="batch_input")
            new_var_name = st.text_input("Save variant as", placeholder="Mutant-2", key="new_var_name")

            if st.button("✦ Apply Batch & Save", use_container_width=True, key="btn_batch"):
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
        with st.expander("🔵  Single Residue  —  one position"):
            st.markdown(
                '<div class="sidebar-section section-single">Swap one amino acid</div>',
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns([3, 2])
            with c1:
                mut_pos = st.number_input(
                    "Position #", min_value=1, max_value=max(len(base_seq), 1), value=1, step=1
                )
            with c2:
                mut_aa = st.text_input("New AA", value="K", max_chars=1).upper().strip()
            s_name = st.text_input("Save as", placeholder="Mutant-1", key="single_name")

            if st.button("✦ Apply Single & Save", use_container_width=True, key="btn_single"):
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
        with st.expander("🟢  Global Swap  —  replace all of one AA"):
            st.markdown(
                '<div class="sidebar-section section-swap">Replace every occurrence</div>',
                unsafe_allow_html=True,
            )
            c3, c4 = st.columns(2)
            with c3:
                swap_from = st.text_input("Replace ALL", value="L", max_chars=1, key="sf").upper().strip()
            with c4:
                swap_to = st.text_input("With", value="K", max_chars=1, key="sw").upper().strip()
            gs_name = st.text_input("Save as", placeholder="SwapVariant", key="gs_name")

            if st.button("✦ Apply Swap & Save", use_container_width=True, key="btn_swap"):
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
        with st.expander("🔴  Remove a Variant"):
            st.markdown(
                '<div class="sidebar-section section-remove">Delete a loaded variant</div>',
                unsafe_allow_html=True,
            )
            non_wt = [n for n in st.session_state.sequences if n != st.session_state.wt_name]
            if non_wt:
                to_remove = st.selectbox("Variant to remove", non_wt, key="to_remove",
                                         label_visibility="collapsed")
                if st.button("🗑 Remove this variant", use_container_width=True, key="btn_remove"):
                    del st.session_state.sequences[to_remove]
                    st.rerun()
            else:
                st.caption("No variants loaded yet — WT cannot be removed.")

        # ── Loaded sequences summary ──────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div class="sidebar-section section-seqs">📋 Loaded Sequences</div>',
            unsafe_allow_html=True,
        )
        for name, seq in st.session_state.sequences.items():
            is_wt = (name == st.session_state.wt_name)
            n_mut = 0 if is_wt else count_mutations(wt_seq, seq)
            cls   = "gr" if is_wt else "hi"
            label = "Wild-Type" if is_wt else f"{n_mut} mut vs WT"
            st.markdown(
                f'<div class="info-box"><span class="{cls}">{name}</span>'
                f'<br><span style="font-size:10px;">{len(seq)} aa · {label}</span></div>',
                unsafe_allow_html=True,
            )
            # Download button for every sequence
            fasta_str = f">{name}\n{seq}\n"
            st.download_button(
                label=f"⬇ Download {name}",
                data=fasta_str,
                file_name=f"{name.replace(' ', '_')}.fasta",
                mime="text/plain",
                use_container_width=True,
                key=f"dl_{name}",
            )

        # ── Upload additional sequence ────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📂  Upload Additional Sequence"):
            st.markdown(
                '<div class="sidebar-section section-seqs">Add sequence to compare</div>',
                unsafe_allow_html=True,
            )
            st.caption("Upload a FASTA or paste a sequence to add as a variant alongside the current WT.")

            add_tab1, add_tab2 = st.tabs(["Paste", "Upload"])

            with add_tab1:
                add_raw = st.text_area(
                    "Sequence", height=80,
                    placeholder=">Mutant-X\nMKTAYIAKQR...",
                    label_visibility="collapsed",
                    key="add_raw",
                )
                add_name_paste = st.text_input("Name", placeholder="Mutant-X", key="add_name_paste")
                if st.button("➕ Add Sequence", use_container_width=True, key="btn_add_paste"):
                    parsed = parse_fasta(add_raw) if add_raw.strip() else {}
                    if not parsed:
                        st.error("No valid sequence found.")
                    else:
                        for i, (n, s) in enumerate(parsed.items()):
                            label = add_name_paste.strip() if (i == 0 and add_name_paste.strip()) else n
                            st.session_state.sequences[label] = s
                        st.success(f"Added {len(parsed)} sequence(s).")
                        st.rerun()

            with add_tab2:
                add_file = st.file_uploader(
                    "FASTA file", type=["fasta", "fa", "txt"],
                    label_visibility="collapsed",
                    key="add_file",
                )
                add_name_upload = st.text_input("Name (first seq)", placeholder="Mutant-X", key="add_name_upload")
                if add_file and st.button("➕ Add from File", use_container_width=True, key="btn_add_upload"):
                    text   = add_file.read().decode("utf-8", errors="ignore")
                    parsed = parse_fasta(text)
                    if not parsed:
                        st.error("No valid sequences found.")
                    else:
                        for i, (n, s) in enumerate(parsed.items()):
                            label = add_name_upload.strip() if (i == 0 and add_name_upload.strip()) else n
                            st.session_state.sequences[label] = s
                        st.success(f"Added {len(parsed)} sequence(s).")
                        st.rerun()


# ── How It Works — friendly explainer ───────────────────────────────────────
with st.expander("👋 How does this work? Click here to find out!", expanded=not st.session_state.loaded):
    st.markdown("""
<style>
.how-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 10px; }
.how-card {
    background: #0f1923; border: 1px solid #1e2d3d; border-radius: 10px;
    padding: 16px; font-family: 'Space Mono', monospace;
}
.how-card .icon { font-size: 2rem; margin-bottom: 8px; }
.how-card .title { font-size: 12px; font-weight: 700; color: white; margin-bottom: 6px; }
.how-card .body  { font-size: 11px; color: #94a3b8; line-height: 1.6; }
.how-card .body b { color: white; }

.color-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.color-chip {
    display: flex; align-items: center; gap: 6px;
    background: #0f1923; border: 1px solid #1e2d3d;
    border-radius: 6px; padding: 6px 10px;
    font-family: 'Space Mono', monospace; font-size: 11px; color: white;
}
.chip-dot { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
.mut-chip { display:flex; align-items:center; gap:6px; background:#1e0a3c;
    border:1px solid #7c3aed44; border-radius:6px; padding:6px 10px;
    font-family:'Space Mono',monospace; font-size:11px; color:#c4b5fd; }
</style>

<div class="how-grid">

  <div class="how-card">
    <div class="icon">🧬</div>
    <div class="title">What is a protein?</div>
    <div class="body">
      A protein is like a very long word made up of just <b>20 letters</b> called amino acids.
      Each letter is a different chemical building block. The order of those letters determines
      what the protein does in your body — like carrying oxygen, fighting germs, or digesting food.
    </div>
  </div>

  <div class="how-card">
    <div class="icon">🎵</div>
    <div class="title">How do we turn it into music?</div>
    <div class="body">
      Each amino acid letter gets sorted into one of <b>4 groups</b> based on its chemistry,
      and each group gets its own instrument. Then the app reads the protein left to right,
      playing one note per letter — like reading sheet music. The result is a unique
      melody for every protein!
    </div>
  </div>

  <div class="how-card">
    <div class="icon">⚗️</div>
    <div class="title">What is a mutation?</div>
    <div class="body">
      A mutation is when one letter in the protein sequence gets swapped for a different one.
      Sometimes mutations are harmless, sometimes they change how the protein works.
      In this app, <b>mutated letters play a clashing note</b> so you can hear exactly
      where the protein changed — like a wrong note in a song.
    </div>
  </div>

</div>

<br>

**🎨 What do the colors mean?**

<div class="color-row">
  <div class="color-chip"><div class="chip-dot" style="background:#38bdf8"></div>Sky blue = Hydrophobic (water-repelling) — plays <b>vibraphone</b></div>
  <div class="color-chip"><div class="chip-dot" style="background:#4ade80"></div>Green = Polar uncharged — plays <b>piano</b></div>
  <div class="color-chip"><div class="chip-dot" style="background:#fbbf24"></div>Amber = Positively charged — plays <b>warm harp</b></div>
  <div class="color-chip"><div class="chip-dot" style="background:#f87171"></div>Red = Negatively charged — plays <b>bright harp</b></div>
  <div class="mut-chip"><div class="chip-dot" style="background:transparent;border:2px solid #a78bfa;"></div>Purple outline = Mutated letter — plays a <b>clashing piano note</b></div>
</div>

<br>

**🚀 How to get started — 3 simple steps:**

| Step | What to do | Why |
|------|-----------|-----|
| **1** | Paste or upload your protein sequence below | This is your "original" protein — called the Wild-Type |
| **2** | Click **ENABLE AUDIO** in the player, then **PLAY** | The app will play a note for every amino acid, left to right |
| **3** | Use the **Mutation Tools** panel on the left to swap letters | Any changed letters will play as clashing notes so you can hear the difference |

""", unsafe_allow_html=True)

st.markdown("---")

# ── Main: Step 1 — Load sequences ────────────────────────────────────────────
st.markdown("### Step 1 · Load Your Protein Sequence")
st.caption("This is your starting protein — called the **Wild-Type (WT)**. Paste the letters directly or upload a FASTA file.")

paste_tab, upload_tab = st.tabs(["📋 Paste sequence", "📁 Upload FASTA file"])

with paste_tab:
    st.caption("Paste your protein as single letters (e.g. MKTAYIAKQR...) or in FASTA format with a > header line.")
    raw_input = st.text_area(
        "WT sequence",
        height=90,
        placeholder=">MyProtein\nMKTAYIAKQRQISFVKSHFSRQTEAERNKHHSSLLTAYGNSQ...",
        label_visibility="collapsed",
    )
    wt_label = st.text_input("Give this sequence a name", value="Wild-Type", key="wt_label_paste")

    if st.button("🔬 Load as Wild-Type", type="primary", use_container_width=True, key="load_paste"):
        parsed = parse_fasta(raw_input) if raw_input.strip() else {}
        if not parsed:
            st.error("No valid sequence found. Make sure you've pasted amino acid letters (A–Z).")
        else:
            name_list = list(parsed.keys())
            wt_seq_name = wt_label.strip() or name_list[0]
            new_seqs = {wt_seq_name: list(parsed.values())[0]}
            for n, s in list(parsed.items())[1:]:
                new_seqs[n] = s
            st.session_state.sequences = new_seqs
            st.session_state.wt_name   = wt_seq_name
            st.session_state.loaded    = True
            st.success(f"✅ Loaded '{wt_seq_name}' — {len(list(parsed.values())[0])} amino acids. Scroll down to play!")
            st.rerun()

with upload_tab:
    st.caption(
        "A FASTA file is a standard biology file format. "
        "If your file has multiple sequences, the first one becomes the Wild-Type "
        "and the rest are loaded as variants to compare."
    )
    uploaded    = st.file_uploader("FASTA file", type=["fasta","fa","txt"], label_visibility="collapsed")
    wt_label_up = st.text_input("Name for the first sequence", value="Wild-Type", key="wt_label_upload")

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
            st.success(f"✅ Loaded {len(parsed)} sequence(s). Wild-Type = '{wt_seq_name}'. Scroll down to play!")
            st.rerun()

st.markdown("---")

# ── Main: Step 2 — Visualise & Play ──────────────────────────────────────────
if st.session_state.loaded and st.session_state.sequences:
    st.markdown("### Step 2 · Listen & Compare")
    st.caption(
        "Each colored square is one amino acid. The app reads them left to right and plays a note for each one. "
        "Switch between sequences using the **SEQUENCE** dropdown inside the player."
    )

    col_l, col_r = st.columns([1, 4])
    with col_l:
        st.markdown(
            "<div style='padding-top:8px;font-size:12px;color:#94a3b8;'>⏱ Speed (BPM)</div>",
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
    tile_rows  = (longest // 28) + 1
    n_rows     = (n_seqs + 1) // 2
    height     = min(220 + n_rows * (tile_rows * 30 + 100), 1600)

    st.components.v1.html(component_html, height=height, scrolling=True)

    st.info(
        "💡 **Quick start:** Click **ENABLE AUDIO** → wait ~5 seconds for piano to load → "
        "pick a sequence from the dropdown → click **PLAY**. "
        "The glowing square shows which amino acid is playing right now. "
        "Purple outlined squares are mutations — listen for the clashing notes!"
    )

    st.markdown("---")
    st.markdown("### Step 3 · Make Mutations")
    st.caption(
        "Use the **⚗️ Mutation Tools** panel on the **left sidebar** to swap amino acids and create new variants. "
        "Every mutation you make is saved as a new sequence you can play and compare."
    )

    with st.expander("📖 How do I write a mutation?"):
        st.markdown("""
A mutation is written as **3 parts** with no spaces:

| Part | Meaning | Example |
|------|---------|---------|
| **First letter** | The original amino acid at that position | `L` = Leucine |
| **Number** | The position in the sequence (counting from 1) | `11` = position 11 |
| **Last letter** | The new amino acid you want there | `K` = Lysine |

So **`L11K`** means: *"Change position 11 from L to K"*

To make multiple mutations at once, separate them with commas:
```
L11K, V3A, G7R
```
This changes position 11, position 3, and position 7 all in one go.

**Then give your new variant a name** (like "Mutant-1") and click Apply — it will appear in the player ready to compare against the Wild-Type!
        """)

else:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;border:2px dashed #1e2d3d;
                border-radius:12px;margin-top:20px;">
        <div style="font-size:3rem;">🧬</div>
        <div style="font-family:'Space Mono',monospace;font-size:14px;margin-top:12px;color:#94a3b8;">
            Paste or upload a protein sequence above to get started!
        </div>
        <div style="font-family:'Space Mono',monospace;font-size:11px;margin-top:8px;color:#475569;">
            Not sure where to get a sequence? Try searching for any protein on
            <a href="https://www.uniprot.org" target="_blank" style="color:#38bdf8;">UniProt.org</a>
            and copying the sequence from there.
        </div>
    </div>
    """, unsafe_allow_html=True)
