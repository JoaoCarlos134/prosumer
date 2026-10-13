"""The Brazilian bill of a low-voltage (grupo B) consumer, with or without micro-generation (Lei 14.300/2022).

What is modelled, and where each rule comes from (all sources accessed on 2026-10-12):

[L] Lei 14.300, de 6 de janeiro de 2022 (Marco Legal da GD), DOU 7.1.2022,
    https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14300.htm
[R] ANEEL REN 1.000/2021, compiled text with REN 1.059/2023, 1.098/2024 and 1.101/2024. ANEEL's own copy
    (www2.aneel.gov.br/cedoc/ren20211000.html) answers 403 to scripts; read from the compiled PDF a
    distributor publishes, https://www.cemig.com.br/wp-content/uploads/2025/08/ren20211000.pdf
[P] Lei 13.169/2015, art. 8: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13169.htm
[C] Convenio ICMS 16/2015 (CONFAZ): https://www.confaz.fazenda.gov.br/legislacao/convenios/2015/CV016_15

- **Full price per kWh** ("tarifa cheia"): (TUSD + TE + bandeira) / (1 - ICMS - PIS/COFINS). The homologated
  TUSD and TE (R$/MWh, `io.aneel`) carry no tax; ICMS and PIS/COFINS are charged "por dentro" (they are part
  of their own base), hence the division. The rates are inputs (`TariffBook.taxes`): ICMS is set by each
  state and PIS/COFINS is assessed monthly by the distributor (the nominal 1.65% + 7.60% is an upper bound).
  Not modelled: the tax reform of LC 214/2025 (CBS/IBS replacing PIS/COFINS and ICMS from 2027).
- **Bandeira** (flag surcharge, R$/MWh) by calendar month, from ANEEL's monthly record; it applies only to the
  energy billed, never to compensated energy ([L] art. 19). The bill follows the meter's reading cycle; here
  the calendar month, so around a flag change a month may differ from the real bill.
- **Custo de disponibilidade** (minimum billing, grupo B): the value of 30 kWh (single-phase or two-phase
  with two wires), 50 kWh (two-phase with three wires) or 100 kWh (three-phase) ([R] art. 291); the bill is
  the larger of the energy billed and that minimum ([R] art. 290), the minimum valued at the CONVENTIONAL
  tariff even for tarifa branca ([R] art. 290 §4). Taxes apply to it ([C] clause 1, §1 II). Whether the
  bandeira applies to it is not stated in [R] art. 291: `bandeira_on_minimum` (default True, the larger bill).
- **Tarifa branca** postos ([R] art. 2 XXXVIII): ponta = 3 consecutive hours set by the distributor and
  approved by ANEEL, intermediario = the hour before and the hour after, fora de ponta = the rest; ponta and
  intermediario do not apply on Saturdays, Sundays, Carnival Tuesday, Good Friday, Corpus Christi and the
  national holidays of 1/1, 21/4, 1/5, 7/9, 12/10, 2/11, 15/11, 20/11 and 25/12 (20/11 added by REN
  1.101/2024; applied here from 2024). The peak start is an input (`peak_start`): each distributor has its
  own (the project's legacy study notes 17:30-20:30 for Copel, not checked against Copel's REH).
- **Compensation (SCEE)**, grupo B ([R] art. 655-I): the bill for energy from the grid is the larger of the
  custo de disponibilidade and [(consumed - compensated) at the full tariff + compensated energy at the SCEE
  charge of its class]; the compensated energy is limited to the energy consumed and to the point where the
  bill still reaches the custo de disponibilidade ([R] art. 655-I §2; [L] art. 16 caput). Credits are kWh
  ([L] art. 13 §1), used oldest first ([L] art. 13 §2; [R] art. 655-G §9), and expire 60 months after the
  bill in which they were generated ([L] art. 13; [R] art. 655-L). READING of "60 meses apos a data do
  faturamento": a credit of month m is usable through month m+59 (the month m+60 bill finds it expired). The
  month's own injection is used before older credits ([L] art. 26 §1 I: consumption minus the month's
  injection plus accumulated credits).
- **Minimum billing of GD II: the law and the regulation differ.** [L] art. 16 §1: for units NOT covered by
  art. 26 (GD II) the minimum billable value applies only if the consumption measured, disregarding the
  compensation, is below the minimum billable consumption. [R] art. 655-I §§1-2 applies one rule to every
  grupo B unit in the SCEE, GD I and GD II alike: the bill is at least the custo de disponibilidade and the
  compensation stops there. Parameter `gd2_minimum`: "ren_655I" (default: the regulation in force, what the
  distributors apply) or "law_16_par1" (a GD II unit whose measured consumption is at or above the minimum
  has no minimum and no limit on its compensation; below it, as [R]). GD I always follows [R] art. 655-I
  (= [L] art. 16 caput).
- **GD I** (direito adquirido): generation existing on 7/1/2022 or whose access was requested up to
  7/1/2023 keeps full compensation (no distribution charge on compensated energy) until 31/12/2045 ([L]
  art. 26; [R] art. 655-O, which names the dates). Caveats not checked here: the injection deadlines of
  [R] art. 655-O §4 and the loss of the right
  ([L] art. 26 §2).
- **GD II**: on all the compensated energy, a share of the distribution components "Fio B" (asset return,
  depreciation, O&M): 15% from 2023, 30% 2024, 45% 2025, 60% 2026, 75% 2027, 90% 2028 ([L] art. 27 I-VI),
  and from 2029 the rule of [L] art. 17 (VII): all tariff components not associated with the cost of energy,
  minus the benefits of DG to the system, valued by ANEEL following CNPE guidelines ([L] art. 17 §§1-2). That
  valuation is not in this module. READING (parameter `after_2028`; default "tusd", the author's decision of
  2026-10-12): "tusd" charges the whole TUSD on compensated energy and values the benefits at zero (art. 17
  §1 may also reach TE items not tied to the energy cost, so "tusd" is not shown to be the largest charge);
  "fio_b" keeps 100% of the Fio B. For access requested between 8/1/2023 and 7/7/2023 the art. 17 rule
  starts in 2031 ([L] art. 27 §2;
  [R] art. 655-Q §2 I); this module keeps 90% of Fio B in 2029-2030 for them, a reading (the law says
  nothing about those two years). GD III (remote minigeneration > 500 kW, [R] art. 655-P) is not modelled.
- **Taxes on compensated energy** (every switch below is a READING). ICMS and PIS/COFINS rates are user
  inputs (`TariffBook.taxes`): no state table is built in (the author's decision of 2026-10-12).
  - PIS/COFINS are zero on the energy supplied in the amount compensated ([P] art. 8):
    `pis_cofins_exempt_compensated=True`.
  - ICMS on compensated energy, `icms_exempt_compensated`: "all" (default; [C] clause 1 caput exempts the
    energy supplied in the amount compensated), "te_only" ([C] clause 1 §1 II excludes "encargos de conexao
    ou uso do sistema de distribuicao" from the exemption: the TUSD of each compensated kWh is taxed, the TE
    is not) or "none" (a state or period without the exemption). Parana adhered to [C] from 1/7/2018 with a
    48-month cap (§3, revoked on 29/12/2023): whether Parana exempted compensated energy between 7/2022 and
    12/2023 is NOT verified here.
  - The GD II charge: ICMS by default (`icms_on_charge=True`: [C] §1 II excludes network-use charges from the
    exemption); PIS/COFINS not by default (`pis_cofins_on_charge=False`: [P] zero-rates the energy "na
    quantidade correspondente" to the compensation). With `icms_exempt_compensated` "te_only" or "none" the
    TUSD of the compensated kWh is already taxed, so the charge gets no second ICMS.
  - Each tax is "por dentro" on its own base: a base B taxed at rates r costs B / (1 - r).

Not modelled (left for the user to add or to a later version): COSIP/CIP (municipal street-lighting fee, not
published by ANEEL: `cosip` is a fixed amount per month), the social tariff and other subsidies, the
reduction of the minimum billing for CadUnico families ([L] art. 16 §2; [R] art. 291 sole paragraph),
tarifa branca WITH micro-generation (per-posto netting weighted by the TE Energia ratio, [L] art. 12; [R] art.
655-G §5), shared/remote generation, grupo A, demand charges and the GD II "Faturamento Uso Injecao".

Open, NOT verified (2026-10-12):
- "por dentro" as T / (1 - ICMS - PIS/COFINS) against T / ((1 - ICMS)(1 - PIS/COFINS)), as distributors may
  bill after STF Tema 69 (ICMS out of the PIS/COFINS base): ~2.4% apart at 19% + 9.25%;
- LC 194/2022 (TUSD and charges in the ICMS base) and the judicial suspension of that part: whether the TUSD
  is in the ICMS base in a given state and period;
- whether the art. 27 percentages change on 1 January ("a partir de 2023", read by calendar year here) or at
  each distributor's tariff process;
- whether ANEEL's `TUSD_FioB` component is exactly the art. 27 components (asset return, depreciation, O&M);
- each distributor's peak hours (Copel 17:30-20:30 comes from the project's legacy notes).

**Prices vary within a month** (a new vigencia starts on a fixed day, e.g. 24/6 at Copel): the netting uses
the import-weighted mean of the month's hourly prices, so a month that straddles two vigencias is a blend.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from ..contracts import EnergySeries
from ..provenance import Provenance
from .core import Bill, Tariff, flows

CURRENCY = "BRL"
# [R] art. 291: minimum billing in kWh by type of connection
MINIMUM_KWH: dict[str, float] = {
    "monofasico": 30.0,
    "bifasico_2": 30.0,  # two-phase, two wires
    "bifasico_3": 50.0,  # two-phase, three wires
    "trifasico": 100.0,
}
# [L] art. 27 I-VI: share of the Fio B components charged on compensated energy (GD II), by year
FIO_B_SHARE: dict[int, float] = {2023: 0.15, 2024: 0.30, 2025: 0.45, 2026: 0.60, 2027: 0.75, 2028: 0.90}
GD_I_UNTIL = 2045  # [L] art. 26: full compensation until 31/12/2045
GD_I_REQUESTED_BY = date(2023, 1, 7)  # [L] art. 26 II, [R] art. 655-O II
DEFERRED_FROM, DEFERRED_TO = date(2023, 1, 8), date(2023, 7, 7)  # [L] art. 27 §2, [R] art. 655-Q §2 I
CREDIT_MONTHS = 60  # [L] art. 13, [R] art. 655-L
POSTOS = ("ponta", "intermediario", "fora_ponta")
_POSTO_DATA = {"Ponta": "ponta", "Intermediário": "intermediario", "Fora ponta": "fora_ponta"}
CONVENTIONAL = "Convencional"
BRANCA = "Branca"
NO_POSTO = "Não se aplica"

GD = Literal["GD I", "GD II"]
After2028 = Literal["tusd", "fio_b"]
Gd2Minimum = Literal["ren_655I", "law_16_par1"]
IcmsExempt = Literal["all", "te_only", "none"]


@dataclass(frozen=True)
class _CompensationTaxes:
    """What a compensated kWh still costs, by the readings of the module docstring."""

    icms_exempt: IcmsExempt = "all"
    pis_cofins_exempt: bool = True
    icms_on_charge: bool = True
    pis_cofins_on_charge: bool = False

    def __post_init__(self) -> None:
        if self.icms_exempt not in ("all", "te_only", "none"):
            raise ValueError("icms_exempt_compensated must be 'all', 'te_only' or 'none'")

    def per_kwh(self, charge: float, tusd: float, te: float, icms: float, pis: float) -> float:
        """R$ per compensated kWh: the charge (R$/kWh, no tax) with its taxes, plus the taxes on the TUSD and
        TE (R$/kWh) of the compensated kWh that are not exempt. Each base B at rates r costs B / (1 - r)."""
        pis_c = 0.0 if self.pis_cofins_exempt else pis
        r_tusd = (icms if self.icms_exempt in ("te_only", "none") else 0.0) + pis_c
        r_te = (icms if self.icms_exempt == "none" else 0.0) + pis_c
        icms_c = icms if self.icms_on_charge and self.icms_exempt == "all" else 0.0
        r_charge = icms_c + (pis if self.pis_cofins_on_charge else 0.0)
        return charge / (1 - r_charge) + tusd * (1 / (1 - r_tusd) - 1) + te * (1 / (1 - r_te) - 1)


# ---------------------------------------------------------------------- calendar
def easter(year: int) -> date:
    """Easter Sunday (Gregorian calendar; anonymous algorithm of Meeus/Jones/Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    day = (h + m - 7 * n + 114) % 31 + 1
    return date(year, month, day)


def holidays(years: Iterable[int]) -> set[date]:
    """Days without ponta and intermediario ([R] art. 2 XXXVIII a): Carnival Tuesday, Good Friday, Corpus
    Christi and the national holidays listed there (20/11 from 2024, see the module docstring)."""
    out: set[date] = set()
    for y in years:
        e = easter(y)
        out |= {e - timedelta(days=47), e - timedelta(days=2), e + timedelta(days=60)}
        fixed = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)]
        if y >= 2024:
            fixed.append((11, 20))
        out |= {date(y, m, d) for m, d in fixed}
    return out


