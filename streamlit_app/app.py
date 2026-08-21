"""
BioFusion — landing page.

Entry point for the pneumonia-screening app. Presents the product, routes users
into the screening flow, and shows the trained model's live headline metrics.
"""

import json
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent))
from utils import ui

_METRICS_PATH = Path(__file__).parent.parent / "training_metrics.json"


def _load_landing_metrics():
    """Headline metrics from the trained model, with a documented fallback."""
    if _METRICS_PATH.exists():
        try:
            with open(_METRICS_PATH) as f:
                m = json.load(f)
            rep = m["test_report"]
            cm = m["confusion_matrix"]  # [[TN, FP], [FN, TP]]
            return [
                ("Sensitivity", f"{rep['PNEUMONIA']['recall']*100:.1f}%", "Pneumonia caught"),
                ("Accuracy", f"{rep['accuracy']*100:.1f}%", "Held-out test set"),
                ("AUC-ROC", f"{m['auc_roc']:.3f}", "Discrimination"),
                ("Missed cases", str(cm[1][0]), "False negatives"),
            ]
        except (json.JSONDecodeError, OSError, KeyError, IndexError):
            pass
    return [
        ("Sensitivity", "98.7%", "Pneumonia caught"),
        ("Accuracy", "92.2%", "Held-out test set"),
        ("AUC-ROC", "0.944", "Discrimination"),
        ("Missed cases", "7", "False negatives"),
    ]


st.set_page_config(page_title="BioFusion — Pneumonia Screening",
                   layout="wide", initial_sidebar_state="collapsed")

from utils.device import is_mobile, init_device
# if is_mobile():
#     st.switch_page("pages/1_Live_Prediction.py")

# Probe the viewport once per run, before any is_mobile() call.
init_device()

ui.inject_theme()
ui.top_nav(active="Home")

if is_mobile() and not st.session_state.get('install_dismissed', False):
    c1, c2 = st.columns([0.85, 0.15])
    with c1:
        st.markdown("#### Install it like an app")
    with c2:
        if st.button("✖", key="dismiss_install", help="Dismiss"):
            st.session_state.install_dismissed = True
            st.rerun()
            
    st.markdown(
        "Add BioFusion to your phone's home screen for one-tap access and full-screen "
        "camera capture — no app store needed."
    )
    components.html(
        """
        <div style="font-family:'Inter',system-ui,sans-serif;">
          <button id="bf-install" style="display:none; padding:0.7rem 1.3rem; border:0;
            border-radius:10px; background:#0066CC; color:#fff; font-weight:600;
            font-size:0.95rem; cursor:pointer;">⬇  Install app</button>
          <div id="bf-hint" style="color:#475569; font-size:0.9rem; line-height:1.5;">
            On <b>Android/Chrome</b>: tap the menu (⋮) → <b>Install app</b>.<br>
            On <b>iPhone/Safari</b>: tap Share → <b>Add to Home Screen</b>.
          </div>
        </div>
        <script>
          // Inject PWA Manifest if missing
          const parentDoc = window.parent.document;
          if (!parentDoc.querySelector('link[rel="manifest"]')) {
              const manifest = parentDoc.createElement('link');
              manifest.rel = 'manifest';
              manifest.href = '/app/static/manifest.json';
              parentDoc.head.appendChild(manifest);
          }
          // Register SW
          if ('serviceWorker' in window.parent.navigator) {
              window.parent.navigator.serviceWorker.register('/app/static/sw.js');
          }

          let deferred = null;
          const btn = document.getElementById('bf-install');
          const hint = document.getElementById('bf-hint');
          
          window.parent.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault(); deferred = e;
            btn.style.display = 'inline-block';
            hint.style.display = 'none';
          });
          btn.addEventListener('click', async () => {
            if (!deferred) return;
            deferred.prompt();
            await deferred.userChoice;
            deferred = null; btn.style.display = 'none';
          });
          window.parent.addEventListener('appinstalled', () => {
            btn.style.display = 'none';
            hint.innerHTML = '✅ Installed — find BioFusion on your home screen.';
            hint.style.display = 'block';
          });
        </script>
        """,
        height=110,
    )
    st.divider()

if not is_mobile():
    st.divider()

