"""
Screening — the core BioFusion flow.

Patients/parents and clinicians use the same page and the same model; the role
selector tunes how the result is shown. Input can be a live camera capture (for
phones) or an uploaded file, and either a digital X-ray or a photo of a film.
Every image passes a quality gate before inference; photos are perspective- and
contrast-corrected first. Results are shown as a triage band with escalation
guidance, never as a diagnosis.
"""

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import (load_model, predict, preprocess_image, load_image,
                   create_gradcam_visualization, rectify_mobile_xray,
                   assess_quality, triage, ui)
import importlib
importlib.reload(ui)
from utils.device import is_mobile, init_device, render_mobile_navbar

st.set_page_config(page_title="Screening | BioFusion", page_icon="🫁",
                   layout="wide", initial_sidebar_state="collapsed")

# Probe the viewport once per run, before any is_mobile() call.
init_device()

ui.inject_theme()
ui.top_nav(active="Screening")

# Fixed-position navbar, so DOM order is irrelevant to placement. Rendering it
# ahead of get_model() keeps it on screen while the model is still loading.
if is_mobile():
    render_mobile_navbar("Prediction")
if not is_mobile():
    st.divider()

# --- model + fail-safe threshold ------------------------------------------- #
WEIGHTS_PATH = Path(__file__).parent.parent.parent / "pneumonia_resnet50_best.pth"
METRICS_PATH = Path(__file__).parent.parent.parent / "training_metrics.json"


@st.cache_resource
def get_model():
    weights = str(WEIGHTS_PATH) if WEIGHTS_PATH.exists() else None
    model, device = load_model(weights)
    return model, device, weights is not None


@st.cache_data
def get_threshold():
    """Fail-safe decision threshold from training; default 0.5 if unavailable."""
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH) as f:
                return float(json.load(f)["operating_point"]["threshold"])
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            pass
    return 0.5


with st.spinner("Starting the screening engine…"):
    model, device, using_trained_weights = get_model()
threshold = get_threshold()

# --- flow control ----------------------------------------------------------- #
mobile = is_mobile()