def is_holiday(ds: pd.DatetimeIndex) -> np.ndarray:
    """Boolean per timestamp: True on the days of `holidays` (for `Tariff.holidays`)."""
    t = pd.DatetimeIndex(ds)
    days = holidays(range(int(t.year.min()), int(t.year.max()) + 1)) if len(t) else set()
    return np.array([d in days for d in t.date], dtype=bool)


def branca_blocks(peak_start: str = "18:00") -> dict[int, str | dict[str, float]]:
    """Hour -> posto (or share of each posto) on working days, for a ponta of 3 h starting at `peak_start`
    ("HH:MM"), intermediario the hour before and after ([R] art. 2 XXXVIII). Boundaries inside an hour split
    it in shares (energy assumed even within the hour)."""
    hh, mm = (int(x) for x in peak_start.split(":"))
    p0 = hh * 60 + mm
    if not 60 <= p0 <= 20 * 60:
        raise ValueError("peak_start must leave room for the intermediario hours (01:00-20:00)")
    spans = {"intermediario": [(p0 - 60, p0), (p0 + 180, p0 + 240)], "ponta": [(p0, p0 + 180)]}
    out: dict[int, str | dict[str, float]] = {}
    for h in range(24):
        a, b = h * 60, h * 60 + 60
        share = {k: sum(max(0, min(b, y) - max(a, x)) for x, y in v) / 60 for k, v in spans.items()}
        share = {k: s for k, s in share.items() if s > 0}
        rest = 1.0 - sum(share.values())
        if rest > 1e-12:
            share["fora_ponta"] = rest
        out[h] = next(iter(share)) if len(share) == 1 else share
    return out


