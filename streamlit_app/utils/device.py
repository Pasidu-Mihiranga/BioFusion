import streamlit as st
from streamlit_javascript import st_javascript

MOBILE_BREAKPOINT = 768


def init_device():
    """Probe the viewport width once per script run.

    Call this once near the top of every page, after st.set_page_config and
    before anything that calls is_mobile().

    st_javascript mounts a frontend component and returns its default (0) until
    the browser answers on a later rerun. Probing from inside is_mobile() meant
    every call site mounted another component with identical parameters, and
    Streamlit derives a component's element ID from its type plus parameters —
    so the second call of a run raised StreamlitDuplicateElementId. Keeping the
    probe in one place means at most one component instance per run.
    """
    if st.session_state.get('device_resolved'):
        return

    window_width = st_javascript("window.innerWidth", key="bf_viewport_probe")

    # Falsy until the browser round-trip completes; retry on the next rerun.
    if window_width and window_width > 0:
        st.session_state['is_mobile'] = window_width < MOBILE_BREAKPOINT
        st.session_state['device_resolved'] = True


def is_mobile():
    """Whether the viewport is phone-sized.

    Pure session_state read — assumes desktop until the probe started by
    init_device() reports back, which happens on the following rerun.
    """
    return st.session_state.get('is_mobile', False)

def render_mobile_navbar(current_page="Prediction"):
    """Renders a bottom navigation bar for mobile views."""
    from streamlit_option_menu import option_menu
    
    # Hide the default sidebar on mobile
    st.markdown("""
        <style>
            /* Hide the default sidebar and its toggle button */
            [data-testid="collapsedControl"] { display: none !important; }
            [data-testid="stSidebar"] { display: none !important; }
            
            /* Fix the option menu container to the bottom */
            .st-key-mobile_nav {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                width: 100%;
                z-index: 999;
                border-radius: 0;
                box-shadow: 0px -4px 16px rgba(0, 0, 0, 0.08);
                background-color: white;
                padding-bottom: env(safe-area-inset-bottom);
            }
            
            /* Add bottom padding to main block so content isn't hidden behind navbar */
            [data-testid="stAppViewBlockContainer"] {
                padding-bottom: 100px;
                padding-top: 0.5rem !important; /* Remove top empty space */
                text-align: center; /* Center alignment */
            }

            /* Center align texts and headers */
            h1, h2, h3, h4, h5, h6, p, .stMarkdown, .bf-result {
                text-align: center !important;
            }

            /* Center align flex containers like page_header */
            .bf-page-header {
                justify-content: center !important;
            }

            /* Hide horizontal dividers */
            [data-testid="stDivider"], hr {
                display: none !important;
            }
            
            /* Hide the blue vertical line in page header */
            .bf-header-line {
                display: none !important;
            }

            /* Style all Streamlit buttons to be full-width pills on mobile */
            html body .stApp button[kind="primary"],
            html body .stApp button[kind="secondary"],
            html body .stApp div[data-testid="baseButton-primary"] button,
            html body .stApp div[data-testid="baseButton-secondary"] button,
            html body .stApp div[data-testid="stButton"] button {
                border-radius: 24px !important;
                padding: 10px 32px !important;
                font-weight: 600 !important;
                font-size: 15px !important;
                width: 100% !important;
                max-width: 100% !important;
                -webkit-appearance: none !important;
            }
            
            /* Explicitly force primary desktop colors */
            html body .stApp button[kind="primary"],
            html body .stApp div[data-testid="baseButton-primary"] button {
                background-color: #0066CC !important;
                color: #ffffff !important;
                border: none !important;
            }
            html body .stApp button[kind="primary"] p,
            html body .stApp div[data-testid="baseButton-primary"] button p {
                color: #ffffff !important;
                font-weight: 600 !important;
                font-size: 16px !important;
            }
            html body .stApp button[kind="primary"]:hover,
            html body .stApp div[data-testid="baseButton-primary"] button:hover {
                background-color: #005bb5 !important;
            }

            /* Explicitly force secondary desktop colors */
            html body .stApp button[kind="secondary"],
            html body .stApp div[data-testid="baseButton-secondary"] button {
                background-color: #ffffff !important;
                color: #31333F !important;
                border: 1px solid rgba(49, 51, 63, 0.2) !important;
            }
            html body .stApp button[kind="secondary"] p,
            html body .stApp div[data-testid="baseButton-secondary"] button p {
                color: #31333F !important;
                font-weight: 600 !important;
                font-size: 16px !important;
            }
            html body .stApp button[kind="secondary"]:hover,
            html body .stApp div[data-testid="baseButton-secondary"] button:hover {
                border-color: #0066CC !important;
                color: #0066CC !important;
            }
            html body .stApp button[kind="secondary"]:hover p,
            html body .stApp div[data-testid="baseButton-secondary"] button:hover p {
                color: #0066CC !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # We use empty container at bottom
    with st.container(key="mobile_nav"):
        selected = option_menu(
            menu_title=None,
            options=["Home", "Prediction", "Insights", "Dataset"],
            icons=[
                "house-door-fill" if current_page == "Home" else "house-door",
                "eye-fill" if current_page == "Prediction" else "eye",
                "pie-chart-fill" if current_page == "Insights" else "pie-chart",
                "folder-fill" if current_page == "Dataset" else "folder"
            ],
            menu_icon="cast",
            default_index=["Home", "Prediction", "Insights", "Dataset"].index(current_page),
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "margin": "0!important", "border-radius": "0", "background-color": "#ffffff"},
                "icon": {"font-size": "22px", "margin": "0"}, 
                "nav-link": {
                    "font-size": "11px", 
                    "text-align": "center", 
                    "margin":"0px", 
                    "padding":"8px 0", 
                    "color": "#4B5563",
                    "display": "flex",
                    "flex-direction": "column",
                    "align-items": "center",
                    "justify-content": "center",
                    "gap": "4px"
                },
                "nav-link-selected": {
                    "background-color": "transparent", 
                    "color": "#0066CC", 
                    "font-weight": "600",
                    "border-radius": "0"
                },
            }
        )
        
    # Handle navigation
    if selected != current_page:
        if selected == "Home":
            st.switch_page("app.py")
        elif selected == "Prediction":
            st.switch_page("pages/1_Live_Prediction.py")
        elif selected == "Insights":
            st.switch_page("pages/2_Model_Insights.py")
        elif selected == "Dataset":
            st.switch_page("pages/3_Dataset_Explorer.py")
