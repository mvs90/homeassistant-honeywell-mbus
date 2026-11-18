"""One nonblocking coordinator per meter."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HoneywellMbusClient, MbusError, MeterSample
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

LOGGER = logging.getLogger(__name__)


class HoneywellCoordinator(DataUpdateCoordinator[MeterSample]):
    """Coordinate a single direct M-Bus connection and fail unavailable."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: HoneywellMbusClient
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> MeterSample:
        try:
            return await self.client.async_read()
        except MbusError as error:
            raise UpdateFailed(str(error)) from error

    async def async_shutdown(self) -> None:
        """Stop scheduled updates and close the owned socket."""
        await super().async_shutdown()
        await self.client.async_close()
