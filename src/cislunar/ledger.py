"""Phase 1 deterministic ledger. No Streamlit, no optimizer, no CR3BP."""
import math
from dataclasses import dataclass
from typing import Optional

MU_EARTH = 398600.4418  # km³/s²
R_EARTH = 6378.137      # km
G0 = 9.80665            # m/s²

# Ariane 64 payload vs C3 curve [A?] — needs citation
ARIANE64_CURVE = [
    (-2.0, 8500.0),   # bound transfer, interpolated [C]
    (0.0,  8500.0),   # escape
    (6.25, 6900.0),   # v_inf = 2.5 km/s
    (20.0, 4000.0),   # high energy
]

ORBITS = {
    "LLO_100_polar": {
        "insertion_dv": 970.0,
        "maintenance_5yr": 350.0,
        "descent_dv": 2000.0,
        "ascent_dv": 1940.0,
        "tei_dv": 950.0,
    },
    "NRHO_9to2": {
        "insertion_dv": 450.0,
        "maintenance_5yr": 10.0,
        "descent_dv": 2700.0,
        "ascent_dv": 2700.0,
        "tei_dv": 300.0,
    },
    "DRO": {
        "insertion_dv": 600.0,
        "maintenance_5yr": 5.0,
        "descent_dv": 2600.0,
        "ascent_dv": 2600.0,
        "tei_dv": 350.0,
    },
    "ELFO": {
        "insertion_dv": 550.0,
        "maintenance_5yr": 50.0,
        "descent_dv": 2800.0,
        "ascent_dv": 2700.0,
        "tei_dv": 400.0,
    },
}

def vis_viva_tli(leo_alt_km: float, c3_km2s2: float) -> float:
    """TLI ΔV in m/s from circular LEO at given altitude, for given C3."""
    r1 = R_EARTH + leo_alt_km
    v_circ = math.sqrt(MU_EARTH / r1)
    v_transfer = math.sqrt(c3_km2s2 + 2 * MU_EARTH / r1)
    return (v_transfer - v_circ) * 1000.0

def ariane64_capability(c3_km2s2: float) -> float:
    pts = sorted(ARIANE64_CURVE)
    c3 = max(pts[0][0], min(pts[-1][0], c3_km2s2))
    for i in range(len(pts) - 1):
        c_lo, m_lo = pts[i]
        c_hi, m_hi = pts[i + 1]
        if c_lo <= c3 <= c_hi:
            frac = (c3 - c_lo) / (c_hi - c_lo)
            return m_lo + frac * (m_hi - m_lo)
    return pts[-1][1]

def mass_ratio(dv_ms: float, isp_s: float) -> float:
    return math.exp(dv_ms / (isp_s * G0))

def stage_sizing(m_u: float, R: float, eps: float) -> dict:
    denom = 1.0 - (R - 1) * eps / (1 - eps)
    if denom <= 0.05:
        return {"feasible": False, "reason": f"inert fraction limit (denom={denom:.3f})"}
    m_prop = (R - 1) * m_u / denom
    m_inert = eps / (1 - eps) * m_prop
    return {
        "feasible": True,
        "m_prop": m_prop,
        "m_inert": m_inert,
        "m_initial": m_u + m_prop + m_inert,
        "R": R,
    }

def compute_separate(
    m_surface: float,
    orbit: str,
    isp: float = 320.0,
    eps_tm: float = 0.10,
    eps_lander: float = 0.15,
    return_mode: str = "none",
    capsule_mass: float = 0.0,
    margin_frac: float = 0.05,
) -> dict:
    o = ORBITS[orbit]
    dv_tcm_ins = o["insertion_dv"] * (1 + margin_frac)
    dv_descent = o["descent_dv"] * (1 + margin_frac)
    dv_ascent = o["ascent_dv"] * (1 + margin_frac) if return_mode != "none" else 0.0

    if return_mode == "none":
        R_d = mass_ratio(dv_descent, isp)
        s = stage_sizing(m_surface, R_d, eps_lander)
        if not s["feasible"]:
            return {"feasible": False, "reason": "lander: " + s["reason"]}
        m_at_orbit = s["m_initial"]
    else:
        R_a = mass_ratio(dv_ascent, isp)
        s_a = stage_sizing(m_surface + capsule_mass, R_a, eps_lander)
        if not s_a["feasible"]:
            return {"feasible": False, "reason": "ascent: " + s_a["reason"]}
        R_d = mass_ratio(dv_descent, isp)
        s_d = stage_sizing(s_a["m_initial"], R_d, eps_lander)
        if not s_d["feasible"]:
            return {"feasible": False, "reason": "descent: " + s_d["reason"]}
        m_at_orbit = s_d["m_initial"]

    R_tm = mass_ratio(dv_tcm_ins, isp)
    s_tm = stage_sizing(m_at_orbit, R_tm, eps_tm)
    if not s_tm["feasible"]:
        return {"feasible": False, "reason": "TM: " + s_tm["reason"]}

    return {
        "feasible": True,
        "architecture": "separate",
        "orbit": orbit,
        "return_mode": return_mode,
        "m_surface": m_surface,
        "m_TLI_kg": s_tm["m_initial"],
        "m_TLI_t": s_tm["m_initial"] / 1000.0,
        "dv_tcm_ins": dv_tcm_ins,
        "dv_descent": dv_descent,
        "dv_ascent": dv_ascent,
    }

def compute_merged(
    m_surface: float,
    orbit: str,
    isp: float = 320.0,
    eps: float = 0.15,
    return_mode: str = "none",
    capsule_mass: float = 0.0,
    margin_frac: float = 0.05,
) -> dict:
    """F1+F2: single stage does insertion + descent + ascent (if return)."""
    o = ORBITS[orbit]
    dv = o["insertion_dv"] + o["descent_dv"]
    if return_mode != "none":
        dv += o["ascent_dv"]
    dv *= (1 + margin_frac)
    R = mass_ratio(dv, isp)
    payload_through = m_surface + (capsule_mass if return_mode != "none" else 0.0)
    s = stage_sizing(payload_through, R, eps)
    if not s["feasible"]:
        return {"feasible": False, "reason": s["reason"], "dv_total": dv, "R": R}
    return {
        "feasible": True,
        "architecture": "merged",
        "orbit": orbit,
        "return_mode": return_mode,
        "m_surface": m_surface,
        "m_TLI_kg": s["m_initial"],
        "m_TLI_t": s["m_initial"] / 1000.0,
        "dv_total": dv,
        "R": R,
    }

if __name__ == "__main__":
    print(f"TLI ΔV from 300 km LEO at C3 = -2.0: {vis_viva_tli(300, -2.0):.0f} m/s")
    print(f"Ariane 64 capability at C3 = -2.0: {ariane64_capability(-2.0)/1000:.1f} t\n")
    print(f"{'Orbit':<15} {'Site':<8} {'Sep t':<8} {'Merged t':<10} {'Cap t':<8} {'Status'}")
    print("-" * 65)
    for orbit in ORBITS:
        for m_surf in [200, 500, 1000]:
            cap = ariane64_capability(-2.0) / 1000.0
            sep = compute_separate(m_surf, orbit)
            mer = compute_merged(m_surf, orbit)
            sep_t = sep["m_TLI_t"] if sep["feasible"] else float("nan")
            mer_t = mer["m_TLI_t"] if mer["feasible"] else float("nan")
            status = "OK" if (sep["feasible"] and sep_t <= cap) else "FAIL"
            print(f"{orbit:<15} {m_surf:<8} {sep_t:<8.2f} {mer_t:<10.2f} {cap:<8.2f} {status}")