import math
from src.cislunar.ledger import vis_viva_tli, mass_ratio, G0, ariane64_capability, stage_sizing

def test_tli_delta_v():
    dv = vis_viva_tli(300, -2.0)
    assert 3050 <= dv <= 3180, f"TLI dV = {dv:.0f} m/s, expected 3050-3180"

def test_apollo_lm_descent():
    m_prop, m_inert, m_u, isp = 8200, 2100, 4700, 311
    dv = isp * G0 * math.log((m_u + m_prop + m_inert) / (m_u + m_inert))
    assert 2300 <= dv <= 2500, f"LM descent dV = {dv:.0f} m/s, expected 2300-2500"

def test_apollo_lm_ascent():
    m_prop, m_inert, m_u, isp = 2350, 2150, 500, 311
    dv = isp * G0 * math.log((m_u + m_prop + m_inert) / (m_u + m_inert))
    assert 1900 <= dv <= 2050, f"LM ascent dV = {dv:.0f} m/s, expected 1900-2050"

def test_ariane_curve_monotone():
    prev = float("inf")
    for c3 in [-2, 0, 3, 6.25, 10, 20]:
        cap = ariane64_capability(c3)
        assert cap <= prev + 1, f"Non-monotone: C3={c3} -> {cap}, prev={prev}"
        prev = cap

def test_stage_sizing_closure():
    m_u, eps, isp = 500, 0.15, 320
    R = mass_ratio(2000, isp)
    s = stage_sizing(m_u, R, eps)
    assert s["feasible"]
    R_check = s["m_initial"] / (m_u + s["m_inert"])
    assert abs(R_check - R) / R < 1e-9, f"R closure: {R_check} vs {R}"
