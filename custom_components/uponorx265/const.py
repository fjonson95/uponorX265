from datetime import timedelta

CONF_UNIQUE_ID = "unique_id"

DOMAIN = "uponorx265"

SIGNAL_UPONOR_STATE_UPDATE = "uponor_state_update"
SCAN_INTERVAL = timedelta(seconds=30)
UNAVAILABLE_THRESHOLD = timedelta(minutes=2)
RELOAD_COOLDOWN = timedelta(minutes=10)

STORAGE_KEY = "uponorx265_data"
STORAGE_VERSION = 1

DEVICE_MANUFACTURER = "Uponor"

STATUS_OK = 'OK'
STATUS_ERROR_BATTERY = 'Battery error'
STATUS_ERROR_VALVE = 'Valve position error'
STATUS_ERROR_GENERAL = 'General system error'
STATUS_ERROR_AIR_SENSOR = 'Air sensor error'
STATUS_ERROR_EXT_SENSOR = 'External sensor error'
STATUS_ERROR_RH_SENSOR = 'Humidity sensor error'
STATUS_ERROR_RF_SENSOR = 'RF sensor error'
STATUS_ERROR_TAMPER = 'Tamper error'
STATUS_ERROR_TOO_HIGH_TEMP = 'API error'
STATUS_ERROR_COMFAILOUT = 'Communication failure out module'
STATUS_ERROR_CONTROLER = 'Communication failure controler'
STATUS_ONLINE = 'Online'
STATUS_OFFLINE = 'Offline'
STATUS_ERROR_MAINCONTROLER_FAIL = 'Communication failure with main controler'
PRESET_MANUAL = 'HA controlled'

CONF_CREATE_CONTROLLERS = "create_controllers"
CONF_SENSOR_TEMP = "sensor_temperature"
CONF_BINARY_SENSOR_VALVE = "binary_sensor_valve"
TOO_HIGH_TEMP_LIMIT = 4508
DEFAULT_TEMP = 20
