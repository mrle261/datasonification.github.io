"""
Protein Synth 2.0 — Bradley Lab
Streamlit app with real-time audio via Tone.js, WT vs Mutant comparison
Run with: streamlit run protein_synth_app.py
"""

import streamlit as st
import re
import json

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Protein Synth 2.0 · Bradley Lab",
    page_icon="🧬",
    layout="wide",
)

# ── Amino acid → (group, note) — hydrophobicity-based ───────────────────────
# Group 1  Hydrophobic (nonpolar)  → warm STRINGS   (sky blue)
# Group 2  Polar / uncharged       → mellow WOODWIND (green)
# Group 3  Positively charged      → bright BRASS    (amber)
# Group 4  Negatively charged      → plucked PIZZ    (red)
AMINO_MAP = {
    # Hydrophobic — strings (9 AAs → cycle C D E F G A B C D)
    'A': {'s': 1, 'n': 'C'}, 'V': {'s': 1, 'n': 'D'}, 'I': {'s': 1, 'n': 'E'},
    'L': {'s': 1, 'n': 'F'}, 'M': {'s': 1, 'n': 'G'}, 'F': {'s': 1, 'n': 'A'},
    'W': {'s': 1, 'n': 'B'}, 'P': {'s': 1, 'n': 'C'}, 'C': {'s': 1, 'n': 'D'},
    # Polar uncharged — woodwind (7 AAs → E F G A B C D)
    'G': {'s': 2, 'n': 'E'}, 'S': {'s': 2, 'n': 'F'}, 'T': {'s': 2, 'n': 'G'},
    'Y': {'s': 2, 'n': 'A'}, 'H': {'s': 2, 'n': 'B'}, 'Q': {'s': 2, 'n': 'C'},
    'N': {'s': 2, 'n': 'D'},
    # Positively charged — brass (2 AAs)
    'K': {'s': 3, 'n': 'E'}, 'R': {'s': 3, 'n': 'G'},
    # Negatively charged — pizzicato (2 AAs)
    'D': {'s': 4, 'n': 'F'}, 'E': {'s': 4, 'n': 'A'},
}

