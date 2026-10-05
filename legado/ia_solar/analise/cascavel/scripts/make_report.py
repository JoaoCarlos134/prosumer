# -*- coding: utf-8 -*-
"""Assemble the standalone HTML report with base64-embedded figures."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "comum" / "scripts"))
from caminhos import caminho
import base64, os, glob
from PIL import Image

FIGDIR = caminho("figs_opt")
os.makedirs(FIGDIR, exist_ok=True)
for p in sorted(glob.glob(caminho("figs/[01]?_*.png")) + glob.glob(caminho("figs/20_*.png"))):
    Image.open(p).convert("RGB").quantize(colors=180, method=Image.MEDIANCUT,
        dither=Image.FLOYDSTEINBERG).save(os.path.join(FIGDIR, os.path.basename(p)), optimize=True)
SLUG = {"01":"pr_timeline","02":"pr_heatmap","03":"cumulative_shortfall","04":"annual",
        "05":"energy_vs_poa","06":"loss_waterfall","07":"driver_grid","08":"driver_ranking",
        "09":"driver_grid_healthy","10":"confounding","11":"multivariate","12":"temp_coefficient",
        "13":"soiling","14":"orientation_fit","15":"degradation","16":"model_validation",
        "17":"pr_distributions","18":"generation_vs_load","19":"credits","20":"bill"}

def b64(n):
    with open(os.path.join(FIGDIR, n + "_" + SLUG[n] + ".png"), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

FIGS = {
 "01": ("Temp-corrected performance ratio, daily and 30-day median",
        "Green bands are healthy regimes, red are degraded ones; horizontal bars are segment means from "
        "changepoint detection. The recovery at Nov 2023 happens between two consecutive months."),
 "02": ("Monthly mean PR by calendar month and year",
        "Reading down a column shows the loss is a period effect, not a seasonal one - every month of "
        "2023 is depressed, not just summer."),
 "03": ("Cumulative generation against a healthy-baseline counterfactual",
        "The counterfactual holds PR at 0.871 - the mean of the 2019-2021 plateau - against the same "
        "modelled POA irradiance."),
 "17": ("Distribution of daily temp-corrected PR by regime",
        "Separated distributions with similar spread: the signature of a step change in system state "
        "rather than gradual drift."),
 "18": ("Monthly generation against household consumption",
        "The array has never produced less than the house consumes, in any month of any year. Everything "
        "above the orange line is exported and becomes a credit."),
 "19": ("Credit balance at year end, and credits that expired in 2024",
        "The balance grows every year and can never be spent against a 2 200 kWh annual load. The 2024 "
        "write-off is energy injected in 2019 hitting the 60-month expiry limit."),
 "20": ("Annual bill and the effective cost of each kWh consumed",
        "2018 is the only pre-PV year. The step down in 2020 is the array; the drift back up since is "
        "fixed charges and tariff inflation, neither of which more generation can touch."),
 "07": ("Temp-corrected PR against all 30 derived drivers, whole record",
        "Dots are daily values shaded light to dark by date; the orange spine is a binned median with "
        "its interquartile band. These are marginal relationships and most are confounded."),
 "09": ("The same 30 drivers, healthy regimes only",
        "Removing the fault strips most of the apparent effects. Where the within-regime r is much "
        "smaller than the whole-record r, the driver was mostly a proxy for the fault period."),
 "10": ("Whole-record correlation against within-regime correlation",
        "Points below the diagonal have their apparent effect inflated by the fault episode."),
 "11": ("Standardised driver effects, with and without regime fixed effects",
        "Change in temp-corrected PR per standard deviation of each driver, with 95% confidence "
        "intervals. Controlling for regime nearly doubles explained variance."),
 "08": ("Drivers ranked by marginal correlation with temp-corrected PR",
        "A map of what covaries with efficiency, not what causes it."),
 "05": ("Daily energy against plane-of-array irradiation, coloured by date",
        "Each fitted line is one regime. The fan of slopes is the efficiency loss: same irradiance, "
        "less energy."),
 "06": ("Loss budget from reference yield to delivered energy",
        "Thermal loss is modelled from cell temperature. The residual lumps soiling, inverter, wiring, "
        "mismatch, shading and the fault - daily data cannot split it further."),
 "04": ("Specific yield and performance ratio, complete calendar years",
        "Now on the true 3.96 kWp rating. 2019 and 2026 are excluded as partial years."),
 "12": ("Estimating the module power temperature coefficient",
        "Left: the raw slope on clear days. Right: the same slope after removing clearness, air mass and "
        "diffuse fraction. Both are far weaker than any datasheet value, because a residual seasonal bias "
        "in the model pushes against the temperature signal."),
 "15": ("Monthly PR within the current healthy regime",
        "The fitted trend is negative but nowhere near significant, and the interval is far too wide to "
        "rule out - or confirm - normal degradation."),
 "13": ("Efficiency against dry-spell length",
        "With the correct geometry the soiling signal is a flat null rather than the wrong sign it showed "
        "before. Cascavel rains often enough that dust never accumulates far."),
 "14": ("Fitted orientation checked against the datasheet",
        "Left: R² against tilt peaks at 14 degrees, one degree from the true 13, and the earlier fit of 17 "
        "sits inside the plateau. Right: R² against azimuth is exactly symmetric about due north, so the "
        "true 155 degrees and its mirror at 205 are indistinguishable by construction."),
 "16": ("Residual diagnostics for the NASA POWER plus transposition model",
        "Mean bias is negligible and daily scatter is 11%. The residual seasonal structure - winter low, "
        "summer high - is the model's error floor and the reason the temperature coefficient will not "
        "come out right."),
}

EST = [
 ("known", "Array geometry", "13&deg; tilt, 25&deg; E of N",
  "Now read from the datasheet rather than fitted. The fitted tilt of 17&deg; was correct to within the plateau; the fitted azimuth of 244&deg; was wrong by 89&deg;.", "14"),
 ("known", "Rated power", "3.96 kWp DC &middot; 4.0 kW AC",
  "12 &times; 330 Wp. The supplied kWh/kWp column divides by 4.00, so every specific-yield figure in the source workbook is 1% low. DC/AC ratio 0.99 means inverter clipping is structurally impossible.", ""),
 ("solid", "Performance ratio (IEC 61724)", "0.758 raw &middot; 0.809 temp-corrected",
  "Daily energy over POA irradiance &times; rated power, on the true geometry.", "1, 2, 4"),
 ("solid", "Specific yield", "1434 kWh/kWp&middot;yr",
  "Complete calendar years, on the corrected 3.96 kWp rating.", "4"),
 ("solid", "Fault detection and dating", "5 breaks; recovery Nov 2023",
  "Exact dynamic-programming changepoint search on monthly PR, BIC-selected. The Nov 2023 step is +21.1% in a single month.", "1, 17"),
 ("solid", "Energy shortfall vs. baseline", "6365 kWh &middot; 13.6%",
  "Counterfactual at the 2019-21 plateau PR of 0.871 against the same modelled irradiance.", "3"),
 ("solid", "Reference yield (POA)", "1899 kWh/m&sup2;&middot;yr",
  "Erbs decomposition, Collares-Pereira hourly synthesis, HDKR anisotropic transposition, ground albedo from POWER, on the datasheet geometry.", "5"),
 ("solid", "Thermal loss share", "&minus;7.4%",
  "Faiman cell-temperature model driven by POA, air temperature and wind, irradiance-weighted to daily.", "6"),
 ("solid", "Model skill", "MBE +0.6% &middot; rRMSE 11.1%",
  "Daily energy, healthy regimes. Normal for reanalysis irradiance.", "16"),
 ("solid", "Driver attribution", "R&sup2; 0.15 &rarr; 0.29 with regime",
  "System state explains as much of the efficiency variance as every weather variable combined.", "7, 9, 10, 11"),
 ("solid", "Load coverage", "2.60&times; consumption",
  "5652 kWh generated against 2183 kWh consumed, averaged over 2020-2024. Only 23% of generation is used on site.", "18"),
 ("solid", "Credit accumulation and expiry", "10 383 kWh banked &middot; 1548 kWh lost",
  "The balance grows every year; the 2024 write-off is 2019 energy hitting the 60-month limit. This is the finding that reframes the fault.", "19"),
 ("solid", "Bill impact", "R$ 0.833 &rarr; R$ 0.418 per kWh",
  "Effective cost of a consumed kWh, 2018 against 2024. Annual payment fell from R$ 2500 to R$ 996 despite similar consumption.", "20"),
 ("partial", "Residual seasonality", "6&ndash;9% peak-to-peak",
  "Winter PR runs about 3.5% below the annual mean and late summer about 2.5% above, after temperature correction. An ASHRAE incidence-angle model was tested and does not explain it. Most likely near-field shading at low winter sun, or a seasonal bias in the reanalysis irradiance for this cell. Unresolved, and it contaminates the temperature estimate.", "16"),
 ("partial", "Degradation rate", "&minus;1.49 &plusmn; 3.24 %/yr",
  "Not separable from the step changes over the full record - a naive fit returns &minus;0.85 %/yr, which is the fault, not ageing. Within the current clean regime the interval spans far more than any plausible degradation rate. Needs 3-5 years of uninterrupted operation.", "15"),
 ("partial", "Loss budget split", "residual &minus;16.6%",
  "Soiling, inverter conversion, wiring, mismatch and shading all land in one term.", "6"),
 ("none", "Module temperature coefficient", "not recoverable",
  "The clear-day slope gives &minus;0.21 %/K and the partial estimate &minus;0.16 &plusmn; 0.09 %/K, against a datasheet expectation near &minus;0.40. The residual winter deficit runs opposite to the temperature signal and cancels most of it. This was reported as indicative before the true geometry was known; on the correct geometry it is worse, and should not be used.", "12"),
 ("none", "Array azimuth from data", "provably not identifiable",
  "R&sup2; against azimuth is <em>exactly</em> symmetric about due north - the fitted values at 155&deg; and 205&deg; differ by zero to machine precision. A daily energy total cannot distinguish an eastward tilt from its westward mirror. This is a structural property of daily aggregation, not a lack of data.", "14"),
 ("none", "Soiling rate", "flat null",
  "&minus;0.07 %/dry-day, p = 0.31. On the corrected geometry the wrong-signed result disappears but no real signal replaces it.", "13"),
 ("none", "Inverter clipping", "structurally absent",
  "DC/AC of 0.99 rules it out, so there is nothing to estimate."),
 ("none", "Shading profile", "needs sub-daily data",
  "Near-field shading has a time-of-day signature that daily totals average away - and it is the leading candidate for the winter deficit."),
 ("none", "Module vs. inverter fault attribution", "needs string-level data",
  "The Nov 2023 step tells you something was fixed, not what."),
]

ROWS = [
 ("2019-08","2021-05",22,0.871,"healthy",11788,1049, 8.2),
 ("2021-06","2022-09",16,0.782,"fault",   7099,1388,16.4),
 ("2022-10","2023-10",13,0.712,"fault",   5399,1656,23.5),
 ("2023-11","2024-03", 5,0.862,"healthy", 2778, 346,11.1),
 ("2024-04","2024-08", 5,0.750,"fault",   1796, 364,16.9),
 ("2024-09","2026-08",24,0.832,"healthy",11485,1561,12.0),
]

REV = [
 ("Rated power", "4.00 kWp assumed", "3.96 kWp (12 &times; 330 Wp)", "PR up 1%; the workbook's own kWh/kWp column is 1% low"),
 ("Tilt", "17&deg; fitted", "13&deg;", "fit was inside the plateau - validated"),
 ("Azimuth", "244&deg; fitted", "155&deg; (25&deg; E of N)", "fit was wrong by 89&deg; - as the diagnostic predicted"),
 ("Coordinates", "city centre", "24&deg;49'30.4\"S 53&deg;38'43.9\"W", "same POWER grid cell: no effect at all"),
 ("Inverter", "unknown", "4.0 kW AC", "DC/AC 0.99 - clipping ruled out"),
 ("Consumption &amp; billing", "not available", "2018-2024 monthly", "reframes the whole cost argument"),
]

def fig(n):
    t, c = FIGS[n]
    return (f'<figure class="plate"><img src="{b64(n)}" alt="{t}" loading="lazy">'
            f'<figcaption><span class="fignum">Fig&nbsp;{n}</span> <b>{t}.</b> {c}</figcaption></figure>')

CHIP = {"known":("&#9632;","Now known"), "solid":("&#9679;","Solid"),
        "partial":("&#9680;","Indicative"), "none":("&#9675;","Not identifiable")}
est_html = []
for kind, name, val, note, *fr in EST:
    g, lbl = CHIP[kind]
    ref = f'<span class="figref">Fig {fr[0]}</span>' if fr and fr[0] else ""
    est_html.append(f'<div class="est est--{kind}"><div class="est__chip"><span class="glyph">{g}</span>{lbl}</div>'
                    f'<div class="est__body"><h4>{name}</h4><p class="est__val">{val}</p>'
                    f'<p class="est__note">{note} {ref}</p></div></div>')

seg_html = "".join(
 f'<tr class="seg--{st}"><td class="mono">{a} &rarr; {b}</td><td class="mono num">{mo}</td>'
 f'<td class="mono num"><b>{pr:.3f}</b></td>'
 f'<td><span class="state state--{st}">{"healthy" if st=="healthy" else "degraded"}</span></td>'
 f'<td class="mono num">{e:,}</td><td class="mono num">{lo:,}</td><td class="mono num">{pc:.1f}%</td></tr>'
 for a,b,mo,pr,st,e,lo,pc in ROWS)

rev_html = "".join(
 f'<tr><td>{w}</td><td class="mono was">{o}</td><td class="mono now">{n}</td><td class="eff">{e}</td></tr>'
 for w,o,n,e in REV)

HTML = f"""<title>Cascavel PV Performance Audit</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root {{
  color-scheme: light;
  --ground:#f5f7f8; --surface:#ffffff;
  --ink:#131920; --ink-2:#4a5560; --ink-3:#77828d;
  --rule:#dbe1e6; --rule-2:#eceff2;
  --accent:#b4690e; --accent-s:#f6ecdd;
  --good:#1b7a53; --good-s:#e4f1eb;
  --bad:#b3322f; --bad-s:#f8e8e7;
  --plate:#fcfcfb; --measure:68ch; --wide:1080px;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --ground:#0f1317; --surface:#171c22;
    --ink:#eef2f5; --ink-2:#b3bdc7; --ink-3:#7d8792;
    --rule:#2a333c; --rule-2:#20272e;
    --accent:#e0952f; --accent-s:#2e2415;
    --good:#4bbd8c; --good-s:#15271f;
    --bad:#e8706c; --bad-s:#2b1818;
    --plate:#fcfcfb;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --ground:#0f1317; --surface:#171c22;
  --ink:#eef2f5; --ink-2:#b3bdc7; --ink-3:#7d8792;
  --rule:#2a333c; --rule-2:#20272e;
  --accent:#e0952f; --accent-s:#2e2415;
  --good:#4bbd8c; --good-s:#15271f;
  --bad:#e8706c; --bad-s:#2b1818;
  --plate:#fcfcfb;
}}
* {{ box-sizing:border-box; }}
body {{
  background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
  font-size:16px; line-height:1.62; -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:var(--wide); margin:0 auto; padding-inline:24px; padding-block:0 72px; }}
