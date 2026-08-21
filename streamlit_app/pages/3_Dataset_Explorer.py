"""
Dataset Explorer Page - Pneumonia Detection
Explore the chest X-ray dataset used for training the model.
"""

import streamlit as st
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import ui
from utils.device import is_mobile, init_device, render_mobile_navbar

# Page config
st.set_page_config(
    page_title="Dataset | BioFusion",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Probe the viewport once per run, before any is_mobile() call.
init_device()

ui.inject_theme()
ui.top_nav(active="Dataset")
if not is_mobile():
    st.divider()

# Page Header
ui.page_header("Dataset analytics", "Cohort demographics and quality assurance")

# Dataset Overview
st.markdown("##### Cohort Summary")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    | Attribute | Details |
    |-----------|---------|
    | **Name** | Chest X-Ray Images (Pneumonia) |
    | **Source Warning** | Class Imbalance Present |
    | **Total Volume** | 5,863 JPEG Images |
    | **Demographics** | Pediatric (1-5 years) |
    | **Site** | Guangzhou Medical Center |
    | **Labels** | Binary: Normal / Pneumonia |
    """)

with col2:
    st.markdown("""
    <div style="text-align: center; padding: 2rem 1.5rem; border: 1px solid var(--hair); border-radius: 12px; background: var(--primary-wash);">
        <div style="font-size: 3rem; font-weight: 700; color: #0066CC; line-height: 1.1; letter-spacing: -0.02em;">5,863</div>
        <div style="color: var(--ink-60); font-size: 0.8rem; font-weight: 500; letter-spacing:0.04em;">TOTAL RADIOGRAPHS</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Class Distribution
st.markdown("##### Distribution Analysis")

col1, col2 = st.columns(2)

with col1:
    split_data = {"Split": ["Train", "Validation", "Test"], "Normal": [1341, 8, 234], "Pneumonia": [3875, 8, 390]}
    
    fig_split = go.Figure()
    # Sapphire for Normal, Amber for Pneumonia (Warning state concepts)
    fig_split.add_trace(go.Bar(name='Normal', x=split_data["Split"], y=split_data["Normal"], marker_color='#059669', text=split_data["Normal"], textposition='inside'))
    fig_split.add_trace(go.Bar(name='Pneumonia', x=split_data["Split"], y=split_data["Pneumonia"], marker_color='#f59e0b', text=split_data["Pneumonia"], textposition='inside'))
    fig_split.update_layout(
        barmode='stack',
        title="Sample Distribution by Split",
        xaxis_title="Split",
        yaxis_title="Image Count",
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Helvetica, Arial, sans-serif")
    )
    st.plotly_chart(fig_split, use_container_width=True)

with col2:
    # Emerald and Amber palette
    fig_pie = go.Figure(data=[go.Pie(labels=['Normal (Healthy)', 'Pneumonia (Pathology)'], values=[1583, 4273], hole=.55, marker_colors=['#059669', '#f59e0b'], textinfo='percent')])
    fig_pie.update_layout(
        title="Global Class Balance",
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=True,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Helvetica, Arial, sans-serif"),
        annotations=[dict(text='27:73', x=0.5, y=0.5, font_size=20, showarrow=False)]
    )
    st.plotly_chart(fig_pie, use_container_width=True)

st.info("ℹ️ **Data Engineering:** Weighted Cross-Entropy Loss (weights=[0.74, 0.26]) applied during training to counteract class imbalance.")

st.divider()

# Data Quality
st.markdown("##### Quality Assurance Protocol")

quality_cols = st.columns(3)

quality_metrics = [
    ("Triple grading", "Primary screening by an expert physician, followed by two independent validator reviews."),
    ("Clinical origin", "Sourced from real-world pediatric inflows at a major metropolitan medical center."),
    ("Adjudication", "Disagreements resolved by a third senior expert review to establish ground truth."),
]

for col, (title, desc) in zip(quality_cols, quality_metrics):
    with col:
        st.markdown(f"""
        <div style="padding: 1.5rem; height: 100%; border: 1px solid var(--hair); border-radius: 12px; background: #fff;">
            <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.5rem;">
                <span style="width:4px; height:18px; border-radius:2px; background:var(--primary); display:inline-block;"></span>
                <span style="font-weight:600; color:var(--black);">{title}</span>
            </div>
            <div style="font-size:0.85rem; color:var(--ink-60); line-height:1.5;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

if is_mobile():
    render_mobile_navbar("Dataset")
