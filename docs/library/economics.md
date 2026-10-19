# Economics

Tariffs are data, bills are computed hour by hour from the consumption and the generation, and the same
pricing ranks the coming hours for a flexible load.

## A tariff and a bill

```python
import numpy as np
from prosumer import EnergySeries, data, economics

tou = economics.Tariff(
    prices={"peak": 0.45, "off_peak": 0.20},
    weekday={h: "peak" if 17 <= h < 21 else "off_peak" for h in range(24)},
    weekend=dict.fromkeys(range(24), "off_peak"),
    export_price=0.08,
    currency="EUR",
)
load = data.example_house(n_series=1, days=31, start="2024-03-01", tz="Europe/Lisbon")
pv, _ = data.example_plant(n_series=1, days=31, start="2024-03-01", tz="Europe/Lisbon")
pv = EnergySeries.from_dataframe(pv.frame.assign(unique_id=load.series[0]), unit="kWh",
                                 quantity="generation", tz="Europe/Lisbon", freq="h")
b = economics.bill(load, pv, tariff=tou, scheme="net_billing")
print(b.monthly.set_index("month")[["grid_import", "export", "total", "without_pv", "savings"]].round(2))
assert np.isfinite(b.monthly["total"]).all()
```

- Schemes: `net_metering` (credits in kWh, used later, optional `credit_months`), `net_billing` (exports paid
  at `export_price`), `self_consumption` (exports worth nothing).
- Import and export are netted hour by hour (a real meter nets instant by instant: declared in the notes).
- `economics.Plan(tariff, scheme=...)` bundles how a household pays; `analyze(series, economics=plan,
  consumption=load)` adds the bill section to the report, with the expected monthly bill over the complete
  months and, with PV, the savings.
- `economics.windows_by_cost(plan, generation=outlook, hours=3, kw=2)` ranks the windows of each forecast day
  for a flexible load by their expected cost.

## Brazil (`economics.brazil`)

The bill of a low-voltage (grupo B) consumer, every rule cited to the law or the ANEEL resolution in the
module's docstring: tarifa cheia with ICMS and PIS/COFINS "por dentro", bandeiras by month, custo de
disponibilidade, tarifa branca postos and holidays, and the compensation of micro-generation under Lei
14.300/2022 (GD I until 2045, the GD II Fio B ramp, 60-month credits). Tarifa branca with generation follows
REN 1.000 art. 655-G: netting per posto, the excess of one posto moved to the others by the ratio of their TE
Energia, credits that keep their posto.

```python
import numpy as np
import pandas as pd
from prosumer import EnergySeries
from prosumer.economics import brazil

book = brazil.TariffBook.from_legacy("legado/ia_solar/analise/tarifas/dados")  # ANEEL snapshot (ODbL)
hours = pd.date_range("2018-03-01", "2018-03-31 23:00", freq="h", tz="America/Sao_Paulo")
load = 0.4 + 0.6 * np.isin(hours.hour, [18, 19, 20])
sun = np.clip(np.sin((hours.hour - 6) / 12 * np.pi), 0, None) * 1.2

def series(y, quantity):
    f = pd.DataFrame({"unique_id": "uc", "ds": hours, "y": y})
    return EnergySeries.from_dataframe(f, unit="kWh", quantity=quantity, tz="America/Sao_Paulo", freq="h")

setup = brazil.Setup(book=book, gd="GD I", modality="Branca", peak_start="18:00")
b = setup.bill(series(load, "consumption"), series(sun, "generation"))
print(b.monthly.set_index("month")[["grid_import", "export", "compensated", "energy_bill", "savings"]].round(2))
print(b.by_block.set_index("block")[["grid_import", "export", "compensated"]].round(1))
assert set(b.by_block["block"]) == set(brazil.POSTOS)
```

For a real distributor, `brazil.TariffBook.from_aneel("COPEL-DIS", icms=0.19, pis_cofins=0.0925,
fio_b_years=[2025, 2026])` builds the book from ANEEL's open data in one call (ODbL: attribute ANEEL). ICMS and
PIS/COFINS are the rates you read on a bill (one number, or `{first day: rate}` when they changed); no state
table is built in.

Every reading of the law that the text leaves open is a parameter, with the distributors' practice as the
default where it is known: `after_2028` (GD II from 2029), `gd2_minimum` (the law and REN 1.000 differ),
`icms_exempt_compensated` ("all", "te_only", "none"), `bandeira_on_minimum`, and for tarifa branca with
generation `te_energy` (the TE Energia component of each posto; by default the homologated TE stands in for it)
and `posto_order` (the order the other postos receive an excess or a credit, once its own posto is served; by
default the dearest first).

Not modelled: COSIP read from a bill (type it as `Setup(cosip=...)`), grupo A (demand charges), the social
tariff, shared or remote generation, the tax reform of LC 214/2025. Checked against real bills: the energy of
a consumer without PV comes within +-5%, but bills with compensation are not reproduced yet (see
[Validation](validation.md)).