.mono {{ font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace; font-variant-numeric:tabular-nums; }}

header.mast {{ padding-block:56px 28px; border-bottom:2px solid var(--ink); }}
.eyebrow {{ font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.13em;
  text-transform:uppercase; color:var(--accent); font-weight:600; margin:0 0 14px; }}
h1 {{ font-size:clamp(30px,5.2vw,46px); line-height:1.08; letter-spacing:-.022em;
  font-weight:600; margin:0 0 16px; text-wrap:balance; max-width:20ch; }}
.standfirst {{ font-size:18px; color:var(--ink-2); margin:0; max-width:var(--measure); }}
.specs {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(128px,1fr)); gap:1px;
  background:var(--rule); border:1px solid var(--rule); margin-block:32px 0; }}
.spec {{ background:var(--ground); padding:12px 14px; }}
.spec dt {{ font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--ink-3); margin:0 0 5px; }}
.spec dd {{ margin:0; font-size:15px; font-weight:600; letter-spacing:-.01em; }}

section {{ padding-block:52px 0; }}
h2 {{ font-size:13px; font-family:"IBM Plex Mono",monospace; font-weight:600; letter-spacing:.12em;
  text-transform:uppercase; color:var(--ink); margin:0 0 8px; padding-bottom:8px;
  border-bottom:1px solid var(--rule); display:flex; align-items:baseline; gap:12px; }}
