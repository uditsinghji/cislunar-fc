import streamlit as st
import sys
import os

# This ensures Python can find the 'src' folder when deployed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cislunar.ledger import (
    ORBITS, compute_separate, compute_merged, ariane64_capability
)

st.set_page_config(page_title="Cislunar Forecasting", layout="wide")
st.title("Cislunar Architecture Forecasting — Phase 1")

st.sidebar.header("Inputs")
m_surface = st.sidebar.number_input("Surface payload (kg)", 100, 5000, 500, step=50)
orbit = st.sidebar.selectbox("Orbit", list(ORBITS.keys()))
architecture = st.sidebar.radio("Architecture", ["separate", "merged"])
return_mode = st.sidebar.radio("Return mode", ["none", "sample_capsule"])
capsule_mass = st.sidebar.number_input("Capsule mass (kg)", 0, 200, 46 if return_mode != "none" else 0)
isp = st.sidebar.slider("Isp (s)", 280, 450, 320)

if architecture == "separate":
    result = compute_separate(m_surface, orbit, isp=isp,
                              return_mode=return_mode, capsule_mass=capsule_mass)
else:
    result = compute_merged(m_surface, orbit, isp=isp,
                            return_mode=return_mode, capsule_mass=capsule_mass)

cap = ariane64_capability(-2.0) / 1000.0  # tonnes

if not result["feasible"]:
    st.error(f"Architecture infeasible: {result['reason']}")
else:
    m_t = result["m_TLI_t"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Required at TLI", f"{m_t:.2f} t")
    col2.metric("Ariane 64 capability", f"{cap:.2f} t")
    col3.metric("Margin", f"{(cap - m_t):.2f} t")

    if m_t <= cap * 0.95:
        st.success(f"✅ FEASIBLE with {(cap - m_t)/cap*100:.0f}% margin")
    elif m_t <= cap:
        st.warning(f"⚠️ KNIFE-EDGE — only {(cap - m_t)/cap*100:.1f}% margin")
    else:
        st.error(f"❌ INFEASIBLE — exceeds Ariane 64 by {m_t - cap:.2f} t")

    st.subheader("ΔV breakdown (m/s)")
    st.json({k: round(v, 0) for k, v in result.items() if k.startswith("dv_")})

st.caption("⚠️ All values [A?] or [C] — pending source verification. See README.")