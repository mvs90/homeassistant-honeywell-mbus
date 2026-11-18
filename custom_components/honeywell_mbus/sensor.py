"""Meter readings and optional diagnostics as native Home Assistant sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HoneywellConfigEntry
from .api import MeterSample
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import HoneywellCoordinator

# Coordinator owns all I/O; entity updates must not create parallel requests.
PARALLEL_UPDATES = 0

type NativeValue = Decimal | int | float | datetime


@dataclass(frozen=True, kw_only=True)
class MeterSensorDescription(SensorEntityDescription):
    """A fixed sensor description and sample accessor."""

    value_fn: Callable[[MeterSample], NativeValue]


SENSORS: tuple[MeterSensorDescription, ...] = (
    MeterSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.reading.power,
    ),
    MeterSensorDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.reading.energy,
    ),
    MeterSensorDescription(
        key="reactive_power",
        translation_key="reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.reading.reactive_power,
    ),
    *(
        description
        for phase in (1, 2, 3)
        for description in (
            MeterSensorDescription(
                key=f"voltage_l{phase}",
                translation_key=f"voltage_l{phase}",
                device_class=SensorDeviceClass.VOLTAGE,
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda s, i=phase - 1: s.reading.phases[i].voltage,
            ),
            MeterSensorDescription(
                key=f"current_l{phase}",
                translation_key=f"current_l{phase}",
                device_class=SensorDeviceClass.CURRENT,
                native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda s, i=phase - 1: s.reading.phases[i].current,
            ),
            MeterSensorDescription(
                key=f"power_l{phase}",
                translation_key=f"power_l{phase}",
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement=UnitOfPower.WATT,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda s, i=phase - 1: s.reading.phases[i].power,
            ),
            MeterSensorDescription(
                key=f"reactive_power_l{phase}",
                translation_key=f"reactive_power_l{phase}",
                device_class=SensorDeviceClass.REACTIVE_POWER,
                native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda s, i=phase - 1: s.reading.phases[i].reactive_power,
            ),
        )
    ),
    MeterSensorDescription(
        key="ct_ratio",
        translation_key="ct_ratio",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.reading.ct_ratio,
    ),
    MeterSensorDescription(
        key="mbus_status",
        translation_key="mbus_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.reading.status,
    ),
    MeterSensorDescription(
        key="last_read",
        translation_key="last_read",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.received_at,
    ),
    MeterSensorDescription(
        key="read_duration",
        translation_key="read_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=3,
        value_fn=lambda s: s.duration,
    ),
    MeterSensorDescription(
        key="read_attempts",
        translation_key="read_attempts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.attempts,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HoneywellConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(HoneywellSensor(coordinator, description) for description in SENSORS)


class HoneywellSensor(CoordinatorEntity[HoneywellCoordinator], SensorEntity):
    """A sensor whose identity does not depend on network configuration."""

    _attr_has_entity_name = True
    entity_description: MeterSensorDescription

    def __init__(
        self, coordinator: HoneywellCoordinator, description: MeterSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        meter = coordinator.data.reading
        self._attr_unique_id = f"{meter.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=MODEL,
            serial_number=meter.serial,
        )
        # The M-Bus device-version byte is not a firmware version string.
        # Do not mislabel it as sw_version or multiply by the CT ratio again.

    @property
    def native_value(self) -> NativeValue:
        return self.entity_description.value_fn(self.coordinator.data)