h2 .n {{ color:var(--accent); }}
h3 {{ font-size:22px; font-weight:600; letter-spacing:-.018em; margin:30px 0 10px; text-wrap:balance; }}
p {{ margin:0 0 15px; max-width:var(--measure); }}
.lede {{ font-size:17.5px; color:var(--ink-2); margin-top:18px; }}
b,strong {{ font-weight:600; }}
code {{ font-family:"IBM Plex Mono",monospace; font-size:.88em; background:var(--rule-2);
  padding:1px 5px; border-radius:3px; }}

.finding {{ border-left:3px solid var(--accent); background:var(--accent-s);
  padding:18px 22px; margin:26px 0; max-width:var(--measure); }}
.finding p:last-child {{ margin-bottom:0; }}
.finding .k {{ font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--accent); font-weight:600; display:block; margin-bottom:6px; }}

.plate {{ margin:34px 0; }}
.plate img {{ display:block; width:100%; max-width:100%; height:auto;
  background:var(--plate); border:1px solid var(--rule); }}
figcaption {{ font-size:13.5px; line-height:1.55; color:var(--ink-2); margin-top:10px; max-width:84ch; }}
.fignum {{ font-family:"IBM Plex Mono",monospace; font-size:11px; font-weight:600;
  letter-spacing:.08em; color:var(--accent); text-transform:uppercase; }}