def run_analysis_and_render_results(captured, is_photo, clinician, mobile):
    if not mobile:
        st.divider()
    original_image = load_image(captured)

    # 2 · Quality gate
    quality = assess_quality(original_image, phone_mode=is_photo)
    for w in quality.warnings:
        st.markdown(f"<p style='color: #ea580c; text-align: center; font-weight: 500; font-size: 14px;'><svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='#ea580c' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' style='margin-bottom:-2px; margin-right:4px;'><path d='M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z'/><line x1='12' y1='9' x2='12' y2='13'/><line x1='12' y1='17' x2='12.01' y2='17'/></svg>{w}</p>", unsafe_allow_html=True)
    if not quality.ok:
        st.error("**This image can't be screened reliably:**")
        for issue in quality.issues:
            st.markdown(f"- {issue}")
        st.stop()

    # 3 · Staged analysis animation
    state = {}

    def _prepare():
        if is_photo:
            rect = rectify_mobile_xray(original_image)
            state["rect"] = rect
            state["image"] = rect.image
        else:
            state["image"] = original_image

    def _infer():
        img = state["image"]
        tensor = preprocess_image(img)
        state["tensor"] = tensor
        pred_class, confidence, probabilities = predict(model, tensor, device)
        state["pred_class"] = pred_class
        state["probs"] = probabilities

    def _triage():
        state["triage"] = triage(float(state["probs"][1]), threshold)

    stages = [("Checking image quality", None)]
    if is_photo:
        stages.append(("Correcting perspective & contrast", _prepare))
    else:
        stages.append(("Preparing the radiograph", _prepare))
    stages += [
        ("Running the screening model", _infer),
        ("Preparing your result", _triage),
    ]
    ui.run_analysis_animation(stages)

    image = state["image"]
    input_tensor = state["tensor"]
    pred_class = state["pred_class"]
    probabilities = state["probs"]
    t = state["triage"]

    if is_photo:
        rect = state["rect"]

    with st.container(key="section_result"):
        if not mobile:
            st.markdown("<div class='bf-step-badge'>Step 3</div>", unsafe_allow_html=True)
        st.markdown("<h4 style='margin-bottom:1rem; color:var(--black);'>Result</h4>", unsafe_allow_html=True)
        
        if mobile:
            ui.render_result_card(t, clinician=clinician, is_mobile=True)
            st.image(image, caption="Screened image", use_container_width=True)
            if is_photo:
                with st.expander("Original photo"):
                    st.image(original_image, use_container_width=True)
        else:
            result_col, image_col = st.columns([1.1, 1])
            with result_col:
                ui.render_result_card(t, clinician=clinician)
            with image_col:
                st.image(image, caption="Screened image", use_container_width=True)
                if is_photo:
                    with st.expander("Original photo"):
                        st.image(original_image, use_container_width=True)

        # 5 · Clinicians get Grad-CAM
        if clinician or mobile:
            if not mobile:
                st.divider()
            st.markdown("##### Explainability (Grad-CAM)")
            try:
                with st.spinner("Generating heatmap…"):
                    heatmap, overlay = create_gradcam_visualization(
                        model, input_tensor, image, device, pred_class)
                
                if mobile:
                    st.image(overlay, caption="Grad-CAM — regions driving the prediction", use_container_width=True)
                else:
                    gc1, gc2 = st.columns(2)
                    with gc1:
                        st.image(image, caption="Input", use_container_width=True)
                    with gc2:
                        st.image(overlay, caption="Grad-CAM — regions driving the prediction",
                                 use_container_width=True)
            except Exception as exc:
                st.markdown("<p style='color: #ea580c; text-align: center; font-weight: 500; font-size: 14px;'><svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='#ea580c' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' style='margin-bottom:-2px; margin-right:4px;'><path d='M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z'/><line x1='12' y1='9' x2='12' y2='13'/><line x1='12' y1='17' x2='12.01' y2='17'/></svg>Grad-CAM unavailable for this image.</p>", unsafe_allow_html=True)
                st.caption(f"Reason: {exc}")

        if not mobile:
            st.markdown("**Class probabilities**")
            pc1, pc2 = st.columns(2)
            pc1.metric("Normal", f"{probabilities[0]*100:.1f}%")
            pc2.metric("Pneumonia", f"{probabilities[1]*100:.1f}%")