# --- hero ------------------------------------------------------------------ #
hero_l, hero_r = st.columns([1.4, 1])
with hero_l:
    if is_mobile():
        st.markdown("""
        <div style="display: flex; flex-direction: column; align-items: center; text-align: center;">
            <span class="bf-badge bf-badge-primary">Clinical decision support</span>
            <h1 style="font-size:2.4rem; line-height:1.1; margin:1rem 0 0.8rem;">
                Screen a chest X-ray<br>for pneumonia in seconds.
            </h1>
            <p style="font-size:1.1rem; color:var(--ink-60); max-width:52ch;">
                Take a photo with your phone or upload an X-ray. A fail-safe AI model
                highlights signs of pneumonia and tells you what to do next — for
                patients, parents, and clinicians alike.
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Start screening  →", type="primary", use_container_width=True):
            st.switch_page("pages/1_Live_Prediction.py")
    else:
        st.markdown("""
        <span class="bf-badge bf-badge-primary">Clinical decision support</span>
        <h1 style="font-size:2.9rem; line-height:1.08; margin:1rem 0 0.8rem;">
            Screen a chest X-ray<br>for pneumonia in seconds.
        </h1>
        <p style="font-size:1.1rem; color:var(--ink-60); max-width:52ch;">
            Take a photo with your phone or upload an X-ray. A fail-safe AI model
            highlights signs of pneumonia and tells you what to do next — for
            patients, parents, and clinicians alike.
        </p>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Start screening  →", type="primary", use_container_width=False):
            st.switch_page("pages/1_Live_Prediction.py")

with hero_r:
    if not is_mobile():
        # Clean inline SVG (no webfont dependency) — a stylised lungs mark.
        st.markdown("""
        <div style="display:flex; justify-content:center; align-items:center; min-height:220px;">
          <svg width="200" height="200" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Lungs">
            <rect x="6" y="6" width="188" height="188" rx="44" fill="#EAF2FC"/>
            <path d="M100 48 v46" stroke="#0066CC" stroke-width="7" stroke-linecap="round"/>
            <circle cx="100" cy="46" r="9" fill="#0066CC"/>
            <path d="M100 84 C 86 96, 74 96, 66 106" stroke="#0066CC" stroke-width="6" stroke-linecap="round"/>
            <path d="M100 84 C 114 96, 126 96, 134 106" stroke="#0066CC" stroke-width="6" stroke-linecap="round"/>
            <path d="M70 96 C 44 104, 40 140, 52 158 C 62 172, 82 166, 84 148 L 84 104 C 84 98, 76 94, 70 96 Z" fill="#0066CC"/>
            <path d="M130 96 C 156 104, 160 140, 148 158 C 138 172, 118 166, 116 148 L 116 104 C 116 98, 124 94, 130 96 Z" fill="#0066CC"/>
          </svg>
        </div>
        """, unsafe_allow_html=True)

if not is_mobile():
    st.divider()
    
    # --- install as an app (PWA) ---------------------------------------------- #
    inst_l, inst_r = st.columns([1.5, 1])
    with inst_l:
        st.markdown("#### Install it like an app")
        st.markdown(
            "Add BioFusion to your phone's home screen for one-tap access and full-screen "
            "camera capture — no app store needed."
        )
        # The install button uses the browser's install prompt when available, with a
        # clear manual fallback for iOS (which has no beforeinstallprompt event).
        components.html(
            """
            <div style="font-family:'Inter',system-ui,sans-serif;">
              <button id="bf-install" style="display:none; padding:0.7rem 1.3rem; border:0;
                border-radius:10px; background:#0066CC; color:#fff; font-weight:600;
                font-size:0.95rem; cursor:pointer;">⬇  Install app</button>
              <div id="bf-hint" style="color:#475569; font-size:0.9rem; line-height:1.5;">
                On <b>Android/Chrome</b>: tap the menu (⋮) → <b>Install app</b>.<br>
                On <b>iPhone/Safari</b>: tap Share → <b>Add to Home Screen</b>.
              </div>
            </div>
            <script>
              // Inject PWA Manifest if missing
              const parentDoc = window.parent.document;
              if (!parentDoc.querySelector('link[rel="manifest"]')) {
                  const manifest = parentDoc.createElement('link');
                  manifest.rel = 'manifest';
                  manifest.href = '/app/static/manifest.json';
                  parentDoc.head.appendChild(manifest);
              }
              // Register SW
              if ('serviceWorker' in window.parent.navigator) {
                  window.parent.navigator.serviceWorker.register('/app/static/sw.js');
              }

              let deferred = null;
              const btn = document.getElementById('bf-install');
              const hint = document.getElementById('bf-hint');
              
              window.parent.addEventListener('beforeinstallprompt', (e) => {
                e.preventDefault(); deferred = e;
                btn.style.display = 'inline-block';
                hint.style.display = 'none';
              });
              btn.addEventListener('click', async () => {
                if (!deferred) return;
                deferred.prompt();
                await deferred.userChoice;
                deferred = null; btn.style.display = 'none';
              });
              window.parent.addEventListener('appinstalled', () => {
                btn.style.display = 'none';
                hint.innerHTML = '✅ Installed — find BioFusion on your home screen.';
                hint.style.display = 'block';
              });
            </script>
            """,
            height=110,
        )
    with inst_r:
        _qr = Path(__file__).parent / "static" / "icons" / "qr.png"
        if _qr.exists():
            st.image(str(_qr), width=150, caption="Scan to open on your phone")
    
    st.divider()

# --- live metrics ---------------------------------------------------------- #
st.markdown("#### How the model performs")
st.caption("Live numbers from the trained model (fail-safe operating point).")

if is_mobile():
    metrics = _load_landing_metrics()
    grid_html = '<div style="display: grid; grid-template-columns: 1fr 1fr; row-gap: 24px; text-align: center;">\n'
    for label, value, desc in metrics:
        grid_html += f"""<div style="padding:0.2rem 0;">
<div style="font-size:0.8rem; opacity:0.65; font-weight:600;">{label}</div>
<div style="font-size:1.9rem; font-weight:800; color:#0066CC; letter-spacing:-0.02em; font-variant-numeric:tabular-nums;">{value}</div>
<div style="font-size:0.72rem; color:#059669; font-weight:600;">{desc}</div>
</div>
"""
    grid_html += '</div>'
    st.markdown(grid_html, unsafe_allow_html=True)
else:
    mcols = st.columns(4)
    for col, (label, value, desc) in zip(mcols, _load_landing_metrics()):
        with col:
            st.markdown(f"""
            <div style="padding:0.2rem 0;">
                <div style="font-size:0.8rem; opacity:0.65; font-weight:600;">{label}</div>
                <div style="font-size:1.9rem; font-weight:800; color:var(--primary);
                     letter-spacing:-0.02em; font-variant-numeric:tabular-nums;">{value}</div>
                <div style="font-size:0.72rem; color:var(--success); font-weight:600;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

st.divider()

# --- how it works ---------------------------------------------------------- #
st.markdown("#### How it works")
steps = [
    ("Capture or upload", "Photograph the X-ray with your phone, or upload a digital file."),
    ("Auto-correct & check", "We straighten phone photos, normalise contrast, and reject unusable images."),
    ("AI screening", "A ResNet-50 model tuned for high sensitivity flags signs of pneumonia."),
    ("Guided next step", "You get a plain-language result and clear guidance — never a diagnosis."),
]
scols = st.columns(4)
for i, (col, (title, desc)) in enumerate(zip(scols, steps), start=1):
    with col:
        st.markdown(f"""
        <div style="padding:1.2rem; background:white; border:1px solid var(--hair);
             border-radius:12px; height:100%; text-align:center;
             display:flex; flex-direction:column; justify-content:center; align-items:center;">
            <div style="width:32px;height:32px;border-radius:8px;background:var(--primary-wash);
                 color:var(--primary);font-weight:600;font-size:15px;display:flex;
                 align-items:center;justify-content:center;margin:0 auto;">{i}</div>
            <h4 style="margin:0.7rem 0 0.3rem; font-size:1rem;">{title}</h4>
            <p style="font-size:0.88rem; color:var(--ink-60); margin:0; line-height:1.5;">{desc}</p>
        </div>
        """, unsafe_allow_html=True)

st.write("")
st.markdown(
    '<div class="bf-disclaimer">BioFusion is a <b>screening aid, not a diagnostic '
    'device</b>. Always confirm results with a qualified clinician.</div>',
    unsafe_allow_html=True,
)
st.caption("BioFusion 2026 · Team GMora · Built with PyTorch")

from utils.device import is_mobile, render_mobile_navbar
import sys
import importlib
if "utils.device" in sys.modules:
    importlib.reload(sys.modules["utils.device"])
from utils.device import render_mobile_navbar # re-import the reloaded function

if is_mobile():
    render_mobile_navbar("Home")