figcaption b {{ color:var(--ink); font-weight:600; }}

.estlist {{ display:flex; flex-direction:column; gap:1px; background:var(--rule);
  border-block:1px solid var(--rule); margin-top:22px; }}
.est {{ background:var(--ground); display:grid; grid-template-columns:150px 1fr; gap:20px; padding:16px 0; }}
.est__chip {{ font-family:"IBM Plex Mono",monospace; font-size:11px; font-weight:600;
  letter-spacing:.07em; text-transform:uppercase; display:flex; align-items:baseline; gap:7px; padding-top:3px; }}
.est__chip .glyph {{ font-size:12px; line-height:1; }}
.est--known   .est__chip {{ color:var(--ink); }}
.est--solid   .est__chip {{ color:var(--good); }}
.est--partial .est__chip {{ color:var(--accent); }}
.est--none    .est__chip {{ color:var(--ink-3); }}
.est__body h4 {{ margin:0 0 3px; font-size:16.5px; font-weight:600; letter-spacing:-.012em; }}
.est__val {{ font-family:"IBM Plex Mono",monospace; font-size:15px; font-weight:500; margin:0 0 6px;
  color:var(--ink); font-variant-numeric:tabular-nums; }}
.est--none .est__val {{ color:var(--ink-3); }}
.est__note {{ font-size:14px; color:var(--ink-2); margin:0; max-width:76ch; }}
.figref {{ font-family:"IBM Plex Mono",monospace; font-size:11px; color:var(--accent);
  border:1px solid var(--rule); padding:1px 5px; white-space:nowrap; margin-left:2px; }}