# ---------------------------------------------------------------------- Lei 14.300
def gd_class(connected: str | date | None = None, requested: str | date | None = None) -> GD:
    """GD I when the generation was connected or its access requested by 7/1/2023, else GD II ([L] art. 26;
    [R] arts. 655-O and 655-Q). Give `requested` (the date the access/connection budget was requested) when
    known: a plant connected after the cut-off may still be GD I. GD III is not modelled."""
    dates = [pd.Timestamp(x).date() for x in (connected, requested) if x is not None]
    if not dates:
        raise ValueError("Give the connection date or the access request date")
    return "GD I" if min(dates) <= GD_I_REQUESTED_BY else "GD II"


def compensation_charge_share(
    year: int, gd: GD, *, requested: str | date | None = None, after_2028: After2028 = "tusd"
) -> tuple[float, str]:
    """(share, base) of the charge on each compensated kWh: `base` is "fio_b" (the TUSD Fio B components) or
    "tusd" (the whole TUSD). GD I pays nothing until 2045; GD II follows [L] art. 27 (see the module docstring
    for the readings after 2028)."""
    if after_2028 not in ("tusd", "fio_b"):
        raise ValueError("after_2028 must be 'tusd' or 'fio_b'")
    art17 = (1.0, "tusd") if after_2028 == "tusd" else (1.0, "fio_b")
    if gd == "GD I":
        return (0.0, "fio_b") if year <= GD_I_UNTIL else art17
    if gd != "GD II":
        raise ValueError("gd must be 'GD I' or 'GD II'")
    if year < 2023:
        return 0.0, "fio_b"
    if year in FIO_B_SHARE:
        return FIO_B_SHARE[year], "fio_b"
    deferred = requested is not None and DEFERRED_FROM <= pd.Timestamp(requested).date() <= DEFERRED_TO
    if deferred and year < 2031:
        return FIO_B_SHARE[2028], "fio_b"  # reading: the law is silent on 2029-2030 for them
    return art17


