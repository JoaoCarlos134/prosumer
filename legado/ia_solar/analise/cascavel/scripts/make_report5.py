# -*- coding: utf-8 -*-
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import base64, os
from PIL import Image
import glob

os.makedirs(caminho("figs5_opt"), exist_ok=True)
for p in sorted(glob.glob(caminho("figs5/2[1-8]_*.png"))):
    Image.open(p).convert("RGB").quantize(colors=180, method=Image.MEDIANCUT,
        dither=Image.FLOYDSTEINBERG).save(os.path.join(caminho("figs5_opt"), os.path.basename(p)), optimize=True)

def b64(n):
    with open(caminho("figs5_opt/%s.png" % n), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

FIGS = {
 "21_azimuth_resolved": ("The degeneracy daily data could not break",
   "Left: with daily totals the fit is exactly symmetric about due north, so the datasheet's 205° and its mirror "
   "155° score identically — azimuth carries no information. Right: the 5-minute profile breaks the symmetry and "
   "peaks at 202.5°, two and a half degrees from the datasheet value."),
 "22_fault_fingerprint": ("String current and voltage against the healthy baseline",
   "Both normalised to modelled irradiance and to the 2019–21 plateau. Current falls to −22% and recovers in a "
   "single month, twice. Voltage just breathes with the seasons and never trends. Red bands are the faulted regimes."),
 "23_soiling_signature": ("Current recovered by the November 2023 cleaning, by solar elevation",
   "Six weeks apart, so the sun's path barely moves. A uniform obstruction removal would restore one band of sky; "
   "this restores everything, but twice as much at low sun as at high sun — the angular signature of a dirt layer."),
 "26_day_curves": ("Median clear-day power curve by regime",
   "Against the clear-sky reference in dashed grey. The faulted curves sag across the whole day rather than losing "
   "a morning or an afternoon, which is what an obstruction would do."),
 "24_inverter_efficiency": ("Measured inverter conversion efficiency against loading",
   "Each point is the median of all 5-minute intervals in that band, labelled with its share of lifetime energy. "
   "The poor efficiency below 5% loading costs almost nothing because almost no energy passes through it."),
 "25_power_bias": ("NASA POWER irradiance against the plant's own clear-sky reference",
   "On clear days the two should agree. POWER runs 3.2% low with a near-unity slope and a fixed offset, and its "
   "error carries a 4.1-point seasonal cycle — a floor under anything the daily analysis could resolve."),
}

FINDINGS = [
 ("resolved", "Array azimuth", "205° — 25° east of north, confirmed",
  "The 5-minute fit lands at 202.5°, and production is weighted to the morning (weighted mean solar time 11.79 h, "
  "where a due-north array gives 12.00). Daily totals gave R²(155°) = R²(205°) to machine precision; at 5-minute "
  "resolution they differ by 0.104. The datasheet is confirmed by data for the first time.", "21_azimuth_resolved"),
 ("corrected", "A sign error of mine", "γ = 205, not 155",
  "I earlier mapped “25° east of north” to Duffie–Beckman γ = 155. That is 25° <em>west</em> of north — the rotation "
  "runs south→west→north→east, so east of north is 180+25. Because daily POA at 155 and 205 is identical to 3.6e−15 "
  "kWh/m², every daily-resolution number in the audit is unaffected: PR, the regimes, the shortfall, all unchanged. "
  "It mattered only once the intraday shape came into play.", ""),
 ("resolved", "What the fault was", "progressive soiling",
  "DC current fell 16% while string voltage held to within 1%. That excludes a failed module, an open circuit and "
  "bypass-diode conduction, all of which cut voltage in discrete steps; inverter efficiency never degraded, which "
  "excludes the inverter. The loss built up gradually over about twelve months and reversed in a single month — "
  "twice.", "22_fault_fingerprint"),
 ("resolved", "Soiling rather than shading", "recovery scales with incidence angle",
  "The November 2023 cleaning restored +28% of current at high sun and +54% at low sun, smoothly across every "
  "elevation band and in both the morning and the evening. An obstruction bites in one band of sky; a dirt layer "
  "attenuates more the more obliquely light passes through it.", "23_soiling_signature"),
 ("resolved", "Why rain never fixed it", "13° tilt",
  "The audit found no correlation between performance and dry-spell length, which looked like evidence against "
  "soiling. It was evidence about the <em>kind</em> of soiling. At 13° there is not enough slope for rain to sheet "
  "off and carry deposits with it, so what accumulates is cemented rather than loose — invisible to a dry-spell "
  "test, and removable only by washing.", "26_day_curves"),
 ("resolved", "Inverter clipping", "none, as predicted",
  "3,744 W at the 99.9th percentile against a 4.0 kW inverter; 58 intervals out of 350,000 above 3,950 W. The "
  "0.99 DC/AC ratio left no room for it and the data agrees.", ""),
 ("new", "Inverter conversion efficiency", "98.53% energy-weighted",
  "Measured directly from the DC and AC channels: 99.0% at 50–70% loading, falling to 75% below 2% loading, which "
  "carries a negligible share of the energy. This removes the inverter from the 16.6% residual loss budget the "
  "audit could not decompose.", "24_inverter_efficiency"),
 ("new", "NASA POWER calibrated", "reads 3.2% low on clear days",
  "Against a physical clear-sky reference built from the plant's own geometry: slope 1.0032, offset −0.21 kWh/m², "
  "R² 0.914, and a 4.1-point seasonal cycle in the ratio. This is the error floor that made a 0.5 %/yr degradation "
  "rate unresolvable.", "25_power_bias"),
 ("open", "Temperature coefficient", "still not recoverable",
  "Four routes disagree: the seasonal amplitude implies −0.36 %/K, the best-flattening fit −0.14 %/K, the clear-sky "
  "envelope +0.07 %/K. Only the string voltage behaves: Vmp falls −0.44 %/K, squarely in the normal crystalline-"
  "silicon range, which confirms the modules are electrically healthy without pinning the power coefficient. "
  "Without measured plane-of-array irradiance or a module temperature sensor, this stays open.", ""),
 ("open", "The 6-point seasonal residual", "partly explained, not closed",
  "I suggested last time it might be near-field shading or reanalysis bias. It is neither, cleanly. The swing is "
  "6.4 points in <em>raw</em> PR as well as 6.3 in the corrected version — the temperature correction moves which "
  "months look worst without shrinking the amplitude. Temperature plausibly accounts for most of it, and the "
  "remainder tracks the wet season, when POWER's irradiance is least accurate.", ""),
]

def fig(n):
    t, c = FIGS[n]
    return ('<figure class="plate"><img src="%s" alt="%s" loading="lazy">'
            '<figcaption><b>%s.</b> %s</figcaption></figure>' % (b64(n), t, t, c))

CHIP = {"resolved":("&#9679;","Resolved"), "new":("&#9632;","New"),
        "corrected":("&#9650;","Correction"), "open":("&#9675;","Still open")}
cards = []
for kind, name, val, note, f_ in FINDINGS:
    g, lbl = CHIP[kind]
    cards.append('<div class="fnd fnd--%s"><div class="fnd__chip"><span>%s</span>%s</div>'
                 '<div class="fnd__body"><h4>%s</h4><p class="fnd__val">%s</p>'
                 '<p class="fnd__note">%s</p></div></div>' % (kind, g, lbl, name, val, note))

REG = [("Aug 19 – May 21","healthy","394.8","8.40","—"),
       ("Jun 21 – Sep 22","fault","397.8","7.54","−10.2%"),
       ("Oct 22 – Oct 23","fault","390.7","7.04","−16.2%"),
       ("Nov 23 – Mar 24","healthy","378.2","8.49","+1.2%"),
       ("Apr 24 – Aug 24","fault","393.7","7.54","−10.2%"),
       ("Sep 24 – Aug 26","healthy","388.1","8.01","−4.6%")]
rows = "".join('<tr class="r--%s"><td>%s</td><td><span class="state state--%s">%s</span></td>'
               '<td class="mono num">%s</td><td class="mono num">%s</td><td class="mono num">%s</td></tr>'
               % (s, p, s, "healthy" if s=="healthy" else "soiled", v, i, d)
               for p, s, v, i, d in REG)

HTML = """<title>Inverter Data Findings</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{color-scheme:light;
 --ground:#f5f7f8;--ink:#131920;--ink-2:#4a5560;--ink-3:#77828d;
 --rule:#dbe1e6;--rule-2:#eceff2;--accent:#b4690e;--accent-s:#f6ecdd;
 --good:#1b7a53;--good-s:#e4f1eb;--bad:#b3322f;--bad-s:#f8e8e7;
 --info:#2a5c9a;--plate:#fcfcfb;--measure:68ch}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --ground:#0f1317;--ink:#eef2f5;--ink-2:#b3bdc7;--ink-3:#7d8792;
 --rule:#2a333c;--rule-2:#20272e;--accent:#e0952f;--accent-s:#2e2415;
 --good:#4bbd8c;--good-s:#15271f;--bad:#e8706c;--bad-s:#2b1818;
 --info:#7aa9e0;--plate:#fcfcfb}}
:root[data-theme="dark"]{color-scheme:dark;
 --ground:#0f1317;--ink:#eef2f5;--ink-2:#b3bdc7;--ink-3:#7d8792;
 --rule:#2a333c;--rule-2:#20272e;--accent:#e0952f;--accent-s:#2e2415;
 --good:#4bbd8c;--good-s:#15271f;--bad:#e8706c;--bad-s:#2b1818;
 --info:#7aa9e0;--plate:#fcfcfb}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
 font-size:16px;line-height:1.62;-webkit-font-smoothing:antialiased}
.wrap{max-width:1060px;margin:0 auto;padding-inline:24px;padding-block:0 76px}
.mono{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
header.mast{padding-block:54px 26px;border-bottom:2px solid var(--ink)}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.13em;text-transform:uppercase;
 color:var(--accent);font-weight:600;margin:0 0 14px}
h1{font-size:clamp(29px,5vw,44px);line-height:1.08;letter-spacing:-.022em;font-weight:600;margin:0 0 16px;
 max-width:21ch;text-wrap:balance}
.standfirst{font-size:18px;color:var(--ink-2);margin:0;max-width:var(--measure)}
.specs{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:1px;background:var(--rule);
 border:1px solid var(--rule);margin-block:30px 0}
.spec{background:var(--ground);padding:12px 14px}
.spec dt{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;
 color:var(--ink-3);margin:0 0 5px}
.spec dd{margin:0;font-size:15px;font-weight:600;letter-spacing:-.01em}
section{padding-block:50px 0}
h2{font-size:13px;font-family:"IBM Plex Mono",monospace;font-weight:600;letter-spacing:.12em;text-transform:uppercase;
 margin:0 0 8px;padding-bottom:8px;border-bottom:1px solid var(--rule);display:flex;gap:12px;align-items:baseline}
h2 .n{color:var(--accent)}
h3{font-size:21px;font-weight:600;letter-spacing:-.018em;margin:30px 0 10px;text-wrap:balance}
p{margin:0 0 15px;max-width:var(--measure)}
.lede{font-size:17.5px;color:var(--ink-2);margin-top:18px}
code{font-family:"IBM Plex Mono",monospace;font-size:.88em;background:var(--rule-2);padding:1px 5px;border-radius:3px}
.finding{border-left:3px solid var(--accent);background:var(--accent-s);padding:18px 22px;margin:26px 0;
 max-width:var(--measure)}
.finding p:last-child{margin-bottom:0}
.finding .k{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
 color:var(--accent);font-weight:600;display:block;margin-bottom:6px}
.plate{margin:32px 0}
.plate img{display:block;width:100%;max-width:100%;height:auto;background:var(--plate);border:1px solid var(--rule)}
figcaption{font-size:13.5px;line-height:1.55;color:var(--ink-2);margin-top:10px;max-width:84ch}
figcaption b{color:var(--ink);font-weight:600}
.fndlist{display:flex;flex-direction:column;gap:1px;background:var(--rule);border-block:1px solid var(--rule);
 margin-top:22px}
.fnd{background:var(--ground);display:grid;grid-template-columns:140px 1fr;gap:20px;padding:16px 0}
.fnd__chip{font-family:"IBM Plex Mono",monospace;font-size:11px;font-weight:600;letter-spacing:.07em;
 text-transform:uppercase;display:flex;align-items:baseline;gap:7px;padding-top:3px}
.fnd--resolved .fnd__chip{color:var(--good)}
.fnd--new .fnd__chip{color:var(--info)}
.fnd--corrected .fnd__chip{color:var(--accent)}
.fnd--open .fnd__chip{color:var(--ink-3)}
.fnd__body h4{margin:0 0 3px;font-size:16.5px;font-weight:600;letter-spacing:-.012em}
.fnd__val{font-family:"IBM Plex Mono",monospace;font-size:14.5px;font-weight:500;margin:0 0 6px;color:var(--ink)}
.fnd--open .fnd__val{color:var(--ink-3)}
.fnd__note{font-size:14px;color:var(--ink-2);margin:0;max-width:76ch}
.tablewrap{overflow-x:auto;margin:24px 0}
table{border-collapse:collapse;width:100%;min-width:540px;font-size:14px}
th{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
 color:var(--ink-3);font-weight:600;text-align:left;padding:0 14px 8px 0;border-bottom:1px solid var(--ink)}
td{padding:9px 14px 9px 0;border-bottom:1px solid var(--rule-2)}
td.num,th.num{text-align:right}
.state{font-family:"IBM Plex Mono",monospace;font-size:10.5px;font-weight:600;letter-spacing:.06em;
 text-transform:uppercase;padding:2px 7px;white-space:nowrap}
.state--healthy{background:var(--good-s);color:var(--good)}
.state--fault{background:var(--bad-s);color:var(--bad)}
footer{margin-top:60px;padding-top:20px;border-top:1px solid var(--rule);font-size:13px;color:var(--ink-3)}
@media(max-width:620px){.fnd{grid-template-columns:1fr;gap:6px}.fnd__chip{padding-top:0}}
</style>
<div class="wrap">
<header class="mast">
  <p class="eyebrow">5-minute inverter data &middot; Cascavel 3.96 kWp</p>
  <h1>The array was never broken. It was dirty.</h1>
  <p class="standfirst">694,488 five-minute records from the Fronius Primo cross-referenced against NASA POWER.
  The two-year performance collapse has a diagnosis, the azimuth the audit called unidentifiable is now pinned,
  and the array is quietly soiling up again.</p>
  <dl class="specs">
    <div class="spec"><dt>Records</dt><dd class="mono">694,488</dd></div>
    <div class="spec"><dt>Daylight</dt><dd class="mono">353,702</dd></div>
    <div class="spec"><dt>Channels</dt><dd class="mono">11</dd></div>
    <div class="spec"><dt>Span</dt><dd class="mono">2019-07 →<br>2026-07</dd></div>
    <div class="spec"><dt>String</dt><dd class="mono">12 × 330 Wp<br>one MPPT</dd></div>
    <div class="spec"><dt>Inverter η</dt><dd class="mono">98.53%</dd></div>
  </dl>
</header>

<section>
  <h2><span class="n">01</span> The diagnosis</h2>
  <p class="lede">A single string of twelve modules on one MPPT tracker turns out to be the ideal
  instrument: voltage and current fail in different ways, so the fault names itself.</p>
  <p>Across every regime the string voltage holds within 1% of its healthy value. The current does not
  — it falls 10%, then 16%, then recovers 27% in the single month between October and November 2023.
  A module failure, an open circuit or a conducting bypass diode all cut <em>voltage</em> in discrete
  steps. None of that happened. The inverter's own conversion efficiency never degraded either.</p>
  @@F22@@
  <div class="tablewrap"><table>
    <thead><tr><th>Regime</th><th>State</th><th class="num">Vmp (V)</th>
      <th class="num">Impp per kW/m²</th><th class="num">Current vs baseline</th></tr></thead>
    <tbody>@@ROWS@@</tbody></table></div>
  <p>What remains is something that attenuates light before it reaches the cells, uniformly across all
  twelve modules, building up over months and removable in an afternoon.</p>

  <div class="finding">
    <span class="k">The clinching detail</span>
    <p>The November 2023 cleaning restored <b>+28%</b> of current at high sun and <b>+54%</b> at low sun,
    smoothly across every elevation band, in the morning and the evening alike. An obstruction removes
    one band of sky. A dirt layer attenuates more the more obliquely the light crosses it — which is
    exactly the shape recovered.</p>
  </div>
  @@F23@@
  @@F26@@

  <h3>Why seven years of daily data said the opposite</h3>
  <p>The audit tested soiling against dry-spell length and found nothing — performance actually rose
  slightly as dry spells lengthened. That result was correct and the inference from it was wrong. It
  tests for loose dust that rain washes off. At <b>13° of tilt</b> there is not enough slope for rain
  to sheet off and carry deposits with it, so what accumulates cements in place. It is invisible to a
  dry-spell test by construction, and it comes off only with a hose.</p>
</section>

<section>
  <h2><span class="n">02</span> The azimuth, and a correction</h2>
  <p class="lede">The audit said array azimuth was provably unidentifiable from daily totals. That was
  right, and the 5-minute data proves it by resolving it.</p>
  @@F21@@
  <div class="finding">
    <span class="k">An error of mine, and its blast radius</span>
    <p>I mapped the datasheet's “25° east of north” to Duffie–Beckman γ = 155. That is 25° <em>west</em>
    of north: the rotation runs south → west → north → east, so east of north is 180+25 = <b>205</b>.
    Because daily plane-of-array irradiance at γ = 155 and γ = 205 is identical to 3.6×10⁻¹⁵ kWh/m²,
    nothing computed at daily resolution moves — performance ratio, the regimes, the 6,365 kWh
    shortfall, all unchanged. The mistake only had teeth once the intraday shape mattered, and the
    5-minute fit then recovered 202.5°, two and a half degrees from truth.</p>
  </div>
</section>

<section>
  <h2><span class="n">03</span> Every question the audit left open</h2>
  <div class="fndlist">@@CARDS@@</div>
</section>

<section>
  <h2><span class="n">04</span> Calibrating the reanalysis</h2>
  <p class="lede">With a clear-sky reference built from the plant's own geometry, NASA POWER can be
  checked rather than trusted.</p>
  <p>On clear days POWER reads <b>3.2% low</b>, as a fixed offset rather than a scale error — slope
  1.0032, intercept −0.21 kWh/m², R² 0.914 — and the ratio carries a <b>4.1-point seasonal cycle</b>.
  That is the floor under everything the daily analysis could resolve, and it is why a 0.5 %/yr
  degradation rate was never going to come out of seven years of it.</p>
  @@F25@@
  @@F24@@
</section>

<section>
  <h2><span class="n">05</span> What to do</h2>
  <p class="lede">One finding is operational and current.</p>
  <p>The string current has been falling again since the September 2024 cleaning and is now about
  <b>8% below baseline</b> — roughly a third of the way back to the 2023 state. The pattern is a
  clean sawtooth: about twelve months to lose 10%, two years to lose 20%, reset by a wash.
  <b>An annual cleaning, scheduled rather than reactive, holds the array within a few percent of
  baseline.</b></p>
  <p>Whether that is worth doing is a separate question, and the billing data already answered it: the
  array generates 2.6× what the house consumes, the credit balance reached 10,383 kWh, and 1,548 kWh
  expired unused in 2024. Recovered kWh have no offset value at this consumption level. Clean it to
  keep the asset healthy and the warranty intact — not to lower the bill, which it will not.</p>
  <p>The genuinely valuable move remains shifting load into daylight or adding storage, so that
  generation has somewhere to go.</p>
</section>

<footer>
  5-minute inverter export 2019-07-26 to 2026-07-26, 694,488 unique records after removing the 982
  duplicated rows at the annual file boundaries. Clear-sky reference: Haurwitz global, Erbs split,
  HDKR transposition on the datasheet geometry. Analysis 2026-09-14.
</footer>
</div>
"""
for k,v in [("@@F22@@",fig("22_fault_fingerprint")),("@@ROWS@@",rows),
            ("@@F23@@",fig("23_soiling_signature")),("@@F26@@",fig("26_day_curves")),
            ("@@F21@@",fig("21_azimuth_resolved")),("@@CARDS@@","".join(cards)),
            ("@@F25@@",fig("25_power_bias")),("@@F24@@",fig("24_inverter_efficiency"))]:
    HTML = HTML.replace(k, v)


open(caminho("report5.html"), "w", encoding="utf-8").write(HTML)
print("report5.html  %.2f MB" % (os.path.getsize(caminho("report5.html"))/1e6))
