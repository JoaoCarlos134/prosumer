"""Solar geometry + daily->hourly synthesis + POA transposition (no pvlib).

Conventions (Duffie & Beckman):
  phi   latitude, negative south
  beta  surface tilt from horizontal
  gamma surface azimuth, 0 = equator-facing-south, +west, -east.
        Northern-facing array in the southern hemisphere => gamma = 180.
"""
import numpy as np

GSC = 1.367          # kW/m2 solar constant
D2R = np.pi / 180.0

# ---------- geometry ----------
def declination(n):
    """Cooper (1969), degrees."""
    return 23.45 * np.sin(2 * np.pi * (284 + n) / 365.0)

def eccentricity(n):
    return 1 + 0.033 * np.cos(2 * np.pi * n / 365.0)

def sunset_hour_angle(phi, delta):
    x = np.clip(-np.tan(phi * D2R) * np.tan(delta * D2R), -1, 1)
    return np.degrees(np.arccos(x))          # degrees

def H0_daily(phi, n):
    """Extraterrestrial daily irradiation on horizontal, kWh/m2/day."""
    d = declination(n)
    ws = sunset_hour_angle(phi, d)
    return (24 / np.pi) * GSC * eccentricity(n) * (
        np.cos(phi * D2R) * np.cos(d * D2R) * np.sin(ws * D2R)
        + (ws * D2R) * np.sin(phi * D2R) * np.sin(d * D2R))

def cos_zenith(phi, delta, omega):
    return (np.sin(delta * D2R) * np.sin(phi * D2R)
            + np.cos(delta * D2R) * np.cos(phi * D2R) * np.cos(omega * D2R))

def cos_incidence(phi, delta, omega, beta, gamma):
    p, d, o = phi * D2R, delta * D2R, omega * D2R
    b, g = beta * D2R, gamma * D2R
    return (np.sin(d) * np.sin(p) * np.cos(b)
            - np.sin(d) * np.cos(p) * np.sin(b) * np.cos(g)
            + np.cos(d) * np.cos(p) * np.cos(b) * np.cos(o)
            + np.cos(d) * np.sin(p) * np.sin(b) * np.cos(g) * np.cos(o)
            + np.cos(d) * np.sin(b) * np.sin(g) * np.sin(o))

# ---------- daily -> hourly ----------
def rt_collares_pereira(omega, ws):
    """Fraction of daily GLOBAL falling in the hour centred on omega."""
    a = 0.409 + 0.5016 * np.sin((ws - 60) * D2R)
    b = 0.6609 - 0.4767 * np.sin((ws - 60) * D2R)
    num = (np.cos(omega * D2R) - np.cos(ws * D2R))
    den = (np.sin(ws * D2R) - (ws * D2R) * np.cos(ws * D2R))
    return (np.pi / 24) * (a + b * np.cos(omega * D2R)) * num / den

def rd_liu_jordan(omega, ws):
    """Fraction of daily DIFFUSE falling in the hour centred on omega."""
    num = (np.cos(omega * D2R) - np.cos(ws * D2R))
    den = (np.sin(ws * D2R) - (ws * D2R) * np.cos(ws * D2R))
    return (np.pi / 24) * num / den

def erbs_daily_diffuse_fraction(Kt):
    """Erbs et al. (1982) daily diffuse fraction, used only as a fallback."""
    Kt = np.asarray(Kt, float)
    out = np.where(
        Kt <= 0.22, 1 - 0.09 * Kt,
        np.where(Kt <= 0.80,
                 0.9511 - 0.1604 * Kt + 4.388 * Kt**2 - 16.638 * Kt**3 + 12.336 * Kt**4,
                 0.165))
    return np.clip(out, 0.0, 1.0)