.tablewrap {{ overflow-x:auto; margin:24px 0; }}
table {{ border-collapse:collapse; width:100%; min-width:620px; font-size:14px; }}
th {{ font-family:"IBM Plex Mono",monospace; font-size:10.5px; letter-spacing:.09em;
  text-transform:uppercase; color:var(--ink-3); font-weight:600; text-align:left;
  padding:0 14px 8px 0; border-bottom:1px solid var(--ink); }}
td {{ padding:9px 14px 9px 0; border-bottom:1px solid var(--rule-2); vertical-align:top; }}
td.num, th.num {{ text-align:right; }}
td.was {{ color:var(--ink-3); text-decoration:line-through; }}
td.now {{ color:var(--ink); font-weight:500; }}
td.eff {{ color:var(--ink-2); font-size:13.5px; }}
.state {{ font-family:"IBM Plex Mono",monospace; font-size:10.5px; font-weight:600;
  letter-spacing:.06em; text-transform:uppercase; padding:2px 7px; white-space:nowrap; }}
.state--healthy {{ background:var(--good-s); color:var(--good); }}
.state--fault {{ background:var(--bad-s); color:var(--bad); }}

.files {{ font-size:14px; margin-top:18px; }}
.files div {{ display:flex; gap:14px; padding:7px 0; border-bottom:1px solid var(--rule-2); }}
.files .p {{ font-family:"IBM Plex Mono",monospace; color:var(--ink); white-space:nowrap; font-size:13px; }}
.files .d {{ color:var(--ink-2); }}
footer {{ margin-top:64px; padding-top:20px; border-top:1px solid var(--rule);
  font-size:13px; color:var(--ink-3); }}
@media (max-width:620px) {{
  .est {{ grid-template-columns:1fr; gap:6px; }}
  .est__chip {{ padding-top:0; }}
  header.mast {{ padding-block:36px 22px; }}
}}
</style>

<div class="wrap">

<header class="mast">
  <p class="eyebrow">Photovoltaic performance assessment &middot; revised on datasheet inputs</p>
  <h1>What seven years of daily generation can and cannot tell you</h1>
  <p class="standfirst">A 3.96&nbsp;kWp rooftop array in Cascavel, Paran&aacute;, against 21 daily
  meteorological variables and seven years of electricity bills. Two headlines: a two-year fault
  that was fixed in November 2023, and the fact that it barely cost anything.</p>
  <dl class="specs">
    <div class="spec"><dt>Array</dt><dd class="mono">12 &times; 330 Wp<br>3.96 kWp</dd></div>
    <div class="spec"><dt>Inverter</dt><dd class="mono">4.0 kW AC</dd></div>
    <div class="spec"><dt>Geometry</dt><dd class="mono">13&deg; tilt<br>25&deg; E of N</dd></div>
    <div class="spec"><dt>Site</dt><dd class="mono">24.83&deg;S<br>53.65&deg;W</dd></div>
    <div class="spec"><dt>Days</dt><dd class="mono">2599</dd></div>
    <div class="spec"><dt>Mean PR</dt><dd class="mono">0.758</dd></div>
  </dl>
</header>

