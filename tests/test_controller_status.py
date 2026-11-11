"""The controller status sensor must see the controller's alarm variables.

`get_controller_status()` built two of its variable names without the
separator - `C1stat_out_module_com_lost` instead of the real
`C1_stat_out_module_com_lost`, and likewise `C1stat_general_system_alarm` - so
those two checks could never match. The only condition that ever surfaced was
`sys_controller_N_lost`; an alarm raised on the central unit, such as losing
contact with the thermostats, left the controller sensor on "ok" while every
thermostat reported its own radio error.

The keys below are the real ones from a gateway dump (see ARCHITECTURE.md).
"""

from custom_components.uponorx265.const import (
    STATUS_ERROR_COMFAILOUT,
    STATUS_ERROR_CONTROLER,
    STATUS_ERROR_GENERAL,
    STATUS_OK,
)

from tests.helpers import make_state_proxy


async def test_ok_when_no_alarm_is_raised(hass):
    proxy = make_state_proxy(hass, data={
        "sys_controller_1_lost": "0",
        "C1_stat_out_module_com_lost": "0",
        "C1_stat_general_system_alarm": "0",
    })

    assert proxy.get_controller_status("C1") == STATUS_OK


async def test_ok_when_the_variables_are_absent(hass):
    proxy = make_state_proxy(hass, data={})

    assert proxy.get_controller_status("C1") == STATUS_OK


async def test_a_lost_controller_is_reported(hass):
    proxy = make_state_proxy(hass, data={"sys_controller_1_lost": "1"})

    assert proxy.get_controller_status("C1") == STATUS_ERROR_CONTROLER


async def test_lost_contact_with_the_output_module_is_reported(hass):
    proxy = make_state_proxy(hass, data={"C1_stat_out_module_com_lost": "1"})

    assert proxy.get_controller_status("C1") == STATUS_ERROR_COMFAILOUT


async def test_a_general_system_alarm_is_reported(hass):
    proxy = make_state_proxy(hass, data={"C1_stat_general_system_alarm": "1"})

    assert proxy.get_controller_status("C1") == STATUS_ERROR_GENERAL


async def test_the_most_specific_alarm_wins(hass):
    """Lost controller, then output module, then the general alarm."""
    everything = {
        "sys_controller_1_lost": "1",
        "C1_stat_out_module_com_lost": "1",
        "C1_stat_general_system_alarm": "1",
    }
    proxy = make_state_proxy(hass, data=everything)
    assert proxy.get_controller_status("C1") == STATUS_ERROR_CONTROLER

    del proxy._data["sys_controller_1_lost"]
    assert proxy.get_controller_status("C1") == STATUS_ERROR_COMFAILOUT

    del proxy._data["C1_stat_out_module_com_lost"]
    assert proxy.get_controller_status("C1") == STATUS_ERROR_GENERAL


async def test_an_alarm_on_one_controller_does_not_flag_another(hass):
    proxy = make_state_proxy(hass, data={
        "C2_stat_general_system_alarm": "1",
        "C2_stat_out_module_com_lost": "1",
        "sys_controller_2_lost": "1",
    })

    assert proxy.get_controller_status("C1") == STATUS_OK
    assert proxy.get_controller_status("C2") == STATUS_ERROR_CONTROLER
