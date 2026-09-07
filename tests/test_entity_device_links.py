"""Entity `device_info` must parent devices with `via_device_id`, not `via_device`.

The entity platform forwards `device_info` key-for-key into
`device_registry.async_get_or_create`, so the deprecation that was fixed at
the integration's own registration call still fired for every entity that
declared a `via_device`. HA reports it against the caller it can see - the
platform's `async_add_entities` line - which is why the warnings named
climate.py, sensor.py and binary_sensor.py rather than helper.py:

    Detected that custom integration 'uponorx265' calls
    `device_registry.async_get_or_create` with a deprecated `via_device`
    parameter; use `via_device_id` instead at
    custom_components/uponorx265/climate.py, line 41

`via_device_id` wants the parent's registry id rather than its identifier
tuple, so `device_info` has to look the parent up. `_register_gateway_devices`
already puts the gateway and controller devices in the registry before
platform setup, which is what makes that lookup resolve.

These tests set the entry up for real - platforms included - so the code path
that produced those log lines is the one under test. The deprecation itself is
caught by watching what reaches `async_get_or_create` rather than by watching
the log: `report_usage` only softens to a warning once it recognises the caller
as a custom integration, and from the test suite it does not, so the same call
raises instead of logging.
"""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.uponorx265 import _register_gateway_devices
from custom_components.uponorx265.const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from custom_components.uponorx265.helper import (
    UponorControllerEntity,
    UponorThermostatEntity,
    _via_device_info,
)
from tests.helpers import make_state_proxy

UNIQUE_ID = "uponorx265_test"
HOST = "192.168.1.10"
MAC = "AA:BB:CC:DD:EE:FF"
MAC_FORM = "AABBCCDDEEFF"
CONTROLLER_ID = "419524869"
THERMOSTAT_ID = "285805788"

LIVE_DATA = {
    "sys_controller_1_presence": "1",
    "controller1_id": CONTROLLER_ID,
    "C1_thermostat1_id": THERMOSTAT_ID,
    "C1_T1_thermostat_type": "2",
    "C1_T1_hw_type": "7",
    "cust_SW_version_update": "X265_121.hex",
}
DEVICE_INFO = {"deviceID": MAC, "serialNumber": "000000XX000000"}

CACHED_META = {
    "thermostats": ["C1_T1"],
    "ids": {"C1_T1": THERMOSTAT_ID},
    "controllers": ["C1"],
    "controller_ids": {"C1": CONTROLLER_ID},
    "models": {"C1_T1": "T-169"},
    "rooms": {"C1_T1": "Kitchen"},
}


@pytest.fixture(autouse=True)
def _no_background_noise():
    """Keep the poll timer out of these tests."""
    with patch("custom_components.uponorx265.async_track_time_interval",
               return_value=lambda: None):
        yield


def _attach(entity, hass, config_entry):
    """What add_to_platform_start() gives an entity before device_info is read."""
    entity.hass = hass
    entity.platform = type("_Platform", (), {"config_entry": config_entry})
    return entity