<section>
  <h2><span class="n">01</span> What the datasheet changed</h2>
  <p class="lede">The billing workbook supplied the rating, geometry and coordinates that were
  previously assumed or fitted. Here is what moved, and what it did to the conclusions.</p>
  <div class="tablewrap">
  <table>
    <thead><tr><th>Input</th><th>Was</th><th>Is</th><th>Effect on the analysis</th></tr></thead>
    <tbody>{rev_html}</tbody>
  </table>
  </div>

  <div class="finding">
    <span class="k">The fitted geometry, graded</span>
    <p>Tilt came out right: R&sup2; against tilt peaks at 14&deg; and the earlier fit of 17&deg; sits
    inside the plateau around the true 13&deg;. Azimuth came out wrong by 89&deg; &mdash; and the
    reason is now provable rather than suspected. R&sup2; against azimuth is <b>exactly symmetric
    about due north</b>: the values at the true 155&deg; and its mirror 205&deg; differ by zero to
    machine precision. A daily energy total contains no information that separates an eastward tilt
    from its westward twin.</p>
  </div>
  {fig("14")}

  <p>Everything structural survived. The regime dates, the November 2023 step, the shape of every
  driver relationship and the conclusion that system state dominates weather are unchanged. What
  moved is the level: PR is now <b>0.758</b> rather than 0.775, the healthy baseline <b>0.871</b>
  rather than 0.885, and the shortfall <b>6365&nbsp;kWh</b> rather than 5750. The corrected
  coordinates land in the same NASA POWER grid cell as the ones used before, so the meteorology is
  byte-identical &mdash; that caveat turned out to be moot.</p>
  <p>One data-quality note worth carrying back to the workbook: the <code>Gera&ccedil;&atilde;o</code>
  sheet records 287.6&nbsp;kWh for December 2024, but the daily series sums to 522.2&nbsp;kWh for
  that month. Every other month in both files agrees to the kWh, so the summary sheet was almost
  certainly filled in mid-month. The daily series is the one to trust.</p>
</section>

<section>
  <h2><span class="n">02</span> The fault</h2>
  <p class="lede">Your generation series does not show a system wearing out. It shows a healthy array,
  a progressive fault from mid-2021, and an abrupt repair.</p>
  <p>Performance ratio sat at <b>0.871</b> for the first two years, fell in two steps to <b>0.712</b>
  by late 2023 &mdash; an 18% loss with nothing to do with weather &mdash; then jumped back to
  <b>0.862</b> between October and November 2023. A single-month step of +21% is a repair or a
  cleaning, not a physical process.</p>

  <div class="finding">
    <span class="k">Why this governs the whole analysis</span>
    <p>A straight line through the whole record returns &minus;0.85 %/yr and looks like a textbook
    degradation rate. It is the fault, not ageing. Once the regimes are separated the current one
    trends at &minus;1.49 &plusmn; 3.24 %/yr &mdash; statistically nothing. Any degradation figure
    computed from this series without handling the steps first will be wrong.</p>
  </div>

  {fig("01")}
  {fig("03")}

  <div class="tablewrap">
  <table>
    <thead><tr><th>Regime</th><th class="num">Months</th><th class="num">PR</th><th>State</th>
    <th class="num">Generated</th><th class="num">Shortfall</th><th class="num">Lost</th></tr></thead>
    <tbody>{seg_html}</tbody>
  </table>
  </div>
  <p style="font-size:13.5px;color:var(--ink-2)">Segments from exact dynamic-programming changepoint
  search on monthly temp-corrected PR, BIC-selected. Energy in kWh.</p>

  {fig("17")}
  {fig("02")}
</section>

<section>
  <h2><span class="n">03</span> What it actually cost</h2>
  <p class="lede">The billing data answers a question the generation data cannot: whether any of the
  lost energy was worth anything. Mostly, it was not.</p>

  <p>The array generates <b>5652&nbsp;kWh a year</b> against a household consumption of
  <b>2183&nbsp;kWh</b>. That is a coverage ratio of <b>2.60&times;</b>, and it holds in every month of
  every year &mdash; generation has never once fallen below consumption. Only <b>23%</b> of what the
  array makes is used on site; the rest is exported as credit.</p>

  {fig("18")}

  <p>Those credits are not being spent. The balance reached <b>10 383&nbsp;kWh</b> by the end of 2024,
  roughly five years of household consumption, and in 2024 <b>1548&nbsp;kWh</b> expired unused &mdash;
  energy injected in 2019 hitting the 60-month limit.</p>

  {fig("19")}

  <div class="finding">
    <span class="k">The reframe</span>
    <p>The fault cost <b>6365&nbsp;kWh</b> of generation. But over the same period the credit balance
    grew every single year and credits started expiring unused. The marginal exported kWh had no
    offset value, because there was never any consumption left for it to offset. The fault is a real
    engineering problem and it was right to fix it &mdash; but its financial cost was close to zero,
    and chasing the last few points of PR on this system will not reduce the bill.</p>
  </div>

  <p>What the bill did do is halve. The effective cost of a consumed kWh went from <b>R$&nbsp;0.833</b>
  in 2018, the only pre-PV year, to <b>R$&nbsp;0.346</b> in 2020. It has since drifted back to
  <b>R$&nbsp;0.418</b> &mdash; fixed availability charges, the Lei 14.300 wire-fee phase-in and tariff
  inflation, none of which more generation can touch. The remaining R$&nbsp;996 a year is largely
  irreducible.</p>

  {fig("20")}

  <p>The actionable conclusion is not about the array. It is that this system is roughly 2.6&times;
  oversized for its load, so the return on any further performance work is small. Value would come
  instead from shifting consumption into daylight hours, adding a controllable load, or storage
  &mdash; anything that converts exported kWh into self-consumed kWh.</p>
