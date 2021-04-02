#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Z-Wave Interpreter - Constants © Autolog 2020
#

# plugin Constants

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError, e:
    pass

DEVICES = 0
MQTT_CLIENT = 1
MQTT_CLIENT_ID = 2
NODE_LIST = 3
NODES_TEMP = 4
PAYLOAD = "$payload"

HE_BATTERY = 10
HE_CONTACT = 11
HE_DEVICES = 12
HE_DEVICE_DRIVER = 13
HE_DEVICE_STATES = 14
HE_HUBS = 15
HE_HUB_EVENT = 16
HE_HUB_INDIGO_DEVICE_ID = 17
HE_HUB_MQTT_BROKER_IP = 18
HE_HUB_MQTT_BROKER_PORT = 19
HE_HUB_MQTT_CLIENT = 20
HE_HUB_MQTT_CLIENT_ID = 21
HE_HUB_MQTT_INITIALISED = 22
HE_HUB_MQTT_MESSAGE_SEQUENCE = 23
HE_HUB_MQTT_TOPIC = 24
HE_HUB_ROOT_TOPIC = u"homie"
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

HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES = dict()
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["acceleration"] = ["motionSensor", "multiSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["battery"] = ["button", "contactSensor", "motionSensor", "multiSensor", "temperatureSensor", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["button"] = ["button"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["color-mode"] = ["dimmer"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["color-name"] = ["dimmer"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["color-temperature"] = ["dimmer"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["contact"] = ["contactSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["dim"] = ["dimmer", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["energy"] = ["outlet"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["humidity"] = ["motionSensor", "multiSensor", "temperatureSensor", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["illuminance"] = ["motionSensor", "multiSensor", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["mode"] = ["thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["motion"] = ["motionSensor", "multiSensor", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["onoff"] = ["outlet", "dimmer", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["power"] = ["outlet"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["presence"] = ["button", "contactSensor", "motionSensor", "multiSensor", "outlet", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["presence-sensor"] = ["button", "contactSensor", "motionSensor", "multiSensor", "outlet", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["pressure"] = ["multiSensor", "temperatureSensor"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["state"] = ["thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["temperature"] = ["motionSensor", "multiSensor", "temperatureSensor", "thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["thermostat-setpoint"] = ["thermostat"]
HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES["voltage"] = ["button", "contactSensor", "motionSensor", "outlet", "temperatureSensor"]

HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES = dict()
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["button"] = ["button"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["contactSensor"] = ["contact"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["dimmer"] = ["dim"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["motionSensor"] = ["motion"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["multiSensor"] = ["motion"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["outlet"] = ["onoff"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["temperatureSensor"] = ["temperature", "measure-temperature"]
HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES["thermostat"] = ["temperature", "measure-temperature"]

INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE = "0"
INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE = "1"
INDIGO_SECONDARY_DEVICE = "2"
INDIGO_SECONDARY_DEVICE_ADDITIONAL_STATE = "3"

INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE = dict()
INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE["button"] = []
INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE["contactSensor"] = []
INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE["dimmer"] = []
INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE["motionSensor"] = ["accelerationSensorSubModel", "illuminanceSensorSubModel", "temperatureSensorSubModel"]
INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE["multiSensor"] = ["accelerationSensorSubModel", "illuminanceSensorSubModel", "temperatureSensorSubModel"]
INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE["temperatureSensor"] = ["motionSensorSubModel", "pressureSensorSubModel", "illuminanceSensorSubModel"]
INDIGO_SUPPORTED_SUB_MODELS_BY_DEVICE["thermostat"] = ["valveSubModel"]

INDIGO_SUB_MODEL_REQUIRED = dict()
INDIGO_SUB_MODEL_REQUIRED["accelerationSensorSubModel"] = ["uspAccelerationIndigo", "Acceleration",
                                                           [("SupportsOnState", True), ("AllowOnStateChange", True), ("SupportsStatusRequest", False),
                                                            ("SupportsSensorValue", False), ("AllowSensorValueChange", False)]]
INDIGO_SUB_MODEL_REQUIRED["illuminanceSensorSubModel"] = ["uspIlluminanceIndigo", "Illuminance",
                                                          [("SupportsOnState", False), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                           ("SupportsSensorValue", True), ("AllowSensorValueChange", False)]]
INDIGO_SUB_MODEL_REQUIRED["motionSensorSubModel"] = ["uspMotionIndigo", "Motion",
                                                     [("SupportsOnState", True), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                      ("SupportsSensorValue", False), ("AllowSensorValueChange", False)]]
INDIGO_SUB_MODEL_REQUIRED["pressureSensorSubModel"] = ["uspPressureIndigo", "Pressure",
                                                       [("SupportsOnState", False), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                        ("SupportsSensorValue", True), ("AllowSensorValueChange", False)]]
INDIGO_SUB_MODEL_REQUIRED["temperatureSensorSubModel"] = ["uspTemperatureIndigo", "Temperature",
                                                          [("SupportsTemperatureReporting", True), ("NumTemperatureInputs", 1),
                                                           ("SupportsHeatSetpoint", False), ("SupportsHvacOperationMode", False),
                                                           ("SupportsCoolSetpoint", False), ("SupportsHvacFanMode", False),
                                                           ("SupportsStatusRequest", False), ("SupportsOnState", False), ("AllowOnStateChange", False)]]
INDIGO_SUB_MODEL_REQUIRED["valveSubModel"] = ["uspValveIndigo", "Valve", [("SupportsStatusRequest", False)]]
INDIGO_SUB_MODEL_REQUIRED["voltageSubModel"] = ["uspVoltageIndigo", "Voltage",
                                                          [("SupportsOnState", False), ("AllowOnStateChange", False), ("SupportsStatusRequest", False),
                                                           ("SupportsSensorValue", True), ("AllowSensorValueChange", False)]]

INDIGO_PRIMARY_DEVICE__MODEL_UI = dict()
INDIGO_PRIMARY_DEVICE__MODEL_UI["button"] = "Button"
INDIGO_PRIMARY_DEVICE__MODEL_UI["contactSensor"] = "Contact"
INDIGO_PRIMARY_DEVICE__MODEL_UI["dimmer"] = "Dimmer"
INDIGO_PRIMARY_DEVICE__MODEL_UI["motionSensor"] = "Motion"
INDIGO_PRIMARY_DEVICE__MODEL_UI["multiSensor"] = "Motion"
INDIGO_PRIMARY_DEVICE__MODEL_UI["outlet"] = "Outlet"
INDIGO_PRIMARY_DEVICE__MODEL_UI["temperatureSensor"] = "Temperature"
INDIGO_PRIMARY_DEVICE__MODEL_UI["thermostat"] = "Thermostat"

INDIGO_SECONDARY_DEVICE__MODEL_UI = dict()
INDIGO_SECONDARY_DEVICE__MODEL_UI["accelerationSensorSubModel"] = "Acceleration"
INDIGO_SECONDARY_DEVICE__MODEL_UI["illuminanceSensorSubModel"] = "Illuminance"
INDIGO_SECONDARY_DEVICE__MODEL_UI["motionSensorSubModel"] = "Motion"
INDIGO_SECONDARY_DEVICE__MODEL_UI["pressureSensorSubModel"] = "Pressure"
INDIGO_SECONDARY_DEVICE__MODEL_UI["temperatureSensorSubModel"] = "Temperature"
INDIGO_SECONDARY_DEVICE__MODEL_UI["valveSubModel"] = "Valve"
INDIGO_SECONDARY_DEVICE__MODEL_UI["voltageSubModel"] = "Voltage"

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
ROUNDED_KELVINS[2500] = ((246, 221, 184), "~2500K Ultra Warm")
ROUNDED_KELVINS[2750] = ((246, 224, 184), "~2750K Incandescent")
ROUNDED_KELVINS[3000] = ((248, 227, 195), "~3000K Warm")
ROUNDED_KELVINS[3200] = ((247, 228, 198), "~3200K Neutral Warm")
ROUNDED_KELVINS[3500] = ((246, 228, 201), "~3500K Neutral")
ROUNDED_KELVINS[4000] = ((249, 234, 210), "~4000K Cool")
ROUNDED_KELVINS[4500] = ((250, 238, 217), "~4500K Cool Daylight")
ROUNDED_KELVINS[5000] = ((250, 239, 219), "~5000K Soft Daylight")
ROUNDED_KELVINS[5500] = ((249, 240, 225), "~5500K Daylight")
ROUNDED_KELVINS[6000] = ((247, 241, 230), "~6000K Noon Daylight")
ROUNDED_KELVINS[6500] = ((245, 242, 234), "~6500K Bright Daylight")
ROUNDED_KELVINS[7000] = ((241, 240, 236), "~7000K Cloudy Daylight")
ROUNDED_KELVINS[7500] = ((236, 236, 238), "~7500K Blue Daylight")
ROUNDED_KELVINS[8000] = ((237, 240, 246), "~8000K Blue Overcast")
ROUNDED_KELVINS[8500] = ((236, 241, 249), "~8500K Blue Water")
ROUNDED_KELVINS[9000] = ((237, 243, 252), "~9000K Blue Ice")