# ---------- main transposition ----------
def poa_daily(phi, n, H, Hd, beta, gamma, albedo=0.2, n_hours=48):
    """Daily plane-of-array irradiation, kWh/m2/day.

    H, Hd : daily global / diffuse on horizontal (kWh/m2/day), 1-D arrays
    Returns dict with poa, poa_beam, poa_diff, poa_grnd, and the
    irradiance-weighted mean cos(incidence) and air mass.
    """
    n   = np.asarray(n, float)
    H   = np.asarray(H, float)
    Hd  = np.asarray(Hd, float)
    alb = np.asarray(albedo, float) * np.ones_like(H)

    d  = declination(n)
    ws = sunset_hour_angle(phi, d)
    E0 = eccentricity(n)

    # sub-hourly grid spanning sunrise..sunset, per day
    frac = (np.arange(n_hours) + 0.5) / n_hours                 # (T,)
    omega = (-ws[:, None] + 2 * ws[:, None] * frac[None, :])     # (D,T) degrees
    dt_h = (2 * ws / 15.0) / n_hours                             # hours per step
    # rt/rd are defined per 1 hour; rescale to the actual step width
    scale = dt_h[:, None]

    rt = rt_collares_pereira(omega, ws[:, None]) * scale
    rd = rd_liu_jordan(omega, ws[:, None]) * scale
    rt = np.clip(rt, 0, None)
    rd = np.clip(rd, 0, None)
    # renormalise so the day sums exactly to 1
    rt = rt / np.where(rt.sum(1, keepdims=True) > 0, rt.sum(1, keepdims=True), 1)
    rd = rd / np.where(rd.sum(1, keepdims=True) > 0, rd.sum(1, keepdims=True), 1)

    I  = rt * H[:, None]                    # hourly global horizontal
    Id = np.minimum(rd * Hd[:, None], I)    # hourly diffuse horizontal
    Ib = np.clip(I - Id, 0, None)           # hourly beam horizontal

    cz = cos_zenith(phi, d[:, None], omega)
    cz_pos = np.clip(cz, 0.01, None)
    ct = cos_incidence(phi, d[:, None], omega, beta, gamma)
    ct = np.clip(ct, 0, None)
    Rb = ct / cz_pos

    I0 = GSC * E0[:, None] * cz_pos * scale          # extraterrestrial, same step
    Ai = np.clip(np.where(I0 > 0, Ib / I0, 0), 0, 1) # anisotropy index
    f  = np.sqrt(np.where(I > 0, Ib / I, 0))
    b2 = np.sin(beta * D2R / 2) ** 3

    poa_beam = (Ib + Id * Ai) * Rb
    poa_diff = Id * (1 - Ai) * ((1 + np.cos(beta * D2R)) / 2) * (1 + f * b2)
    poa_grnd = I * alb[:, None] * ((1 - np.cos(beta * D2R)) / 2)

    day = cz > 0
    wsum = np.where(day, I, 0).sum(1)
    wsafe = np.where(wsum > 0, wsum, 1)
    kappa = 0.50572; am = 1 / (cz_pos + kappa * (96.07995 - np.degrees(np.arccos(np.clip(cz,-1,1)))) ** -1.6364)

    return dict(
        poa       = poa_beam.sum(1) + poa_diff.sum(1) + poa_grnd.sum(1),
        poa_beam  = poa_beam.sum(1),
        poa_diff  = poa_diff.sum(1),
        poa_grnd  = poa_grnd.sum(1),
        cos_inc_w = (np.where(day, ct, 0) * np.where(day, I, 0)).sum(1) / wsafe,
        airmass_w = (np.where(day, np.clip(am, 1, 30), 0) * np.where(day, I, 0)).sum(1) / wsafe,
        daylength = 2 * ws / 15.0,
        # hourly grids reused by the cell-temperature model
        _I = I, _poa_h = poa_beam + poa_diff + poa_grnd, _day = day, _cz = cz,
    )

# ---------- cell temperature ----------
def cell_temp_faiman(poa_h, tamb, wind, u0=25.0, u1=6.84):
    """Faiman (2008). poa_h in kWh/m2 per step -> needs W/m2; caller converts."""
    return tamb + poa_h / (u0 + u1 * wind)

def weighted_cell_temp(poa_h_wm2, tamb, wind, u0=25.0, u1=6.84):
    """Irradiance-weighted daily mean cell temperature."""
    tc = tamb[:, None] + poa_h_wm2 / (u0 + u1 * wind[:, None])
    w = np.clip(poa_h_wm2, 0, None)
    ws_ = w.sum(1)
    return np.where(ws_ > 0, (tc * w).sum(1) / np.where(ws_ > 0, ws_, 1), tamb)