# ---------------------------------------------------------------------- tariff data
@dataclass
class TariffBook:
    """The tariff data of one distributor: homologated TUSD/TE by vigencia, the monthly bandeira, the tax
    rates by period and (for GD II) the Fio B component.

    `tariffs`: `start, end, subgroup, modality, posto, tusd, te` (+ optional `resolution`), R$/MWh, as
    `io.aneel.fetch_tariffs` returns (already filtered to one class/subclass and to rows without SCEE
    detail); rows of the same vigencia, subgroup, modality and posto are added (ANEEL publishes some postos
    in two rows, one TUSD-only and one TE-only). `bandeiras`: `month` ("YYYY-MM"), `flag`, `add` (R$/MWh).
    `taxes`: `start, icms, pis_cofins` (fractions), each valid from `start` to the next row. `fio_b`:
    `start, value` (R$/MWh of TUSD_FioB), optional. A day after the end of the last vigencia raises unless
    `extend_last`; a day before the first Fio B value raises unless `fio_b_backfill`; either assumption is
    recorded in `notes`.
    """

    tariffs: pd.DataFrame
    bandeiras: pd.DataFrame
    taxes: pd.DataFrame
    fio_b: pd.DataFrame | None = None
    distributor: str = ""
    provenance: list[Provenance] = field(default_factory=list)
    extend_last: bool = False  # after the end of the last vigencia, keep using it (else raise)
    fio_b_backfill: bool = False  # before the first Fio B value, use it (else raise)
    notes: list[str] = field(default_factory=list)  # what a lookup had to assume (`bill` repeats them)

    def __post_init__(self) -> None:
        t = self.tariffs.copy()
        t["start"] = pd.to_datetime(t["start"])
        t["end"] = pd.to_datetime(t["end"])
        keys = ["start", "end", "subgroup", "modality", "posto"]
        self.tariffs = t.groupby(keys, as_index=False, sort=True)[["tusd", "te"]].sum()
        b = self.bandeiras.copy()
        b["month"] = b["month"].astype(str).str[:7]
        self.bandeiras = b.drop_duplicates("month", keep="last").set_index("month").sort_index()
        x = self.taxes.copy()
        x["start"] = pd.to_datetime(x["start"])
        self.taxes = x.sort_values("start").reset_index(drop=True)
        if self.fio_b is not None:
            f = self.fio_b.copy()
            f["start"] = pd.to_datetime(f["start"])
            self.fio_b = f.sort_values("start").reset_index(drop=True)

    @classmethod
    def from_legacy(cls, folder: str | Path, *, distributor: str = "COPEL-DIS") -> TariffBook:
        """The project's legacy CSVs (`legado/ia_solar/analise/tarifas/dados/`: ANEEL data downloaded by
        `baixa_tarifas_aneel.py`, B1/B3 residential, plus the Parana tax table of that study)."""
        d = Path(folder)
        t = pd.read_csv(d / "copel_tarifas_historico.csv", encoding="utf-8-sig").rename(
            columns={
                "vigencia_ini": "start",
                "vigencia_fim": "end",
                "subgrupo": "subgroup",
                "modalidade": "modality",
                "tusd_RS_MWh": "tusd",
                "te_RS_MWh": "te",
                "resolucao": "resolution",
            }
        )
        b = pd.read_csv(d / "bandeiras_mensal.csv", encoding="utf-8-sig").rename(
            columns={"competencia": "month", "bandeira": "flag", "adicional_RS_MWh": "add"}
        )
        f = pd.read_csv(d / "parametros_fiscais.csv", encoding="utf-8-sig")
        icms = f[f["tributo"] == "ICMS"][["vigencia_ini", "aliquota_pct"]]
        pis = float(f.loc[f["tributo"] == "PIS_COFINS", "aliquota_pct"].iloc[0]) / 100
        taxes = pd.DataFrame(
            {"start": icms["vigencia_ini"], "icms": icms["aliquota_pct"] / 100, "pis_cofins": pis}
        )
        fio_b = None
        comp = d / "copel_componentes_b1.csv"
        if comp.exists():
            c = pd.read_csv(comp, encoding="utf-8-sig")
            c = c[c["componente"] == "TUSD_FioB"]
            fio_b = pd.DataFrame({"start": c["vigencia_ini"], "value": c["valor_RS_MWh"]})
        prov = Provenance(
            source=f"ANEEL open data ({distributor} tariffs, bandeiras, components), project snapshot",
            license="ODbL-1.0",
            citation="Agência Nacional de Energia Elétrica (ANEEL), Dados Abertos.",
            url="https://dadosabertos.aneel.gov.br/",
            notes="tax rates: the project's own table (Parana ICMS, nominal PIS/COFINS)",
        )
        return cls(t, b, taxes, fio_b, distributor, [prov])

    # ------------------------------------------------------------------ lookups
    def base(
        self,
        day: str | pd.Timestamp,
        *,
        modality: str = CONVENTIONAL,
        posto: str = NO_POSTO,
        subgroup: str = "B1",
    ) -> tuple[float, float]:
        """(TUSD, TE) in R$/MWh, without taxes, of the vigencia in force on `day`."""
        d = pd.Timestamp(day).tz_localize(None) if pd.Timestamp(day).tzinfo else pd.Timestamp(day)
        t = self.tariffs
        t = t[(t["subgroup"] == subgroup) & (t["modality"] == modality) & (t["posto"] == posto)]
        t = t[t["start"] <= d.normalize()]
        if t.empty:
            raise ValueError(f"No {subgroup} {modality} {posto} tariff in force on {d.date()}")
        row = t[t["start"] == t["start"].max()].iloc[0]
        end = pd.Timestamp(row["end"])
        if pd.notna(end) and d.normalize() > end:
            if not self.extend_last:
                raise ValueError(
                    f"No {subgroup} {modality} {posto} tariff in force on {d.date()}: the last vigencia "
                    f"ended on {end.date()} (download newer data, or set extend_last=True to keep using it)"
                )
            self._note(f"Tariffs after {end.date()} reuse the last vigencia (extend_last=True).")
        return float(row["tusd"]), float(row["te"])

    def _note(self, msg: str) -> None:
        if msg not in self.notes:
            self.notes.append(msg)

    def bandeira(self, month: str | pd.Timestamp) -> tuple[str, float] | None:
        """(flag, surcharge R$/MWh) of a calendar month, or None when the record has no such month."""
        key = pd.Timestamp(month).strftime("%Y-%m") if not isinstance(month, str) else month[:7]
        flags = dict(zip(self.bandeiras.index, self.bandeiras["flag"], strict=True))
        if key not in flags:
            return None
        adds = dict(zip(self.bandeiras.index, self.bandeiras["add"].astype(float), strict=True))
        return str(flags[key]), float(adds[key])

    def tax(self, day: str | pd.Timestamp) -> tuple[float, float]:
        """(ICMS, PIS/COFINS) as fractions on `day`."""
        d = pd.Timestamp(day).tz_localize(None) if pd.Timestamp(day).tzinfo else pd.Timestamp(day)
        x = self.taxes[self.taxes["start"] <= d]
        if x.empty:
            raise ValueError(f"No tax rate in force on {d.date()}")
        r = x.iloc[-1]
        return float(r["icms"]), float(r["pis_cofins"])

    def fio_b_value(self, day: str | pd.Timestamp) -> float:
        """TUSD Fio B (R$/MWh) on `day`: the latest value published up to it; before the first one, raises
        unless `fio_b_backfill` (then the earliest value, recorded in `notes`)."""
        if self.fio_b is None or self.fio_b.empty:
            raise ValueError(
                "This TariffBook has no Fio B values: needed for GD II (see io.aneel.fetch_components)"
            )
        d = pd.Timestamp(day).tz_localize(None) if pd.Timestamp(day).tzinfo else pd.Timestamp(day)
        x = self.fio_b[self.fio_b["start"] <= d]
        if x.empty:
            first = pd.Timestamp(self.fio_b["start"].iloc[0])
            if not self.fio_b_backfill:
                raise ValueError(
                    f"No Fio B value on {d.date()} (the first starts on {first.date()}): fetch that year's "
                    "components, or set fio_b_backfill=True to use the earliest value"
                )
            self._note(f"Fio B before {first.date()} uses the value of {first.date()} (fio_b_backfill=True).")
            return float(self.fio_b["value"].iloc[0])
        return float(x["value"].iloc[-1])

    def daily(
        self,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        *,
        modality: str = CONVENTIONAL,
        posto: str = NO_POSTO,
        subgroup: str = "B1",
        assume_bandeira: float | None = None,
    ) -> pd.DataFrame:
        """One row per day: `date, tusd, te, flag, bandeira, icms, pis_cofins, price` (`price` = full R$/kWh
        with bandeira and taxes, see `full_price`). A month without a bandeira record raises, unless
        `assume_bandeira` (R$/MWh) is given (e.g. 0 for green, for future months)."""
        days = pd.date_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize(), freq="D")
        rows = []
        for d in days:
            tusd, te = self.base(d, modality=modality, posto=posto, subgroup=subgroup)
            b = self.bandeira(d)
            if b is None:
                if assume_bandeira is None:
                    raise ValueError(f"No bandeira for {d:%Y-%m}; pass assume_bandeira (R$/MWh)")
                b = ("assumed", float(assume_bandeira))
            icms, pis = self.tax(d)
            rows.append(
                {
                    "date": d,
                    "tusd": tusd,
                    "te": te,
                    "flag": b[0],
                    "bandeira": b[1],
                    "icms": icms,
                    "pis_cofins": pis,
                    "price": full_price(tusd + te, b[1], icms, pis),
                }
            )
        return pd.DataFrame(rows)


