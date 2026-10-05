# -*- coding: utf-8 -*-
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "comum" / "scripts"))
from caminhos import caminho
import base64, os, glob
from PIL import Image
os.makedirs(caminho("figs2_opt"), exist_ok=True)
for p in list(glob.glob(caminho("figs_curitiba/*.png"))) + [caminho("R4_sites.png"), caminho("figs5/22_fault_fingerprint.png")]:
    Image.open(p).convert("RGB").quantize(colors=180, method=Image.MEDIANCUT,
        dither=Image.FLOYDSTEINBERG).save(os.path.join(caminho("figs2_opt"), os.path.basename(p)), optimize=True)
def b64(n):
    with open(caminho("figs2_opt/%s.png" % n), "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode()

FIGS = {
 "R1_string_fault": ("Irradiance-normalised DC current, per string",
   "Both traces are normalised to their own 2021 baseline, so only relative change shows. MPP1 collapses to "
   "−58% while MPP2 stays near or above baseline, then recovers in a single month. The dashed orange line "
   "is the June 2025 rewiring."),
 "R2_rewiring": ("String voltages either side of June 2025",
   "Vₘₚ on input 1 falls 19% and input 2 rises 21% within one month, while their sum moves 1%. Modules "
   "were moved between the inputs, not added or removed — and combined DC power rose 15%."),
 "R3_asymmetry": ("Afternoon-to-morning current ratio",
   "Left: at low sun the two strings are mirror images — MPP1 favours the afternoon, MPP2 the morning. Right: "
   "the deficit swings hard with season. Neither is what a clean, unshaded, single-orientation array looks like."),
 "22_fault_fingerprint": ("Cascavel for comparison: current and voltage, one string",
   "The same diagnostic on the single-MPPT plant. Current falls, voltage never does — but with only one string "
   "there is nothing to compare against, so 'the array is dirty' could not be separated from 'this string is dirty'."),
}
def fig(n):
    t, c = FIGS[n]
    return ('<figure class="plate"><img src="%s" alt="%s" loading="lazy">'
            '<figcaption><b>%s.</b> %s</figcaption></figure>' % (b64(n), t, t, c))

SITES = [
 ("Usina Cascavel", "Cascavel, PR", "24.83&deg;S 53.65&deg;W", "3.96 kWp (12 &times; 330 Wp)",
  "Fronius Primo 4.0-1, 1 MPPT, single phase", "13&deg; / 25&deg; E of N &mdash; from datasheet, confirmed by data",
  "2019-07 &rarr; 2026-07", "694,488", "1,419", "0.79", "progressive soiling, two cleanings"),
 ("Usina Curitiba", "Curitiba, PR", "25.43&deg;S 49.27&deg;W", "~9.6 kWp estimated (workbook says 12.0)",
  "Fronius Symo 12.0-3, 2 MPPT, three phase 127/220 V", "not recoverable &mdash; see below",
  "2021-07 &rarr; 2026-07", "490,013", "983", "0.67", "string-1 fault, then a rewiring"),
]
rows = "".join(
 "<tr><td><b>%s</b><br><span class='sub'>%s</span></td><td class='mono'>%s</td><td class='mono'>%s</td>"
 "<td>%s</td><td class='mono'>%s</td><td class='mono'>%s</td><td class='mono num'>%s</td>"
 "<td class='mono num'>%s</td><td class='mono num'>%s</td><td>%s</td></tr>" % s for s in SITES)

FINDINGS = [
 ("new", "A string-specific fault, provable", "MPP1 &minus;50%, MPP2 &minus;18%",
  "From December 2022 to July 2023 the first string's irradiance-normalised current fell by half while the second "
  "lost 18%, and both recovered in the single month of August 2023. With two independent trackers this is "
  "unambiguous: the fault was in one string's wiring, connectors or modules, not in the inverter and not in the "
  "weather. Cascavel's single tracker could never have separated these.", "R1_string_fault"),
 ("new", "A rewiring in June 2025", "V1 &minus;19%, V2 +21%, sum +1%",
  "String voltages changed places within one month while their sum barely moved: modules were redistributed "
  "between the two MPPT inputs. Combined DC power rose 15% immediately after, so the reconfiguration worked. "
  "It also means per-string capacity changed, and per-string metrics are not comparable across that date.", "R2_rewiring"),
 ("new", "Mornings are obstructed", "afternoon/morning current up to 5.9&times;",
  "At low sun the two strings are mirror images — one favours the afternoon, the other the morning — and in "
  "summer the ratio reaches 5.9 for MPP1. A fixed obstruction east of the array, combined with two genuinely "
  "different roof orientations, is the only reading consistent with both facts.", "R3_asymmetry"),
 ("open", "Curitiba geometry", "not recoverable",
  "The method that pinned Cascavel's tilt to within 1&deg; fails here: the best single-orientation fit reaches "
  "R&sup2; 0.52 and 0.59 against 0.89 at Cascavel, and returns azimuths (24&deg; and 60&deg; west of north) that "
  "the day curve contradicts — production peaks at solar noon, so the arrays are near due north. The "
  "single-orientation assumption is simply wrong for this roof. The inverter clock was checked and is correct "
  "to within 10 minutes, so that is not the cause.", ""),
 ("open", "Curitiba nameplate", "~9.6 kWp, uncertain",
  "Nothing was supplied. Normalising clear-sky high-irradiance DC power to 1000 W/m&sup2; gives 4.6 + 5.0 kWp, "
  "but that is a lower bound because field power is temperature-depressed, and it inherits the error in the "
  "geometry above. The workbook divides by 12.000 — the inverter's AC rating, which is almost certainly not "
  "the array size. Treat every per-kWp figure for this site as provisional until someone reads the panel labels.", ""),
 ("solid", "Data quality", "cleaner than Cascavel",
  "Zero physical-bound violations — no over-rating AC, no negatives, no impossible power factors, against 47 "
  "energy-register faults at Cascavel. 574 duplicate timestamps, all agreeing exactly. One real gap: ten "
  "consecutive days absent, 23 May to 1 June 2025.", ""),
 ("solid", "Same leakage structure", "5 of 19 channels restate the target",
  "<code>rendimento_especifico &times; 12000 = energia_Wh</code>, <code>energia = producao_fotovoltaica</code>, and "
  "<code>MPP1 + MPP2 = total</code> to within 0.01 Wh. Identical trap to Cascavel, one column wider.", ""),
]
CHIP = {"new":("&#9632;","New"), "solid":("&#9679;","Solid"), "open":("&#9675;","Open")}
cards = "".join(
 '<div class="fnd fnd--%s"><div class="fnd__chip"><span>%s</span>%s</div><div class="fnd__body">'
 '<h4>%s</h4><p class="fnd__val">%s</p><p class="fnd__note">%s %s</p></div></div>'
 % (k, CHIP[k][0], CHIP[k][1], n, v, note,
    ('<span class="figref">see figure</span>' if f_ else ""))
 for k, n, v, note, f_ in FINDINGS)

TREE = [
 ("analise/", "the whole analysis, reorganised by site"),
 ("&nbsp;&nbsp;cascavel/", "Usina Cascavel — 3.96 kWp, 2019-2026"),
 ("&nbsp;&nbsp;&nbsp;&nbsp;relatorios/", "3 reports: the audit, the 5-minute findings, the interactive explorer"),
 ("&nbsp;&nbsp;&nbsp;&nbsp;dados/", "35 files — merged 5-min record, NASA POWER daily + hourly, billing, model results"),
 ("&nbsp;&nbsp;&nbsp;&nbsp;figuras/", "29 figures"),
 ("&nbsp;&nbsp;&nbsp;&nbsp;scripts/", "36 scripts, fetch through to report"),
 ("&nbsp;&nbsp;curitiba/", "Usina Curitiba — ~9.6 kWp, 2021-2026"),
 ("&nbsp;&nbsp;&nbsp;&nbsp;dados/", "merged 5-min record (490,013 rows), NASA POWER daily + hourly for Curitiba, regimes"),
 ("&nbsp;&nbsp;&nbsp;&nbsp;figuras/", "3 figures"),
 ("&nbsp;&nbsp;&nbsp;&nbsp;scripts/", "6 scripts, same pipeline retargeted"),
 ("&nbsp;&nbsp;comum/scripts/", "shared code: solar geometry / transposition, chart style"),
 ("&nbsp;&nbsp;comparativo/", "cross-site comparison"),
]
tree = "".join('<div><span class="p">%s</span><span class="d">%s</span></div>' % t for t in TREE)

HTML = """<title>Two Plants, One Method</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{color-scheme:light;--ground:#f5f7f8;--ink:#131920;--ink-2:#4a5560;--ink-3:#77828d;
 --rule:#dbe1e6;--rule-2:#eceff2;--accent:#b4690e;--accent-s:#f6ecdd;--good:#1b7a53;--good-s:#e4f1eb;
 --bad:#b3322f;--bad-s:#f8e8e7;--info:#2a5c9a;--plate:#fcfcfb;--measure:68ch}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --ground:#0f1317;--ink:#eef2f5;--ink-2:#b3bdc7;--ink-3:#7d8792;--rule:#2a333c;--rule-2:#20272e;
 --accent:#e0952f;--accent-s:#2e2415;--good:#4bbd8c;--good-s:#15271f;--bad:#e8706c;--bad-s:#2b1818;
 --info:#7aa9e0;--plate:#fcfcfb}}
:root[data-theme="dark"]{color-scheme:dark;--ground:#0f1317;--ink:#eef2f5;--ink-2:#b3bdc7;--ink-3:#7d8792;
 --rule:#2a333c;--rule-2:#20272e;--accent:#e0952f;--accent-s:#2e2415;--good:#4bbd8c;--good-s:#15271f;
 --bad:#e8706c;--bad-s:#2b1818;--info:#7aa9e0;--plate:#fcfcfb}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
 font-size:16px;line-height:1.62;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding-inline:24px;padding-block:0 76px}
.mono{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
header.mast{padding-block:54px 26px;border-bottom:2px solid var(--ink)}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.13em;text-transform:uppercase;
 color:var(--accent);font-weight:600;margin:0 0 14px}
h1{font-size:clamp(29px,5vw,44px);line-height:1.08;letter-spacing:-.022em;font-weight:600;margin:0 0 16px;
 max-width:21ch;text-wrap:balance}
.standfirst{font-size:18px;color:var(--ink-2);margin:0;max-width:var(--measure)}
section{padding-block:50px 0}
h2{font-size:13px;font-family:"IBM Plex Mono",monospace;font-weight:600;letter-spacing:.12em;
 text-transform:uppercase;margin:0 0 8px;padding-bottom:8px;border-bottom:1px solid var(--rule);
 display:flex;gap:12px;align-items:baseline}
h2 .n{color:var(--accent)}
h3{font-size:21px;font-weight:600;letter-spacing:-.018em;margin:30px 0 10px;text-wrap:balance}
p{margin:0 0 15px;max-width:var(--measure)}
.lede{font-size:17.5px;color:var(--ink-2);margin-top:18px}
code{font-family:"IBM Plex Mono",monospace;font-size:.86em;background:var(--rule-2);padding:1px 5px;border-radius:3px}
.finding{border-left:3px solid var(--accent);background:var(--accent-s);padding:18px 22px;margin:26px 0;max-width:var(--measure)}
.finding p:last-child{margin-bottom:0}
.finding .k{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
 color:var(--accent);font-weight:600;display:block;margin-bottom:6px}
.plate{margin:32px 0}
.plate img{display:block;width:100%;max-width:100%;height:auto;background:var(--plate);border:1px solid var(--rule)}
figcaption{font-size:13.5px;line-height:1.55;color:var(--ink-2);margin-top:10px;max-width:84ch}
figcaption b{color:var(--ink);font-weight:600}
.tablewrap{overflow-x:auto;margin:24px 0}
table{border-collapse:collapse;width:100%;min-width:900px;font-size:13.5px}
th{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.09em;text-transform:uppercase;
 color:var(--ink-3);font-weight:600;text-align:left;padding:0 12px 8px 0;border-bottom:1px solid var(--ink)}
td{padding:10px 12px 10px 0;border-bottom:1px solid var(--rule-2);vertical-align:top}
td.num,th.num{text-align:right}
.sub{color:var(--ink-3);font-size:12px}
.fndlist{display:flex;flex-direction:column;gap:1px;background:var(--rule);border-block:1px solid var(--rule);margin-top:22px}
.fnd{background:var(--ground);display:grid;grid-template-columns:132px 1fr;gap:20px;padding:16px 0}
.fnd__chip{font-family:"IBM Plex Mono",monospace;font-size:11px;font-weight:600;letter-spacing:.07em;
 text-transform:uppercase;display:flex;align-items:baseline;gap:7px;padding-top:3px}
.fnd--new .fnd__chip{color:var(--info)}
.fnd--solid .fnd__chip{color:var(--good)}
.fnd--open .fnd__chip{color:var(--ink-3)}
.fnd__body h4{margin:0 0 3px;font-size:16.5px;font-weight:600;letter-spacing:-.012em}
.fnd__val{font-family:"IBM Plex Mono",monospace;font-size:14.5px;font-weight:500;margin:0 0 6px}
.fnd--open .fnd__val{color:var(--ink-3)}
.fnd__note{font-size:14px;color:var(--ink-2);margin:0;max-width:76ch}
.figref{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--accent);border:1px solid var(--rule);padding:1px 5px}
.files{font-size:14px;margin-top:18px}
.files div{display:flex;gap:16px;padding:6px 0;border-bottom:1px solid var(--rule-2)}
.files .p{font-family:"IBM Plex Mono",monospace;color:var(--ink);white-space:nowrap;font-size:13px;min-width:210px}
.files .d{color:var(--ink-2)}
footer{margin-top:60px;padding-top:20px;border-top:1px solid var(--rule);font-size:13px;color:var(--ink-3)}
@media(max-width:620px){.fnd{grid-template-columns:1fr;gap:6px}.fnd__chip{padding-top:0}
 .files div{flex-direction:column;gap:2px}}
</style>
<div class="wrap">
<header class="mast">
  <p class="eyebrow">Two plants &middot; Paran&aacute; &middot; 1.18 million five-minute records</p>
  <h1>The same method, a second plant, and a different answer</h1>
  <p class="standfirst">Cascavel's array was uniformly dirty. Curitiba's has one bad string, an
  obstructed morning, and a rewiring nobody wrote down. Two MPPT inputs instead of one is the
  difference between guessing and knowing.</p>
</header>

<section>
  <h2><span class="n">01</span> The two plants</h2>
  <div class="tablewrap"><table>
   <thead><tr><th>Site</th><th>Coordinates</th><th>Capacity</th><th>Inverter</th><th>Geometry</th>
   <th>Record</th><th class="num">5-min rows</th><th class="num">kWh/kWp&middot;yr</th>
   <th class="num">PI clear</th><th>What the data shows</th></tr></thead>
   <tbody>@@ROWS@@</tbody></table></div>
  <p>Curitiba receives <b>12% less irradiance</b> than Cascavel (1,590 against 1,807 kWh/m&sup2;&middot;yr)
  and converts it less well: performance index <b>0.67</b> against <b>0.79</b> on clear days at high sun.
  Some of that gap is the obstructed morning; some is the uncertain nameplate. The two sites are 446 km
  apart and their daily irradiance correlates at r&nbsp;=&nbsp;0.72, which is a useful measure of how far
  a single-site model would travel.</p>
</section>

<section>
  <h2><span class="n">02</span> What two trackers buy you</h2>
  <p class="lede">At Cascavel the diagnosis rested on an inference: current fell, voltage did not, so
  something was attenuating light. At Curitiba the two strings check each other directly.</p>
  @@F_R1@@
  <div class="finding">
    <span class="k">The finding</span>
    <p>Between December 2022 and July 2023 string 1's irradiance-normalised current fell <b>50%</b>
    while string 2 lost <b>18%</b>, and both snapped back in August 2023. A shared cause &mdash; soiling,
    an inverter derate, a bad irradiance model &mdash; moves both traces together. This did not. The
    fault was in one string, and it was repaired.</p>
  </div>
  @@F_22@@
  <p>The same chart for Cascavel shows why the single-tracker plant was harder: current falls, voltage
  holds, and there is no second string to ask whether the problem is the array or just part of it. The
  soiling conclusion there had to be reached through the angular signature of the recovery instead.</p>
</section>

<section>
  <h2><span class="n">03</span> A maintenance event nobody recorded</h2>
  @@F_R2@@
  <p>In June 2025 the two string voltages change places inside one month: input 1 drops 19%, input 2
  rises 21%, and their sum moves 1%. Voltage is set by how many modules are in series, so this is a
  redistribution of modules between the two inputs &mdash; and combined DC power rose <b>15%</b>
  immediately afterwards, so whoever did it improved the plant. It is invisible in the energy channel
  and obvious in the voltage channels.</p>
</section>

<section>
  <h2><span class="n">04</span> Where the method breaks</h2>
  <p class="lede">The geometry fit that pinned Cascavel's tilt to within one degree does not work here,
  and it is worth being precise about why.</p>
  @@F_R3@@
  <p>The best single-orientation fit reaches R&sup2; 0.52 and 0.59, against 0.89 at Cascavel, and the
  azimuths it returns are contradicted by the day curve, which peaks at solar noon. Meanwhile the two
  strings show <em>opposite</em> asymmetry at low sun and a seasonal swing that reaches 5.9&times;. The
  assumption that each string is one flat plane with one orientation is false for this roof, and no
  amount of fitting repairs a wrong model. The inverter clock was checked separately and is correct to
  within 10 minutes, so that is not the explanation.</p>
  <div class="finding">
    <span class="k">What this needs</span>
    <p>A photograph of the roof and the installer's string map would resolve in a minute what the data
    cannot resolve at all: how many modules are on each input, which faces they sit on, and what is
    east of them.</p>
  </div>
</section>

<section>
  <h2><span class="n">05</span> Findings</h2>
  <div class="fndlist">@@CARDS@@</div>
</section>

<section>
  <h2><span class="n">06</span> What can be done with these two together</h2>
  <p><b>A cross-site reference.</b> Two plants 446 km apart in the same state, on the same inverter
  family, with the same export format. When both dip at once it is weather; when one dips it is the
  plant. That is a far stronger anomaly detector than either site alone, and it needs no extra hardware.</p>
  <p><b>A transferable fault library.</b> Three distinct signatures are now characterised and dated:
  uniform soiling (current down, voltage flat, recovery scaling with incidence angle), a single-string
  fault (one tracker down, the other steady), and a rewiring (voltages exchange, sum constant). Each is
  a rule that can run automatically over any Fronius export.</p>
  <p><b>A calibration target for NASA POWER.</b> Cascavel gave a 3.2% low bias with a 4.1-point seasonal
  cycle. A second site in a different climate tells you whether that bias is general or local &mdash;
  which decides whether reanalysis can be trusted for sites with no measured irradiance at all.</p>
  <p><b>What it cannot do yet.</b> Curitiba has no billing data, so the economic analysis that reframed
  Cascavel entirely &mdash; 2.6&times; oversizing, credits expiring unused &mdash; cannot be repeated.
  And without a nameplate, every per-kWp number here carries an unquantified error.</p>
</section>

<section>
  <h2><span class="n">07</span> How it is organised</h2>
  <div class="files">@@TREE@@</div>
  <p style="margin-top:18px">Shared geometry and transposition code now lives in <code>comum/scripts/</code>
  and is used unchanged by both sites. The Curitiba pipeline is the Cascavel pipeline retargeted: merge,
  fetch weather, build frame, audit, diagnose.</p>
</section>

<footer>
  Cascavel 2019-07-26 to 2026-07-26 (694,488 records) &middot; Curitiba 2021-07-17 to 2026-07-17
  (490,013 records) &middot; NASA POWER daily and hourly for both sites &middot; analysis 2026-09-16.
  Curitiba capacity and geometry are inferred and provisional.
</footer>
</div>
"""
for k, v in [("@@ROWS@@", rows), ("@@CARDS@@", cards), ("@@TREE@@", tree),
             ("@@F_R1@@", fig("R1_string_fault")), ("@@F_R2@@", fig("R2_rewiring")),
             ("@@F_R3@@", fig("R3_asymmetry")), ("@@F_22@@", fig("22_fault_fingerprint"))]:
    HTML = HTML.replace(k, v)
open(caminho("report2sites.html"), "w", encoding="utf-8").write(HTML)
print("report2sites.html  %.2f MB" % (os.path.getsize(caminho("report2sites.html"))/1e6))
