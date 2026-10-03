"""`_device_config_entry_ids` must work on both device-registry models.

Current cores give a device exactly one config entry (`config_entry_id`) and
raise a RuntimeError if the deprecated `config_entries` set is even read. Older
cores only have the set. The helper has to pick by what the device offers and
must never touch `config_entries` on a device that has the new attribute.

The branches are exercised with stand-in devices rather than registry entries,
so each one runs on every HA version instead of only the core that happens to
have that shape. One test at the end runs the real registry as a sanity check.
"""

from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.uponorx265.const import DOMAIN
from custom_components.uponorx265.helper import _device_config_entry_ids


class _NewCoreDevice:
    """Single-entry model; reading the legacy set raises, as on current cores."""

    def __init__(self, config_entry_id):
        self.config_entry_id = config_entry_id

    @property
    def config_entries(self):
        raise RuntimeError(
            "Detected code that accesses `DeviceEntry.config_entries`, which is "
            "deprecated"
        )


class _OldCoreDevice:
    """Pre-single-entry model: only the `config_entries` set exists."""

    def __init__(self, config_entries):
        self.config_entries = config_entries


def test_new_core_device_returns_its_single_entry():
    assert _device_config_entry_ids(_NewCoreDevice("entry-1")) == {"entry-1"}


def test_new_core_device_never_reads_the_deprecated_set():
    # _NewCoreDevice raises if config_entries is read, so merely succeeding
    # proves the shim stayed on the new attribute.
    _device_config_entry_ids(_NewCoreDevice("entry-1"))


def test_new_core_device_without_an_entry_is_empty():
    assert _device_config_entry_ids(_NewCoreDevice(None)) == set()


def test_old_core_device_falls_back_to_the_set():
    assert _device_config_entry_ids(_OldCoreDevice({"a", "b"})) == {"a", "b"}


def test_old_core_result_is_a_copy_not_the_registry_set():
    original = {"a"}
    result = _device_config_entry_ids(_OldCoreDevice(original))
    result.add("b")
    assert original == {"a"}


async def test_real_registry_device_resolves_to_its_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="uponorx265_test")
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("uponorx265_test", "AABBCCDDEEFF")},
    )

    assert _device_config_entry_ids(device) == {entry.entry_id}
