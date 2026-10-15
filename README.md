# Data Sonification — Bradley Lab

Turns protein sequences into music so you can hear where, and how severely, a mutation changes a protein.
Opens with a sickle cell demo (hemoglobin β, Glu6Val), then a "Try it yourself" mode for your own sequences.

The whole app is `index.html` (plain HTML + [Tone.js](https://tonejs.github.io/)); there is no build step.

- **GitHub Pages / any static host:** serve `index.html`.
- **Locally:** open `index.html` in a browser.
- **Streamlit:** `streamlit run v_2protein_synth_app.py` (embeds `index.html`).

The sonification model is documented in the comment at the top of `index.html`.

© 2026 University of Kentucky
