from __future__ import annotations

from datetime import timedelta
import logging
import math

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


def _float_state(hass, entity_id):
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        value = float(state.state)
        if not math.isfinite(value):
            return None
        return value
    except (ValueError, TypeError):
        return None


def _energy_kwh(hass, entity_id):
    """Read a cumulative energy entity and normalize Wh/kWh/MWh to kWh."""
    value = _float_state(hass, entity_id)
    if value is None:
        return None
    state = hass.states.get(entity_id)
    unit = (state.attributes.get("unit_of_measurement") or "").lower()
    if unit == "wh":
        return value / 1000
    if unit == "mwh":
        return value * 1000
    return value


class ThermoPilotCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.hass = hass
        self.entry = entry
        self.config = {**entry.data, **entry.options}
        self.config.pop("hp_heater_status_entity", None)
        # Room temperatures now come from the selected climate entities.
        self.config.pop("room_entities", None)
        self.store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        self.history = {
            "days": [],
            "last_energy_kwh": None,
            "last_date": None,
            "day_energy_kwh": 0.0,
            "outdoor_sum": 0.0,
            "outdoor_count": 0,
            "indoor_sum": 0.0,
            "indoor_count": 0,
            "room_thermal": {},
        }

    async def async_setup(self):
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.history.update(saved)

    async def async_shutdown(self):
        await self.store.async_save(self.history)

    async def _async_update_data(self):
        now = dt_util.now()
        energy = _energy_kwh(self.hass, self.config.get("energy_entity"))
        outdoor = _float_state(self.hass, self.config.get("outdoor_entity"))
        room_values = []
        for entity_id in self.config.get("climate_entities", []):
            climate_state = self.hass.states.get(entity_id)
            if climate_state is None:
                continue
            try:
                room_temp = float(climate_state.attributes.get("current_temperature"))
                if math.isfinite(room_temp):
                    room_values.append(room_temp)
            except (TypeError, ValueError):
                continue
        indoor_avg = sum(room_values) / len(room_values) if room_values else None

        supply = _float_state(self.hass, self.config.get("supply_entity"))
        return_temp = _float_state(self.hass, self.config.get("return_entity"))

        local_date = now.date().isoformat()
        old_date = self.history.get("last_date")
        if old_date and old_date != local_date:
            self._close_day(old_date)
        self.history["last_date"] = local_date

        previous = self.history.get("last_energy_kwh")
        if energy is not None and previous is not None:
            delta = energy - previous
            if 0 <= delta < 20:
                self.history["day_energy_kwh"] = (
                    float(self.history.get("day_energy_kwh", 0)) + delta
                )
        if energy is not None:
            self.history["last_energy_kwh"] = energy

        if outdoor is not None:
            self.history["outdoor_sum"] = float(self.history.get("outdoor_sum", 0)) + outdoor
            self.history["outdoor_count"] = int(self.history.get("outdoor_count", 0)) + 1
        if indoor_avg is not None:
            self.history["indoor_sum"] = float(self.history.get("indoor_sum", 0)) + indoor_avg
            self.history["indoor_count"] = int(self.history.get("indoor_count", 0)) + 1

        room_thermal = self._update_room_thermal(now)

        days = self.history.get("days", [])
        model = self._fit_model(days, now.date())
        base = float(self.config.get("degree_base", 17.0))
        outdoor_today = self._mean("outdoor_sum", "outdoor_count")
        indoor_today = self._mean("indoor_sum", "indoor_count")
        weather_dependent_kwh = None
        estimated_total_kwh = None
        if model and outdoor_today is not None:
            degree_days = max(0.0, base - outdoor_today)
            weather_dependent_kwh = max(0.0, model["slope"] * degree_days)
            estimated_total_kwh = max(
                0.0, model["slope"] * degree_days + model["intercept"]
            )

        data = {
            "energy_total_kwh": energy,
            "energy_today_kwh": round(float(self.history.get("day_energy_kwh", 0)), 3),
            "outdoor_temperature": outdoor,
            "outdoor_average_today": outdoor_today,
            "indoor_average": indoor_avg,
            "indoor_average_today": indoor_today,
            "room_sensor_count": len(room_values),
            "supply_temperature": supply,
            "return_temperature": return_temp,
            "temperature_difference": (
                supply - return_temp
                if supply is not None and return_temp is not None
                else None
            ),
            "thermostat_active_count": self._climate_heat_call_count(),
            "room_heat_demand_c": round(sum(r["deficit_c"] for r in room_thermal), 2) if room_thermal else None,
            "estimated_room_warmup_minutes": max((r["estimated_minutes"] for r in room_thermal if r["estimated_minutes"] is not None), default=None),
            "room_thermal_details": room_thermal,
            "weather_dependent_electricity_today": weather_dependent_kwh,
            "estimated_total_electricity_today": estimated_total_kwh,
            "model_slope": model["slope"] if model else None,
            "model_intercept": model["intercept"] if model else None,
            "model_days": len(days),
            "model_status": "Klar" if model else f"Indsamler data ({len(days)}/5 dage)",
            "last_updated": now.isoformat(),
        }

        await self.store.async_save(self.history)
        return data


    def _update_room_thermal(self, now):
        """Learn each climate circuit's observed warm-up rate and estimate lead time."""
        learned = self.history.setdefault("room_thermal", {})
        results = []
        for entity_id in self.config.get("climate_entities", []):
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            attrs = state.attributes
            current = attrs.get("current_temperature")
            target = attrs.get("temperature")
            try:
                current = float(current)
                target = float(target)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(current) or not math.isfinite(target):
                continue

            room = learned.setdefault(entity_id, {})
            now_ts = now.timestamp()
            previous_temp = room.get("last_current")
            previous_ts = room.get("last_ts")
            if previous_temp is not None and previous_ts is not None:
                elapsed_hours = (now_ts - float(previous_ts)) / 3600.0
                rise = current - float(previous_temp)
                # Learn only plausible positive warm-up observations. A 5-minute
                # sample is noisy, so smooth the rate rather than replacing it.
                previous_target = float(room.get("last_target", previous_temp))
                was_calling_for_heat = previous_target > float(previous_temp) + 0.2
                is_calling_for_heat = target > current + 0.2
                if (
                    0.04 <= elapsed_hours <= 1.0
                    and rise > 0.015
                    and was_calling_for_heat
                    and is_calling_for_heat
                ):
                    rate = rise / elapsed_hours
                    if 0.05 <= rate <= 3.0:
                        old_rate = room.get("warmup_rate")
                        room["warmup_rate"] = (
                            rate if old_rate is None
                            else 0.8 * float(old_rate) + 0.2 * rate
                        )

            room["last_current"] = current
            room["last_ts"] = now_ts
            room["last_target"] = target
            deficit = max(0.0, target - current)
            rate = room.get("warmup_rate")
            estimated_minutes = (
                round(deficit / float(rate) * 60.0)
                if deficit > 0.05 and rate is not None and float(rate) >= 0.05
                else (0 if deficit <= 0.05 else None)
            )
            results.append({
                "entity_id": entity_id,
                "current_temperature": round(current, 2),
                "setpoint": round(target, 2),
                "deficit_c": round(deficit, 2),
                "learned_warmup_rate_c_per_hour": round(float(rate), 3) if rate is not None else None,
                "estimated_minutes": estimated_minutes,
            })
        return results

    def _climate_heat_call_count(self):
        """Count selected climate entities currently requesting heat."""
        count = 0
        for entity_id in self.config.get("climate_entities", []):
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            attrs = state.attributes
            action = str(attrs.get("hvac_action", "")).lower()
            if action == "heating":
                count += 1
                continue
            try:
                current = float(attrs.get("current_temperature"))
                target = float(attrs.get("temperature"))
            except (TypeError, ValueError):
                continue
            if state.state.lower() != "off" and target > current + 0.2:
                count += 1
        return count if self.config.get("climate_entities") else self._active_count(
            self.config.get("thermostat_entities", [])
        )

    def _active_count(self, entity_ids):
        if not entity_ids:
            return None
        count = 0
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            if state and state.state.lower() in (
                "on", "heat", "heating", "open", "true", "1"
            ):
                count += 1
        return count

    def _mean(self, sum_key, count_key):
        count = int(self.history.get(count_key, 0))
        if count <= 0:
            return None
        return round(float(self.history.get(sum_key, 0)) / count, 2)

    def _close_day(self, day):
        count = int(self.history.get("outdoor_count", 0))
        outdoor_mean = (
            float(self.history.get("outdoor_sum", 0)) / count if count else None
        )
        energy = float(self.history.get("day_energy_kwh", 0))
        if outdoor_mean is not None:
            self.history.setdefault("days", []).append({
                "date": day,
                "energy_kwh": round(energy, 3),
                "outdoor_mean": round(outdoor_mean, 2),
            })
            self.history["days"] = self.history["days"][-730:]
        self.history["day_energy_kwh"] = 0.0
        self.history["outdoor_sum"] = 0.0
        self.history["outdoor_count"] = 0
        self.history["indoor_sum"] = 0.0
        self.history["indoor_count"] = 0

    def _fit_model(self, days, reference_date):
        """Fit daily electricity against heating degree days.

        Recent observations adapt the model to current behavior. Observations
        from roughly the same calendar period in previous years receive a
        seasonal weight, so the model can reuse comparable seasonal experience.
        """
        from datetime import date
        import math

        base = float(self.config.get("degree_base", 17.0))
        rows = []
        for index, day in enumerate(days):
            if day.get("outdoor_mean") is None or day.get("energy_kwh") is None:
                continue
            try:
                day_date = date.fromisoformat(day["date"])
                x = max(0.0, base - float(day["outdoor_mean"]))
                y = float(day["energy_kwh"])
            except (KeyError, TypeError, ValueError):
                continue
            age_days = max(0, (reference_date - day_date).days)
            recent_weight = 0.5 ** (age_days / 45.0)

            # Seasonal match: compare day-of-year, including year-end wrap.
            day_of_year_delta = abs(day_date.timetuple().tm_yday - reference_date.timetuple().tm_yday)
            day_of_year_delta = min(day_of_year_delta, 365 - day_of_year_delta)
            seasonal_weight = 0.0
            years_old = reference_date.year - day_date.year
            if years_old >= 1 and day_of_year_delta <= 30:
                seasonal_weight = (
                    0.50
                    * math.exp(-day_of_year_delta / 15.0)
                    * (0.5 ** (max(0, years_old - 1) / 2.0))
                )

            weight = max(recent_weight, seasonal_weight)
            rows.append((x, y, weight))

        if len(rows) < 5 or len({round(x, 1) for x, _, _ in rows}) < 3:
            return None

        weight_sum = sum(weight for _, _, weight in rows)
        if weight_sum <= 0:
            return None
        x_mean = sum(x * weight for x, _, weight in rows) / weight_sum
        y_mean = sum(y * weight for _, y, weight in rows) / weight_sum
        denominator = sum(
            weight * (x - x_mean) ** 2 for x, _, weight in rows
        )
        if denominator <= 0:
            return None
        slope = sum(
            weight * (x - x_mean) * (y - y_mean)
            for x, y, weight in rows
        ) / denominator
        intercept = y_mean - slope * x_mean
        if slope < 0:
            return None
        return {"slope": slope, "intercept": max(0.0, intercept)}