def full_price(tusd_te: float, bandeira: float, icms: float, pis_cofins: float) -> float:
    """Full price in R$/kWh from TUSD + TE and the bandeira surcharge (R$/MWh) and the tax rates (fractions),
    with ICMS and PIS/COFINS "por dentro": (TUSD + TE + bandeira) / 1000 / (1 - ICMS - PIS/COFINS)."""
    return (tusd_te + bandeira) / 1000.0 * gross_up(icms, pis_cofins)


def gross_up(icms: float, pis_cofins: float) -> float:
    """1 / (1 - ICMS - PIS/COFINS): the factor of taxes charged "por dentro"."""
    if not 0 <= icms + pis_cofins < 1:
        raise ValueError("ICMS + PIS/COFINS must be in [0, 1)")
    return 1.0 / (1.0 - icms - pis_cofins)


def tariff(
    book: TariffBook,
    month: str | pd.Timestamp,
    *,
    modality: str = CONVENTIONAL,
    peak_start: str | None = None,
    gd: GD | None = None,
    subgroup: str = "B1",
    assume_bandeira: float | None = None,
    after_2028: After2028 = "tusd",
    requested: str | date | None = None,
    icms_exempt_compensated: IcmsExempt = "all",
    pis_cofins_exempt_compensated: bool = True,
    icms_on_charge: bool = True,
    pis_cofins_on_charge: bool = False,
) -> Tariff:
    """The full prices of `month` (first day's vigencia, the month's bandeira, taxes) as a core `Tariff` in
    BRL, to rank flexible loads with `economics.cheapest_windows(..., scheme="net_billing")`.

    `export_price` is what an injected kWh is worth as a credit: the full price for GD I, the full price minus
    what a compensated kWh still costs (the GD II charge and any tax on compensated energy: the switches
    of `bill`, same defaults; `requested` places a GD II unit in the deferred group), zero without `gd`.
    Conventional: one block; tarifa
    branca (`modality="Branca"`, `peak_start` required): the three postos on working days, fora de ponta on
    weekends and the holidays of `holidays`.
    """
    m = pd.Timestamp(month).to_period("M").to_timestamp()
    b = book.bandeira(m)
    if b is None:
        if assume_bandeira is None:
            raise ValueError(f"No bandeira for {m:%Y-%m}; pass assume_bandeira (R$/MWh)")
        b = ("assumed", float(assume_bandeira))
    icms, pis = book.tax(m)
    taxes = _CompensationTaxes(
        icms_exempt_compensated, pis_cofins_exempt_compensated, icms_on_charge, pis_cofins_on_charge
    )

    def charge(tusd: float, te: float) -> float:
        if gd is None:
            return 0.0
        share, base = compensation_charge_share(m.year, gd, requested=requested, after_2028=after_2028)
        v = tusd if base == "tusd" else book.fio_b_value(m) if share > 0 else 0.0
        return taxes.per_kwh(share * v / 1000.0, tusd / 1000.0, te / 1000.0, icms, pis)

    if modality == CONVENTIONAL:
        tusd, te = book.base(m, subgroup=subgroup)
        p = full_price(tusd + te, b[1], icms, pis)
        export = 0.0 if gd is None else p - charge(tusd, te)
        return Tariff.flat(p, export_price=export, currency=CURRENCY, name=f"{book.distributor} {m:%Y-%m}")
    if modality != BRANCA:
        raise ValueError("modality must be 'Convencional' or 'Branca'")
    if peak_start is None:
        raise ValueError("Tarifa branca needs the distributor's peak start (peak_start='HH:MM')")
    prices, exports = {}, {}
    for data_name, name in _POSTO_DATA.items():
        tusd, te = book.base(m, modality=BRANCA, posto=data_name, subgroup=subgroup)
        prices[name] = full_price(tusd + te, b[1], icms, pis)
        exports[name] = 0.0 if gd is None else prices[name] - charge(tusd, te)
    return Tariff(
        prices={k: prices[k] for k in POSTOS},
        weekday=branca_blocks(peak_start),
        weekend=dict.fromkeys(range(24), "fora_ponta"),
        export_price=exports,
        currency=CURRENCY,
        holidays=is_holiday,
        name=f"{book.distributor} branca {m:%Y-%m}",
    )


