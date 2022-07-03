#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Z-Wave Interpreter - Constants © Autolog 2020
#

# plugin Constants

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass


LOCK_MQTT = 0
LOCK_HE_LINKED_INDIGO_DEVICES = 1
QUEUES = 2
LOCALIP = 3
LOCALMAC = 4
COLOR_DEBUG = 5

HE_BATTERY = 10
HE_CONTACT = 11
HE_DEVICES = 12
HE_DEVICE_DRIVER = 13
HE_DEVICE_STATES = 14
HE_HUBS = 15
HE_HUB_EVENT = 16
HE_HUB_INDIGO_DEVICE_ID = 17
# HE_HUB_MQTT_BROKER_IP = 18
# HE_HUB_MQTT_BROKER_PORT = 19
# HE_HUB_MQTT_CLIENT = 20
# HE_HUB_MQTT_CLIENT_ID = 21
# HE_HUB_MQTT_MESSAGE_SEQUENCE = 23
#HE_HUB_MQTT_TOPIC = 24
HE_HUB_THREAD = 25
HE_HUMIDITY = 26
HE_INDIGO_DEVICE_ID = 27
HE_LINKED_INDIGO_DEVICES = 28
HE_MOTION = 29
HE_MQTT_FILTERS = 30
HE_MQTT_FILTER_DEVICES = 31
HE_MQTT_FILTER_HUB = 32
HE_OUTLET = 33
HE_PROPERTIES = 34
HE_STATES = 35
HE_STATE_DIM = 36
HE_STATE_VALVE_LEVEL = 37
HE_TEMPERATURE = 38
HE_INDIGO_HUB_ID = 39

# HE_VIRTUAL_DEVICES = 40
# HE_VRTUAL_DEVICE_TYPE = 41
# HE_VIRTUAL_DEVICE_RGB_LIGHT = 42

EXPORT = 43
AVAILABLE = 44
SELECTED = 45
EXPORT_NAME = 46
EXPORT_TYPE = 47
EXPORT_MQTT_FILTERS = 48
EXPORT_ROOT_TOPIC_ID = 49
ENABLED = 50
EXPORT_ROOT_TOPIC_DEFAULT_NAME = "Indigo One"
EXPORT_EVENT = 51
EXPORT_THREAD = 52
EXPORT_FILTERS = 53
EXPORT_TOPIC_PAYLOAD_ERROR = 54
EXPORT_TOPIC_PROCESSED = 55
EXPORT_TOPIC_IGNORED = 56
EXPORT_DEVICES = 57
STORED_COLOR_MODE = 58

HE_EXPORT_DEVICE_TYPE_ALL = 0
HE_EXPORT_DEVICE_TYPE_DIMMER = 1
HE_EXPORT_DEVICE_TYPE_RELAY = 2
HE_EXPORT_DEVICE_TYPE_SENSOR = 3
HE_EXPORT_DEVICE_TYPE_THERMOSTAT = 4
HE_EXPORT_DEVICE_TYPE_SPRINKLER = 5
HE_EXPORT_DEVICE_TYPE_DEVICE = 6
HE_EXPORT_DEVICE_TYPE_OTHER = 99