</section>

<section>
  <h2><span class="n">04</span> What can be estimated</h2>
  <p class="lede">Twenty-two candidate quantities, sorted by whether daily energy, daily reanalysis
  weather and monthly bills can actually support them.</p>
  <p>The distinction that matters is not statistical significance &mdash; with 2599 days almost
  everything is significant. It is whether the quantity is <em>identifiable</em>: whether this data
  contains information about it at all, or whether an apparent effect is a proxy for something else.</p>
  <div class="estlist">{''.join(est_html)}</div>
</section>

<section>
  <h2><span class="n">05</span> Efficiency against every driver</h2>
  <p class="lede">Thirty derived variables against temp-corrected PR. This is the complete set the
  data supports.</p>
  <p>Seven irradiance and sky variables, nine thermal and humidity variables, five precipitation and
  soiling proxies, four geometric variables, plus aerosol, albedo, pressure and a spectral proxy, all
  derived from the 21 NASA POWER parameters and solar geometry for the site.</p>

  {fig("07")}
  <p>Read alone this grid is misleading. Most of these correlations are the fault in disguise: any
  variable with a trend or a seasonal cycle picks up the 2021&ndash;23 depression and looks like a
  driver of efficiency.</p>
  {fig("09")}
  {fig("10")}

  <h3>What survives the control</h3>
  <p>Adding regime fixed effects to a standardised multivariate model lifts explained variance from
  <b>0.150 to 0.291</b>. System state accounts for as much of the daily efficiency variation as all
  the weather variables put together.</p>
  {fig("11")}

  <p>Two caveats on those coefficients. The irradiance variables are strongly collinear &mdash; POA,
  clearness index and diffuse fraction measure overlapping things, which is why POA carries a negative
  coefficient once clearness is held fixed. And the strongest raw correlate of PR is precipitation at
  &minus;0.29, which is largely artefact: on overcast days reanalysis irradiance is least accurate and
  the PR denominator is smallest. Low-light inverter efficiency contributes too, and the two cannot be
  separated here.</p>

  {fig("08")}
  {fig("05")}
  {fig("06")}
  {fig("04")}
</section>

<section>
  <h2><span class="n">06</span> Parameter estimates</h2>
  <p class="lede">Three quantities the data can be pushed toward, and an honest account of how far
  each can be trusted. On the corrected geometry, one of them got worse.</p>

  <h3>Temperature coefficient &mdash; withdrawn</h3>
  <p>The clear-day regression now gives <b>&minus;0.21 %/K</b> and the partial estimate, after
  removing clearness, air mass and diffuse fraction, <b>&minus;0.16 &plusmn; 0.09 %/K</b>. A 330 Wp
  module's datasheet value would be near &minus;0.40 %/K. The estimate is too weak because a residual
  seasonal bias in the model &mdash; winter PR about 3.5% low, late summer about 2.5% high &mdash;
  runs directly against the temperature signal and cancels most of it. On the assumed geometry this
  looked like a usable if soft estimate; on the true geometry it does not. Do not use it.</p>
  {fig("12")}

  <p>The seasonal residual is now the largest unexplained term in the model. An ASHRAE
  incidence-angle correction was tested against it &mdash; plausible given the unusually low 13&deg;
  tilt &mdash; and it does not work: even an aggressive coefficient closes less than a sixth of the
  gap while making the daily fit slightly worse. The leading remaining candidates are near-field
  shading at low winter sun and a seasonal bias in the reanalysis irradiance for this grid cell.
  Sub-daily data would separate them immediately.</p>

  <h3>Degradation</h3>
  <p>Not estimable over the full record. Within the current clean regime the trend is <b>&minus;1.49
  %/yr with a 95% interval of &plusmn;3.24</b> &mdash; consistent with zero and equally consistent
  with any normal degradation rate. Two years of monthly points cannot resolve a 0.5 %/yr signal
  against this scatter.</p>
  {fig("15")}

  <h3>Soiling</h3>
  <p>On the corrected geometry this improves from a wrong-signed result to a clean null:
  <b>&minus;0.07 %/dry-day, p = 0.31</b>. The earlier positive slope was an artefact of the wrong
  array orientation. There is no detectable soiling accumulation, which is unsurprising in a climate
  that rains often enough to keep the glass washed.</p>
  {fig("13")}