@pytest.fixture
def registered_device_kwargs(monkeypatch):
    """Every keyword set reaching the device registry, in call order."""
    calls = []
    original = dr.DeviceRegistry.async_get_or_create

    def recording_get_or_create(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(
        dr.DeviceRegistry, "async_get_or_create", recording_get_or_create
    )
    return calls


@pytest.fixture
async def loaded_entry(hass, hass_storage, registered_device_kwargs):
    """A fully set-up entry, platforms and all, with the gateway mocked out."""
    hass_storage[f"{STORAGE_KEY}_{UNIQUE_ID}"] = {
        "version": STORAGE_VERSION,
        "key": f"{STORAGE_KEY}_{UNIQUE_ID}",
        "data": {"_meta": CACHED_META},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, "name": "Uponor"},
        options={CONF_HOST: HOST, "name": "Uponor"},
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    client = AsyncMock()
    client.get_data.return_value = dict(LIVE_DATA)
    client.get_device_info.return_value = dict(DEVICE_INFO)
    with patch("custom_components.uponorx265.UponorJnap", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    return entry


async def test_platform_setup_does_not_use_the_deprecated_via_device(
    loaded_entry, registered_device_kwargs
):
    """Nothing the platforms register may still carry the deprecated key."""
    assert registered_device_kwargs, "no device was registered at all"
    offenders = [kwargs for kwargs in registered_device_kwargs if "via_device" in kwargs]
    assert offenders == [], (
        "device_info still passes the deprecated `via_device` for: "
        f"{[sorted(k.get('identifiers') or []) for k in offenders]}"
    )


async def test_entity_devices_are_still_nested_under_their_parents(hass, loaded_entry):
    """Dropping `via_device` must not flatten the device tree."""
    dev_reg = dr.async_get(hass)
    entry_id = loaded_entry.entry_id

    gateway = dev_reg.async_get_device_by_identifier((UNIQUE_ID, MAC_FORM), entry_id)
    controller = dev_reg.async_get_device_by_identifier((UNIQUE_ID, CONTROLLER_ID), entry_id)
    thermostat = dev_reg.async_get_device_by_identifier((UNIQUE_ID, THERMOSTAT_ID), entry_id)

    assert gateway is not None, "no gateway device was registered"
    assert controller is not None, "no controller device was registered"
    assert thermostat is not None, "the climate entity registered no thermostat device"

    assert gateway.via_device_id is None, "the gateway is the root of the tree"
    assert controller.via_device_id == gateway.id, "controller is not under the gateway"
    assert thermostat.via_device_id == controller.id, "thermostat is not under its controller"


async def test_entity_device_info_carries_the_modern_via_key(hass):
    """The key itself, asserted off the entities rather than off the registry."""
    proxy = make_state_proxy(
        hass,
        data={
            "sys_controller_1_presence": "1",
            "controller1_id": CONTROLLER_ID,
            "C1_thermostat1_id": THERMOSTAT_ID,
        },
        unique_id=UNIQUE_ID,
    )
    proxy._gateway_id = MAC_FORM
    entry = proxy._config_entry
    _register_gateway_devices(hass, entry, UNIQUE_ID, proxy)

    dev_reg = dr.async_get(hass)
    gateway = dev_reg.async_get_device_by_identifier((UNIQUE_ID, MAC_FORM), entry.entry_id)
    controller = dev_reg.async_get_device_by_identifier(
        (UNIQUE_ID, CONTROLLER_ID), entry.entry_id
    )

    for entity, parent in (
        (UponorControllerEntity(UNIQUE_ID, proxy, "C1"), gateway),
        (UponorThermostatEntity(UNIQUE_ID, proxy, "C1_T1"), controller),
    ):
        info = _attach(entity, hass, entry).device_info
        assert "via_device" not in info, (
            f"{type(entity).__name__} still declares the deprecated `via_device`"
        )
        assert info["via_device_id"] == parent.id


async def test_unresolvable_parent_leaves_the_device_unlinked(hass):
    """A missing parent must not cost the entity.

    `via_device_id` naming no registered device raises `DeviceInfoError`, and
    the entity platform responds by dropping the entity entirely. The
    deprecated `via_device` only logged and skipped the link, so omitting the
    key is what keeps that previous, lenient behaviour.
    """
    proxy = make_state_proxy(
        hass,
        data={"sys_controller_1_presence": "1", "controller1_id": CONTROLLER_ID},
        unique_id=UNIQUE_ID,
    )
    entity = _attach(UponorControllerEntity(UNIQUE_ID, proxy, "C1"), hass, proxy._config_entry)

    # Nothing is registered yet, so the gateway identifier resolves to nothing.
    assert _via_device_info(entity, (UNIQUE_ID, "not-registered")) == {}
    assert "via_device" not in entity.device_info
    assert "via_device_id" not in entity.device_info


async def test_via_device_info_is_skipped_on_an_unattached_entity(hass):
    """`device_info` read before the platform attaches must not raise."""
    proxy = make_state_proxy(hass, unique_id=UNIQUE_ID)
    entity = UponorThermostatEntity(UNIQUE_ID, proxy, "C1_T1")

    assert _via_device_info(entity, (UNIQUE_ID, CONTROLLER_ID)) == {}