TASMOTA = 100
TASMOTA_SUPPORT = 101
TASMOTA_ROOT_TOPIC_STAT = u"stat"
TASMOTA_ROOT_TOPIC_TASMOTA_DISCOVERY = u"tasmota/discovery"
TASMOTA_ROOT_TOPIC_TASMOTA = u"tasmota"
TASMOTA_ROOT_TOPIC_DISCOVERY = u"discovery"
TASMOTA_ROOT_TOPIC_TELE = u"tele"
TASMOTA_MQTT_TOPICS = 140
TASMOTA_MQTT_BROKER_IP = 102
TASMOTA_MQTT_BROKER_PORT = 108
# TASMOTA_CLIENT = 103
# TASMOTA_CLIENT_ID = 104
TASMOTA_MQTT_CLIENT = 113
TASMOTA_MQTT_CLIENT_ID = 114
TASMOTA_MQTT_INITIALISED = 105
TASMOTA_MQTT_MESSAGE_SEQUENCE = 106
TASMOTA_DEVICES = 107
TASMOTA_MQTT_FILTER_DEVICES = 109
TASMOTA_EVENT = 171
TASMOTA_THREAD = 170
TASMOTA_INDIGO_DEVICE_ID = 173
TASMOTA_PAYLOAD_POWER = 200
TASMOTA_PAYLOAD_FIRMWARE = 201
TASMOTA_PAYLOAD_FRIENDLY_NAME = 202
TASMOTA_PAYLOAD_DEVICE_NAME = 203
TASMOTA_PAYLOAD_MAC = 204
TASMOTA_PAYLOAD_MODEL = 205
TASMOTA_PAYLOAD_T = 206
TASMOTA_PAYLOAD_IP_ADDRESS = 207
TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS = 208
TASMOTA_MQTT_FILTERS = 209

TASMOTA_PAYLOAD_TIME = 210
TASMOTA_PAYLOAD_ENERGY_APPARENT_POWER = 211
TASMOTA_PAYLOAD_ENERGY_CURRENT = 212
TASMOTA_PAYLOAD_ENERGY_FACTOR = 213
TASMOTA_PAYLOAD_ENERGY_PERIOD = 214
TASMOTA_PAYLOAD_ENERGY_POWER = 215
TASMOTA_PAYLOAD_ENERGY_REACTIVE_POWER = 216
TASMOTA_PAYLOAD_ENERGY_TODAY = 217
TASMOTA_PAYLOAD_ENERGY_TOTAL = 218
TASMOTA_PAYLOAD_ENERGY_TOTAL_START_TIME = 219
TASMOTA_PAYLOAD_ENERGY_VOLTAGE = 220
TASMOTA_PAYLOAD_ENERGY_YESTERDAY = 221
TASMOTA_DISCOVERY_DETAILS = 222
TASMOTA_QUEUE = 223

MQTT = 500
MQTT_CLIENT_ID = 501
MQTT_IP = 502
MQTT_PORT = 503
MQTT_USERNAME = 504
MQTT_PASSWORD = 505
# MQTT_ENCRYPTION_KEY = 519  # Defned below in number sequence
MQTT_ENCRYPTION_KEY_PYTHON_2 = "indigo_to_hubitat"
MQTT_ENCRYPTION_PASSWORD_PYTHON_3 = b"indigo_to_hubitat"
MQTT_ROOT_TOPIC = u"homie"
MQTT_EVENT = 506
MQTT_THREAD = 507
MQTT_CLIENT =508
MQTT_CONNECTION_INITIALISED = 509
MQTT_HUB_QUEUE = 510
MQTT_EXPORT_QUEUE = 511
MQTT_TASMOTA_QUEUE = 512
MQTT_SUBSCRIBED_TOPICS = 513
MQTT_PROCESS_COMMAND_HANDLE_TOPICS = 514
MQTT_PROCESS_COMMAND_HANDLE_STOP_THREAD = 515
MQTT_CONNECTED = 516
MQTT_CLIENT_PREFIX = 517
MQTT_BROKERS = 518
MQTT_ENCRYPTION_KEY = 519

MQTT_SUBSCRIBE_TO_HOMIE = 520
MQTT_SUBSCRIBE_TO_TASMOTA = 521
MQTT_PUBLISH_TO_HOMIE = 522
MQTT_PUBLISH_TO_TASMOTA = 523

HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES = dict()
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["acceleration"] = ["humiditySensor", "illuminanceSensor", "motionSensor", "multiSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["battery"] = ["button", "contactSensor", "humiditySensor", "illuminanceSensor", "motionSensor", "multiSensor", "temperatureSensor", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["button"] = ["button"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["color-mode"] = ["dimmer"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["color-name"] = ["dimmer"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["color-temperature"] = ["dimmer"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["contact"] = ["contactSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["dim"] = ["dimmer", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["energy"] = ["outlet"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["humidity"] = ["humiditySensor", "illuminanceSensor", "motionSensor", "multiSensor", "temperatureSensor", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["illuminance"] = ["humiditySensor", "illuminanceSensor", "motionSensor", "multiSensor", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["mode"] = ["thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["motion"] = ["humiditySensor", "illuminanceSensor", "motionSensor", "multiSensor", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["onoff"] = ["blind", "dimmer", "outlet", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["position"] = ["blind"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["power"] = ["outlet"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["presence"] = ["button", "contactSensor", "motionSensor", "multiSensor", "presenceSensor", "outlet", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["presence-sensor"] = ["button", "contactSensor", "motionSensor", "multiSensor", "outlet", "presenceSensor", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["pressure"] = ["multiSensor", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["state"] = ["blind", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["temperature"] = ["humiditySensor", "illuminanceSensor", "motionSensor", "multiSensor", "temperatureSensor", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["thermostat-setpoint"] = ["thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["voltage"] = ["button", "contactSensor", "motionSensor", "outlet", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["hsm"] = ["hubitatElevationHub"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["refresh"] = ["outlet", "thermostat"]

HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES = dict()
# HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["hubitatElevationHub"] = ["hsm"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["button"] = ["button"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["blind"] = ["position"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["contactSensor"] = ["contact"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["dimmer"] = ["dim"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["humiditySensor"] = ["humidity", "measure-humidity"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["illuminanceSensor"] = ["illuminance", "measure-illuminance"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["motionSensor"] = ["motion"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["multiSensor"] = ["motion"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["outlet"] = ["onoff"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["presenceSensor"] = ["presence"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["temperatureSensor"] = ["temperature", "measure-temperature"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["thermostat"] = ["temperature", "measure-temperature"]

INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE = "0"
INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE = "1"
INDIGO_SECONDARY_DEVICE = "2"
# INDIGO_SECONDARY_DEVICE_ADDITIONAL_STATE = "3"

INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE = dict()
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["button"] = []
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["contactSensor"] = []
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["dimmer"] = []
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["humiditySensor"] = ["accelerationSensorSecondary", "illuminanceSensorSecondary", "motionSensorSecondary", "pressureSensorSecondary", "temperatureSensorSecondary"]
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["illuminanceSensor"] = ["accelerationSensorSecondary", "humiditySensorSecondary", "motionSensorSecondary", "pressureSensorSecondary", "temperatureSensorSecondary"]
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["motionSensor"] = ["accelerationSensorSecondary", "humiditySensorSecondary", "illuminanceSensorSecondary", "temperatureSensorSecondary"]
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["multiSensor"] = ["accelerationSensorSecondary", "humiditySensorSecondary", "illuminanceSensorSecondary", "temperatureSensorSecondary"]
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["outlet"] = ["voltageSensorSecondary"]
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["presenceSensor"] = []
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["temperatureSensor"] = ["humiditySensorSecondary", "illuminanceSensorSecondary", "motionSensorSecondary", "pressureSensorSecondary"]
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["thermostat"] = ["valveSecondary"]
INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE["hubitatElevationHub"] = ["hsmSensorSecondary"]

INDIGO_SUB_TYPE_INFO = dict()
INDIGO_SUB_TYPE_INFO["accelerationSensorSecondary"] = ["uspAccelerationIndigo", [indigo.kSensorDeviceSubType.Tamper, "Acceleration"],
                                                       [("SupportsOnState", True), ("AllowOnStateChange", True), ("SupportsStatusRequest", False),
                                                        ("SupportsSensorValue", False), ("AllowSensorValueChange", False)]]
INDIGO_SUB_TYPE_INFO["illuminanceSensorSecondary"] = ["uspIlluminanceIndigo", [indigo.kSensorDeviceSubType.Illuminance, "Illuminance"],
                                                      [("SupportsOnState", False), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                       ("SupportsSensorValue", True), ("AllowSensorValueChange", False)]]
INDIGO_SUB_TYPE_INFO["humiditySensorSecondary"] = ["uspHumidityIndigo", [indigo.kSensorDeviceSubType.Humidity, "Humidity"],
                                                   [("SupportsOnState", False), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                    ("SupportsSensorValue", True), ("AllowSensorValueChange", False)]]
INDIGO_SUB_TYPE_INFO["motionSensorSecondary"] = ["uspMotionIndigo", [indigo.kSensorDeviceSubType.Motion, "Motion"],
                                                 [("SupportsOnState", True), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                  ("SupportsSensorValue", False), ("AllowSensorValueChange", False)]]
INDIGO_SUB_TYPE_INFO["pressureSensorSecondary"] = ["uspPressureIndigo", [indigo.kSensorDeviceSubType.Pressure, "Pressure"],
                                                   [("SupportsOnState", False), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                    ("SupportsSensorValue", True), ("AllowSensorValueChange", False)]]
INDIGO_SUB_TYPE_INFO["temperatureSensorSecondary"] = ["uspTemperatureIndigo", [indigo.kSensorDeviceSubType.Temperature, "Temperature"],
                                                      [("SupportsOnState", False), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                       ("SupportsSensorValue", True), ("AllowSensorValueChange", False)]]
INDIGO_SUB_TYPE_INFO["valveSecondary"] = ["uspValveIndigo", [indigo.kDimmerDeviceSubType.Valve, "Valve"], [("SupportsStatusRequest", True)]]
INDIGO_SUB_TYPE_INFO["voltageSensorSecondary"] = ["uspVoltageIndigo", [indigo.kSensorDeviceSubType.Voltage, "Voltage"],
                                            [("SupportsOnState", False), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                             ("SupportsSensorValue", True), ("AllowSensorValueChange", False)]]
INDIGO_SUB_TYPE_INFO["hsmSensorSecondary"] = ["uspHsmIndigo", [indigo.kDeviceSubType.Security, "Alarm"],
                                              [("SupportsOnState", True), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                               ("SupportsSensorValue", False), ("AllowSensorValueChange", False)]]

INDIGO_PRIMARY_DEVICE_INFO = dict()
INDIGO_PRIMARY_DEVICE_INFO["button"] = [indigo.kRelayDeviceSubType.PlugIn, "Button"]
INDIGO_PRIMARY_DEVICE_INFO["blind"] = [indigo.kDimmerDeviceSubType.Dimmer, "Blind"]
INDIGO_PRIMARY_DEVICE_INFO["contactSensor"] = [indigo.kSensorDeviceSubType.DoorWindow, "Contact"]
INDIGO_PRIMARY_DEVICE_INFO["dimmer"] = [indigo.kDimmerDeviceSubType.Dimmer, "Dimmer"]
INDIGO_PRIMARY_DEVICE_INFO["humidity"] = [indigo.kSensorDeviceSubType.Humidity, "Humidity"]
INDIGO_PRIMARY_DEVICE_INFO["illuminance"] = [indigo.kSensorDeviceSubType.Illuminance, "Illuminance"]
INDIGO_PRIMARY_DEVICE_INFO["motionSensor"] = [indigo.kSensorDeviceSubType.Motion, "Motion"]
INDIGO_PRIMARY_DEVICE_INFO["multiSensor"] = [indigo.kSensorDeviceSubType.Motion, "Motion"]
INDIGO_PRIMARY_DEVICE_INFO["outlet"] = [indigo.kRelayDeviceSubType.Outlet, "Outlet"]
INDIGO_PRIMARY_DEVICE_INFO["presenceSensor"] = [indigo.kSensorDeviceSubType.Presence, "Presence"]
INDIGO_PRIMARY_DEVICE_INFO["temperatureSensor"] = [indigo.kSensorDeviceSubType.Temperature, "Temperature"]
INDIGO_PRIMARY_DEVICE_INFO["thermostat"] = [indigo.kSensorDeviceSubType.Temperature, "Thermostat"]
INDIGO_PRIMARY_DEVICE_INFO["hubitatElevationHub"] = [indigo.kDeviceSubType.Other, "Hub"]

INDIGO_ONE_SPACE_BEFORE_UNITS = True
INDIGO_NO_SPACE_BEFORE_UNITS = False

K_ADDRESS = 1
K_API_VERSION = 2
K_PATH = 3
K_PLUGIN_DISPLAY_NAME = 4
K_PLUGIN_ID = 5
K_PLUGIN_INFO = 6
K_PLUGIN_VERSION = 7
K_ZWI = 8
K_ZWAVE_LOGGING = 9
K_ZWAVE_LOGGING_FOLDER = 10
K_ZWAVE_LOGGING_FILE_NAME = 11
K_ZWAVE_LOGGING_MODE = 12
K_INTERPRETER_CLASS_INSTANCES = 13
K_ZWAVE_LOG_TO_INDIGO_EVENT_LOG = 14
K_ZWAVE_LOGGING_AUTO_START = 15

K_LOG_LEVEL_NOT_SET = 0
K_LOG_LEVEL_DEBUGGING = 10
K_LOG_LEVEL_TOPIC = 15
K_LOG_LEVEL_INFO = 20
K_LOG_LEVEL_WARNING = 30
K_LOG_LEVEL_ERROR = 40
K_LOG_LEVEL_CRITICAL = 50

K_LOG_LEVEL_TRANSLATION = dict()
K_LOG_LEVEL_TRANSLATION[K_LOG_LEVEL_NOT_SET] = "Not Set"
K_LOG_LEVEL_TRANSLATION[K_LOG_LEVEL_DEBUGGING] = "Debugging"
K_LOG_LEVEL_TRANSLATION[K_LOG_LEVEL_TOPIC] = "Topic Logging"
K_LOG_LEVEL_TRANSLATION[K_LOG_LEVEL_INFO] = "Info"
K_LOG_LEVEL_TRANSLATION[K_LOG_LEVEL_WARNING] = "Warning"
K_LOG_LEVEL_TRANSLATION[K_LOG_LEVEL_ERROR] = "Error"
K_LOG_LEVEL_TRANSLATION[K_LOG_LEVEL_CRITICAL] = "Critical"

# Rounded  Kelvin Descriptions (from iOS LIFX App)
ROUNDED_KELVINS =dict()
ROUNDED_KELVINS[2500] = ((246, 221, 184), "~ Ultra Warm")
ROUNDED_KELVINS[2750] = ((246, 224, 184), "~ Incandescent")
ROUNDED_KELVINS[3000] = ((248, 227, 195), "~ Warm")
ROUNDED_KELVINS[3200] = ((247, 228, 198), "~ Neutral Warm")
ROUNDED_KELVINS[3500] = ((246, 228, 201), "~ Neutral")
ROUNDED_KELVINS[4000] = ((249, 234, 210), "~ Cool")
ROUNDED_KELVINS[4500] = ((250, 238, 217), "~ Cool Daylight")
ROUNDED_KELVINS[5000] = ((250, 239, 219), "~ Soft Daylight")
ROUNDED_KELVINS[5500] = ((249, 240, 225), "~ Daylight")
ROUNDED_KELVINS[6000] = ((247, 241, 230), "~ Noon Daylight")
ROUNDED_KELVINS[6500] = ((245, 242, 234), "~ Bright Daylight")
ROUNDED_KELVINS[7000] = ((241, 240, 236), "~ Cloudy Daylight")
ROUNDED_KELVINS[7500] = ((236, 236, 238), "~ Blue Daylight")
ROUNDED_KELVINS[8000] = ((237, 240, 246), "~ Blue Overcast")
ROUNDED_KELVINS[8500] = ((236, 241, 249), "~ Blue Water")
ROUNDED_KELVINS[9000] = ((237, 243, 252), "~ Blue Ice")
