from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

DEFAULT_ENABLED_SENSORS = {
    "estimated_room_warmup_minutes",
    "energy_today_kwh",
    "forecast_electricity_next_24h_kwh",
    "model_accuracy_30d",
    "model_status",
}

SENSORS = [
    ("energy_total_kwh", "Samlet energimåler", "kWh", "energy", "total"),
    ("energy_today_kwh", "Brugt energi i dag", "kWh", "energy", "measurement"),
    ("outdoor_temperature", "Udetemperatur", "°C", "temperature", "measurement"),
    ("outdoor_average_today", "Gennemsnitlig udetemperatur i dag", "°C", "temperature", "measurement"),
    ("indoor_average", "Gennemsnitlig rumtemperatur", "°C", "temperature", "measurement"),
    ("indoor_average_today", "Gennemsnitlig rumtemperatur i dag", "°C", "temperature", "measurement"),
    ("room_sensor_count", "Aktive rumfølere", None, None, None),
    ("supply_temperature", "Fremløbstemperatur", "°C", "temperature", "measurement"),
    ("return_temperature", "Returtemperatur", "°C", "temperature", "measurement"),
    ("temperature_difference", "Temperaturforskel fremløb/retur", "°C", "temperature", "measurement"),
    ("thermostat_active_count", "Aktive termostater", None, None, None),
    ("room_heat_demand_c", "Samlet temperaturunderskud i rum", "°C", None, "measurement"),
    ("estimated_room_warmup_minutes", "Estimeret opvarmningstid for rum", "min", "duration", "measurement"),
    ("forecast_electricity_next_24h_kwh", "Forventet elforbrug næste 24 timer", "kWh", "energy", "measurement"),
    ("weather_dependent_electricity_today", "Vejrafhængigt elforbrug i dag", "kWh/døgn", None, "measurement"),
    ("estimated_total_electricity_today", "Estimeret samlet elforbrug i dag", "kWh/døgn", None, "measurement"),
    ("model_slope", "Modelkoefficient", "kWh pr. graddøgn", None, "measurement"),
    ("model_intercept", "Modelgrundlast", "kWh/døgn", None, "measurement"),
    ("model_days", "Dage i beregningsmodel", "dage", None, "measurement"),
    ("model_accuracy_30d", "Prognosenøjagtighed – 30 dage", "%", None, "measurement"),
    ("model_status", "Status for varmebehovsmodel", None, None, None),
]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ThermoPilotSensor(coordinator, entry, *description)
        for description in SENSORS
    ])


class ThermoPilotSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, unit, device_class, state_class):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        # Keep the normal entity list focused on user-facing results.
        # Diagnostic/input entities remain available and can be enabled manually.
        self._attr_entity_registry_enabled_default = key in DEFAULT_ENABLED_SENSORS
        self._attr_native_unit_of_measurement = unit

        if device_class == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif device_class == "energy":
            self._attr_device_class = SensorDeviceClass.ENERGY
        elif device_class == "duration":
            self._attr_device_class = SensorDeviceClass.DURATION

        if state_class == "measurement":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif state_class == "total":
            self._attr_state_class = SensorStateClass.TOTAL

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ThermoPilot",
            "manufacturer": "Custom",
            "model": "ThermoPilot heating optimizer",
        }

    @property
    def native_value(self):
        return self.coordinator.data.get(self.key) if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        if self.key in ("room_heat_demand_c", "estimated_room_warmup_minutes"):
            return {
                "rooms": self.coordinator.data.get("room_thermal_details", []),
                "explanation": "Setpunkt minus aktuel rumtemperatur. Opvarmningstiden bygger på den indlærte temperaturstigning for hver valgt climate-entitet.",
                "note": "Estimaterne er foreløbige og påvirkes af udetemperatur, varmekildens drift og måleusikkerhed.",
            }
        if self.key in ("weather_dependent_electricity_today", "estimated_total_electricity_today"):
            return {
                "explanation": "Adaptivt estimat baseret på dagligt samlet elforbrug, graddøgn og en estimeret grundlast.",
                "warning": "Det er et estimat af samlet elforbrug, ikke isoleret rumopvarmning eller målt varmeenergi. Varmtvandsproduktion og elpatronforbrug kan indgå.",
                "model_days": self.coordinator.data.get("model_days"),
                "model_status": self.coordinator.data.get("model_status"),
                "model_type": "Recency-weighted linear regression, 45-day half-life",
            }
        if self.key == "forecast_electricity_next_24h_kwh":
            return {
                "method": "Døgnmodellen evalueres med den senest målte udetemperatur som proxy for gennemsnittet de næste 24 timer.",
                "limitation": "Dette er endnu ikke en vejrprognosebaseret beregning. En vejrprognosekilde skal tilføjes for at tage højde for forventede temperaturændringer.",
                "model_days": self.coordinator.data.get("model_days"),
                "model_status": self.coordinator.data.get("model_status"),
            }
        if self.key == "model_accuracy_30d":
            return {
                "samples": self.coordinator.data.get("model_accuracy_samples_30d"),
                "mean_error_percent": self.coordinator.data.get("model_accuracy_mean_error_percent_30d"),
                "method": "Gennemsnitlig daglig absolut procentafvigelse, beregnet med historisk backtest uden at træne på måldagen.",
                "weather_note": "Bruger den målte gennemsnitlige udetemperatur for dagen. Måler derfor modellens forbrugsestimat isoleret fra fejl i vejrudsigten.",
            }
        if self.key == "energy_today_kwh":
            return {
                "source": self.coordinator.config.get("energy_entity"),
                "note": "Akkumuleres fra en kumulativ energimåler. Første måleinterval efter opstart tælles ikke med.",
            }
        return {"last_updated": self.coordinator.data.get("last_updated")}