GROUP_LABELS = {
    1: "Hydrophobic (strings)",
    2: "Polar uncharged (woodwind)",
    3: "Positive charged (brass)",
    4: "Negative charged (pizzicato)",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def clean_sequence(raw: str) -> str:
    """Strip FASTA headers and non-AA characters."""
    lines = raw.strip().splitlines()
    seq_lines = [l for l in lines if not l.startswith(">")]
    joined = "".join(seq_lines).upper()
    return re.sub(r"[^A-Z]", "", joined)


def validate_sequence(seq: str) -> tuple[str, list[str]]:
    """Return cleaned valid AAs and list of unrecognised characters."""
    valid = ""
    unknown = []
    for ch in seq:
        if ch in AMINO_MAP:
            valid += ch
        else:
            unknown.append(ch)
    return valid, list(set(unknown))


def apply_single_mutation(seq: str, pos: int, new_aa: str) -> str:
    """1-indexed position mutation."""
    if 1 <= pos <= len(seq) and new_aa in AMINO_MAP:
        return seq[: pos - 1] + new_aa + seq[pos:]
    return seq


def apply_global_swap(seq: str, target: str, replacement: str) -> str:
    if target in AMINO_MAP and replacement in AMINO_MAP:
        return seq.replace(target, replacement)
    return seq


def count_mutations(wt: str, mut: str) -> int:
    return sum(a != b for a, b in zip(wt, mut))


# ── Build the self-contained Tone.js HTML component ─────────────────────────

def build_audio_component(wt_seq: str, mut_seq: str, bpm: int) -> str:
    """
    Returns an HTML string that:
    - Shows WT vs Mutant grids side by side
    - Plays EITHER sequence via Tone.js
    - Highlights active residue while playing
    """
    wt_json = json.dumps(list(wt_seq))
    mut_json = json.dumps(list(mut_seq))
    amino_json = json.dumps({
        k: {"s": v["s"], "n": v["n"]} for k, v in AMINO_MAP.items()
    })

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/tone/14.8.49/Tone.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@600;800&display=swap');

  :root {{
    --bg:   #080d14;
    --card: #0f1923;
    --line: #1e2d3d;
    --s1:   #38bdf8;
    --s2:   #4ade80;
    --s3:   #fbbf24;
    --s4:   #f87171;
    --text: #e2e8f0;
    --dim:  #64748b;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Space Mono', monospace;
    background: var(--bg);
    color: var(--text);
    padding: 16px;
    font-size: 13px;
  }}

  /* ── Controls bar ── */
  .controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    margin-bottom: 16px;
    padding: 14px 16px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 10px;
  }}

  button {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .05em;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: opacity .15s, transform .1s;
  }}
  button:hover {{ opacity: .85; transform: translateY(-1px); }}
  button:active {{ transform: translateY(0); }}

  .btn-init   {{ background: #e11d48; color: #fff; }}
  .btn-init.ready {{ background: #059669; color: #fff; }}
  .btn-play   {{ background: #3b82f6; color: #fff; }}
  .btn-stop   {{ background: #475569; color: #fff; }}
  .btn-beep   {{ background: #334155; color: var(--s1); border: 1px solid var(--s1); }}

  label {{ color: var(--dim); font-size: 11px; }}
  input[type=range] {{ accent-color: var(--s1); width: 120px; cursor: pointer; }}
  .bpm-val {{ color: var(--s1); font-weight: 700; min-width: 60px; }}

  select {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    background: var(--card);
    color: var(--text);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 6px 10px;
    cursor: pointer;
  }}

  /* ── Status bar ── */
  #status {{
    font-size: 11px;
    color: var(--s2);
    margin-left: auto;
    font-weight: 700;
  }}

  /* ── Grids layout ── */
  .grids-wrapper {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }}

  .seq-panel {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 16px;
  }}

  .panel-title {{
    font-family: 'Syne', sans-serif;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: .08em;
    text-transform: uppercase;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .panel-title .badge {{
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    font-weight: 400;
    background: var(--line);
    padding: 2px 8px;
    border-radius: 99px;
    color: var(--dim);
  }}
  .panel-title .mut-badge {{
    background: #7c3aed22;
    color: #a78bfa;
    border: 1px solid #7c3aed55;
  }}

  /* ── Tiles ── */
  .grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }}
  .tile {{
    width: 32px;
    height: 32px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 11px;
    color: #0f172a;
    cursor: default;
    transition: transform .1s, box-shadow .1s;
    position: relative;
  }}
  .s1 {{ background: var(--s1); }}
  .s2 {{ background: var(--s2); }}
  .s3 {{ background: var(--s3); }}
  .s4 {{ background: var(--s4); }}

  .tile.mutated {{
    outline: 2px solid #a78bfa;
    outline-offset: 1px;
  }}
  .tile.active {{
    transform: scale(1.25);
    box-shadow: 0 0 12px 4px rgba(255,255,255,.6);
    z-index: 10;
  }}
  .tile[title]:hover::after {{
    content: attr(title);
    position: absolute;
    bottom: 110%;
    left: 50%;
    transform: translateX(-50%);
    background: #1e293b;
    color: white;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    white-space: nowrap;
    pointer-events: none;
    z-index: 20;
  }}

  /* ── Legend ── */
  .legend {{
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
  }}
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 10px;
    color: var(--dim);
  }}
  .legend-dot {{
    width: 10px; height: 10px; border-radius: 2px;
  }}

  /* ── Diff summary ── */
  #diff-summary {{
    margin-top: 12px;
    padding: 10px 14px;
    background: #1e0a3c;
    border: 1px solid #7c3aed55;
    border-radius: 8px;
    font-size: 11px;
    color: #c4b5fd;
    display: none;
  }}
</style>
</head>
<body>

<!-- ── Control bar ──────────────────────────── -->
<div class="controls">
  <button class="btn-init" id="initBtn" onclick="initAudio()">▶ ENABLE AUDIO</button>
  <button class="btn-beep" id="beepBtn" onclick="testBeep()" disabled>♪ TEST</button>

  <label>BPM</label>
  <input type="range" id="bpmSlider" min="60" max="450" value="{bpm}" oninput="updateBpm(this.value)" disabled>
  <span class="bpm-val" id="bpmVal">{bpm}</span>

  <label style="color:#a78bfa;">KEY OFFSET</label>
  <input type="range" id="keyOffset" min="-12" max="12" value="5" oninput="updateKeyOffset(this.value)" disabled style="accent-color:#a78bfa; width:80px;">
  <span class="bpm-val" id="keyOffsetVal" style="color:#a78bfa; min-width:30px;">+5</span>

  <label>PLAY</label>
  <select id="seqSelect" disabled>
    <option value="wt">Wild-Type</option>
    <option value="mut">Mutant</option>
  </select>

  <button class="btn-play" id="playBtn" onclick="togglePlay()" disabled>▶ PLAY</button>
  <button class="btn-stop" onclick="stopAll()">■ STOP</button>

  <span id="status">— audio off —</span>
</div>

<!-- ── Grids ──────────────────────────────────── -->
<div class="grids-wrapper">
  <div class="seq-panel">
    <div class="panel-title">
      🧬 Wild-Type
      <span class="badge" id="wt-len">0 aa</span>
    </div>
    <div class="grid" id="wt-grid"></div>
  </div>

  <div class="seq-panel">
    <div class="panel-title">
      ⚗️ Mutant
      <span class="badge mut-badge" id="mut-badge">0 mutations</span>
    </div>
    <div class="grid" id="mut-grid"></div>
  </div>
</div>

<!-- ── Diff summary ─────────────────────────── -->
<div id="diff-summary"></div>

<!-- ── Legend ───────────────────────────────── -->
<div class="legend" style="margin-top:14px; padding: 0 4px;">
  <div class="legend-item"><div class="legend-dot" style="background:var(--s1)"></div>Hydrophobic — vibraphone</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--s2)"></div>Polar uncharged — piano</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--s3)"></div>Positive charged — harp (warm)</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--s4)"></div>Negative charged — harp (bright)</div>
  <div class="legend-item"><div class="legend-dot" style="background:transparent;border:2px solid #a78bfa;"></div>Mutated — piano + key offset</div>