if mobile:
    # --- Mobile 2-Step Wizard Flow ---
    if "mobile_step" not in st.session_state:
        st.session_state.mobile_step = 1

    if st.session_state.mobile_step == 1:
        ui.page_header("Chest X-ray screening", "Take a photo or upload an X-ray to check for signs of pneumonia.")
        
        
        if "role" not in st.session_state:
            st.session_state.role = ui.ROLE_PATIENT
            
        def on_mobile_role_change():
            if st.session_state.mobile_role_pills:
                st.session_state.role = st.session_state.mobile_role_pills
                
        if st.session_state.get("mobile_role_pills") != st.session_state.get("role"):
            st.session_state.mobile_role_pills = st.session_state.get("role")
        
        with st.container(key="section_role_mobile"):
            st.pills("I am a...", [ui.ROLE_PATIENT, ui.ROLE_CLINICIAN], selection_mode="single", key="mobile_role_pills", on_change=on_mobile_role_change)
                
        with st.container(key="section_upload_mobile"):
            st.markdown("<p style='text-align: center; font-weight: 500; color: #4B5563; margin-bottom: 1rem;'>Provide the X-ray</p>", unsafe_allow_html=True)
            
            st.markdown("""
            <style>
            /* --- 1. Dropzone (Before Upload) --- */
            .st-key-file_mobile section {
                background-color: #ffffff !important;
                border: 2px dashed #d0d7de !important;
                border-radius: 12px !important;
                padding: 40px 20px !important;
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
            }
            .st-key-file_mobile section svg {
                display: none !important;
            }
            .st-key-file_mobile section::before {
                content: "";
                background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'/%3E%3Cpolyline points='17 8 12 3 7 8'/%3E%3Cline x1='12' y1='3' x2='12' y2='15'/%3E%3C/svg%3E");
                background-repeat: no-repeat;
                background-position: center;
                display: flex;
                align-items: center;
                justify-content: center;
                width: 70px;
                height: 70px;
                border-radius: 50%;
                border: 3px solid #cbd5e1;
                color: #64748b;
                margin-bottom: 16px;
                transition: all 0.3s ease;
            }
            .st-key-file_mobile section > div {
                display: none !important;
            }
            
            /* Button inside dropzone */
            html body .stApp .st-key-file_mobile section button {
                background-color: #0066CC !important;
                color: white !important;
                border: none !important;
                border-radius: 24px !important;
                padding: 10px 32px !important;
                font-weight: 600 !important;
                font-size: 15px !important;
                position: relative;
                overflow: hidden;
            }
            html body .stApp .st-key-file_mobile section button:hover {
                background-color: #005bb5 !important;
                color: white !important;
            }
            html body .stApp .st-key-file_mobile section button::after {
                content: "Upload Image";
                position: absolute;
                left: 0; right: 0; top: 0; bottom: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                background-color: inherit;
                border-radius: inherit;
                color: white !important;
            }
            
            /* --- 2. Uploading Animation (During Upload) --- */
            @keyframes spin-ring {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .st-key-file_mobile section {
                position: relative;
            }
            .st-key-file_mobile:has([data-testid="stProgressBar"]) section::after,
            .st-key-file_mobile:has(progress) section::after,
            .st-key-file_mobile:has([role="progressbar"]) section::after {
                content: "";
                position: absolute;
                top: 40px;
                left: 50%;
                margin-left: -38px;
                width: 76px;
                height: 76px;
                border-radius: 50%;
                border: 3px solid transparent;
                border-top-color: #007aff;
                animation: spin-ring 1s linear infinite;
                z-index: 2;
                box-sizing: border-box;
            }

            /* --- 3. Uploaded File Box (After Upload) --- */
            .st-key-file_mobile div[data-testid="stUploadedFile"] {
                background-color: #ffffff !important;
                border: 2px solid #007aff !important;
                border-radius: 12px !important;
                padding: 30px 20px !important;
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
                justify-content: center !important;
            }
            /* Hide the small file icon and size text */
            .st-key-file_mobile div[data-testid="stUploadedFile"] > div > svg,
            .st-key-file_mobile div[data-testid="stUploadedFile"] > div > div > small {
                display: none !important;
            }
            /* Show the filename nicely */
            .st-key-file_mobile div[data-testid="stUploadedFile"] > div > div > span {
                font-size: 14px;
                color: #475569;
                font-weight: 500;
                margin-bottom: 12px;
                display: block;
                text-align: center;
            }
            .st-key-file_mobile div[data-testid="stUploadedFile"]::before {
                content: "";
                background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='36' height='36' viewBox='0 0 24 24' fill='none' stroke='%23007aff' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E");
                background-repeat: no-repeat;
                background-position: center;
                display: flex;
                align-items: center;
                justify-content: center;
                width: 70px;
                height: 70px;
                border-radius: 50%;
                border: 3px solid #007aff;
                color: #007aff;
                margin-bottom: 16px;
                font-weight: bold;
            }
            /* Style the remove button */
            .st-key-file_mobile div[data-testid="stUploadedFile"] button {
                background-color: #f1f5f9 !important;
                color: #64748b !important;
                border-radius: 24px !important;
                padding: 8px 24px !important;
                font-weight: 600 !important;
                font-size: 13px !important;
                position: relative;
                overflow: hidden;
                margin-top: 5px;
            }
            .st-key-file_mobile div[data-testid="stUploadedFile"] button svg {
                display: none !important; /* Hide the X icon */
            }
            .st-key-file_mobile div[data-testid="stUploadedFile"] button::after {
                content: "Remove";
                position: absolute;
                left: 0; right: 0; top: 0; bottom: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                background-color: inherit;
                border-radius: inherit;
            }
            </style>
            """, unsafe_allow_html=True)
            
            captured = st.file_uploader("Take a photo or upload", type=["jpg", "jpeg", "png", "bmp"], key="file_mobile", label_visibility="collapsed")
            is_photo = False
            
            if captured is not None:
                st.markdown("""
                <style>
                .st-key-file_mobile section::before {
                    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='36' height='36' viewBox='0 0 24 24' fill='none' stroke='%23007aff' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E") !important;
                    border-color: #007aff !important;
                }
                </style>
                """, unsafe_allow_html=True)
                is_photo = st.checkbox("This is a phone photo of a film", help="We'll correct perspective.", key="chk_mobile_is_photo")
            
            if captured is not None:
                st.session_state.mobile_captured_bytes = captured.getvalue()
                st.session_state.mobile_is_photo = is_photo

                if is_photo:
                    import io
                    preview_image = load_image(io.BytesIO(st.session_state.mobile_captured_bytes))
                    rect = rectify_mobile_xray(preview_image)

            st.markdown("<br>", unsafe_allow_html=True)
            if "mobile_captured_bytes" in st.session_state and st.session_state.mobile_captured_bytes:
                if st.button("Analyze", type="primary", use_container_width=True):
                    st.session_state.mobile_step = 2
                    st.rerun()

    elif st.session_state.mobile_step == 2:
        ui.page_header("Chest X-ray screening")
        
        import io
        captured_bytes = st.session_state.get("mobile_captured_bytes")
        is_photo = st.session_state.get("mobile_is_photo", False)
        clinician = st.session_state.get("role") == ui.ROLE_CLINICIAN
        
        if captured_bytes:
            captured = io.BytesIO(captured_bytes)
            run_analysis_and_render_results(captured, is_photo, clinician, mobile)
            
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container():
            if st.button("Start Over", type="primary", use_container_width=True):
                st.session_state.mobile_step = 1
                st.session_state.mobile_captured_bytes = None
                st.rerun()


