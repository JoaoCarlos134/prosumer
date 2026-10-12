"""Economics of a prosumer: what the energy costs, and when a flexible load is cheapest.

Two layers:

- the international core (this namespace, `economics.core`): tariffs as data (`Tariff.flat`, time-of-use
  blocks by hour for weekdays and weekends/holidays, export price, fixed monthly charge, currency), the
  hourly energy flows of a site (`flows`), its monthly `bill` under net metering, net billing or
  self-consumption, and `cheapest_windows`, which ranks the hours of the forecast days for a flexible load by
  expected cost (price AND sun, from an `outlook.Outlook`);
- the Brazilian layer (`economics.brazil`): the tarifa cheia with taxes "por dentro", bandeiras, custo de
  disponibilidade, tarifa branca postos, and the compensation rules of Lei 14.300/2022 (GD I / GD II, Fio B
  ramp, 60-month credits), each rule with its source; ANEEL open data via `io.aneel`.
"""

from __future__ import annotations

from . import brazil, core
from .core import SCHEMES, Bill, Scheme, Tariff, bill, cheapest_windows, flows

__all__ = ["SCHEMES", "Bill", "Scheme", "Tariff", "bill", "brazil", "cheapest_windows", "core", "flows"]