# ---------------------------------------------------------------------- the bill
def bill(
    consumption: EnergySeries,
    generation: EnergySeries | None = None,
    *,
    book: TariffBook,
    connection: str = "bifasico_3",
    gd: GD | None = None,
    connected: str | date | None = None,
    requested: str | date | None = None,
    modality: str = CONVENTIONAL,
    peak_start: str | None = None,
    subgroup: str = "B1",
    initial_credit: float | Mapping[str, float] = 0.0,
    credit_months: int = CREDIT_MONTHS,
    after_2028: After2028 = "tusd",
    bandeira_on_minimum: bool = True,
    gd2_minimum: Gd2Minimum = "ren_655I",
    icms_exempt_compensated: IcmsExempt = "all",
    pis_cofins_exempt_compensated: bool = True,
    icms_on_charge: bool = True,
    pis_cofins_on_charge: bool = False,
    cosip: float = 0.0,
    assume_bandeira: float | None = None,
) -> Bill:
    """Monthly bill (R$) of grupo B consumers, with or without micro-generation (see the module docstring for
    every rule and its source).

    `connection`: a key of `MINIMUM_KWH` or the minimum in kWh. With `generation`, the class is `gd` or, if
    not given, `gd_class(connected, requested)`. `initial_credit`: kWh banked before the first month (treated
    as earned the month before it). `cosip`: the municipal lighting fee, R$ per month (not published by
    ANEEL; read it from a bill). `assume_bandeira`: R$/MWh for months without a bandeira record.
    `gd2_minimum`, `icms_exempt_compensated`, `pis_cofins_exempt_compensated`, `icms_on_charge`,
    `pis_cofins_on_charge`: readings, see the module docstring.

    Monthly columns: `unique_id, month, coverage, consumption, generation, self_consumption, grid_import,
    export, gd_class, charge_share, charge_base, flag, price, minimum_value, compensated, credit_used,
    credit_new, credit_expired, credit_balance, energy_charge, compensation_charge, minimum_applied,
    energy_bill, cosip, total, without_pv, savings`. `price` is the month's full price (R$/kWh, import
    weighted); `without_pv` is the bill the same consumption would have had all from the grid;
    `compensation_charge` is the GD II charge plus any tax on compensated energy; `minimum_applied` is True
    when the minimum sets the bill, directly or by stopping the compensation.
    """
    if modality not in (CONVENTIONAL, BRANCA):
        raise ValueError("modality must be 'Convencional' or 'Branca'")
    if modality == BRANCA and generation is not None:
        raise NotImplementedError(
            "Tarifa branca with micro-generation (per-posto netting weighted by the TE Energia ratio, "
            "REN 1.000 art. 655-G §5) is not implemented yet"
        )
    if modality == BRANCA and peak_start is None:
        raise ValueError("Tarifa branca needs the distributor's peak start (peak_start='HH:MM')")
    if gd2_minimum not in ("ren_655I", "law_16_par1"):
        raise ValueError("gd2_minimum must be 'ren_655I' or 'law_16_par1'")
    taxes = _CompensationTaxes(
        icms_exempt_compensated, pis_cofins_exempt_compensated, icms_on_charge, pis_cofins_on_charge
    )
    minimum_kwh = float(MINIMUM_KWH[connection]) if isinstance(connection, str) else float(connection)
    klass: GD | None = None
    if generation is not None:
        klass = gd or gd_class(connected, requested)
    h = flows(consumption, generation)
    if h.empty:
        raise ValueError("No hours to bill")
    local = h["ds"].dt.tz_localize(None)
    h["month"] = local.dt.to_period("M").dt.to_timestamp()
    h["date"] = local.dt.normalize()
    days = book.daily(local.min(), local.max(), subgroup=subgroup, assume_bandeira=assume_bandeira).set_index(
        "date"
    )
    # per hour: price components of the conventional tariff (R$/kWh, without taxes) and the tax factor
    h["base"] = h["date"].map((days["tusd"] + days["te"]) / 1000.0)
    h["tusd"] = h["date"].map(days["tusd"] / 1000.0)
    h["te"] = h["date"].map(days["te"] / 1000.0)
    h["icms"] = h["date"].map(days["icms"])
    h["pis"] = h["date"].map(days["pis_cofins"])
    h["band"] = h["date"].map(days["bandeira"] / 1000.0)
    h["gross"] = h["date"].map(1.0 / (1.0 - days["icms"] - days["pis_cofins"]))
    if modality == BRANCA:
        assert peak_start is not None
        tb = Tariff(
            prices=dict.fromkeys(POSTOS, 0.0),
            weekday=branca_blocks(peak_start),
            weekend=dict.fromkeys(range(24), "fora_ponta"),
            holidays=is_holiday,
        )
        sh = tb.shares(h["ds"])
        base_b = np.zeros(len(h))
        for j, name in enumerate(POSTOS):
            data_name = next(k for k, v in _POSTO_DATA.items() if v == name)
            per_day = pd.Series(
                {
                    d: sum(book.base(d, modality=BRANCA, posto=data_name, subgroup=subgroup)) / 1000.0
                    for d in days.index
                }
            )
            base_b += sh[:, j] * h["date"].map(per_day).to_numpy()
        h["base_energy"] = base_b
    else:
        h["base_energy"] = h["base"]
    imp = np.nan_to_num(h["grid_import"].to_numpy())
    cons = np.nan_to_num(h["consumption"].to_numpy())
    h["pay"] = imp * (h["base_energy"] + h["band"]) * h["gross"]  # what each imported kWh costs, full
    h["pay_nopv"] = cons * (h["base_energy"] + h["band"]) * h["gross"]
    notes = [
        "Import and export are netted hour by hour; a real meter nets instant by instant.",
        "Months are calendar months; the bill follows the meter's reading cycle.",
    ]
    rows = []
    for uid_key, g in h.groupby("unique_id", sort=True):
        uid = str(uid_key)
        lots: list[tuple[pd.Timestamp, float]] = []
        start = float(initial_credit.get(uid, 0.0) if isinstance(initial_credit, Mapping) else initial_credit)
        first = pd.Timestamp(g["month"].min())
        if start > 0:
            lots.append((first - pd.offsets.MonthBegin(1), start))
        for month_key, m in g.groupby("month", sort=True):
            month = pd.Timestamp(month_key)  # type: ignore[arg-type]
            w = np.nan_to_num(m["grid_import"].to_numpy())

            def mean(col: str, weights: np.ndarray, frame: pd.DataFrame = m) -> float:
                v = frame[col].to_numpy(dtype=float)
                return float(np.average(v, weights=weights)) if weights.sum() > 0 else float(v.mean())

            imported, inj = float(w.sum()), float(np.nan_to_num(m["export"].to_numpy()).sum())
            gross, band = mean("gross", w), mean("band", w)
            base_conv = mean("base", w)
            p_full = (
                float(m["pay"].sum() / imported) if imported > 0 else (mean("base_energy", w) + band) * gross
            )
            minimum_value = minimum_kwh * (base_conv + (band if bandeira_on_minimum else 0.0)) * gross
            limit = month - pd.DateOffset(months=credit_months)
            expired = sum(k for t, k in lots if t <= limit)
            lots = [(t, k) for t, k in lots if t > limit]
            share, base_name, c = 0.0, "", 0.0
            if klass is not None:
                share, base_name = compensation_charge_share(
                    month.year, klass, requested=requested, after_2028=after_2028
                )
                v = 0.0
                if share > 0:
                    v = mean("tusd", w) if base_name == "tusd" else book.fio_b_value(month) / 1000.0
                c = taxes.per_kwh(share * v, mean("tusd", w), mean("te", w), mean("icms", w), mean("pis", w))
            available = inj + sum(k for _, k in lots)
            comp, binds = 0.0, False
            no_minimum = klass == "GD II" and gd2_minimum == "law_16_par1" and imported >= minimum_kwh
            if klass is not None and no_minimum:
                comp = min(available, imported)  # [L] art. 16 §1: no minimum, so no limit on the compensation
            elif klass is not None:
                free = min(available, imported)
                if imported * p_full > minimum_value and p_full > c:
                    comp = min(free, (imported * p_full - minimum_value) / (p_full - c))
                binds = comp < free - 1e-9  # the minimum stopped the compensation
            comp = max(comp, 0.0)
            from_inj = min(comp, inj)
            used = comp - from_inj
            for j in range(len(lots)):  # oldest first
                if used <= 1e-12:
                    break
                t, k = lots[j]
                take = min(k, used)
                lots[j] = (t, k - take)
                used -= take
            lots = [(t, k) for t, k in lots if k > 1e-12]
            new = inj - from_inj
            if new > 1e-12:
                lots.append((month, new))
            energy_charge = (imported - comp) * p_full
            comp_charge = comp * c
            v_bill = energy_charge + comp_charge
            energy_bill = v_bill if no_minimum else max(v_bill, minimum_value)
            p_nopv = float(m["pay_nopv"].sum())
            without = max(p_nopv, minimum_value) + cosip
            total = energy_bill + cosip
            rows.append(
                {
                    "unique_id": uid,
                    "month": month,
                    "coverage": float(m["valid"].mean()),
                    "consumption": float(np.nansum(m["consumption"])),
                    "generation": float(np.nansum(m["generation"])),
                    "self_consumption": float(np.nansum(m["self_consumption"])),
                    "grid_import": imported,
                    "export": inj,
                    "gd_class": klass,
                    "charge_share": share,
                    "charge_base": base_name or None,
                    "flag": str(m["date"].map(days["flag"]).iloc[0]),
                    "price": p_full,
                    "minimum_value": minimum_value,
                    "compensated": comp,
                    "credit_used": comp - from_inj,
                    "credit_new": max(new, 0.0),
                    "credit_expired": expired,
                    "credit_balance": float(sum(k for _, k in lots)),
                    "energy_charge": energy_charge,
                    "compensation_charge": comp_charge,
                    "minimum_applied": bool(not no_minimum and (binds or v_bill < minimum_value - 1e-9)),
                    "energy_bill": energy_bill,
                    "cosip": float(cosip),
                    "total": total,
                    "without_pv": without,
                    "savings": without - total,
                }
            )
    monthly = pd.DataFrame(rows)
    if (monthly["coverage"] < 1).any():
        notes.append("Some months have missing hours: their energy and bill cover only the valid hours.")
    if monthly["credit_expired"].sum() > 0:
        notes.append(f"{monthly['credit_expired'].sum():.1f} kWh of credits expired unused (60 months).")
    if h["generation_missing"].any():
        notes.append(
            f"{int(h['generation_missing'].sum())} hour(s) have consumption but no generation row (e.g. the "
            "PV series starts later): left out as unknown. If the PV was not installed yet, pass zeros for "
            "that period."
        )
    notes.extend(book.notes)
    if cosip == 0:
        notes.append("COSIP/CIP (municipal street-lighting fee) not included: read it from a bill.")
    if klass == "GD II" and (monthly["month"].dt.year >= 2029).any():
        notes.append(
            f"From 2029 the GD II charge is a reading of Lei 14.300 art. 17 ({after_2028!r}): "
            "ANEEL's valuation of DG benefits is not modelled."
        )
    by_block = (
        h.assign(block="all")
        .groupby(["unique_id", "month", "block"], as_index=False)[["grid_import", "export"]]
        .sum()
    )
    return Bill(
        monthly=monthly,
        by_block=by_block,
        hourly=h[
            ["unique_id", "ds", "consumption", "generation", "self_consumption", "grid_import", "export"]
        ],
        scheme="SCEE (Lei 14.300)" if klass else "no generation",
        currency=CURRENCY,
        notes=notes,
    )


def retail_price_by_month(book: TariffBook, start: str, end: str, **kwargs: Any) -> pd.Series:
    """Mean over the days of each calendar month of the full price (R$/kWh, `TariffBook.daily`). The project's
    legacy tariff study averaged these over a year; reproducing its number is a regression of the port, not
    an independent validation (only a real bill is)."""
    d = book.daily(start, end, **kwargs)
    return d.groupby(d["date"].dt.to_period("M"))["price"].mean()


__all__ = [
    "CREDIT_MONTHS",
    "CURRENCY",
    "FIO_B_SHARE",
    "GD",
    "MINIMUM_KWH",
    "POSTOS",
    "TariffBook",
    "bill",
    "branca_blocks",
    "compensation_charge_share",
    "easter",
    "full_price",
    "gd_class",
    "gross_up",
    "holidays",
    "is_holiday",
    "retail_price_by_month",
    "tariff",
]