</div>

<script>
const WT  = {wt_json};
const MUT = {mut_json};
const AM  = {amino_json};

let part, playing = false;

// ── Render grids ──────────────────────────────
function renderGrids() {{
  const wtDiv  = document.getElementById('wt-grid');
  const mutDiv = document.getElementById('mut-grid');
  wtDiv.innerHTML = ''; mutDiv.innerHTML = '';

  document.getElementById('wt-len').textContent = WT.length + ' aa';

  let mutCount = 0;
  for (let i = 0; i < Math.max(WT.length, MUT.length); i++) {{
    const wAA = WT[i]  || '?';
    const mAA = MUT[i] || '?';
    const isMut = wAA !== mAA;
    if (isMut) mutCount++;

    const wa = AM[wAA] || {{s:1}};
    const ma = AM[mAA] || {{s:1}};

    const wt = makeTile(wAA, wa.s, i, 'wt', false, i+1);
    const mt = makeTile(mAA, ma.s, i, 'mut', isMut, i+1);
    wtDiv.appendChild(wt);
    mutDiv.appendChild(mt);
  }}

  document.getElementById('mut-badge').textContent = mutCount + ' mutation' + (mutCount===1?'':'s');

  // Diff summary
  if (mutCount > 0) {{
    const diffs = [];
    for (let i = 0; i < Math.max(WT.length, MUT.length); i++) {{
      if ((WT[i]||'?') !== (MUT[i]||'?')) {{
        diffs.push(`#${{i+1}} ${{WT[i]||'?'}}→${{MUT[i]||'?'}}`);
      }}
    }}
    const el = document.getElementById('diff-summary');
    el.style.display = 'block';
    el.textContent = '⚗ Mutations: ' + diffs.join('  ·  ');
  }}
}}

