"""Direct Honeywell wired M-Bus integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .api import HoneywellMbusClient
from .const import CONF_ADDRESS, CONF_SERIAL, CONF_TIMEOUT, DEFAULT_TIMEOUT
from .coordinator import HoneywellCoordinator

type HoneywellConfigEntry = ConfigEntry[HoneywellCoordinator]
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HoneywellConfigEntry) -> None:
    """Validate the connection before creating entities."""
    client = HoneywellMbusClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_ADDRESS],
        timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        expected_serial=entry.data[CONF_SERIAL],
    )
    coordinator = HoneywellCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        raise


async def async_unload_entry(hass: HomeAssistant, entry: HoneywellConfigEntry) -> None:
    """Release the bus only after all entities unload successfully."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        raise ConfigEntryError("Sensor platform could not unload")
    await entry.runtime_data.async_shutdown()