</section>

<section>
  <h2><span class="n">07</span> Method and its limits</h2>
  <p>Generation is daily energy for a 3.96 kWp array. Weather is NASA POWER daily point data for
  24.83&deg;S 53.65&deg;W &mdash; 21 parameters covering irradiance, temperature, humidity, wind,
  precipitation, cloud, aerosol and albedo. Billing is monthly consumption, injection, payment and
  credit balance for 2018&ndash;2024.</p>
  <p>Plane-of-array irradiance is not supplied by POWER and had to be modelled: daily global and
  diffuse split into sub-hourly steps using Collares-Pereira &amp; Rabl and Liu &amp; Jordan,
  transposed with the HDKR anisotropic sky model including circumsolar and horizon-brightening terms
  plus ground reflection, then re-summed on the datasheet geometry. Cell temperature uses the Faiman
  model, irradiance-weighted to a daily value. Temperature correction follows IEC 61724-1 at an
  assumed &minus;0.4 %/K &mdash; the assumption stands because, as above, the data cannot replace it.</p>

  <h3>Error floor</h3>
  <p>Against measured daily energy in healthy regimes the model runs <b>+0.6% mean bias and 11.1%
  daily RMSE</b>. That is normal for reanalysis irradiance at a point &mdash; POWER resolves a grid
  cell of roughly half a degree, not a rooftop &mdash; and good enough to detect regime shifts of
  9&ndash;21%. It is not good enough to resolve a 0.5 %/yr degradation rate in under three years, nor
  a temperature coefficient against a 6% seasonal residual.</p>
  {fig("16")}

  <h3>What would unlock the rest</h3>
  <p>Sub-daily inverter data remains the single highest-value addition: it would resolve the winter
  deficit, shading, low-light efficiency and spectral effects, and would make azimuth identifiable
  for the first time. After that, a maintenance log to confirm what was fixed in November 2023, and
  the module and inverter datasheets to replace the assumed temperature coefficient with a real one.</p>
</section>

<section>
  <h2><span class="n">08</span> Files</h2>
  <p>Everything is written to <code>ia_solar/analise/</code> and is reproducible end to end.</p>
  <div class="files">
    <div><span class="p">dados/master.csv</span><span class="d">2599 days &times; 51 columns &mdash; generation, all POWER variables, solar geometry, POA components, cell temperature, PR, soiling proxies</span></div>
    <div><span class="p">dados/billing.csv</span><span class="d">Monthly consumption, injection, payment, credit, self-consumption</span></div>
    <div><span class="p">dados/billing_annual.csv</span><span class="d">Annual energy and economic summary</span></div>
    <div><span class="p">dados/segments.csv</span><span class="d">Detected regimes with PR, trend and lost energy</span></div>
    <div><span class="p">dados/driver_strength.csv</span><span class="d">Correlation of every driver with efficiency</span></div>
    <div><span class="p">dados/confounding.csv</span><span class="d">Whole-record vs. within-regime correlation</span></div>
    <div><span class="p">dados/multivariate.csv</span><span class="d">Standardised coefficients with and without regime control</span></div>
    <div><span class="p">figuras/</span><span class="d">All 20 figures at full resolution</span></div>
    <div><span class="p">scripts/solar.py</span><span class="d">Solar geometry, hourly synthesis, HDKR transposition, Faiman cell temperature</span></div>
    <div><span class="p">scripts/build2.py</span><span class="d">Merge and PR computation on the datasheet geometry</span></div>
    <div><span class="p">scripts/changepoint.py</span><span class="d">Regime detection and energy accounting</span></div>
    <div><span class="p">scripts/billing.py</span><span class="d">Economic layer</span></div>
    <div><span class="p">scripts/estimate.py</span><span class="d">Parameter estimation suite</span></div>
    <div><span class="p">scripts/viz_*.py</span><span class="d">Figure generation</span></div>
  </div>
</section>

<footer>
  Generation 2019-07-26 to 2026-09-11; billing 2018-2024. NASA POWER release through 2026-09-06 for
  irradiance, 2026-05-30 for MERRA-2 derived cloud, aerosol and albedo. Revised 2026-09-11 on
  datasheet inputs from <span class="mono">Fatura de energia.xlsx</span>.
</footer>

</div>
"""

open(caminho("report.html"), "w", encoding="utf-8").write(HTML)
print("report.html  %.2f MB" % (os.path.getsize(caminho("report.html")) / 1e6))