function makeTile(aa, scale, idx, prefix, isMut, pos) {{
  const t = document.createElement('div');
  t.className = `tile s${{scale}}` + (isMut ? ' mutated' : '');
  t.id = `${{prefix}}-${{idx}}`;
  t.textContent = aa;
  t.title = `#${{pos}} ${{aa}}`;
  return t;
}}

// ── Audio ─────────────────────────────────────
// Instruments inspired by the original Max patch:
//   Group 1 (Hydrophobic)      → Vibraphone  (FM mallet synthesis)
//   Group 2 (Polar uncharged)  → Piano       (Salamander real samples)
//   Group 3 (Positive charged) → Harp low    (PluckSynth, warm)
//   Group 4 (Negative charged) → Harp high   (PluckSynth, bright)
//   Mutations                  → Piano + Key Offset (original deviation indicator)

let vibraSynth, pianoSampler, pianoLoaded = false;
let masterComp, room;
let keyOffsetSemitones = 5;

// ── Semitone shift utility ────────────────────
function semitoneShift(note, semitones) {{
  const notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
  const m = note.match(/^([A-G]#?)(\d+)$/);
  if (!m) return note;
  let idx = notes.indexOf(m[1]);
  let oct = parseInt(m[2]);
  idx += semitones;
  while (idx >= 12) {{ idx -= 12; oct++; }}
  while (idx <  0)  {{ idx += 12; oct--; }}
  return notes[idx] + oct;
}}

function updateKeyOffset(val) {{
  keyOffsetSemitones = parseInt(val);
  const sign = val >= 0 ? '+' : '';
  document.getElementById('keyOffsetVal').textContent = sign + val;
}}

async function initAudio() {{
  await Tone.start();

  // Master compressor — glues everything like a mixing desk
  masterComp = new Tone.Compressor({{
    threshold: -18, ratio: 3.5, attack: 0.05, release: 0.3, knee: 8
  }}).toDestination();

  // Small chamber room reverb — intimate, like a recital hall
  room = new Tone.Reverb({{ decay: 1.6, wet: 0.25, preDelay: 0.015 }}).connect(masterComp);

  // ── Vibraphone (Group 1 — Hydrophobic) ──────────────────────────────────
  // FMSynth: harmonicity 1 = pure mallet, low modIdx = metallic shimmer.
  // Fast attack (mallet strike), decaying sustain = vibraphone resonance.
  vibraSynth = new Tone.PolySynth(Tone.FMSynth, {{
    harmonicity: 1,
    modulationIndex: 2.5,
    oscillator: {{ type: 'sine' }},
    envelope: {{ attack: 0.001, decay: 0.8, sustain: 0.3, release: 1.6 }},
    modulation: {{ type: 'sine' }},
    modulationEnvelope: {{ attack: 0.001, decay: 0.5, sustain: 0.1, release: 0.8 }}
  }}).connect(room);
  vibraSynth.volume.value = -6;

  // ── Piano sampler (Groups 2 + mutations) — Salamander real recordings ───
  // Closest available equivalent to the original Max "Bright Acoustic Piano".
  document.getElementById('status').textContent = '⏳ loading piano samples…';
  pianoSampler = new Tone.Sampler({{
    urls: {{
      A0:'A0.mp3', C1:'C1.mp3', 'D#1':'Ds1.mp3', 'F#1':'Fs1.mp3',
      A1:'A1.mp3', C2:'C2.mp3', 'D#2':'Ds2.mp3', 'F#2':'Fs2.mp3',
      A2:'A2.mp3', C3:'C3.mp3', 'D#3':'Ds3.mp3', 'F#3':'Fs3.mp3',
      A3:'A3.mp3', C4:'C4.mp3', 'D#4':'Ds4.mp3', 'F#4':'Fs4.mp3',
      A4:'A4.mp3', C5:'C5.mp3', 'D#5':'Ds5.mp3', 'F#5':'Fs5.mp3',
      A5:'A5.mp3', C6:'C6.mp3', 'D#6':'Ds6.mp3', 'F#6':'Fs6.mp3',
      A6:'A6.mp3', C7:'C7.mp3', 'D#7':'Ds7.mp3', 'F#7':'Fs7.mp3',
      A7:'A7.mp3', C8:'C8.mp3'
    }},
    release: 1.2,
    baseUrl: 'https://tonejs.github.io/audio/salamander/',
    onload: () => {{
      pianoLoaded = true;
      document.getElementById('status').textContent = '— ready —';
    }}
  }}).connect(room);
  pianoSampler.volume.value = -4;

  const btn = document.getElementById('initBtn');
  btn.textContent = '✓ AUDIO READY';
  btn.className = 'btn-init ready';
  document.getElementById('playBtn').disabled   = false;
  document.getElementById('beepBtn').disabled   = false;
  document.getElementById('bpmSlider').disabled = false;
  document.getElementById('seqSelect').disabled = false;
  document.getElementById('keyOffset').disabled = false;
  document.getElementById('status').textContent = '⏳ loading piano samples…';
}}

// ── Harp voices (PluckSynth per note) ────────────────────────────────────
function pluckHarp(note, time, bright) {{
  const h = new Tone.PluckSynth({{
    attackNoise: bright ? 0.8 : 0.4,
    dampening:   bright ? 4200 : 2800,
    resonance:   0.96
  }}).connect(room);
  h.volume.value = bright ? -5 : -4;
  h.triggerAttackRelease(note, '8n', time);
}}

// ── Main note router ─────────────────────────────────────────────────────
function playNote(group, note, duration, time) {{
  if      (group === 1) vibraSynth.triggerAttackRelease(note, duration, time);
  else if (group === 2 && pianoLoaded) pianoSampler.triggerAttackRelease(note, duration, time);
  else if (group === 2) vibraSynth.triggerAttackRelease(note, duration, time);
  else if (group === 3) pluckHarp(note, time, false);
  else if (group === 4) pluckHarp(note, time, true);
}}

// ── Mutation: piano + Key Offset (mirrors original Max deviation indicator)
function playMutationNote(note, time) {{
  const shifted = semitoneShift(note, keyOffsetSemitones);
  if (pianoLoaded) pianoSampler.triggerAttackRelease(shifted, '2n', time);
  else             vibraSynth.triggerAttackRelease(shifted, '2n', time);
}}

function testBeep() {{
  if (!vibraSynth) return;
  const t = Tone.now();
  playNote(1, 'C4', '4n', t);
  playNote(2, 'E4', '4n', t + 0.3);
  playNote(3, 'G3', '4n', t + 0.6);
  playNote(4, 'C5', '4n', t + 0.9);
  playMutationNote('E4', t + 1.5);
}}

function updateBpm(val) {{
  Tone.Transport.bpm.value = val;
  document.getElementById('bpmVal').textContent = val;
}}

function setupPart() {{
  Tone.Transport.cancel();
  if (part) part.dispose();

  const seqType = document.getElementById('seqSelect').value;
  const seq     = seqType === 'wt' ? WT : MUT;
  const prefix  = seqType;

  // Note durations per group — strings sustain, pizz short, etc.
  const durations = {{ 1: '4n', 2: '8n', 3: '8n', 4: '16n' }};
  // Octave per group — strings low, woodwind mid, brass mid, pizz upper mid
  const octaves   = {{ 1: 3, 2: 4, 3: 4, 4: 5 }};

  const mutatedIdx = new Set();
  for (let i = 0; i < Math.max(WT.length, MUT.length); i++) {{
    if ((WT[i]||'?') !== (MUT[i]||'?')) mutatedIdx.add(i);
  }}

  const events = seq.map((aa, i) => {{
    const d = AM[aa];
    if (!d) return null;
    const isMut = mutatedIdx.has(i);
    // Mutations in mutant mode: bell, one octave above its group
    const octave = octaves[d.s] + (isMut && seqType === 'mut' ? 1 : 0);
    return {{ time: i * 0.25, note: `${{d.n}}${{octave}}`, group: d.s, i, prefix, isMut }};
  }}).filter(Boolean);

  part = new Tone.Part((time, val) => {{
    if (val.isMut && seqType === 'mut') {{
      playMutationNote(val.note, time);
    }} else {{
      playNote(val.group, val.note, durations[val.group], time);
    }}

    Tone.Draw.schedule(() => {{
      document.querySelectorAll('.tile').forEach(t => t.classList.remove('active'));
      const el = document.getElementById(`${{val.prefix}}-${{val.i}}`);
      if (el) el.classList.add('active');
    }}, time);
  }}, events).start(0);

  Tone.Transport.loop = true;
  Tone.Transport.loopEnd = events.length * 0.25;
}}

function togglePlay() {{
  const btn = document.getElementById('playBtn');
  if (Tone.Transport.state === 'started') {{
    Tone.Transport.pause();
    playing = false;
    btn.textContent = '▶ PLAY';
    document.getElementById('status').textContent = '— paused —';
  }} else {{
    setupPart();
    Tone.Transport.bpm.value = parseInt(document.getElementById('bpmSlider').value);
    Tone.Transport.start();
    playing = true;
    btn.textContent = '⏸ PAUSE';
    const which = document.getElementById('seqSelect').value === 'wt' ? 'WT' : 'Mutant';
    document.getElementById('status').textContent = `♪ playing ${{which}}…`;
  }}
}}

function stopAll() {{
  Tone.Transport.stop();
  Tone.Transport.seconds = 0;
  playing = false;
  document.getElementById('playBtn').textContent = '▶ PLAY';
  document.getElementById('status').textContent = '— stopped —';
  document.querySelectorAll('.tile').forEach(t => t.classList.remove('active'));
}}

// ── Init ──────────────────────────────────────
renderGrids();
</script>
</body>
</html>
"""
    return html


# ── Session state defaults ───────────────────────────────────────────────────
for key, default in [
    ("wt_seq", ""),
    ("mut_seq", ""),
    ("loaded", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Custom CSS for the Streamlit shell ───────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] { font-family: 'Space Mono', monospace; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }

section[data-testid="stSidebar"] { background: #0f1923; border-right: 1px solid #1e2d3d; }
.block-container { padding-top: 2rem; max-width: 1200px; }

div[data-testid="stTextArea"] textarea {
    font-family: 'Space Mono', monospace !important;
    font-size: 12px !important;
    background: #0f1923 !important;
    border: 1px solid #1e2d3d !important;
    color: #60a5fa !important;
}

div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input {
    font-family: 'Space Mono', monospace !important;
    background: #0f1923 !important;
    color: white !important;
}

.mutation-info {
    background: #0f1923;
    border: 1px solid #1e2d3d;
    border-radius: 8px;
    padding: 12px 16px;
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: #64748b;
    margin-top: 8px;
}
.mutation-info .highlight { color: #a78bfa; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("# 🧬 Protein Synth 2.0")
st.markdown("<p style='color:#64748b; font-family:Space Mono,monospace; font-size:13px; margin-top:-10px;'>Bradley Lab · Sequence Sonification</p>", unsafe_allow_html=True)
st.divider()

# ── Sidebar: Mutations ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚗️ Mutation Tools")
    st.caption("Mutations apply to the Mutant sequence.")

    if st.session_state.loaded:
        st.markdown("---")
        st.markdown("**Single Residue Mutation**")
        col1, col2 = st.columns(2)
        with col1:
            mut_pos = st.number_input("Position #", min_value=1, max_value=max(len(st.session_state.wt_seq), 1), value=1, step=1, key="mut_pos")
        with col2:
            mut_aa = st.text_input("New AA", value="K", max_chars=1, key="mut_aa").upper().strip()

        if st.button("Apply Single Mutation", use_container_width=True):
            if mut_aa in AMINO_MAP:
                st.session_state.mut_seq = apply_single_mutation(st.session_state.mut_seq, mut_pos, mut_aa)
                st.rerun()
            else:
                st.error(f"'{mut_aa}' is not a recognised amino acid.")

        st.markdown("---")
        st.markdown("**Global Swap**")
        col3, col4 = st.columns(2)
        with col3:
            swap_from = st.text_input("Replace ALL", value="L", max_chars=1, key="swap_from").upper().strip()
        with col4:
            swap_to = st.text_input("With", value="K", max_chars=1, key="swap_to").upper().strip()

        if st.button("Apply Global Swap", use_container_width=True):
            if swap_from in AMINO_MAP and swap_to in AMINO_MAP:
                st.session_state.mut_seq = apply_global_swap(st.session_state.mut_seq, swap_from, swap_to)
                st.rerun()
            else:
                st.error("Both amino acids must be valid single-letter codes.")

        st.markdown("---")
        if st.button("↺ Reset Mutant to WT", use_container_width=True):
            st.session_state.mut_seq = st.session_state.wt_seq
            st.rerun()

        # ── Mutation count readout ──
        if st.session_state.wt_seq and st.session_state.mut_seq:
            n_mut = count_mutations(st.session_state.wt_seq, st.session_state.mut_seq)
            st.markdown(f"""
            <div class="mutation-info">
                Mutations vs WT: <span class="highlight">{n_mut}</span><br>
                WT length: <span class="highlight">{len(st.session_state.wt_seq)}</span> aa<br>
                Mutant length: <span class="highlight">{len(st.session_state.mut_seq)}</span> aa
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Load a sequence first to use mutation tools.")

# ── Main: Sequence input ──────────────────────────────────────────────────────
st.markdown("### 1 · Paste Sequence")
st.caption("Accepts raw one-letter codes or FASTA format.")

raw_input = st.text_area(
    "Protein sequence",
    height=90,
    placeholder=">MyProtein\nMKTAYIAKQRQISFVKSHFSRQTEAERNKHHSSLLTAYGNSQ...",
    label_visibility="collapsed",
)

col_load, col_bpm_label, col_bpm = st.columns([2, 1, 3])
with col_load:
    load_clicked = st.button("🔬 Load & Visualize", type="primary", use_container_width=True)
with col_bpm_label:
    st.markdown("<div style='padding-top:8px; font-size:12px; color:#64748b;'>Tempo (BPM)</div>", unsafe_allow_html=True)
with col_bpm:
    bpm = st.slider("BPM", 60, 450, 120, label_visibility="collapsed")

if load_clicked:
    cleaned = clean_sequence(raw_input)
    valid, unknown = validate_sequence(cleaned)
    if not valid:
        st.error("No valid amino acid residues found. Please check your input.")
    else:
        if unknown:
            st.warning(f"Skipped unrecognised characters: {', '.join(unknown)}")
        st.session_state.wt_seq = valid
        st.session_state.mut_seq = valid   # mutant starts as copy of WT
        st.session_state.loaded = True
        st.success(f"Loaded {len(valid)} residues.")
        st.rerun()

st.markdown("---")

# ── Main: Audio + Visualisation component ─────────────────────────────────────
if st.session_state.loaded and st.session_state.wt_seq:
    st.markdown("### 2 · Visualize & Play")

    component_html = build_audio_component(
        wt_seq=st.session_state.wt_seq,
        mut_seq=st.session_state.mut_seq,
        bpm=bpm,
    )

    # Height scales with sequence length, capped
    n_tiles = len(st.session_state.wt_seq)
    tile_rows = (n_tiles // 20) + 1
    component_height = min(180 + tile_rows * 42, 900)

    st.components.v1.html(component_html, height=component_height + 120, scrolling=False)

    st.caption("💡 Click **ENABLE AUDIO** inside the panel first, then **PLAY**. Switch between Wild-Type and Mutant using the dropdown. Purple outlines = mutated residues.")

else:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color:#1e2d3d; border: 2px dashed #1e2d3d; border-radius:12px; margin-top:20px;">
        <div style="font-size:3rem;">🧬</div>
        <div style="font-family:'Space Mono',monospace; font-size:13px; margin-top:10px; color:#334155;">
            Paste a sequence above and click <strong style="color:#60a5fa;">Load & Visualize</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