else:
    # --- Desktop Single-Page Flow ---
    ui.page_header("Chest X-ray screening", "Take a photo or upload an X-ray to check for signs of pneumonia.")


    with st.container(key="section_role"):
        st.markdown("<div class='bf-step-badge'>Step 1</div>", unsafe_allow_html=True)
        role = ui.role_selector()
        clinician = ui.is_clinician()

    with st.container(key="section_upload"):
        st.markdown("<div class='bf-step-badge'>Step 2</div>", unsafe_allow_html=True)
        st.markdown("<h4 style='margin:0 0 1rem 0;'>Provide the X-ray</h4>", unsafe_allow_html=True)

        source = st.radio("Source", ["Take a photo", "Upload a file"], horizontal=True, label_visibility="collapsed")
        is_photo = source == "Take a photo"

        captured = None
        if is_photo:
            st.caption("Point your camera straight at the X-ray film, fill the frame, and avoid glare.")
            captured = st.camera_input("Capture X-ray", label_visibility="collapsed")
        else:
            file_is_photo = st.checkbox("This is a phone photo of a film (not a digital X-ray)", help="We'll correct perspective and contrast before screening.")
            captured = st.file_uploader("Upload X-ray", type=["jpg", "jpeg", "png", "bmp"], label_visibility="collapsed")
            is_photo = file_is_photo

    if captured is not None:
        run_analysis_and_render_results(captured, is_photo, clinician, mobile)
    else:
        st.markdown("""
        <div style="padding:3rem 2rem; text-align:center; color:var(--ink-60);
             border:2px dashed #d7dee8; border-radius:12px; background:#FAFBFD; margin-top:1rem;">
            <p style="font-weight:500; margin:0;">Take a photo or upload an X-ray to begin</p>
        </div>
        """, unsafe_allow_html=True)

