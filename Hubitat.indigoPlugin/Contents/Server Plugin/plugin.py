#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Hubitat - Plugin © Autolog 2021-2022
#


# noinspection PyUnresolvedReferences
# ============================== Native Imports ===============================
import base64

try:
    from cryptography.fernet import Fernet  # noqa
    from cryptography.hazmat.primitives import hashes  # noqa
    from cryptography.hazmat.primitives import hashes  # noqa
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # noqa
except ImportError:
    raise ImportError("'cryptography' library missing.\n\n========> Run 'pip3 install cryptography' in Terminal window, then reload plugin. <========\n")

import colorsys
from datetime import datetime
import logging
import os
import platform
try:
    # Python 3
    import queue
except ImportError:
    # Python 2
    import Queue as queue
import re
import socket
import sys
import threading
import traceback


# ============================== Custom Imports ===============================
try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

from constants import *
from hubHandler import ThreadHubHandler
from tasmotaHandler import ThreadTasmotaHandler
from mqttHandler import ThreadMqttHandler
from exportHandler import ThreadExportHandler

# ================================== Header ===================================
__author__    = "Autolog"
__copyright__ = ""
__license__   = "MIT"
__build__     = "unused"
__title__     = "Hubitat Bridge Plugin for Indigo"
__version__   = "unused"

# https://stackoverflow.com/questions/2490334/simple-way-to-encode-a-string-according-to-a-password/66728699#66728699


def encode(unencrypted_password):
    # print(f"Python 3 Encode, Argument: Unencrypted Password = {unencrypted_password}")

    internal_password = MQTT_ENCRYPTION_PASSWORD_PYTHON_3  # Byte string
    # print(f"Python 3 Encode - Internal Password: {internal_password}")

    salt = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    key = base64.urlsafe_b64encode(kdf.derive(internal_password))
    # print(f"Python 3 Encode - Key: {key}")

    f = Fernet(key)

    unencrypted_password = unencrypted_password.encode()  # str -> b
    encrypted_password = f.encrypt(unencrypted_password)
    # print(f"Python 3 Encode - Encrypted Password: {encrypted_password}")

    return key, encrypted_password


def decode(key, encrypted_password):
    # print(f"Python 3 Decode, Arguments: Key='{key}', Encrypted Password='{encrypted_password}'")

    f = Fernet(key)
    unencrypted_password = f.decrypt(encrypted_password)

    # print(f"Python 3 Decode: Unencrypted Password = {unencrypted_password}")
    
    return unencrypted_password


# noinspection PyPep8Naming
class Plugin(indigo.PluginBase):

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super(Plugin, self).__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)

        logging.addLevelName(K_LOG_LEVEL_TOPIC, "topic")

        def topic(self, message, *args, **kws):  # noqa [Shadoeing names from outer scope = self]
            # if self.isEnabledFor(K_LOG_LEVEL_TOPIC):
            # Yes, logger takes its '*args' as 'args'.
            self.log(K_LOG_LEVEL_TOPIC, message, *args, **kws)

        logging.Logger.topic = topic

        # Initialise dictionary to store plugin Globals
        self.globals = dict()

        self.globals[COLOR_DEBUG] = False

        self.globals[LOCK_MQTT] = threading.Lock()  # Used to lock updating of self.globals[MQTT]
        self.globals[LOCK_HE_LINKED_INDIGO_DEVICES] = threading.Lock()  # Used to lock updating of 'self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]'
        self.globals[QUEUES] = dict()

        self.globals[LOCALIP] = socket.gethostbyname('localhost')

        # Initialise Indigo plugin info
        self.globals[K_PLUGIN_INFO] = {}
        self.globals[K_PLUGIN_INFO][K_PLUGIN_ID] = plugin_id
        self.globals[K_PLUGIN_INFO][K_PLUGIN_DISPLAY_NAME] = plugin_display_name
        self.globals[K_PLUGIN_INFO][K_PLUGIN_VERSION] = plugin_version
        self.globals[K_PLUGIN_INFO][K_PATH] = indigo.server.getInstallFolderPath()
        self.globals[K_PLUGIN_INFO][K_API_VERSION] = indigo.server.apiVersion
        self.globals[K_PLUGIN_INFO][K_ADDRESS] = indigo.server.address

        log_format = logging.Formatter("%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.plugin_file_handler.setFormatter(log_format)
        self.plugin_file_handler.setLevel(K_LOG_LEVEL_INFO)  # Logging Level for plugin log file
        self.indigo_log_handler.setLevel(K_LOG_LEVEL_INFO)   # Logging level for Indigo Event Log

        self.logger = logging.getLogger("Plugin.Hubitat")

        # Now logging is set up, output Initialising Message
        startup_message_ui = "\n"  # Start with a line break
        startup_message_ui += f"{' Initialising Hubitat Bridge Plugin Plugin ':={'^'}130}\n"
        startup_message_ui += f"{'Plugin Name:':<31} {self.globals[K_PLUGIN_INFO][K_PLUGIN_DISPLAY_NAME]}\n"
        startup_message_ui += f"{'Plugin Version:':<31} {self.globals[K_PLUGIN_INFO][K_PLUGIN_VERSION]}\n"
        startup_message_ui += f"{'Plugin ID:':<31} {self.globals[K_PLUGIN_INFO][K_PLUGIN_ID]}\n"
        startup_message_ui += f"{'Indigo Version:':<31} {indigo.server.version}\n"
        startup_message_ui += f"{'Indigo License:':<31} {indigo.server.licenseStatus}\n"
        startup_message_ui += f"{'Indigo API Version:':<31} {indigo.server.apiVersion}\n"
        machine = platform.machine()
        startup_message_ui += f"{'Architecture:':<31} {machine}\n"
        sys_version = sys.version.replace("\n", "")
        startup_message_ui += f"{'Python Version:':<31} {sys_version}\n"
        startup_message_ui += f"{'Mac OS Version:':<31} {platform.mac_ver()[0]}\n"
        startup_message_ui += f"{'':={'^'}130}\n"
        self.logger.info(startup_message_ui)

        self.globals[MQTT] = dict()

        # Setup stores for Hubitat and Tasmota devices
        self.globals[HE_HUBS] = dict()
        self.globals[HE_MQTT_FILTERS] = list()

        self.globals[TASMOTA] = dict()
        self.globals[TASMOTA][TASMOTA_DEVICES] = dict()
        self.globals[TASMOTA][TASMOTA_QUEUE] = dict()
        self.globals[TASMOTA_MQTT_FILTERS] = list()
        self.globals[TASMOTA][MQTT_BROKERS] = dict()

        # Set Plugin Config Values
        self.closedPrefsConfigUi(plugin_prefs, False)

        # python 2 / 3
        def _no_image():
            try:
                return getattr(indigo.kStateImageSel, "NoImage")
            except Exception:
                return getattr(indigo.kStateImageSel, "None")

        self.globals[EXPORT] = dict()
        self.globals[EXPORT][EXPORT_NAME] = None
        self.globals[EXPORT][AVAILABLE] = dict()
        self.globals[EXPORT][SELECTED] = dict()
        self.globals[EXPORT][ENABLED] = dict()
        self.globals[EXPORT][MQTT_BROKERS] = list()
        self.globals[EXPORT][EXPORT_DEVICES] = dict()
        self.globals[EXPORT][EXPORT_ROOT_TOPIC_ID] = ""

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method}'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.logger.error(log_message)

    def actionControlDevice(self, action, dev):
        try:
            if not dev.enabled:
                return

            def dp(dev):
                # Dim / Position
                if dev.subType == indigo.kDimmerDeviceSubType.Blind:
                    return "position", "open", "close"
                else:
                    return "dim", "brighten", "dim"

            def oooc(dev):
                # on|off / open|close
                if dev.subType == indigo.kDimmerDeviceSubType.Blind:
                    return "open", "close"
                else:
                    return "turn on", "turn off"

            dev_id = dev.id

            dev_props = dev.pluginProps

            hubitat_hub_name = ""  # Only needed here to avoid PyCharm flagging a possible error
            hubitat_device_name = ""  # Only needed here to avoid PyCharm flagging a possible error

            if dev.deviceTypeId == "tasmotaOutlet":
                tasmota_key = dev_props["tasmotaDevice"]
                # Set default topic for tasmota
                topic = f"cmnd/tasmota_{tasmota_key}/Power"  # e.g. "cmnd/tasmota_6E641A/Power"

            elif dev.deviceTypeId == "indigoExport":
                self.actionControlDevice_indigoExport(action, dev)
                return

            else:
                if "hubitatDevice" in dev_props:
                    hubitat_device_name = dev_props["hubitatDevice"]
                    hubitat_hub_name = dev_props.get("hubitatHubName", "")
                    hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
                elif "linkedPrimaryIndigoDeviceId" in dev_props:
                    hubitat_device_name = dev_props["associatedHubitatDevice"]
                    linked_indigo_device_id = int(dev_props.get("linkedPrimaryIndigoDeviceId", 0))
                    linked_indigo_dev = indigo.devices[linked_indigo_device_id]
                    linked_dev_props = linked_indigo_dev.pluginProps
                    hubitat_hub_name = linked_dev_props.get("hubitatHubName", "")
                    hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
                else:
                    self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as unable to resolve Hubitat Hub device.")
                    return

                if hubitat_hub_dev_id > 0:
                    mqtt_connected = False
                    for mqtt_broker_device_id in self.globals[HE_HUBS][hubitat_hub_name][MQTT_BROKERS]:
                        if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                            mqtt_connected = True
                            break
                    if not mqtt_connected:
                        self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as Hubitat Hub device '{hubitat_hub_name}' is not initialised. Is MQTT running?")
                        return
                else:
                    self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as unable to resolve Hubitat Hub device.")
                    return

                # Set default topic for turn on / off / toggle
                topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/onoff/set"  # e.g. "homie/home-1/study-socket-spare/onoff/set"

            mqtt_filter_key = f"{hubitat_hub_name.lower()}|{hubitat_device_name.lower()}"

            # ##### TURN ON ######
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "blind" or dev.deviceTypeId == "outlet" or dev.deviceTypeId == "tasmotaOutlet":
                    positive, negative = oooc(dev)
                    self.logger.info(f"sending \"{positive}\" to \"{dev.name}\"")
                    if dev.deviceTypeId == "tasmotaOutlet":
                        topic_payload = "On"
                        self.publish_tasmota_topic(tasmota_key, topic, topic_payload)  # noqa [Local variable 'tasmota_key' might be referenced before assignment]
                    else:
                        topic_payload = "true"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                elif dev.deviceTypeId == "valveSecondary":
                    valve_level = 50  # Assume 50% open
                    if HE_STATE_VALVE_LEVEL in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES]:
                        try:
                            saved_valve_level = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_VALVE_LEVEL]
                            if saved_valve_level > 0:
                                valve_level = saved_valve_level
                        except ValueError:
                            pass
                    dev_id_list = indigo.device.getGroupList(dev_id)
                    if len(dev_id_list) == 1:
                        return
                    thermostat_dev_id = 0
                    for linked_dev_id in dev_id_list:
                        if linked_dev_id != dev_id:
                            thermostat_dev_id = linked_dev_id
                    if thermostat_dev_id == 0:
                        return
                    thermostat_dev = indigo.devices[thermostat_dev_id]
                    hvac_state = thermostat_dev.states["hvacState"]

                    if hvac_state != "Direct Valve Control":
                        topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/mode/set"  # e.g. "homie/home-1/trv-valve/mode/set"
                        topic_payload = "off"  # Forces TRV into "Direct Valve Control"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                    topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/dim/set"  # e.g. "homie/home-1/trv-valve/dim/set"
                    topic_payload = f"{valve_level}"
                    self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)

                    self.logger.info(f"sending \"Open Valve to {valve_level} %\" to \"{dev.name}\"")

            # ##### TURN OFF ######
            elif action.deviceAction == indigo.kDeviceAction.TurnOff:
                if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "blind" or dev.deviceTypeId == "outlet" or dev.deviceTypeId == "tasmotaOutlet":
                    positive, negative = oooc(dev)
                    self.logger.info(f"sending \"{negative}\" to \"{dev.name}\"")
                    if dev.deviceTypeId == "tasmotaOutlet":
                        topic_payload = "Off"
                        self.publish_tasmota_topic(tasmota_key, topic, topic_payload)  # noqa [Local variable 'tasmota_key' might be referenced before assignment]
                    else:
                        topic_payload = "false"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                elif dev.deviceTypeId == "valveSecondary":
                    dev_id_list = indigo.device.getGroupList(dev_id)
                    if len(dev_id_list) == 1:
                        return
                    thermostat_dev_id = 0
                    for linked_dev_id in dev_id_list:
                        if linked_dev_id != dev_id:
                            thermostat_dev_id = linked_dev_id
                    if thermostat_dev_id == 0:
                        return
                    thermostat_dev = indigo.devices[thermostat_dev_id]

                    self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_VALVE_LEVEL] = dev.brightness
                    hvac_state = thermostat_dev.states["hvacState"]
                    if hvac_state != "Direct Valve Control":
                        topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/mode/set"  # e.g. "homie/home-1/trv-valve/mode/set"
                        topic_payload = "off"  # Forces TRV into "Direct Valve Control"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                    topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/dim/set"  # e.g. "homie/home-1/trv-valve/dim/set"
                    topic_payload = "0"  # Close the valve = 0% open
                    self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)

                    self.logger.info(f"sending \"close valve\"to \"{dev.name}\"")

            # ##### TOGGLE ######
            elif action.deviceAction == indigo.kDeviceAction.Toggle:
                if dev.onState:
                    # dev.updateStateOnServer(key="onOffState", value=False)
                    positive, negative = oooc(dev)
                    self.logger.info(f"sending \"toggle {negative}\" to \"{dev.name}\"")
                    if dev.deviceTypeId == "tasmotaOutlet":
                        topic_payload = "Off"
                        self.publish_tasmota_topic(tasmota_key, topic, topic_payload)  # noqa [Local variable 'tasmota_key' might be referenced before assignment]
                    else:
                        topic_payload = "false"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                else:
                    positive, negative = oooc(dev)
                    self.logger.info(f"sending \"toggle {positive}\" to \"{dev.name}\"")
                    if dev.deviceTypeId == "tasmotaOutlet":
                        topic_payload = "On"
                        # noinspection PyUnboundLocalVariable
                        self.publish_tasmota_topic(tasmota_key, topic, topic_payload)  # noqa [Local variable 'tasmota_key' might be referenced before assignment]
                    else:
                        topic_payload = "true"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)

            # ##### SET BRIGHTNESS ######
            elif action.deviceAction == indigo.kDeviceAction.SetBrightness:
                if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "blind" :
                    topic_coomand, positive, negative = dp(dev)
                    new_brightness = int(action.actionValue)   # action.actionValue contains brightness value (0 - 100)
                    action_ui = "set"
                    if new_brightness > 0:
                        if new_brightness > dev.brightness:
                            action_ui = positive  # eg "brighten"
                        else:
                            action_ui = negative  # eg "dim"
                    new_brightness_ui = f"{new_brightness}%"

                    topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/{topic_coomand}/set"  # e.g. "homie/home-1/study-socket-spare/dim/set"
                    topic_payload = f"{new_brightness}"
                    self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)

                    self.logger.info(f"sending \"{action_ui} to {new_brightness_ui}\" to \"{dev.name}\"")

                elif dev.deviceTypeId == "valveSecondary":
                    new_valve_level = int(action.actionValue)  # action.actionValue contains brightness value (0 - 100)
                    action_ui = "set"
                    if new_valve_level > 0:
                        if new_valve_level > dev.brightness:
                            action_ui = "open"
                        else:
                            action_ui = "close"
                    new_brightness_ui = f"{new_valve_level}%"

                    if new_valve_level > 99:
                        new_valve_level = 99  # Fix for Eurotronic Spirit where 99 = 100 !!!

                    topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/dim/set"  # e.g. "homie/home-1/study-socket-spare/dim/set"
                    topic_payload = f"{new_valve_level}"
                    self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)

                    self.logger.info(f"sending \"{new_brightness_ui} to {dev.name}\" to \"{action_ui}\" ")

            # # ##### BRIGHTEN BY ######
            elif action.deviceAction == indigo.kDeviceAction.BrightenBy:
                # if not dev.onState:
                #     pass  # TODO: possibly turn on?
                if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "blind" :
                    topic_coomand, positive, negative = dp(dev)
                    if dev.brightness < 100:
                        brighten_by = int(action.actionValue)  # action.actionValue contains brightness increase value
                        new_brightness = dev.brightness + brighten_by
                        if new_brightness > 100:
                            new_brightness = 100
                        brighten_by_ui = f"{brighten_by}%"
                        new_brightness_ui = f"{new_brightness}%"

                        topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/{topic_coomand}/set"  # e.g. "homie/home-1/study-socket-spare/dim/set"
                        topic_payload = f"{new_brightness}"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                        self.logger.info(f"sending \"{positive} by {brighten_by_ui} to {new_brightness_ui}\" to \"{dev.name}\"")
                    else:
                        self.logger.info(f"Ignoring {positive} request for {positive} as device is already at full brightness")

                elif dev.deviceTypeId == "valveSecondary":
                    if dev.brightness < 99:  # Fix for Eurotronic Spirit where 99 = 100 !!!
                        open_by = int(action.actionValue)  # action.actionValue contains brightness increase value
                        new_valve_level = dev.brightness + open_by
                        if new_valve_level > 100:
                            new_valve_level = 100
                        brighten_by_ui = f"{open_by}%"
                        new_brightness_ui = f"{new_valve_level}%"
                        if new_valve_level > 99:
                            new_valve_level = 99  # Fix for Eurotronic Spirit where 99 = 100 !!!

                        topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/dim/set"  # e.g. "homie/home-1/study-socket-spare/dim/set"
                        topic_payload = f"{new_valve_level}"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                        self.logger.info(f"sending \"open valve by {new_brightness_ui} to {dev.name}\" to \"{dev.name}\"")
                    else:
                        self.logger.info(f"Ignoring \"open Valve\" request for {dev.name} as valve is already fully open")

            # ##### DIM BY ######
            elif action.deviceAction == indigo.kDeviceAction.DimBy:
                if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "blind" :
                    topic_coomand, positive, negative = dp(dev)
                    if dev.onState and dev.brightness > 0:
                        dim_by = int(action.actionValue)  # action.actionValue contains brightness decrease value
                        new_brightness = dev.brightness - dim_by
                        if new_brightness < 0:
                            new_brightness = 0

                            topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/{topic_coomand}/set"  # e.g. "homie/home-1/study-socket-spare/dim/set"
                            topic_payload = f"{new_brightness}"
                            self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                            topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/onoff/set"  # e.g. "homie/home-1/study-socket-spare/onoff/set"
                            topic_payload = "false"
                            self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                            self.logger.info(f"sending \" {topic_coomand} to off\" to  \"{dev.name}\"")

                        else:
                            dim_by_ui = f"{dim_by}%"
                            new_brightness_ui = f"{new_brightness}%"

                            topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/{topic_coomand}/set"  # e.g. "homie/home-1/study-socket-spare/dim/set"
                            topic_payload = f"{new_brightness}"
                            self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                            self.logger.info(f"sending \"{negative} by {dim_by_ui} to {new_brightness_ui}\" to \"{dev.name}\"")

                    else:
                        self.logger.info(f"Ignoring \"{topic_coomand}\" request for '{dev.name}'' as device is already Off")

                elif dev.deviceTypeId == "valveSecondary":
                    if dev.onState and dev.brightness > 0:
                        close_by = int(action.actionValue)  # action.actionValue contains brightness decrease value
                        new_valve_level = dev.brightness - close_by
                        if new_valve_level < 0:
                            new_valve_level = 0

                            topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/dim/set"  # e.g. "homie/home-1/study-socket-spare/dim/set"
                            topic_payload = f"{new_valve_level}"
                            self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                            topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/onoff/set"  # e.g. "homie/home-1/study-socket-spare/onoff/set"
                            topic_payload = "false"
                            self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                            self.logger.info(f"sending \"{dev.name}\"' close valve")

                        else:
                            dim_by_ui = f"{close_by}%"
                            new_brightness_ui = f"{new_valve_level}%"

                            topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/dim/set"  # e.g. "homie/home-1/study-socket-spare/dim/set"
                            topic_payload = f"{new_valve_level}"
                            self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                            self.logger.info(f"sending \"close valve by {new_brightness_ui} to {dev.name}\" to \"{dev.name}\"")

                    else:
                        self.logger.info(f"Ignoring \"close valve\" request for '{dev.name}'' as valve is already closed")

            # ##### SET COLOR LEVELS ######
            elif action.deviceAction == indigo.kDeviceAction.SetColorLevels:
                self.process_set_color_levels(action, dev, hubitat_hub_name, mqtt_filter_key)

            else:
                self.logger.warning(f"Unhandled \"actionControlDevice\" action \"{action.deviceAction}\" for \"{dev.name}\"")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def actionControlDevice_indigoExport(self, action, dev):
        try:

            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                self.logger.info(f"Starting Publishing Indigo Export devices for Hubitat discovery")
                dev.updateStateOnServer(key="onOffState", value=True, uiValue="publishing . . .")
                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                self.process_export_indigo_devices(dev)
                indigo.device.turnOff(dev.id, delay=2)
            elif action.deviceAction == indigo.kDeviceAction.TurnOff:
                dev.updateStateOnServer(key="onOffState", value=False, uiValue="idle")
                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                self.logger.info(f"Completed Publishing Indigo Export devices for Hubitat discovery")
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def actionControlThermostat(self, action, dev):
        try:
            if not dev.enabled:
                return

            dev_props = dev.pluginProps
            if "hubitatDevice" in dev_props:
                hubitat_device_name = dev_props["hubitatDevice"]
                hubitat_hub_name = dev_props.get("hubitatHubName", "")
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            elif "linkedPrimaryIndigoDeviceId" in dev_props:
                hubitat_device_name = dev_props["associatedHubitatDevice"]
                linked_indigo_device_id = int(dev_props.get("linkedPrimaryIndigoDeviceId", 0))
                linked_indigo_dev = indigo.devices[linked_indigo_device_id]
                linked_dev_props = linked_indigo_dev.pluginProps
                hubitat_hub_name = linked_dev_props.get("hubitatHubName", "")
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            else:
                self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as unable to resolve Hubitat Hub device.")
                return

            if hubitat_hub_dev_id > 0:
                mqtt_connected = False
                for mqtt_broker_device_id in self.globals[HE_HUBS][hubitat_hub_name][MQTT_BROKERS]:
                    if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                        mqtt_connected = True
                        break
                if not mqtt_connected:
                    self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as Hubitat Hub device '{hubitat_hub_name}' is not initialised. Is MQTT running?")
                    return

                mqtt_filter_key = f"{hubitat_hub_name.lower()}|{hubitat_device_name.lower()}"

                if (action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint or
                        action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint or
                        action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint):

                    heating_setpoint = float(dev.states["setpointHeat"])
                    if action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
                        heating_setpoint = heating_setpoint + float(action.actionValue)
                        thermostat_action_ui = "increase"
                    elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
                        heating_setpoint = heating_setpoint - float(action.actionValue)
                        thermostat_action_ui = "decrease"
                    else:
                        # action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint
                        heating_setpoint = float(action.actionValue)
                        thermostat_action_ui = "set"
                    topic_payload = f"{heating_setpoint}"
                    topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/heating-setpoint/set"  # e.g. "homie/home-1/study-socket-spare/heating-setpoint/set"
                    self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                    self.logger.info(f"sent {dev.name} \"{thermostat_action_ui} setpoint\" to {heating_setpoint}")

                elif action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
                    if action.actionMode == indigo.kHvacMode.Off:
                        topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/onoff/set"  # e.g. "homie/home-1/study-test-trv/onoff/set"
                        topic_payload = "false"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                        self.logger.info(f"sending \"set hvac mode to Switched Off\" to \"{dev.name}\"")
                    elif action.actionMode in (indigo.kHvacMode.HeatCool, indigo.kHvacMode.Heat, indigo.kHvacMode.Cool):
                        if action.actionMode == indigo.kHvacMode.HeatCool:
                            topic_payload = "auto"
                        elif action.actionMode == indigo.kHvacMode.Heat:
                            topic_payload = "heat"
                        elif action.actionMode == indigo.kHvacMode.Cool:
                            topic_payload = "cool"
                        else:
                            return
                        topic_payload_ui = topic_payload
                        if topic_payload == "cool":
                            topic_payload_ui = "eco"

                        topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/mode/set"  # e.g. "homie/home-1/study-test-trv/mode/set"
                        self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)

                        self.logger.info(f"sending \"set hvac mode to {topic_payload_ui}\" to \"{dev.name}\"")

                else:
                    self.logger.warning(f"Action '{action.thermostatAction}' on device '{dev.name} is not supported by the plugin.")
                    return

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def actionControlUniversal(self, action, dev):
        try:
            if not dev.enabled:
                return

            if dev.deviceTypeId == "tasmotaOutlet":
                tasmota_key = dev.pluginProps["tasmotaDevice"]
                if action.deviceAction == indigo.kUniversalAction.EnergyUpdate:
                    topic = f"cmnd/tasmota_{tasmota_key}/Status"  # e.g. "cmnd/tasmota_6E641A/Status"
                    topic_payload = "8"  # Show power usage
                    self.publish_tasmota_topic(tasmota_key, topic, topic_payload)
                elif action.deviceAction == indigo.kUniversalAction.RequestStatus:
                    topic = f"cmnd/tasmota_{tasmota_key}/Power"  # e.g. "cmnd/tasmota_6E641A/Power"
                    topic_payload = ""  # No payload returns status
                    self.publish_tasmota_topic(tasmota_key, topic, topic_payload)
                elif action.deviceAction == indigo.kUniversalAction.EnergyReset:
                    topic = f"cmnd/tasmota_{tasmota_key}/EnergyReset"  # e.g. "cmnd/tasmota_6E641A/EnergyReset"
                    topic_payload = "0"  # Zero value
                    for i in range(1, 4):
                        topic_updated = f"{topic}{i}"  # Modifies e.g. "cmnd/tasmota_6E641A/EnergyReset" > "cmnd/tasmota_6E641A/EnergyReset1" etc
                        self.publish_tasmota_topic(tasmota_key, topic_updated, topic_payload)
                    topic = f"cmnd/tasmota_{tasmota_key}/Status"  # e.g. "cmnd/tasmota_6E641A/Status"
                    topic_payload = "8"  # Show power usage
                    self.publish_tasmota_topic(tasmota_key, topic, topic_payload)
                return

            dev_props = dev.pluginProps
            if "hubitatDevice" in dev_props:
                hubitat_device_name = dev_props["hubitatDevice"]
                hubitat_hub_name = dev_props.get("hubitatHubName", "")
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            elif "linkedPrimaryIndigoDeviceId" in dev_props:
                hubitat_device_name = dev_props["associatedHubitatDevice"]
                linked_indigo_device_id = int(dev_props.get("linkedPrimaryIndigoDeviceId", 0))
                linked_indigo_dev = indigo.devices[linked_indigo_device_id]
                linked_dev_props = linked_indigo_dev.pluginProps
                hubitat_hub_name = linked_dev_props.get("hubitatHubName", "")
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            else:
                self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as unable to resolve Hubitat Hub device.")
                return

            if hubitat_hub_dev_id > 0:
                mqtt_connected = False
                for mqtt_broker_device_id in self.globals[HE_HUBS][hubitat_hub_name][MQTT_BROKERS]:
                    if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                        mqtt_connected = True
                        break
                if not mqtt_connected:
                    self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as Hubitat Hub device '{hubitat_hub_name}' is not initialised. Is MQTT running?")
                    return

            mqtt_filter_key = f"{hubitat_hub_name.lower()}|{hubitat_device_name.lower()}"

            if action.deviceAction == indigo.kUniversalAction.RequestStatus:
                topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/refresh/set"  # e.g. "homie/home-1/study-socket-spare/refresh/set"
                topic_payload = "true"
                self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                return

            self.logger.warning(f"Action '{action.deviceAction}' on device '{dev.name} is not supported by the plugin.")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def closedDeviceConfigUi(self, values_dict=None, user_cancelled=False, type_id="", dev_id=0):
        """
        Indigo method invoked after device configuration dialog is closed.

        -----
        :param values_dict:
        :param user_cancelled:
        :param type_id:
        :param dev_id:
        :return:
        """

        dev = indigo.devices[int(dev_id)]  # dev is not currently used.

        try:
            if user_cancelled:
                self.logger.threaddebug(f"'closedDeviceConfigUi' called with userCancelled = {str(user_cancelled)}")
                return
            if type_id == "mqttBroker":
                self.closedDeviceConfigUiMqttBroker(values_dict, user_cancelled, type_id, dev_id)

            if type_id == "indigoExport":
                self.closedDeviceConfigUiExport(values_dict, user_cancelled, type_id, dev_id)
            elif type_id == "button":
                pass
            elif type_id == "blind":
                pass
            elif type_id == "contactSensor":
                pass
            elif type_id == "dimmer":
                pass
            elif type_id == "humidity":
                pass
            elif type_id == "illuminance":
                pass
            elif type_id == "motionSensor":
                pass
            elif type_id == "multiSensor":
                pass
            elif type_id == "outlet":
                pass
            elif type_id == "tasmotaOutlet":
                tasmota_key = values_dict.get("tasmotaDevice", "-NONE-")
                if tasmota_key != "-NONE-":
                    self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS][tasmota_key] = dev.id
            elif type_id == "temperatureSensor":
                pass
            elif type_id == "thermostat":
                pass
            elif type_id == "accelerationSensorSecondary":
                pass
            elif type_id == "hsmSensorSecondary":
                pass
            elif type_id == "humiditySensorSecondary":
                pass
            elif type_id == "illuminanceSensorSecondary":
                pass
            elif type_id == "motionSensorSecondary":
                pass
            elif type_id == "presenceSensorSecondary":
                pass
            elif type_id == "pressureSensorSecondary":
                pass
            elif type_id == "temperatureSensorSecondary":
                pass
            elif type_id == "valveSecondary":
                pass
            elif type_id == "voltageSensorSecondary":
                pass

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
                       
    def closedDeviceConfigUiMqttBroker(self, values_dict, user_cancelled, type_id, dev_id):
        try:
            with self.globals[LOCK_MQTT]:
                if dev_id not in self.globals[MQTT]:
                    self.globals[MQTT][dev_id] = dict()

            self.globals[MQTT][dev_id][MQTT_CLIENT_PREFIX] = values_dict.get("mqttClientPrefix", "indigo_mac")
            self.globals[MQTT][dev_id][MQTT_CLIENT_ID] = f"{self.globals[MQTT][dev_id][MQTT_CLIENT_PREFIX]}-D{dev_id}"
            self.globals[MQTT][dev_id][MQTT_IP] = str(values_dict.get("mqtt_broker_ip", ""))
            self.globals[MQTT][dev_id][MQTT_PORT] = int(values_dict.get("mqtt_broker_port", 0))
            self.globals[MQTT][dev_id][MQTT_USERNAME] = values_dict.get("mqtt_username", "")
            self.globals[MQTT][dev_id][MQTT_PASSWORD] = values_dict.get("mqtt_password", "")
            self.globals[MQTT][dev_id][MQTT_ENCRYPTION_KEY] = values_dict.get("mqtt_password_encryption_key", "").encode('utf-8')
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def closedDeviceConfigUiExport(self, values_dict=None, user_cancelled=False, type_id="", export_dev_id=0):
        try:
            self.globals[EXPORT][ENABLED] = {}  # Clear out enabled devices

            for key, value in self.globals[EXPORT][SELECTED].items():  # Copy Selected devices to Enabled
                self.globals[EXPORT][ENABLED][key] = value

            # export_dev = indigo.devices[export_dev_id]
            for key, value in self.globals[EXPORT][ENABLED].items():
                dev_id = key
                dev = indigo.devices[dev_id]
                dev_props = dev.pluginProps
                dev_props["export_enabled"] = True
                dev_props["export_root_topic_id"] = values_dict.get("export_root_topic_id", "indigo-1").lower()
                dev.replacePluginPropsOnServer(dev_props)

            # Now scan for all Indigo devices that aren't owned by this plugin and aren't enabled for export
            #  and make sure that export is either not present, present and not enabled
            #  and if it is enabled, disable it.
            for dev_to_check in indigo.devices:
                if dev_to_check.pluginId != "com.autologplugin.indigoplugin.hubitat":
                    if dev_to_check.id not in self.globals[EXPORT][ENABLED]:
                        if "discovery_enabled" in dev_to_check.pluginProps or "export_enabled" in dev_to_check.pluginProps:  # Old version used "discovery_enabled" which is now "export_enabled"
                            dev_to_check.replacePluginPropsOnServer(None)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def closedPrefsConfigUi(self, values_dict=None, user_cancelled=False):
        try:
            if user_cancelled:
                return

            self.globals[COLOR_DEBUG] = bool(values_dict.get("colorDebug", False))

            # Get required Event Log and Plugin Log logging levels
            plugin_log_level = int(values_dict.get("pluginLogLevel", K_LOG_LEVEL_INFO))
            event_log_level = int(values_dict.get("eventLogLevel", K_LOG_LEVEL_INFO))

            # Ensure following logging level messages are output
            self.indigo_log_handler.setLevel(K_LOG_LEVEL_INFO)
            self.plugin_file_handler.setLevel(K_LOG_LEVEL_INFO)

            # Output required logging levels and TP Message Monitoring requirement to logs
            self.logger.info(f"Logging to Indigo Event Log at the '{K_LOG_LEVEL_TRANSLATION[event_log_level]}' level")
            self.logger.info(f"Logging to Plugin Event Log at the '{K_LOG_LEVEL_TRANSLATION[plugin_log_level]}' level")

            # Now set required logging levels
            self.indigo_log_handler.setLevel(event_log_level)
            self.plugin_file_handler.setLevel(plugin_log_level)

            # Set Hubitat MQTT Message Filter
            self.globals[HE_MQTT_FILTERS] = list()  # Initialise Hubitat MQTT filter dictionary
            mqtt_hubitat_message_filter = values_dict.get("mqttHubitatDeviceMessageFilter", ["-0-|||-- Don't Log Any Devices --"])
            log_message = "MQTT Topic Filtering active for the following Hubitat device(s):"  # Not used if no logging required
            filtering_required = False

            spaces = " " * 35  # used to pad log messages

            if len(mqtt_hubitat_message_filter) == 0:
                self.globals[HE_MQTT_FILTERS] = ["-0-"]
            else:
                for entry in mqtt_hubitat_message_filter:
                    hubitat_hub_name, hubitat_device_name = entry.split("|||")
                    if hubitat_hub_name == "-0-":  # Ignore '-- Don't Log Any Devices --'
                        self.globals[HE_MQTT_FILTERS] = ["-0-"]
                        break
                    elif hubitat_hub_name == "-1-":  # Ignore '-- Log All Devices --'
                        self.globals[HE_MQTT_FILTERS] = ["-1-"]
                        log_message = f"{log_message}\n{spaces}All Hubitat Devices"
                        filtering_required = True
                        break
                    else:
                        hubitat_hub_and_device_name_ui = f"{hubitat_hub_name} | {hubitat_device_name}"
                        self.globals[HE_MQTT_FILTERS].append(f"{hubitat_hub_name.lower()}|{hubitat_device_name.lower()}")
                        spaces = " " * 24
                        log_message = f"{log_message}\n{spaces}Hubitat Device: '{hubitat_hub_and_device_name_ui}'"
                        filtering_required = True

            if filtering_required:
                self.logger.warning(f"{log_message}\n")

            # Set Export MQTT Message Filter
            self.globals[EXPORT_FILTERS] = list()  # Initialise Export MQTT filter dictionary
            mqtt_export_message_filter = values_dict.get("mqttExportDeviceMessageFilter", [0])
            log_message = "MQTT Topic Filtering active for the following Exported Indigo device(s):"  # Not used if no logging required
            filtering_required = False

            spaces = " " * 35  # used to pad log messages

            if len(mqtt_export_message_filter) == 0:
                self.globals[EXPORT_FILTERS] = ["dev-none"]
            else:
                for entry_dev_id in mqtt_export_message_filter:
                    entry_dev_id = int(entry_dev_id)
                    if entry_dev_id == 0:  # Ignore '-- Don't Log Any Devices --'
                        self.globals[EXPORT_FILTERS] = ["dev-none"]
                        break
                    elif entry_dev_id == 1:  # Ignore '-- Log All Devices --'
                        self.globals[EXPORT_FILTERS] = ["dev-all"]
                        log_message = f"{log_message}\n{spaces}All Exported Indigo Devices"
                        filtering_required = True
                        break
                    else:
                        pass
                        export_device_name_ui = f"{indigo.devices[int(entry_dev_id)].name}"
                        self.globals[EXPORT_FILTERS].append(f"dev-{entry_dev_id}")
                        spaces = " " * 24
                        log_message = f"{log_message}\n{spaces}Exported Indigo Device: '{export_device_name_ui}'"
                        filtering_required = True

            if filtering_required:
                self.logger.warning(f"{log_message}\n")

            # Set Tasmota MQTT Message Filter
            self.globals[TASMOTA_MQTT_FILTERS] = list()  # Initialise Tasmota MQTT filter dictionary
            mqtt_tasmota_message_filter = values_dict.get("mqttTasmotaMessageFilter", ["-0-|||-- Don't Log Any Devices --"])
            log_message = "MQTT Topic Filtering active for the following Tasmota device(s):"  # Not used if no logging required
            filtering_required = False

            if len(mqtt_tasmota_message_filter) == 0:
                self.globals[TASMOTA_MQTT_FILTERS] = ["-0-"]
            else:
                for entry in mqtt_tasmota_message_filter:
                    entry_key, entry_name = entry.split("|||")
                    if entry_key == "-0-":  # Ignore '-- Don't Log Any Devices --'
                        self.globals[TASMOTA_MQTT_FILTERS] = ["-0-"]
                        break
                    elif entry_key == "-1-":  # Ignore '-- Log All Devices --'
                        self.globals[TASMOTA_MQTT_FILTERS] = ["-1-"]
                        log_message = f"{log_message}\n{spaces}All Tasmota Devices"
                        filtering_required = True
                        break
                    else:
                        self.globals[TASMOTA_MQTT_FILTERS].append(entry_key)
                        log_message = f"{log_message}\n{spaces}Tasmota Device: '{entry_name}'"
                        filtering_required = True

            if filtering_required:
                self.logger.warning(f"{log_message}\n")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
            return True

    # Undocumented API - runs after all devices have been started.  Actually, it's the super._postStartup() call that starts the devices.
    def _postStartup(self):
        super(Plugin, self)._postStartup()  # noqa

        for dev in indigo.devices.iter("self"):
            if dev.deviceTypeId == "indigoExport":
                auto_export = bool(dev.pluginProps.get("autoExport", True))
                if auto_export:
                    indigo.device.turnOn(dev.id, delay=10)  # Allow MQTT to Connect  # TODO: Check if MQTT Connected and invoke this sooner

    def deviceStartComm(self, dev):
        try:
            dev.stateListOrDisplayStateIdChanged()  # Ensure that latest devices.xml is being used

            if not dev.enabled:
                return

            if dev.deviceTypeId == "mqttBroker":  # Only process if Hubitat Export
                self.deviceStartComm_mqttBroker(dev)

            elif dev.deviceTypeId == "indigoExport":  # Only process if Hubitat Export
                self.deviceStartComm_indigoExport(dev)

            elif dev.deviceTypeId == "hubitatElevationHub":  # Only process if Hubitat Hub
                self.deviceStartComm_hubitatElevationHub(dev)

            elif dev.deviceTypeId == "tasmotaOutlet":  # Only process if Tasmota Outlet
                self.deviceStartComm_tasmotaOutlet(dev)

            else:
                # Assume Hubitat Elevation device
                self.deviceStartComm_HubitatElevationDevice(dev)

            self.logger.info(f"Device '{dev.name}' Started")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStartComm_mqttBroker(self, dev):
        try:
            # Create the thread to connect to the MQTT Broker
            dev_id = dev.id
            with self.globals[LOCK_MQTT]:
                if dev_id not in self.globals[MQTT]:
                    self.globals[MQTT][dev_id] = dict()

            self.globals[MQTT][dev_id][MQTT_CLIENT_PREFIX] = dev.pluginProps.get("mqttClientPrefix", "indigo_mac")
            self.globals[MQTT][dev_id][MQTT_CLIENT_ID] = f"{self.globals[MQTT][dev_id][MQTT_CLIENT_PREFIX]}-D{dev.id}"
            self.globals[MQTT][dev_id][MQTT_IP] = str(dev.pluginProps.get("mqtt_broker_ip", ""))
            self.globals[MQTT][dev_id][MQTT_PORT] = int(dev.pluginProps.get("mqtt_broker_port", 0))
            self.globals[MQTT][dev_id][MQTT_USERNAME] = dev.pluginProps.get("mqtt_username", "")
            self.globals[MQTT][dev_id][MQTT_PASSWORD] = dev.pluginProps.get("mqtt_password", "")
            self.globals[MQTT][dev_id][MQTT_ENCRYPTION_KEY] = dev.pluginProps.get("mqtt_password_encryption_key", "").encode('utf-8')

            self.globals[MQTT][dev_id][MQTT_EVENT] = threading.Event()
            self.globals[MQTT][dev_id][MQTT_THREAD] = ThreadMqttHandler(self.globals, self.globals[MQTT][dev_id][MQTT_EVENT], dev_id)
            self.globals[MQTT][dev_id][MQTT_THREAD].start()

            pass
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStartComm_hubitatElevationHub(self, dev):
        try:
            dev.updateStateOnServer(key='status', value="disconnected")
            dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
            dev.updateStateOnServer(key='lastTopic', value="")
            dev.updateStateOnServer(key='lastPayload', value="")

            hub_props = dev.ownerProps
            hubitat_hub_name = hub_props["hub_name"]
            if hubitat_hub_name not in self.globals[HE_HUBS]:
                self.globals[HE_HUBS][hubitat_hub_name] = dict()
            if HE_MQTT_FILTER_DEVICES not in self.globals[HE_HUBS][hubitat_hub_name]:
                self.globals[HE_HUBS][hubitat_hub_name][HE_MQTT_FILTER_DEVICES] = list()
            self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID] = dev.id
            if HE_DEVICES not in self.globals[HE_HUBS][hubitat_hub_name]:
                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES] = dict()

            self.globals[HE_HUBS][hubitat_hub_name][MQTT_BROKERS] = list()
            for mqtt_broker in dev.pluginProps.get("mqttBrokers", list()):
                self.globals[HE_HUBS][hubitat_hub_name][MQTT_BROKERS].append(int(mqtt_broker))

            self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_EVENT] = threading.Event()
            self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_THREAD] = ThreadHubHandler(self.globals, dev.id, self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_EVENT])
            self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_THREAD].start()

            self.process_hsm_secondary_device(dev)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStartComm_indigoExport(self, dev):
        try:

            self.globals[EXPORT][MQTT_BROKERS] = list()
            for mqtt_broker in dev.pluginProps.get("mqttBrokers", list()):
                self.globals[EXPORT][MQTT_BROKERS].append(int(mqtt_broker))

            dev_props = dev.pluginProps
            initiate_export = dev_props.get("initiateExport", False)
            if initiate_export:
                self.logger.info(f"Device '{dev.name}' Starting . . .")
                self.process_export_indigo_devices(dev)
                dev_props["initiateExport"] = False  # Only run if set by save of device config
                dev.replacePluginPropsOnServer(dev_props)

            # self.logger.info(f"Device '{dev.name}' Started")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_export_indigo_devices(self, dev):
        try:
            self.logger.info(f"Publishing Indigo Export devices commencing for '{dev.name}' . . .")

            plugin_props = dev.pluginProps

            indigo_root_topic_id = plugin_props.get("export_root_topic_id", "indigo-1")
            indigo_root_name = plugin_props.get("indigo_name", EXPORT_ROOT_TOPIC_DEFAULT_NAME)
            if indigo_root_name == "":
                indigo_root_name = EXPORT_ROOT_TOPIC_DEFAULT_NAME

            self.globals[EXPORT][EXPORT_ROOT_TOPIC_ID] = indigo_root_topic_id  # used in mqttHandler.py to identify export related topics

            topic = f"homie/{indigo_root_topic_id}/$state"
            payload = "init"
            self. publish_export_topic("dev-root", None, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/$fw/indigo"
            payload = f"{indigo.server.version}"
            self.publish_export_topic("dev-root", None, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/$fw/plugin"
            payload = f"{self.globals[K_PLUGIN_INFO][K_PLUGIN_DISPLAY_NAME]}"
            self.publish_export_topic("dev-root", None, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/$fw/version"
            payload = f"{self.globals[K_PLUGIN_INFO][K_PLUGIN_VERSION]}"
            self.publish_export_topic("dev-root", None, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/$name"
            payload = indigo_root_name
            self. publish_export_topic("dev-root", None, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/$extensions"
            payload = "indigo"
            self. publish_export_topic("dev-root", None, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/$localip"
            payload = self.globals[LOCALIP]
            self. publish_export_topic("dev-root", None, topic, payload)

            nodes = ""
            for key, value in self.globals[EXPORT][ENABLED].items():
                node_id = f"dev-{key}"
                if nodes == "":
                    nodes = nodes + f"{node_id}"
                else:
                    nodes = nodes + f",{node_id}"

            topic = f"homie/{indigo_root_topic_id}/$nodes"
            payload = nodes
            self.publish_export_topic("dev-root", None, topic, payload)

            for key, value in self.globals[EXPORT][ENABLED].items():
                export_dev = indigo.devices[key]
                device_key = f"dev-{export_dev.id}"

                topic = f"homie/{indigo_root_topic_id}/{device_key}"
                payload = export_dev.name
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/$name"
                payload = export_dev.name
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                if isinstance(export_dev, indigo.DimmerDevice):
                    self.process_export_indigo_devices_dimmer(export_dev, indigo_root_topic_id, device_key)
                elif  isinstance(export_dev, indigo.RelayDevice):
                    self.process_export_indigo_devices_relay(export_dev, indigo_root_topic_id, device_key)
                elif  isinstance(export_dev, indigo.SensorDevice):
                    self.process_export_indigo_devices_sensor(export_dev, indigo_root_topic_id, device_key)

            topic = f"homie/{indigo_root_topic_id}/$state"
            payload = "ready"
            self. publish_export_topic("dev-root", None, topic, payload)

            self.logger.info(f"Publishing Indigo Export devices complete")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_export_indigo_devices_dimmer(self, export_dev, indigo_root_topic_id, device_key):
        try:
            supports_color = True if getattr(export_dev, "supportsColor", False) else False
            supports_rgb = True if getattr(export_dev, "supportsRGB", False) else False
            supports_white = True if getattr(export_dev, "supportsWhite", False) else False
            supports_white_temperature = True if getattr(export_dev, "supportsWhiteTemperature", False) else False

            # Hubitat Types:
            #  light
            #  RGBT light
            #  RGB light
            #  CT light

            battery_level = self.process_export_indigo_devices_property_battery(indigo_root_topic_id, device_key, export_dev)

            payload = "onoff,dim"
            topic = f"homie/{indigo_root_topic_id}/{device_key}/$properties"
            if battery_level is not None:
                payload = f"{payload},battery"
            if supports_color:
                payload = f"{payload},color-mode"
            if supports_rgb:
                payload = f"{payload},color"
            if supports_white and supports_white_temperature:
                payload = f"{payload},color-temperature"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/$type"
            payload = "light"  # Default
            if supports_color:
                if supports_rgb:
                    payload = "RGB light"
                    if supports_white:
                        payload = "RGBW light"
                elif supports_white and supports_white_temperature:
                    payload = "CT light"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            # property Attributes: dim
            node_property = "dim"

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}"
            payload = f"{export_dev.brightness}"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$datatype"
            payload = "integer"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$format"
            payload = "0:100"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$unit"
            payload = "%"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$name"
            payload = export_dev.name
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$retained"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$settable"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            # property Attributes: onoff
            node_property = "onoff"

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}"
            payload = f"{bool(export_dev.onState)}".lower()
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$datatype"
            payload = "boolean"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$name"
            payload = export_dev.name
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$retained"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$settable"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            # if not (supports_color and supports_rgb) and not (supports_white and supports_white_temperature):
            #     return

            if not supports_color:
                return

            he_hue = None  # To suppress PyCharm Warning
            he_saturation = None  # To suppress PyCharm Warning
            he_value = None  # To suppress PyCharm Warning

            color_mode_enum_list = list()

            if supports_rgb:
                color_mode = "HSV"  # HSV is Hubitat Default
                color_mode_enum_list.append("RGB,HSV")
                red_level = float(export_dev.redLevel)
                green_level = float(export_dev.greenLevel)
                blue_level = float(export_dev.blueLevel)

                # Convert Indigo values for rGB (0-100) to colorSys values (0.0-1.0)
                red = float(red_level / 100.0)  # e.g. 100.0/100.0 = 1.0
                green = float(green_level / 100.0)  # e.g. 70.0/100.0 = 0.7
                blue = float(blue_level / 100.0)  # e.g. 40.0/100.0 = 0.4

                hsv_hue, hsv_saturation, hsv_value = colorsys.rgb_to_hsv(red, green, blue)

                # Colorsys values for HSV are (0.0-1.0). Convert to to H (0-360), S (0 - 100) and V (0 - 100)
                he_hue = int(hsv_hue * 360.0)
                he_saturation = int(hsv_saturation * 100.0)
                he_value = int(hsv_value * 100.0)

            else:
                if supports_white and supports_white_temperature:
                    color_mode = "CT"  # Colour Temperature
                    color_mode_enum_list.append("CT")
                else:
                    # Plugin does not currently support white lights without colour temperature control
                    return

            if supports_rgb and supports_white and supports_white_temperature:
                color_mode_enum_list.append("CT")
                if red_level == green_level == blue_level:  # noqa [Not referenced before assignment]
                    color_mode = "CT"

            # property Attributes: color-mode
            node_property = "color-mode"

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}"
            payload = color_mode
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$datatype"
            payload = "enum"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$format"
            color_mode_enum_set = set(color_mode_enum_list)  # Remove duplicates
            color_mode_enum = ",".join(color_mode_enum_set)
            payload = color_mode_enum
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$name"
            payload = export_dev.name
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$retained"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$settable"
            payload = "false"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            self.globals[EXPORT][ENABLED][export_dev.id][STORED_COLOR_MODE] = color_mode

            if "HSV" in color_mode_enum_list:
            # if color_mode == "HSV":

                # property Attributes: color
                node_property = "color"

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}"
                # red_255 = f"{int((red_level * 255.0) / 100.0)}"
                # green_255 = f"{int((green_level * 255.0) / 100.0)}"
                # blue_255 = f"{int((blue_level * 255.0) / 100.0)}"
                payload = f"{he_hue},{he_saturation},{he_value}"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$datatype"
                payload = "color"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$format"
                payload = "hsv"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$name"
                payload = export_dev.name
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$retained"
                payload = "true"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$settable"
                payload = "true"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

            if "CT" in color_mode_enum_list:
            # if color_mode == "CT":

                # property Attributes: color-temperature
                node_property = "color-temperature"

                # print(int(export_dev.ownerProps.get("WhiteTemperatureMax", 8000)))

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}"
                white_temperature = export_dev.whiteTemperature
                payload = f"{white_temperature}"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$datatype"
                payload = "integer"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$format"
                White_temperature_min = int(export_dev.ownerProps.get("WhiteTemperatureMin", 2500))
                White_temperature_max = int(export_dev.ownerProps.get("WhiteTemperatureMax", 8000))
                payload = f"{White_temperature_min}:{White_temperature_max}"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$name"
                payload = export_dev.name
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$unit"
                payload = "Kelvin"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                # topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/temp"
                # payload = f"{white_temperature}"
                # self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/mireds"
                mireds = int(round(1000000.0 / float(white_temperature)))
                payload = f"{mireds}"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$retained"
                payload = "true"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

                topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$settable"
                payload = "true"
                self.publish_export_topic(device_key, export_dev.name, topic, payload)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_export_indigo_devices_relay(self, export_dev, indigo_root_topic_id, device_key):
        try:
            battery_level = self.process_export_indigo_devices_property_battery(indigo_root_topic_id, device_key, export_dev)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/$properties"
            if battery_level is not None:
                payload = "onoff,battery"
            else:
                payload = "onoff"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/$type"
            payload = "switch"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            # property Attributes: onoff
            node_property = "onoff"

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}"
            payload = f"{bool(export_dev.onState)}".lower()
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$datatype"
            payload = "boolean"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$name"
            payload = export_dev.name
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$retained"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$settable"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_export_indigo_devices_sensor(self, export_dev, indigo_root_topic_id, device_key):
        try:
            # TODO: Need to figure out sensor type

            # root settings: $properties & $type

            battery_level = self.process_export_indigo_devices_property_battery(indigo_root_topic_id, device_key, export_dev)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/$properties"
            if battery_level is not None:
                payload = "temperature,battery"
            else:
                payload = "temperature"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/$type"
            payload = "sensor"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            # property Attributes: temperature
            node_property = "temperature"

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}"
            payload = f"{export_dev.sensorValue}"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$datatype"
            payload = "float"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$unit"
            payload = "ºC"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$name"
            payload = export_dev.name
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$retained"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$settable"
            payload = "false"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_export_indigo_devices_property_battery(self, indigo_root_topic_id, device_key, export_dev):
        try:
            battery_level = None
            try:
                battery_level = int(export_dev.batteryLevel)
            except Exception:  # noqa
                return battery_level

            if battery_level is None:
                return battery_level

            # property Attributes: battery
            node_property = "battery"

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}"
            payload = f"{battery_level}"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$datatype"
            payload = "integer"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$unit"
            payload = "%"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$name"
            payload = export_dev.name
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$retained"
            payload = "true"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            topic = f"homie/{indigo_root_topic_id}/{device_key}/{node_property}/$settable"
            payload = "false"
            self.publish_export_topic(device_key, export_dev.name, topic, payload)

            return battery_level

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStartComm_HubitatElevationDevice(self, dev):
        try:
            if "[UNGROUPED @" in dev.name:
                self.logger.warning(f"Secondary Device '{dev.name}' ungrouped from a Primary Device - please delete it!")
                return

            # Make Sure that device address is correct and also on related sub-models
            dev_props = dev.pluginProps
            hubitat_device_name = dev_props.get("hubitatDevice", "")  # Only present in a primary device
            if hubitat_device_name != "":
                if dev.address != hubitat_device_name:
                    self.logger.warning(f"Indigo Primary Device {dev.name} address updated from '{dev.address} to '{hubitat_device_name}")
                    dev_props["address"] = hubitat_device_name
                    dev.replacePluginPropsOnServer(dev_props)

                self.optionally_set_indigo_2021_device_sub_type(dev)

            else:
                member_of_device_group = bool(dev_props.get("member_of_device_group", False))  # Only true in a secondary device
                if member_of_device_group:
                    dev_id_list = indigo.device.getGroupList(dev.id)
                    if len(dev_id_list) > 1:
                        for linked_dev_id in dev_id_list:
                            if linked_dev_id != dev.id:
                                linked_dev = indigo.devices[linked_dev_id]
                                linked_props = linked_dev.pluginProps
                                hubitat_device_name = linked_props.get("hubitatDevice", "")
                                if hubitat_device_name != "":
                                    if dev.address != hubitat_device_name:
                                        self.logger.warning(f"Indigo Sub-Model Device {dev.name} address updated from '{dev.address} to '{hubitat_device_name}'")
                                        dev_props["address"] = hubitat_device_name
                                        dev.replacePluginPropsOnServer(dev_props)

                                    self.optionally_set_indigo_2021_device_sub_type(dev)

            if "hubitatPropertiesInitialised" not in dev_props or not dev_props["hubitatPropertiesInitialised"]:
                self.logger.warning(f"Hubitat Device {dev.name} has not been initialised - Edit and Save device Settings for device.")
                return

            hubitat_hub_name = dev_props.get("hubitatHubName", "")
            try:
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            except Exception:
                hubitat_hub_dev_id = 0

            if hubitat_hub_dev_id <= 0:
                self.logger.warning(f"No Hubitat Elevation Hub is associated with hubitat device '{dev.name}'")
                return

            # if hubitat_hub_name not in self.globals[HE_HUBS]:
            #     self.logger.warning(f"Hubitat Elevation Hub '{hubitat_hub_name}' associated with hubitat device '{dev.name}' is unknown or disabled")
            #     return

            self.process_sub_models(dev, hubitat_hub_name)  # Check if Sub-Model(s) required to be created and create as necessary

            dev_props = dev.pluginProps
            if "associatedHubitatDevice" in dev_props and dev_props.get("associatedHubitatDevice", "") != "":
                hubitat_device_name = dev_props["associatedHubitatDevice"]
            else:
                hubitat_device_name = dev_props["hubitatDevice"]

            if hubitat_device_name not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:
                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name] = dict()  # Hubitat device name
            with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                if HE_LINKED_INDIGO_DEVICES not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                    self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES] = dict()
                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES][dev.id] = dev.id
            if HE_PROPERTIES not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] = None
            if self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] is None:
                stored_hubitat_properties = dev_props.get("storedHubitatDeviceProperties", "")
                if stored_hubitat_properties != "":
                    self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] = stored_hubitat_properties

            if HE_DEVICE_DRIVER not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] = None

            # TODO: Consider setting image for UI depending on deviceTypeId?

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStartComm_tasmotaOutlet(self, dev):
        try:
            # Check if the Tasmota Thread Handler has been started and if not start it: On ethread handles all Tasmotas
            if TASMOTA_THREAD not in self.globals[TASMOTA]:
                self.globals[TASMOTA][TASMOTA_EVENT] = threading.Event()
                self.globals[TASMOTA][TASMOTA_THREAD] = ThreadTasmotaHandler(self.globals, dev.id, self.globals[TASMOTA][TASMOTA_EVENT])
                self.globals[TASMOTA][TASMOTA_THREAD].start()

            if float(indigo.server.apiVersion) >= 2.5:
                if dev.subType != indigo.kRelayDeviceSubType.Outlet:
                    dev.subType = indigo.kRelayDeviceSubType.Outlet
                    dev.replaceOnServer()

            dev_props = dev.ownerProps
            tasmota_key = dev_props.get("tasmotaDevice", "-SELECT-")
            if tasmota_key != "-SELECT-":
                if dev.address != tasmota_key:
                    # self.logger.warning(f"Indigo Tasmota Device {dev.name} address updated from '{dev.address}' to '{tasmota_key}")
                    dev_props["address"] = tasmota_key
                    dev.replacePluginPropsOnServer(dev_props)

            if tasmota_key not in self.globals[TASMOTA][TASMOTA_DEVICES]:
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key] = dict()
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_DISCOVERY_DETAILS] = False

            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] = dev.id
            self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS][tasmota_key] = dev.id

            # self.logger.error(f"Tasmota List = '{tasmota_key}', Dev ID = '{dev.id}', Dev Name = '{dev.name}':\n{self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]}")

            if not self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_DISCOVERY_DETAILS]:
                # Default Tasmota device internal store
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_POWER] = False
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE] = "n/a"
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_DEVICE_NAME] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_T] = ""

                # Update  Tasmota device internal store from Indigo device
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME] = dev.states["friendlyName"]
                # self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_DEVICE_NAME] = tasmota_dev.states["friendlyName"]
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC] = dev.states["macAddress"]
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL] = dev.states["model"]
                # self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_T] = tasmota_dev.states["friendlyName"]

                key_value_list = list()
                key_value_list.append({"key": "onOffState", "value": False})
                key_value_list.append({"key": "lwt", "value": "Offline"})
                dev.updateStatesOnServer(key_value_list)
                dev.setErrorStateOnServer("offline")
            else:
                key_value_list = list()
                key_value_list.append({"key": "friendlyName", "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME]})
                key_value_list.append({"key": "ipAddress", "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_IP_ADDRESS]})
                key_value_list.append({"key": "macAddress", "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC]})
                key_value_list.append({"key": "model", "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL]})
                dev.updateStatesOnServer(key_value_list)
                dev.setErrorStateOnServer("offline")

                props = dev.ownerProps
                firmware = props.get("version", "")
                if firmware != self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE]:
                    props["version"] = self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE]
                    dev.replacePluginPropsOnServer(props)

            if dev.address not in self.globals[TASMOTA][MQTT_BROKERS]:  # dev.address is the Tasmota Key e.g. 6C39A6
                self.globals[TASMOTA][MQTT_BROKERS][dev.address] = 0  # Defaulting the Indigo MQTT Broker Device Id to zero
            self.globals[TASMOTA][MQTT_BROKERS][dev.address] = int(dev.pluginProps.get("mqttBroker", 0))  # Pickup the select MQTT Broker Id from props
            mqtt_connected = False
            if self.globals[TASMOTA][MQTT_BROKERS][dev.address] != 0:
                mqtt_broker_device_id = self.globals[TASMOTA][MQTT_BROKERS][dev.address]
                if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                    mqtt_connected = True
            if mqtt_connected:
                topic = f"cmnd/tasmota_{tasmota_key}/Power"  # e.g. "cmnd/tasmota_6E641A/Power"
                topic_payload = ""  # No payload returns status
                self.publish_tasmota_topic(tasmota_key, topic, topic_payload)
                topic = f"cmnd/tasmota_{tasmota_key}/Status"  # e.g. "cmnd/tasmota_6E641A/Status"
                topic_payload = "8"  # Show power usage
                self.publish_tasmota_topic(tasmota_key, topic, topic_payload)
            else:
                self.globals[TASMOTA][TASMOTA_QUEUE][tasmota_key] = dev.id

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStopComm(self, dev):
        try:
            self.logger.info(f"Device '{dev.name}' Stopped")

            if dev.deviceTypeId == "mqttBroker":
                self.globals[MQTT][dev.id][MQTT_EVENT].set()  # Stop the MQTT Client

                return

            if dev.deviceTypeId == "indigoExport":
                dev.updateStateOnServer(key="onOffState", value=False, uiValue="idle")
                return

            if dev.deviceTypeId == "hubitatElevationHub":
                hub_props = dev.ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_EVENT].set()  # Stop the Hub handler Thread
                self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_THREAD].join(5.0)  # noqa [Expected type 'Iterable[str]', got 'float' instead] - Wait for up t0 5 seconds for it to end

                # Delete thread so that it can be recreated if Hubitat Elevation Hub devices is turned on again
                del self.globals[HE_HUBS][hubitat_hub_name][HE_HUB_THREAD]

                dev.updateStateOnServer(key='status', value="disconnected")
                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

                return

            elif dev.deviceTypeId == "tasmotaOutlet":
                return

            # As Hubitat device is being stopped - delete its id from internal Hubitat Devices table.

            dev_props = dev.pluginProps

            hubitat_hub_name = dev_props.get("hubitatHubName", "")
            try:
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            except Exception:
                hubitat_hub_dev_id = 0

            if hubitat_hub_dev_id <= 0:
                self.logger.debug(f"No Hubitat Elevation Hub is associated with hubitat device '{dev.name}'")
                return
            if hubitat_hub_dev_id not in indigo.devices:
                self.logger.debug(f"Hubitat Elevation Hub no longer associated with hubitat device '{dev.name}'")
                return
            hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
            hubitat_hub_name = hub_props["hub_name"]
            if hubitat_hub_name not in self.globals[HE_HUBS]:
                self.logger.debug(f"Hubitat Elevation Hub '{hubitat_hub_name}' associated with hubitat device '{dev.name}' is unknown or disabled")
                return

            dev_props = dev.pluginProps
            hubitat_device_name = dev_props.get("hubitatDevice", "")  # Allows for entry not being present in Sub-Models
            if hubitat_device_name in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    if HE_LINKED_INDIGO_DEVICES in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                        if dev.id in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                            del self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES][dev.id]

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceUpdated(self, origDev, newDev):
        try:
            if origDev.pluginId == "com.autologplugin.indigoplugin.hubitat":
                if origDev.deviceTypeId == "dimmer":
                    if "whiteLevel" in newDev.states:
                        if newDev.states["whiteLevel"] != newDev.states["brightnessLevel"]:
                            white_level = newDev.states["brightnessLevel"]
                            newDev.updateStateOnServer(key='whiteLevel', value=white_level)
                            # self.logger.debug(
                            #     f"Brightness: {origDev.states['brightnessLevel']} vs {newDev.states['brightnessLevel']}, White Level: {origDev.states['whiteLevel']} vs {newDev.states['whiteLevel']}")

            elif origDev.id in self.globals[EXPORT][ENABLED]:
                # Indigo Exported Device update checking follows . . .
                device_type = self.globals[EXPORT][ENABLED][origDev.id][EXPORT_TYPE]
                mqtt_connected = False
                for mqtt_broker_device_id in self.globals[EXPORT][MQTT_BROKERS]:
                    if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                        mqtt_connected = True
                        break
                if mqtt_connected:
                    if device_type == HE_EXPORT_DEVICE_TYPE_DIMMER:
                        self.export_device_updated_dimmer(origDev, newDev)
                    elif device_type == HE_EXPORT_DEVICE_TYPE_RELAY:
                        self.export_device_updated_relay(origDev, newDev)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        super(Plugin, self).deviceUpdated(origDev, newDev)

    def export_device_updated_relay(self, origDev, newDev):
        try:
            device_key = f"dev-{newDev.id}"
            root_topic = self.globals[EXPORT][EXPORT_ROOT_TOPIC_ID]

            if origDev.onState != newDev.onState:
                topic = f"homie/{root_topic}/{device_key}/onoff"
                payload = f"{bool(newDev.onState)}".lower()
                self.publish_export_topic(device_key, newDev.name, topic, payload)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def export_device_updated_dimmer(self, origDev, newDev):
        try:
            if self.globals[COLOR_DEBUG]: self.logger.warning(f"Interception starting for Device \"{newDev.name}\" update.")
            device_key = f"dev-{newDev.id}"
            root_topic = self.globals[EXPORT][EXPORT_ROOT_TOPIC_ID]

            dim_published = False
            if origDev.brightness != newDev.brightness:
                topic = f"homie/{root_topic}/{device_key}/dim"
                payload = f"{newDev.brightness}"
                self.publish_export_topic(device_key, newDev.name, topic, payload)
                dim_published = True

            if origDev.onState != newDev.onState:
                topic = f"homie/{root_topic}/{device_key}/onoff"
                payload = f"{bool(newDev.onState)}".lower()
                self.publish_export_topic(device_key, newDev.name, topic, payload)

            supports_color = True if getattr(newDev, "supportsColor", False) else False
            if supports_color:
                self.export_device_updated_color_light(origDev, newDev, root_topic, device_key, dim_published)
                if self.globals[COLOR_DEBUG]: self.logger.warning(f"Updated Color_Mode: {self.globals[EXPORT][ENABLED][origDev.id][STORED_COLOR_MODE]}")

            if self.globals[COLOR_DEBUG]: self.logger.warning(f"Interception ending for Device \"{newDev.name}\" update.")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def export_device_updated_color_light(self, origDev, newDev, root_topic, device_key, dim_published):
        try:
            if STORED_COLOR_MODE not in self.globals[EXPORT][ENABLED][origDev.id]:
                self.globals[EXPORT][ENABLED][origDev.id][STORED_COLOR_MODE] = None
            stored_color_mode = self.globals[EXPORT][ENABLED][origDev.id][STORED_COLOR_MODE]

            if self.globals[COLOR_DEBUG]: self.logger.warning(f"Previous Color_Mode: {stored_color_mode}")

            supports_rgb = True if getattr(newDev, "supportsRGB", False) else False
            supports_white = True if getattr(newDev, "supportsWhite", False) else False
            supports_white_temperature = True if getattr(newDev, "supportsWhiteTemperature", False) else False
            updated_color_hsv = False
            updated_white_level = False
            updated_white_temperature = False

            color_mode = None
            white_detected = False
            if supports_rgb:
                red_level = float(newDev.redLevel)
                green_level = float(newDev.greenLevel)
                blue_level = float(newDev.blueLevel)

                if int(newDev.redLevel) == int(newDev.greenLevel) == int(newDev.whiteLevel):
                    if self.globals[COLOR_DEBUG]: self.logger.warning(f"White Detected: R = G = B = {int(newDev.redLevel)}")
                    white_detected = True
                else:
                    if self.globals[COLOR_DEBUG]: self.logger.warning(f"Colour Detected: RGB({int(newDev.redLevel)},{int(newDev.greenLevel)},{int(newDev.whiteLevel)})")

                orig_red = int(origDev.redLevel)
                orig_green = int(origDev.greenLevel)
                orig_blue = int(origDev.blueLevel)

                if orig_red != int(newDev.redLevel) or orig_green != int(newDev.greenLevel) or orig_blue != int(newDev.blueLevel):

                    # Convert Indigo values for RGB (0-100) to colorSys values (0.0-1.0)
                    red = float(red_level / 100.0)  # e.g. 100.0/100.0 = 1.0
                    green = float(green_level / 100.0)  # e.g. 70.0/100.0 = 0.7
                    blue = float(blue_level / 100.0)  # e.g. 40.0/100.0 = 0.4

                    hsv_hue, hsv_saturation, hsv_value = colorsys.rgb_to_hsv(red, green, blue)

                    # Colorsys values for HSV are (0.0-1.0). Convert to to H (0-360), S (0 - 100) and V (0 - 100)
                    he_hue = int(hsv_hue * 360.0)
                    he_saturation = int(hsv_saturation * 100.0)
                    he_value = int(hsv_value * 100.0)
                    color_mode = "HSV"  # HSV / RGB
                    updated_color_hsv = True
                    updated_white_temperature = False

            if supports_white and supports_white_temperature:
                change_color_mode = False
                if supports_rgb and white_detected:
                    change_color_mode = True
                elif white_detected:
                    change_color_mode = True
                if (origDev.whiteLevel != newDev.whiteLevel) and change_color_mode:
                    color_mode = "CT"  # Colour Temperature
                    updated_white_level = True  # TODO: Already set by dim value?
                    updated_color_hsv = False
                if origDev.whiteTemperature != newDev.whiteTemperature:
                    color_mode = "CT"  # Colour Temperature
                    updated_white_temperature = True
                    updated_color_hsv = False
            else:
                # Note Plugin does not support white lights without colour temperature control
                return

            if not updated_color_hsv and not updated_white_level and not updated_white_temperature:
                return

            if stored_color_mode is not None and color_mode is not None:
                if stored_color_mode != color_mode:
                    topic = f"homie/{root_topic}/{device_key}/{u'color-mode'}"
                    payload = color_mode  # noqa [Local variable 'color_mode' might be referenced before assignment]
                    self.publish_export_topic(device_key, newDev.name, topic, payload)
                self.globals[EXPORT][ENABLED][origDev.id][STORED_COLOR_MODE] = color_mode

            if updated_color_hsv and color_mode is "HSV":
                topic = f"homie/{root_topic}/{device_key}/{u'color'}"
                payload = f"{he_hue},{he_saturation},{he_value}"  # noqa [Referenced before assignment]
                self.publish_export_topic(device_key, newDev.name, topic, payload)

            elif color_mode is "CT":
                if updated_white_temperature:
                    white_temperature = newDev.whiteTemperature

                    topic = f"homie/{root_topic}/{device_key}/{u'color-temperature'}"
                    payload = f"{white_temperature}"
                    self.publish_export_topic(device_key, newDev.name, topic, payload)

                    topic = f"homie/{root_topic}/{device_key}/{u'color-temperature'}/mireds"
                    mireds = int(round(1000000.0 / float(white_temperature)))
                    payload = f"{mireds}"
                    self.publish_export_topic(device_key, newDev.name, topic, payload)
                if updated_white_level:
                    if not dim_published:  # Only publish dim if not already published in this update
                        topic = f"homie/{root_topic}/{device_key}/{u'dim'}"
                        white_level = f"{int(newDev.whiteLevel)}"
                        self.publish_export_topic(device_key, newDev.name, topic, white_level)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def listExportAvailableIndigoDevices(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]
        try:
            available_indigo_devices_list = []

            available_indigo_devices_filter = int(valuesDict.get("availableIndigoDevicesFilter", 0))

            # self.logger.warning(f"available_indigo_devices_filter: {available_indigo_devices_filter}")

            available_indigo_devices_list.append((0, "-- Select Device[s]--"))

            available_key_list = []

            if available_indigo_devices_filter == HE_EXPORT_DEVICE_TYPE_ALL:
                for key, value in self.globals[EXPORT][AVAILABLE].items():
                    available_indigo_devices_list.append((key, value[EXPORT_NAME]))
                    available_key_list.append(key)

            elif available_indigo_devices_filter == HE_EXPORT_DEVICE_TYPE_OTHER:
                for key, value in self.globals[EXPORT][AVAILABLE].items():
                    if value[EXPORT] not in (HE_EXPORT_DEVICE_TYPE_DIMMER, HE_EXPORT_DEVICE_TYPE_RELAY,
                                                               HE_EXPORT_DEVICE_TYPE_SENSOR, HE_EXPORT_DEVICE_TYPE_THERMOSTAT,
                                                               HE_EXPORT_DEVICE_TYPE_SPRINKLER, HE_EXPORT_DEVICE_TYPE_DEVICE):
                        available_indigo_devices_list.append((key, value[EXPORT_NAME]))
                        available_key_list.append(key)

            else:
                for key, value in self.globals[EXPORT][AVAILABLE].items():
                    if value[EXPORT_TYPE] == available_indigo_devices_filter:
                        available_indigo_devices_list.append((key, value[EXPORT_NAME]))
                        available_key_list.append(key)

            # if int(valuesDict["availableIndigoDevices"]) not in available_key_list:
            #     valuesDict["availableIndigoDevices"] = 0
            if len(available_indigo_devices_list) == 1:  # i.E. No devices match filter
                available_indigo_devices_list=[(0, "-- No Devices Match Filter --")]

            return sorted(available_indigo_devices_list, key=lambda name: name[1].lower())  # sort by device name

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def menuAvailableIndigoDevicesFilterChanged(self, valuesDict, typeId, devId):
        # To force Dynamic Reload of devices
        pass
        return valuesDict

    def availableIndigoDevicesSelected(self, valuesDict, typeId, devId):
        # To force Dynamic Reload of devices

        # print(valuesDict)
        pass
        return valuesDict

    def addToExportIndigoDevices(self, valuesDict, typeId, root_dev_id):
        try:
            pluginProps = indigo.devices[root_dev_id].pluginProps
            indigo_id = pluginProps.get("indigo_id", "Indigo-1")
            for item in valuesDict["availableIndigoDevices"]:
                devId = int(item)
                if devId != 0:
                    # First add the available device to the list of discovered devices
                    self.globals[EXPORT][SELECTED][devId] = {}
                    self.globals[EXPORT][SELECTED][devId][EXPORT_NAME] = self.globals[EXPORT][AVAILABLE][devId][EXPORT_NAME]
                    self.globals[EXPORT][SELECTED][devId][EXPORT_TYPE] = self.globals[EXPORT][AVAILABLE][devId][EXPORT_TYPE]
                    self.globals[EXPORT][SELECTED][devId][EXPORT_ROOT_TOPIC_ID] = indigo_id

                    # Second, remove the device from the list of available devices
                    del self.globals[EXPORT][AVAILABLE][int(item)]

            return valuesDict

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def listExportSelectedIndigoDevices(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]
        try:
            export_indigo_devices_list = []

            export_indigo_devices_filter = int(valuesDict.get("exportIndigoDevicesFilter", 0))

            # self.logger.warning(f"export_indigo_devices_filter: {export_indigo_devices_filter}")

            export_indigo_devices_list.append((0, "-- Select Device[s] --"))

            export_key_list = []

            if export_indigo_devices_filter == HE_EXPORT_DEVICE_TYPE_ALL:
                for key, value in self.globals[EXPORT][SELECTED].items():
                    export_indigo_devices_list.append((key, value[EXPORT_NAME]))
                    export_key_list.append(key)

            elif export_indigo_devices_filter == HE_EXPORT_DEVICE_TYPE_OTHER:
                for key, value in self.globals[EXPORT][SELECTED].items():
                    if value[EXPORT_TYPE] not in (HE_EXPORT_DEVICE_TYPE_DIMMER, HE_EXPORT_DEVICE_TYPE_RELAY,
                                                               HE_EXPORT_DEVICE_TYPE_SENSOR, HE_EXPORT_DEVICE_TYPE_THERMOSTAT,
                                                               HE_EXPORT_DEVICE_TYPE_SPRINKLER, HE_EXPORT_DEVICE_TYPE_DEVICE):
                        export_indigo_devices_list.append((key, value[EXPORT_NAME]))
                        export_key_list.append(key)

            else:
                for key, value in self.globals[EXPORT][SELECTED].items():
                    if value[EXPORT_TYPE] == export_indigo_devices_filter:
                        export_indigo_devices_list.append((key, value[EXPORT_NAME]))
                        export_key_list.append(key)

            # if int(valuesDict["exportIndigoDevices"]) not in export_key_list:
            #     valuesDict["exportIndigoDevices"] = 0
            if len(export_indigo_devices_list) == 1:  # i.e. No devices match filter
                export_indigo_devices_list=[(0, "-- No Devices Match Filter--")]

            return sorted(export_indigo_devices_list, key=lambda name: name[1].lower())  # sort by device name

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def removeFromExportIndigoDevices(self, valuesDict, typeId, devId):
        try:
            for item in valuesDict["exportIndigoDevices"]:
                devId = int(item)
                if devId != 0:
                    # First add the available device to the list of discovered devices
                    self.globals[EXPORT][AVAILABLE][devId] = {}
                    self.globals[EXPORT][AVAILABLE][devId][EXPORT_NAME] = self.globals[EXPORT][SELECTED][devId][EXPORT_NAME]
                    self.globals[EXPORT][AVAILABLE][devId][EXPORT_TYPE] = self.globals[EXPORT][SELECTED][devId][EXPORT_TYPE]

                    # Second, remove the device from the list of available devices
                    del self.globals[EXPORT][SELECTED][int(item)]

            return valuesDict

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def menuExportIndigoDevicesFilterChanged(self, valuesDict, typeId, devId):
        # To force Dynamic Reload of devices
        pass
        return valuesDict

    def exportIndigoDevicesSelected(self, valuesDict, typeId, devId):
        # To force Dynamic Reload of devices
        pass
        return valuesDict

    def didDeviceCommPropertyChange(self, origDev, newDev):  # TODO: Disabled method
        if newDev.deviceTypeId == "indigoExport":
            origDev_initiate_export = bool(origDev.pluginProps.get('initiateExport', False))
            newDev_initiate_export = bool(newDev.pluginProps.get('initiateExport', False))

            if origDev_initiate_export != newDev_initiate_export:
                if newDev_initiate_export:
                    # initiate_export = newDev.pluginProps.get('initiateExport', None)
                    # self.logger.error(f"didDeviceCommPropertyChange - Initiate export: {initiate_export}")
                    return True
            return False
        return super(Plugin, self).didDeviceCommPropertyChange(origDev, newDev)

    def getDeviceConfigUiValues(self, plugin_props, type_id="", dev_id=0):
        try:
            if type_id == "mqttBroker":
                if "mqtt_password" not in plugin_props:
                    plugin_props["mqtt_password"] = ""

                # print(f"getPrefsConfigUiValues | mqtt_password [1]: {plugin_props[u'mqtt_password']}")

                if "mqtt_password_is_encoded" not in plugin_props:
                    plugin_props["mqtt_password_is_encoded"] = False
                if "mqtt_password" in plugin_props and plugin_props["mqtt_password_is_encoded"]:
                    plugin_props["mqtt_password_is_encoded"] = False
                    mqtt_password_encryption_key = plugin_props.get("mqtt_password_encryption_key", "")
                    plugin_props["mqtt_password"] = decode(mqtt_password_encryption_key.encode('utf-8'), plugin_props["mqtt_password"].encode('utf-8'))
                aa = 1 + 2
                bb = aa + 1
                print(f"getPrefsConfigUiValues | mqtt_password [2]: {plugin_props[u'mqtt_password']}")  # TODO: DEBUG ONLY

                if "mqttClientPrefix" not in plugin_props:
                    plugin_props["mqttClientPrefix"] = ""
                if plugin_props["mqttClientPrefix"] == "":
                    try:
                        # As MQTT CLIENT PREFIX is empty, try setting it to Computer Name
                        plugin_props["mqttClientPrefix"] = socket.gethostbyaddr(socket.gethostname())[0].split(".")[0]  # Used in creation of MQTT Client Id
                    except Exception:  # noqa
                        plugin_props["mqttClientPrefix"] = "Mac"

            elif type_id == "tasmotaOutlet":
                plugin_props["SupportsEnergyMeter"] = True
                plugin_props["SupportsEnergyMeterCurPower"] = True
                plugin_props["SupportsAccumEnergyTotal"] = True
                if "tasmotaDevice" not in plugin_props:
                    plugin_props["tasmotaDevice"] = "-SELECT-"  # Name of Tasmota Device - Default: "-SELECT-", "-- Select Tasmota Device --"

                # TODO: Initialise Power props if not set-up

            elif type_id == "indigoExport":

                plugin_props["availableIndigoDevices"] = indigo.List([0])  # Defaults the list to empty
                plugin_props["exportIndigoDevices"] = indigo.List([0])

                self.globals[EXPORT][AVAILABLE] = dict()
                self.globals[EXPORT][SELECTED] = dict()

                device_types = {}

                def determine_device_type(dev):
                    if isinstance(dev, indigo.DimmerDevice):
                        return HE_EXPORT_DEVICE_TYPE_DIMMER
                    if isinstance(dev, indigo.RelayDevice):
                        return HE_EXPORT_DEVICE_TYPE_RELAY
                    if isinstance(dev, indigo.SensorDevice):
                        return HE_EXPORT_DEVICE_TYPE_SENSOR
                    if isinstance(dev, indigo.ThermostatDevice):
                        return HE_EXPORT_DEVICE_TYPE_THERMOSTAT
                    if isinstance(dev, indigo.SprinklerDevice):
                        return HE_EXPORT_DEVICE_TYPE_SPRINKLER
                    # Default
                    isinstance(dev, indigo.Device)
                    return HE_EXPORT_DEVICE_TYPE_DEVICE

                for dev in indigo.devices:
                    if dev.pluginId != "com.autologplugin.indigoplugin.hubitat":
                        if bool(dev.pluginProps.get("export_enabled", False)):
                            self.globals[EXPORT][SELECTED][dev.id] = dict()
                            self.globals[EXPORT][SELECTED][dev.id][EXPORT_NAME] = dev.name
                            self.globals[EXPORT][SELECTED][dev.id][EXPORT_TYPE] = determine_device_type(dev)
                        else:
                            self.globals[EXPORT][AVAILABLE][dev.id] = dict()
                            self.globals[EXPORT][AVAILABLE][dev.id][EXPORT_NAME] = dev.name
                            self.globals[EXPORT][AVAILABLE][dev.id][EXPORT_TYPE] = determine_device_type(dev)
                            device_types[type(dev)] = ""

            elif type_id == "hubitatElevationHub":
                if "hub_name" not in plugin_props:
                    plugin_props["hub_name"] = ""  # Name of Hubitat Elevation Hub - "" if not present
                if "mqtt_broker_ip" not in plugin_props:
                    plugin_props["mqtt_broker_ip"] = ""  # IP of MQTT Broker - "" if not present
                if "mqtt_broker_port" not in plugin_props:
                    plugin_props["mqtt_broker_port"] = "1883"  # Port of MQTT Broker - Default = "1883" if not present

            elif type_id in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES:
                plugin_props["primaryIndigoDevice"] = True
                if "hubitatDevice" not in plugin_props:
                    plugin_props["hubitatDevice"] = "-SELECT-"  # Name of Hubitat Elevation Device - Default: "-SELECT-", "-- Select Hubitat Device(s) --"
                if "hubitatHubName" not in plugin_props:
                    plugin_props["hubitatHubName"] = "-SELECT-"  # Id of Indigo Hubitat Elevation Hub device - Default: "-SELECT-", "-- Select Hubitat Hub --"

                if plugin_props["hubitatHubName"] != "-SELECT-" and plugin_props["hubitatHubName"] != "-NONE-":
                    if plugin_props["hubitatHubName"] not in self.globals[HE_HUBS]:
                        plugin_props["hubitatHubName"] = "-NONE-"

                if "hubitatPropertiesInitialised" not in plugin_props or not plugin_props["hubitatPropertiesInitialised"]:
                    plugin_props["hubitatPropertyAcceleration"] = False
                    plugin_props["hubitatPropertyBattery"] = False
                    plugin_props["hubitatPropertyButton"] = False
                    plugin_props["hubitatPropertyColor"] = False
                    plugin_props["hubitatPropertyColorName"] = False
                    plugin_props["hubitatPropertyColorTemperature"] = False
                    plugin_props["hubitatPropertyContact"] = False
                    plugin_props["hubitatPropertyDim"] = False
                    plugin_props["hubitatPropertyEnergy"] = False
                    plugin_props["hubitatPropertyHumidity"] = False
                    plugin_props["hubitatPropertyIlluminance"] = False
                    plugin_props["hubitatPropertyHvacMode"] = False
                    plugin_props["hubitatPropertyMotion"] = False
                    plugin_props["hubitatPropertyOnOff"] = False
                    plugin_props["hubitatPropertyPosition"] = False
                    plugin_props["hubitatPropertyPower"] = False
                    plugin_props["hubitatPropertyPresence"] = False
                    plugin_props["hubitatPropertyPressure"] = False
                    plugin_props["hubitatPropertySetpoint"] = False
                    plugin_props["hubitatPropertyHvacState"] = False
                    plugin_props["hubitatPropertyState"] = False
                    plugin_props["hubitatPropertyTemperature"] = False
                    plugin_props["hubitatPropertyValve"] = False
                    plugin_props["hubitatPropertyVoltage"] = False

                    plugin_props["uspAcceleration"] = False
                    plugin_props["uspBattery"] = False
                    plugin_props["uspButton"] = False
                    plugin_props["uspColorRGB"] = False
                    plugin_props["uspContact"] = False
                    plugin_props["uspDimmer"] = False
                    plugin_props["uspEnergy"] = False
                    plugin_props["uspHumidity"] = False
                    plugin_props["uspHvacMode"] = False
                    plugin_props["uspHvacState"] = False
                    plugin_props["uspIlluminance"] = False
                    plugin_props["uspMotion"] = False
                    plugin_props["uspOnOff"] = False
                    plugin_props["uspPosition"] = False
                    plugin_props["uspPower"] = False
                    plugin_props["uspPresence"] = False
                    plugin_props["uspPressure"] = False
                    plugin_props["uspSetpoint"] = False
                    plugin_props["uspState"] = False
                    plugin_props["uspTemperature"] = False
                    plugin_props["uspValve"] = False
                    plugin_props["uspVoltage"] = False
                    plugin_props["uspWhiteTemperature"] = False

            elif type_id in ("accelerationSensorSecondary", "humiditySensorSecondary", "illuminanceSensorSecondary",
                             "motionSensorSecondary", "presenceSensorSecondary", "pressureSensorSecondary",
                             "temperatureSensorSecondary", "valveSecondary"):
                plugin_props['primaryIndigoDevice'] = False
                # The following code sets the property "member_of_device_group" to True if the secondary device
                #   is associated with a primary device. If not it is set to False. This property is used
                #   in Devices.xml to display a red warning box and disable device editing if set to False.
                plugin_props['member_of_device_group'] = False
                plugin_props["primaryIndigoDevice"] = False
                dev_id_list = indigo.device.getGroupList(dev_id)
                if len(dev_id_list) > 1:
                    plugin_props['member_of_device_group'] = True
                    for linked_dev_id in dev_id_list:
                        linked_dev_props = indigo.devices[linked_dev_id].ownerProps
                        primary_device = linked_dev_props.get("primaryIndigoDevice", False)
                        if primary_device:
                            plugin_props['linkedIndigoDeviceId'] = indigo.devices[linked_dev_id].id
                            plugin_props['linkedIndigoDevice'] = indigo.devices[linked_dev_id].name
                            plugin_props['associatedHubitatDevice'] = linked_dev_props["hubitatDevice"]

            return super(Plugin, self).getDeviceConfigUiValues(plugin_props, type_id, dev_id)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def getDeviceStateList(self, dev):
        try:
            self.logger.debug(f"getDeviceStateList invoked for '{dev.name}'")

            state_list = indigo.PluginBase.getDeviceStateList(self, dev)

            # Acceleration State
            if (bool(dev.pluginProps.get("uspAcceleration", False)) and
                    dev.pluginProps.get("uspAccelerationIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                acceleration_state = self.getDeviceStateDictForBoolTrueFalseType("acceleration", "Acceleration Changed", "Acceleration")
                if acceleration_state not in state_list:
                    state_list.append(acceleration_state)

            # Button State(s)
            if bool(dev.pluginProps.get("uspButton", False)):
                number_of_buttons = int(dev.pluginProps.get("uspNumberOfButtons", 1))
                for button_number in range(1, (number_of_buttons + 1)):
                    button_state_id = f"button_{button_number}"
                    button_trigger_label = f"Button {button_number} Changed"
                    button_control_page_label = f"Button {button_number}"
                    button_state = self.getDeviceStateDictForStringType(button_state_id, button_trigger_label, button_control_page_label)
                    if button_state not in state_list:
                        state_list.append(button_state)
                button_state_id = "lastButtonPressed"
                button_trigger_label = "Last Button Pressed Changed"
                button_control_page_label = "Last Button Pressed"
                button_state = self.getDeviceStateDictForStringType(button_state_id, button_trigger_label, button_control_page_label)
                if button_state not in state_list:
                    state_list.append(button_state)

            # humidity State
            if (bool(dev.pluginProps.get("uspHumidity", False)) and
                    dev.pluginProps.get("uspHumidityIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                humidity_state = self.getDeviceStateDictForNumberType("humidity", "Humidity Changed", "Humidity")
                if humidity_state not in state_list:
                    state_list.append(humidity_state)

            # Illuminance State
            if (bool(dev.pluginProps.get("uspIlluminance", False)) and
                    dev.pluginProps.get("uspIlluminanceIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                illuminance_state = self.getDeviceStateDictForNumberType("illuminance", "Illuminance Changed", "Illuminance")
                if illuminance_state not in state_list:
                    state_list.append(illuminance_state)

            # Pressure State
            if (bool(dev.pluginProps.get("uspPressure", False)) and
                    dev.pluginProps.get("uspPressureIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                pressure_state = self.getDeviceStateDictForNumberType("pressure", "Pressure Changed", "Pressure")
                if pressure_state not in state_list:
                    state_list.append(pressure_state)

            # Presence State
            if (bool(dev.pluginProps.get("uspPresence", False)) and
                    dev.pluginProps.get("uspPresenceIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                presence_state = self.getDeviceStateDictForBoolTrueFalseType("presence", "Presence Changed", "Presence")
                if presence_state not in state_list:
                    state_list.append(presence_state)

            # State  [used by Blind]
            if bool(dev.pluginProps.get("uspState", False)):
                state_state = self.getDeviceStateDictForStringType("state", "State Mode Changed", "State")
                if state_state not in state_list:
                    state_list.append(state_state)

            # Temperature State
            if (bool(dev.pluginProps.get("uspTemperature", False)) and
                    dev.pluginProps.get("uspTemperatureIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                temperature_state = self.getDeviceStateDictForNumberType("temperature", "Temperature Changed", "Temperature")
                if temperature_state not in state_list:
                    state_list.append(temperature_state)

            # Voltage State
            if (bool(dev.pluginProps.get("uspVoltage", False)) and
                    dev.pluginProps.get("uspVoltageIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                voltage_state = self.getDeviceStateDictForNumberType("voltage", "Voltage Changed", "Voltage")
                if voltage_state not in state_list:
                    state_list.append(voltage_state)

            # Color RGB
            if bool(dev.pluginProps.get("uspColorRGB", False)) or bool(dev.pluginProps.get("uspWhiteTemperature", False)):
                color_mode_state = self.getDeviceStateDictForStringType("colorMode", "Color Mode Changed", "Color Mode")
                if color_mode_state not in state_list:
                    state_list.append(color_mode_state)
                color_name_state = self.getDeviceStateDictForStringType("colorName", "Color Name Changed", "Color Name")
                if color_name_state not in state_list:
                    state_list.append(color_name_state)

            # HVAC Mode
            if bool(dev.pluginProps.get("uspHvacMode", False)):
                hvac_mode_state = self.getDeviceStateDictForStringType("hvacMode", "HVAC Mode Changed", "HVAC Mode")
                if hvac_mode_state not in state_list:
                    state_list.append(hvac_mode_state)

            # HVAC State
            if bool(dev.pluginProps.get("uspHvacState", False)):
                hvac_state_state = self.getDeviceStateDictForStringType("hvacState", "HVAC Mode Changed", "HVAC State")
                if hvac_state_state not in state_list:
                    state_list.append(hvac_state_state)

            # Motion State
            if (bool(dev.pluginProps.get("uspMotion", False)) and
                    dev.pluginProps.get("uspMotionIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                motion_state = self.getDeviceStateDictForStringType("motion", "Motion Changed", "Motion")
                if motion_state not in state_list:
                    state_list.append(motion_state)

            # Valve State
            if (bool(dev.pluginProps.get("uspValve", False)) and
                    dev.pluginProps.get("uspValveIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                valve_state = self.getDeviceStateDictForStringType("valve", "Valve Changed", "Valve")
                if valve_state not in state_list:
                    state_list.append(valve_state)

            # Voltage State
            if (bool(dev.pluginProps.get("uspVoltage", False)) and
                    dev.pluginProps.get("uspVoltageIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE):
                voltage_state = self.getDeviceStateDictForStringType("voltage", "Voltage Changed", "Voltage")
                if voltage_state not in state_list:
                    state_list.append(voltage_state)

            self.logger.debug(f"State List [Amended]: {state_list}")
            return state_list
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def getPrefsConfigUiValues(self):
        prefs_config_ui_values = self.pluginPrefs

        if "mqttClientPrefix" not in prefs_config_ui_values:
            prefs_config_ui_values["mqttClientPrefix"] = ""
        if prefs_config_ui_values["mqttClientPrefix"] == "":
            try:
                # As MQTT CLIENT PREFIX is empty, try setting it to Computer Name
                prefs_config_ui_values["mqttClientPrefix"] = socket.gethostbyaddr(socket.gethostname())[0].split(".")[0]  # Used in creation of MQTT Client Id
            except Exception:  # noqa
                prefs_config_ui_values["mqttClientPrefix"] = "Mac"
                pass

        return prefs_config_ui_values

    def refreshUiCallback(self, valuesDict, typeId="", devId=None):  # noqa [parameter value is not used]
        errors_dict = indigo.Dict()
        try:
            if typeId == "hubitatElevationHub":
                return valuesDict, errors_dict

            # self.logger.warning(f"'refreshUiCallback' valuesDict:'{valuesDict['hubitatDevice']}'")

            if valuesDict["hubitatDevice"] == "":
                valuesDict["hubitatDevice"] = "-SELECT-"
            if valuesDict["hubitatHubName"] == "":
                valuesDict["hubitatHubName"] = "-SELECT-"
            if valuesDict["hubitatHubName"] == "-SELECT-":
                valuesDict["hubitatDevice"] = "-FIRST-"
            elif valuesDict["hubitatHubName"] == "-NONE-":
                valuesDict["hubitatDevice"] = "-NONE-"

            usp_field_id_check_1 = ""
            usp_field_id_check_2 = ""
            if typeId == "button":
                usp_field_id_check_1 = "uspButtonIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "contactSensor":
                usp_field_id_check_1 = "uspContactIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "dimmer":
                dev = indigo.devices[devId]
                if dev.subType == indigo.kDimmerDeviceSubType.Blind:
                    usp_field_id_check_1 = "uspPositionIndigo"
                    valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
                else:
                    usp_field_id_check_1 = "uspDimmerIndigo"
                    valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
                usp_field_id_check_2 = "uspOnOffIndigo"
                valuesDict[usp_field_id_check_2] = INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE
            elif typeId == "humiditySensor":
                usp_field_id_check_1 = "uspHumidityIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "illuminanceSensor":
                usp_field_id_check_1 = "uspIlluminanceIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "motionSensor":
                usp_field_id_check_1 = "uspMotionIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "multiSensor":
                usp_field_id_check_1 = "uspMotionIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "outlet":
                usp_field_id_check_1 = "uspOnOffIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "temperatureSensor":
                usp_field_id_check_1 = "uspTemperatureIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
            elif typeId == "thermostat":
                usp_field_id_check_1 = "uspTemperatureIndigo"
                valuesDict[usp_field_id_check_1] = INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE
                usp_field_id_check_2 = "uspSetpointIndigo"
                valuesDict[usp_field_id_check_2] = INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE

            for usp_field_id in ("uspAccelerationIndigo", "uspButtonIndigo", "uspPositionIndigo", "uspContactIndigo", "uspDimmerIndigo",
                                 "uspEnergyIndigo", "uspHumidityIndigo", "uspIlluminanceIndigo", "uspMotionIndigo",
                                 "uspOnOffIndigo", "uspPowerIndigo", "uspPresenceIndigo", "uspPressureIndigo",
                                 "uspTemperatureIndigo", "uspSetpointIndigo", "uspValveIndigo", "uspVoltageIndigo"):
                if (usp_field_id != usp_field_id_check_1 and usp_field_id != usp_field_id_check_2 and
                        (usp_field_id not in valuesDict or
                         valuesDict[usp_field_id] not in [INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE, INDIGO_SECONDARY_DEVICE])):

                    valuesDict[usp_field_id] = INDIGO_SECONDARY_DEVICE  # Default

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        return valuesDict, errors_dict

    def shutdown(self):

        self.logger.info("Hubitat plugin shutdown invoked")

    def startup(self):
        try:
            indigo.devices.subscribeToChanges()

            # Create Queues for receiving MQTT topics
            self.globals[QUEUES][MQTT_HUB_QUEUE] = queue.Queue()  # Used to queue MQTT topics for Hubitat Hubs
            self.globals[QUEUES][MQTT_TASMOTA_QUEUE] = queue.Queue()  # Used to queue MQTT topics for Tasmota Outlets
            self.globals[QUEUES][MQTT_EXPORT_QUEUE] = queue.Queue()  # Used to queue MQTT topics for Indigo Export

            # Create the thread to handle export /set processing
            self.globals[EXPORT][EXPORT_EVENT] = threading.Event()
            self.globals[EXPORT][EXPORT_THREAD] = ThreadExportHandler(self.globals, self.globals[EXPORT][EXPORT_EVENT])
            self.globals[EXPORT][EXPORT_THREAD].start()

            # Initialise dictionary to record Tasmota Keys to Indigo Device IDs
            self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS] = dict()

            for dev in indigo.devices.iter("self"):
                if dev.deviceTypeId == "mqttBroker":  # Only process if MQTT Client
                    self.globals[MQTT][dev.id] = dict()
                    self.globals[MQTT][dev.id][MQTT_CONNECTED] = False

                elif dev.deviceTypeId == "hubitatElevationHub":  # Only process if Hubitat Hub
                    if dev.enabled:
                        props = dev.ownerProps
                        hubitat_hub_name = props["hub_name"]
                        if hubitat_hub_name not in self.globals[HE_HUBS]:
                            self.globals[HE_HUBS][hubitat_hub_name] = dict()
                            self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID] = dev.id
                            self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES] = dict()

                elif dev.deviceTypeId == "tasmotaOutlet":  # Only process if a Tasmota Outlet
                    if dev.enabled:
                        tasmota_key = dev.address
                        self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS][tasmota_key] = dev.id

                        if tasmota_key not in self.globals[TASMOTA][TASMOTA_DEVICES]:
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key] = dict()
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_DISCOVERY_DETAILS] = False

                        self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] = dev.id
                        self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS][tasmota_key] = dev.id

                        # self.logger.error(f"Tasmota List = '{tasmota_key}', Dev ID = '{dev.id}', Dev Name = '{dev.name}':\n{self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]}")

                        if not self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_DISCOVERY_DETAILS]:
                            # Default Tasmota device internal store
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_POWER] = False
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE] = "n/a"
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME] = ""
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_DEVICE_NAME] = ""
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC] = ""
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL] = ""
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_T] = ""

                            # Update  Tasmota device internal store from Indigo device
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME] = dev.states["friendlyName"]
                            # self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_DEVICE_NAME] = tasmota_dev.states["friendlyName"]
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC] = dev.states["macAddress"]
                            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL] = dev.states["model"]
                            # self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_T] = tasmota_dev.states["friendlyName"]
                    # dev.setErrorStateOnServer("offline")

            # Hubitat Elevation MQTT Device Export logic follows

            def determine_device_type(dev):
                if isinstance(dev, indigo.DimmerDevice):
                    return HE_EXPORT_DEVICE_TYPE_DIMMER
                if isinstance(dev, indigo.RelayDevice):
                    return HE_EXPORT_DEVICE_TYPE_RELAY
                if isinstance(dev, indigo.SensorDevice):
                    return HE_EXPORT_DEVICE_TYPE_SENSOR
                if isinstance(dev, indigo.ThermostatDevice):
                    return HE_EXPORT_DEVICE_TYPE_THERMOSTAT
                if isinstance(dev, indigo.SprinklerDevice):
                    return HE_EXPORT_DEVICE_TYPE_SPRINKLER
                # Default
                isinstance(dev, indigo.Device)
                return HE_EXPORT_DEVICE_TYPE_DEVICE

            for dev in indigo.devices:
                if dev.pluginId != "com.autologplugin.indigoplugin.hubitat":
                    if dev.pluginProps.get("export_enabled", False):
                        self.globals[EXPORT][ENABLED][dev.id] = {}
                        self.globals[EXPORT][ENABLED][dev.id][EXPORT_NAME] = dev.name
                        self.globals[EXPORT][ENABLED][dev.id][EXPORT_TYPE] = determine_device_type(dev)
                        self.globals[EXPORT][ENABLED][dev.id][EXPORT_ROOT_TOPIC_ID] = dev.pluginProps.get("export_root_topic_id", "indigo-1")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def stopConcurrentThread(self):
        self.logger.info("Hubitat plugin closing down")

    def validateActionConfigUi(self, values_dict, type_id, action_id):  # noqa [parameter value is not used]
        try:
            error_dict = indigo.Dict()

            white_level = -1  # Only needed to suppress a PyCharm warning!
            white_temperature = -1  # Only needed to suppress a PyCharm warning!

            if bool(values_dict.get("setWhiteLevel", True)):
                valid = True
                try:
                    white_level = int(values_dict["whiteLevel"])
                except ValueError:
                    valid = False
                if not valid or (white_level < 0 or white_level > 100):
                    error_dict["whiteLevel"] = "White Level must be an integer between 0 and 100"
                    error_dict["showAlertText"] = "You must enter an integer between 0 and 100 for White Level"
                    return False, values_dict, error_dict

            if bool(values_dict.get("setWhiteTemperature", True)):
                valid = True
                try:
                    white_temperature = int(values_dict["whiteTemperature"])
                except ValueError:
                    valid = False
                if not valid or (white_temperature < 1700 or white_temperature > 15000):
                    error_dict["whiteTemperature"] = "White Temperature must be an integer between 1700 and 15000"
                    error_dict["showAlertText"] = "You must enter an integer between 1700 and 15000 for White Temperature"
                    return False, values_dict, error_dict

            return True, values_dict

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def validateDeviceConfigUi(self, values_dict=None, type_id="", dev_id=0):
        try:
            error_dict = indigo.Dict()

            if type_id == "mqttBroker":
                mqtt_client_prefix = values_dict.get("mqttClientPrefix", "")

                mqtt_client_prefix_is_valid = True

                if len(mqtt_client_prefix) == 0:
                    mqtt_client_prefix_is_valid = False
                else:
                    regex = r"^[a-zA-Z0-9_-]+"
                    match = re.match(regex, mqtt_client_prefix)
                    if match is None:
                        mqtt_client_prefix_is_valid = False
                    else:
                        if not mqtt_client_prefix[0].isalpha():
                            mqtt_client_prefix_is_valid = False

                if not mqtt_client_prefix_is_valid:
                    error_message = "MQTT Client Prefix must be made up of the characters [A-Z], [a-z], [0-9], [-] or [_] and start with an alpha."
                    error_dict = indigo.Dict()
                    error_dict["mqttClientPrefix"] = error_message
                    error_dict["showAlertText"] = error_message
                    return False, values_dict, error_dict

                unencrypted_password = values_dict.get("mqtt_password", "")
                if unencrypted_password != "":
                    values_dict["mqtt_password_is_encoded"] = True
                    key, password = encode(unencrypted_password)
                    values_dict["mqtt_password"] = password
                    values_dict["mqtt_password_encryption_key"] = key
                else:
                    values_dict["mqtt_password_is_encoded"] = False
                    values_dict["mqtt_password_encryption_key"] = ""

                return True, values_dict

            if type_id == "indigoExport":
                values_dict["initiateExport"] = True  # Force publication when saving Device Settings
                return True, values_dict

            if type_id == "tasmotaOutlet":
                if len(values_dict["mqttBroker"]) == 0:
                    error_message = "You must select an MQTT Broker"
                    error_dict['mqttBroker'] = error_message
                    error_dict["showAlertText"] = error_message
                    return False, values_dict, error_dict

                if (values_dict["tasmotaDevice"] == "-NONE-" or
                        values_dict["tasmotaDevice"] == "-NONE-"):
                    error_dict['tasmotaDevice'] = "A tasmota device must be selected"
                    return False, values_dict, error_dict

                return True, values_dict

            if type_id == "hubitatElevationHub":
                values_dict["address"] = values_dict["hub_name"]

                if len(values_dict["mqttBrokers"]) == 0:
                    error_message = "You must select at least one MQTT Broker"
                    error_dict['mqttBrokers'] = error_message
                    error_dict["showAlertText"] = error_message
                    return False, values_dict, error_dict

                return True, values_dict

            # Start of Special validation for linked devices [Sub-Models]

            if type_id not in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES:
                return True, values_dict

            # ^^^ - End of Special validation for linked devices [Sub-Models]

            if values_dict["hubitatHubName"] == "-SELECT-":
                error_dict['hubitatHubName'] = "A Hubitat hub must be selected"
                return False, values_dict, error_dict

            if values_dict["hubitatDevice"] == "-SELECT-":
                error_dict['hubitatDevice'] = "A Hubitat device must be selected"
                return False, values_dict, error_dict
            elif values_dict["hubitatDevice"] == "-NONE-":
                error_dict['hubitatDevice'] = "Unable to save as no available Hubitat devices"
                return False, values_dict, error_dict
            elif values_dict["hubitatDevice"] == "-FIRST-":
                error_dict['hubitatDevice'] = "Unable to save as no Hubitat Hub selected"
                return False, values_dict, error_dict

            values_dict["address"] = values_dict["hubitatDevice"]

            values_dict["SupportsBatteryLevel"] = False
            values_dict["NumHumidityInputs"] = 0
            values_dict["NumTemperatureInputs"] = 0
            values_dict["ShowCoolHeatEquipmentStateUI"] = False
            values_dict["SupportsCoolSetpoint"] = False
            values_dict["SupportsEnergyMeter"] = False
            values_dict["SupportsEnergyMeterCurPower"] = False
            values_dict["SupportsAccumEnergyTotal"] = False

            values_dict["SupportsHeatSetpoint"] = False
            values_dict["SupportsHvacFanMode"] = False
            values_dict["SupportsHvacOperationMode"] = False
            values_dict["SupportsOnState"] = False
            values_dict["SupportsSensorValue"] = False
            values_dict["SupportsStatusRequest"] = False
            values_dict["supportsTemperatureReporting"] = False
            values_dict["supportsValve"] = False

            values_dict["SupportsColor"] = False
            values_dict["SupportsRGB"] = False
            values_dict["SupportsWhite"] = False
            values_dict["SupportsWhiteTemperature"] = False
            values_dict["SupportsTwoWhiteLevels"] = False

            if values_dict.get("hubitatPropertyBattery", False):
                values_dict["SupportsBatteryLevel"] = True
            else:
                values_dict["SupportsBatteryLevel"] = False

            values_dict["address"] = values_dict["hubitatDevice"]

            # TODO: Consider using $nodes to check if device address is still valid - old nodes can be left behind in MQTT?

            if type_id == "button":
                # Scene (Button) validation and option settings
                if not values_dict.get("uspButton", False):
                    error_message = "An Indigo Scene (Button) device requires an association to the Hubitat 'button' property"
                    error_dict['uspButton'] = error_message
                    error_dict["showAlertText"] = error_message

            elif type_id == "blind":
                # Blind validation and option settings
                if not values_dict.get("uspPosition", False):
                    error_message = "An Indigo Blind device requires an association to the Hubitat 'position' property"
                    error_dict['uspPosition'] = error_message
                    error_dict["showAlertText"] = error_message
                elif not values_dict.get("uspOnOff", False):
                    error_message = "An Indigo Dimmer device requires an association to the Hubitat 'onoff' property"
                    error_dict['uspOnOff'] = error_message
                    error_dict["showAlertText"] = error_message

            elif type_id == "contactSensor":
                # Contact Sensor validation and option settings
                if not values_dict.get("uspContact", False):
                    error_message = "An Indigo Contact Sensor device requires an association to the Hubitat 'contact' property"
                    error_dict['uspContact'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsOnState"] = True
                    values_dict["allowOnStateChange"] = False

            elif type_id == "dimmer":
                # Dimmer validation and option settings
                if not values_dict.get("uspDimmer", False):
                    error_message = "An Indigo Dimmer device requires an association to the Hubitat 'dim' property"
                    error_dict['uspDimmer'] = error_message
                    error_dict["showAlertText"] = error_message
                elif not values_dict.get("uspOnOff", False):
                    error_message = "An Indigo Dimmer device requires an association to the Hubitat 'onoff' property"
                    error_dict['uspOnOff'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    if bool(values_dict.get("uspColorRGB", False)):
                        values_dict["SupportsColor"] = True
                        values_dict["SupportsRGB"] = True
                    if bool(values_dict.get("uspWhiteTemperature", False)):
                        values_dict["SupportsColor"] = True
                        values_dict["SupportsWhite"] = True
                        values_dict["SupportsWhiteTemperature"] = True
                        try:
                            values_dict["WhiteTemperatureMin"] = int(values_dict.get("uspKelvinMinimum", 2500))
                        except ValueError:
                            error_message = "Kelvin Minimum must be an integer"
                            error_dict['uspKelvinMinimum'] = error_message
                            error_dict["showAlertText"] = error_message
                        try:
                            values_dict["WhiteTemperatureMax"] = int(values_dict.get("uspKelvinMaximum", 9000))
                        except ValueError:
                            error_message = "Kelvin Minimum must be an integer"
                            error_dict['uspKelvinMaximum'] = error_message
                            error_dict["showAlertText"] = error_message

            elif type_id == "humiditySensor":
                # Humidity Sensor validation and option settings
                if not values_dict.get("uspHumidity", False):
                    error_message = "An Indigo Humidity Sensor device requires an association to the Hubitat 'humidity' property"
                    error_dict['uspHumidity'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsSensorValue"] = True

            elif type_id == "illuminanceSensor":
                # Illuminance Sensor validation and option settings
                if not values_dict.get("uspIlluminance", False):
                    error_message = "An Indigo Illuminance Sensor device requires an association to the Hubitat 'illuminance' property"
                    error_dict['uspIlluminance'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsSensorValue"] = True

            elif type_id == "motionSensor":
                # Motion Sensor validation and option settings
                if not values_dict.get("uspMotion", False):
                    error_message = "An Indigo Motion Sensor device requires an association to the Hubitat 'motion' property"
                    error_dict['uspMotion'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsOnState"] = True
                    values_dict["allowOnStateChange"] = False

            elif type_id == "multiSensor":
                # Multi Sensor validation and option settings
                if not values_dict.get("uspMotion", False):
                    error_message = "An Indigo Multi-Sensor device requires an association to the Hubitat 'motion' property"
                    error_dict['uspMotion'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsOnState"] = True
                    values_dict["allowOnStateChange"] = False

            elif type_id == "outlet":
                # Outlet (Socket) validation and option settings
                if not values_dict.get("uspOnOff", False):
                    error_message = "An Indigo Outlet (Socket) device requires an association to the Hubitat 'onoff' property"
                    error_dict['uspOnOff'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsOnState"] = True
                    if bool(values_dict.get("uspPower", False)):
                        values_dict["SupportsEnergyMeter"] = True
                        values_dict["SupportsEnergyMeterCurPower"] = True
                    if bool(values_dict.get("uspEnergy", False)):
                        values_dict["SupportsEnergyMeter"] = True
                        values_dict["SupportsAccumEnergyTotal"] = True
                    if bool(values_dict.get("hubitatPropertyRefresh", False)):
                        values_dict["SupportsStatusRequest"] = True

            elif type_id == "thermostat":
                # Thermostat validation and option settings
                if not values_dict.get("uspTemperature", False):
                    error_message = "An Indigo Thermostat device requires an association to the Hubitat 'temperature' property"
                    error_dict['uspTemperature'] = error_message
                    error_dict["showAlertText"] = error_message
                elif not values_dict.get("uspSetpoint", False):
                    error_message = "An Indigo Thermostat device requires an association to the Hubitat 'setpoint' property"
                    error_dict['uspSetpoint'] = error_message
                    error_dict["showAlertText"] = error_message
                # elif not values_dict.get("uspOnOff", False):
                #     error_message = "An Indigo Thermostat device requires an association to the Hubitat 'onoff' property"
                #     error_dict['uspOnOff'] = error_message
                #     error_dict["showAlertText"] = error_message
                else:
                    values_dict["SupportsHeatSetpoint"] = True
                    values_dict["NumTemperatureInputs"] = 1
                    values_dict["supportsTemperatureReporting"] = True
                    if values_dict.get("uspHvacMode", False):
                        values_dict["SupportsHvacOperationMode"] = True
                    if (bool(values_dict.get("uspValve", False)) and
                            values_dict.get("uspValveIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_SECONDARY_DEVICE):
                        values_dict["supportsValve"] = True
                    if bool(values_dict.get("hubitatPropertyRefresh", False)):
                        values_dict["SupportsStatusRequest"] = True

            elif type_id == "temperatureSensor":
                # Thermostat validation and option settings
                if not values_dict.get("uspTemperature", False):
                    error_message = "An Indigo Thermostat device requires an association to the Hubitat 'temperature' property"
                    error_dict['uspTemperature'] = error_message
                    error_dict["showAlertText"] = error_message
                else:
                    values_dict["supportsTemperatureReporting"] = True
                    values_dict["NumTemperatureInputs"] = 1
                    values_dict["SupportsSensorValue"] = True

            # ============================ Process Any Errors =============================
            if len(error_dict) > 0:
                return False, values_dict, error_dict
            else:
                values_dict["hubitatPropertiesInitialised"] = True
                return True, values_dict

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def validatePrefsConfigUi(self, values_dict): # noqa [Method is not declared static] 
        try:
            if len(values_dict["mqttHubitatDeviceMessageFilter"]) == 0:
                values_dict["mqttHubitatDeviceMessageFilter"] = ["-0-"]  # '-- Don't Log Any Devices --'
            else:
                for entry in values_dict["mqttHubitatDeviceMessageFilter"]:
                    entry_key = entry.split("|||")[0]
                    if entry_key == "-0-":  # '-- Don't Log Any Devices --'
                        values_dict["mqttHubitatDeviceMessageFilter"] = ["-0-|||-- Don't Log Any Devices --"]
                        break
                    elif entry_key == "-1-":  # '-- Log All Devices --'
                        values_dict["mqttHubitatDeviceMessageFilter"] = ["-1-|||-- Log All Devices --"]
                        break

            if len(values_dict["mqttTasmotaMessageFilter"]) == 0:
                values_dict["mqttTasmotaMessageFilter"] = ["-0-"]  # '-- Don't Log Any Devices --'
            else:
                for entry in values_dict["mqttTasmotaMessageFilter"]:
                    entry_key = entry.split("|||")[0]
                    if entry_key == "-0-":  # '-- Don't Log Any Devices --'
                        values_dict["mqttTasmotaMessageFilter"] = ["-0-|||-- Don't Log Any Devices --"]
                        break
                    elif entry_key == "-1-":  # '-- Log All Devices --'
                        values_dict["mqttTasmotaMessageFilter"] = ["-1-|||-- Log All Devices --"]
                        break

            return True, values_dict

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    #################################
    #
    # Start of bespoke plugin methods
    #
    #################################

    def listDeviceStateMenuOptions(self, filter="", valuesDict=None, typeId="", targetId=0):   # noqa [parameter value is not used]
        try:

            # <Option value="0">Primary Device - Main UI State</Option>
            # <Option value="1">Primary Device - Additional State</Option>
            # <Option value="2">Secondary Device</Option>
            # <Option value="3">Primary Device - Additional UI State</Option>

            if ((filter == "button" and typeId == "button") or
                    (filter == "contactSensor" and typeId == "contactSensor") or
                    (filter == "dimmer" and typeId == "blind") or
                    (filter == "dimmer" and typeId == "dimmer") or
                    (filter == "humiditySensor" and typeId == "humiditySensor") or
                    (filter == "illuminanceSensor" and typeId == "illuminanceSensor") or
                    (filter == "motionSensor" and typeId == "motionSensor") or
                    (filter == "motionSensor" and typeId == "multiSensor") or
                    (filter == "onoff" and typeId == "outlet") or
                    (filter == "temperatureSensor" and typeId == "temperatureSensor") or
                    (filter == "temperatureSensor" and typeId == "thermostat")):
                menu_list = [("0", "Primary Device - Main UI State")]
            elif ((filter == "setpoint" and typeId == "thermostat") or
                  (filter == "onoff" and typeId == "thermostat") or
                  (filter == "onoff" and typeId == "blind") or
                  (filter == "onoff" and typeId == "dimmer")):
                menu_list = [("1", "Primary Device - Additional State")]
            else:
                menu_list = [("1", "Primary Device - Additional State"), ("2", "Secondary Device")]

            return menu_list

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def listHubitatHubs(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]
        try:
            self.logger.debug("List Hubitat Hubs")

            hubitat_hubs_list = list()
            hubitat_hubs_list.append(("-SELECT-", "-- Select Hubitat Hub --"))
            for dev in indigo.devices.iter("self"):
                if dev.deviceTypeId == "hubitatElevationHub":
                    hubitat_hubs_list.append((dev.address, dev.name))

            if len(hubitat_hubs_list) > 1:
                return sorted(hubitat_hubs_list, key=lambda name: name[1].lower())   # sort by hubitat hub name
            else:
                hubitat_hubs_list = list()
                hubitat_hubs_list.append(("-NONE-", "No Hubitat hubs available"))
                return hubitat_hubs_list
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def listHubitatHubSelected(self, valuesDict, typeId, devId):  # noqa [parameter value is not used]
        try:
            # do whatever you need to here
            #   typeId is the device type specified in the Devices.xml
            #   devId is the device ID - 0 if it's a new device
            self.logger.debug(f"Hubitat Hub Selected: {valuesDict['hubitatHubName']}")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        return valuesDict

    def listHubitatDevices(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]
        try:
            hubitat_devices_list = list()

            hubitat_hub_name = valuesDict["hubitatHubName"]
            if hubitat_hub_name == "-SELECT-":
                hubitat_devices_list.append(("-FIRST-", "^^^ Select Hubitat Hub First ^^^"))
                return hubitat_devices_list
            elif hubitat_hub_name == "-NONE-":
                hubitat_devices_list.append(("-NONE-", "^^^ No Hubitat hubs available ^^^"))
                return hubitat_devices_list

            # build list of Indigo primary devices already allocated to Hubitat devices
            allocated_devices = dict()
            for dev in indigo.devices.iter("self"):
                if dev.id != targetId and dev.deviceTypeId in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES:
                    dev_props = dev.ownerProps
                    hubitat_device_name = dev_props.get("hubitatDevice", "")
                    if hubitat_device_name != "":
                        if hubitat_device_name not in allocated_devices:
                            allocated_devices[hubitat_device_name] = dev.id
            # self.logger.warning(f"List of allocated Devices: {allocated_devices}")

            dev = indigo.devices[targetId]
            try:
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            except Exception:
                hubitat_hub_dev_id = 0

            self.logger.debug("List Hubitat Devices [1]")

            if hubitat_hub_dev_id > 0 and hubitat_hub_dev_id in indigo.devices:

                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                hubitat_devices_list.append(("-SELECT-", "-- Select Hubitat Device --"))
                for hubitat_device_name, hubitat_devices_details in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES].items():
                    # already_allocated = False
                    if hubitat_device_name in allocated_devices:
                        continue  # Continue as already allocated

                    hubitat_device_properties = list()
                    if HE_PROPERTIES in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                        if self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] is not None:
                            # self.logger.warning(f"listHubitatDevices - PROPERTIES: {self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES]}")
                            hubitat_device_properties = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES].replace(" ", "").split(",")

                    # device_type_supported_hubitat_properties = HE_DEVICE_TYPES_MAIN_HABITAT_PROPERTIES[dev.deviceTypeId]
                    for device_type_main_hubitat_properties in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES[dev.deviceTypeId]:
                        if device_type_main_hubitat_properties in hubitat_device_properties:
                            hubitat_devices_list.append((hubitat_device_name, hubitat_device_name))
                            break

            if len(hubitat_devices_list) > 1:
                return sorted(hubitat_devices_list, key=lambda name: name[1].lower())   # sort by hubitat device name
            else:
                if hubitat_hub_dev_id  == 0:
                    hubitat_devices_list = list()
                    hubitat_devices_list.append(("-FIRST-", "^^^ Select Hubitat Hub First ^^^"))
                else:
                    hubitat_devices_list = list()
                    hubitat_devices_list.append(("-SELECT-", f"No \"{typeId}\" devices available"))

                return hubitat_devices_list

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def listTasmotaDeviceSelected(self, valuesDict, typeId, devId):  # noqa [parameter value is not used]
        try:
            # props = indigo.devices[devId].ownerProps
            pass
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def listHubitatDeviceSelected(self, valuesDict, typeId, devId):
        try:
            # do whatever you need to here
            #   typeId is the device type specified in the Devices.xml
            #   devId is the device ID - 0 if it's a new device

            hubitat_hub_name = valuesDict["hubitatHubName"]

            if hubitat_hub_name == "-SELECT-" or hubitat_hub_name == "-NONE-":
                return

            dev = indigo.devices[devId]
            try:
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            except IndexError:
                hubitat_hub_dev_id = 0

            self.logger.debug(f"Hubitat Device Selected: {valuesDict['hubitatDevice']} on Indigo Device ID {int(hubitat_hub_dev_id)}")

            hubitat_device_name = valuesDict.get("hubitatDevice", "-SELECT-")

            # hubitat_device_properties_list = []
            if hubitat_device_name == "-SELECT-" or hubitat_device_name == "-NONE-" or hubitat_device_name == "-FIRST-":
                return

            if hubitat_hub_dev_id > 0 and hubitat_hub_dev_id in indigo.devices:
                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                hubitat_device_name = valuesDict.get("hubitatDevice", "-SELECT-")
                if hubitat_device_name != "" and hubitat_device_name in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:

                    valuesDict["hubitatDeviceDriver"] = "-"
                    if HE_DEVICE_DRIVER in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                        if (self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] is not None and
                                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] != ""):
                            valuesDict["hubitatDeviceDriver"] = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER]

                    hubitat_device_properties = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES].replace(" ", "").split(",")

                    for hubitat_device_property in hubitat_device_properties:

                        if hubitat_device_property == "acceleration":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyAcceleration"] = True
                            else:
                                valuesDict["hubitatPropertyAcceleration"] = False

                        elif hubitat_device_property == "measure-battery" or hubitat_device_property == "battery":
                            hubitat_device_property = "battery"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyBattery"] = True
                            else:
                                valuesDict["hubitatPropertyBattery"] = False

                        elif hubitat_device_property == "button":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyButton"] = True
                            else:
                                valuesDict["hubitatPropertyButton"] = False

                        elif hubitat_device_property == "position":
                            if dev.deviceTypeId == "blind":
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyPosition"] = True
                                else:
                                    valuesDict["hubitatPropertyPosition"] = False

                        elif hubitat_device_property == "dim":
                            if dev.deviceTypeId == "dimmer":
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyDim"] = True
                                else:
                                    valuesDict["hubitatPropertyDim"] = False

                            elif dev.deviceTypeId == "thermostat":
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyValve"] = True
                                else:
                                    valuesDict["hubitatPropertyValve"] = False

                            elif dev.deviceTypeId == "valveSecondary":
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyValve"] = True
                                else:
                                    valuesDict["hubitatPropertyValve"] = False

                        elif hubitat_device_property == "color-name":  # TODO: Should really be checking for 'color' - awaiting fix from Kevin
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyColor"] = True
                            else:
                                valuesDict["hubitatPropertyColor"] = False

                        elif hubitat_device_property == "color-temperature":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyColorTemperature"] = True
                            else:
                                valuesDict["hubitatPropertyColorTemperature"] = False

                        elif hubitat_device_property == "contact":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyContact"] = True
                            else:
                                valuesDict["hubitatPropertyContact"] = False

                        elif hubitat_device_property == "measure-energy" or hubitat_device_property == "energy":
                            hubitat_device_property = "energy"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyEnergy"] = True
                            else:
                                valuesDict["hubitatPropertyEnergy"] = False

                        elif hubitat_device_property == "measure-humidity" or hubitat_device_property == "humidity":
                            hubitat_device_property = "humidity"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyHumidity"] = True
                            else:
                                valuesDict["hubitatPropertyHumidity"] = False

                        elif hubitat_device_property == "measure-illuminance" or hubitat_device_property == "illuminance":
                            hubitat_device_property = "illuminance"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyIlluminance"] = True
                            else:
                                valuesDict["hubitatPropertyIlluminance"] = False

                        elif hubitat_device_property == "motion":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyMotion"] = True
                            else:
                                valuesDict["hubitatPropertyMotion"] = False

                        elif hubitat_device_property == "onoff":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyOnOff"] = True
                            else:
                                valuesDict["hubitatPropertyOnOff"] = False

                        elif hubitat_device_property == "measure-power" or hubitat_device_property == "power":
                            hubitat_device_property = "power"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyPower"] = True
                            else:
                                valuesDict["hubitatPropertyPower"] = False

                        elif hubitat_device_property == "presence-sensor" or hubitat_device_property == "presence":
                            hubitat_device_property = "presence"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyPresence"] = True
                            else:
                                valuesDict["hubitatPropertyPresence"] = False

                        elif hubitat_device_property == "pressure":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyPressure"] = True
                            else:
                                valuesDict["hubitatPropertyPressure"] = False

                        elif hubitat_device_property == "measure-temperature" or hubitat_device_property == "temperature":
                            hubitat_device_property = "temperature"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyTemperature"] = True
                            else:
                                valuesDict["hubitatPropertyTemperature"] = False

                        elif hubitat_device_property == "thermostat-setpoint":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertySetpoint"] = True
                            else:
                                valuesDict["hubitatPropertySetpoint"] = False

                        elif hubitat_device_property == "measure-voltage" or hubitat_device_property == "voltage":
                            hubitat_device_property = "voltage"
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyVoltage"] = True
                            else:
                                valuesDict["hubitatPropertyVoltage"] = False

                        elif hubitat_device_property == "mode":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyHvacMode"] = True
                            else:
                                valuesDict["hubitatPropertyHvacMode"] = False

                        elif hubitat_device_property == "state":
                            if dev.deviceTypeId == "thermostat" :
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyHvacState"] = True
                                else:
                                    valuesDict["hubitatPropertyHvacState"] = False
                            elif dev.deviceTypeId == "dimmer" and dev.dev.subType == indigo.kDimmerDeviceSubType.Blind:
                                if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                    valuesDict["hubitatPropertyState"] = True
                                else:
                                    valuesDict["hubitatPropertyState"] = False

                        elif hubitat_device_property == "refresh":
                            if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                                valuesDict["hubitatPropertyRefresh"] = True
                            else:
                                valuesDict["hubitatPropertyRefresh"] = False

                        elif hubitat_device_property == "measure-water":
                            pass  # Property not supported

                        elif hubitat_device_property == "custom":
                            pass  # Property not supported

                        elif hubitat_device_property in "heating-setpoint,cooling-setpoint,thermostat-setpoint,mode,fanmode,state,modes,fanmodes":
                            pass  # Property not supported

                        else:
                            self.logger.warning(f"Hubitat Device '{hubitat_device_name}' has unsupported property '{hubitat_device_property}'")

            # Consistency checking for dimmer (color / white) - only allow color and/or white if dim is true
            if not valuesDict.get("hubitatPropertyDim", False):
                valuesDict["hubitatPropertyColor"] = False
                valuesDict["hubitatPropertyColorTemperature"] = False

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        return valuesDict

    def listHubitatDeviceProperties(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]

        try:
            hubitat_device_name = valuesDict.get("hubitatDevice", "-NONE-")

            hubitat_device_properties_list = []
            if hubitat_device_name == "-SELECT-" or hubitat_device_name == "-NONE-" or hubitat_device_name == "-FIRST-":
                return hubitat_device_properties_list

            hubitat_hub_name = valuesDict["hubitatHubName"]
            if hubitat_hub_name == "-SELECT-" or hubitat_hub_name == "-NONE-":
                return hubitat_device_properties_list

            # dev = indigo.devices[targetId]
            try:
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            except IndexError:
                hubitat_hub_dev_id = 0

            if hubitat_hub_dev_id > 0 and hubitat_hub_dev_id in indigo.devices:
                hub_props = indigo.devices[hubitat_hub_dev_id].ownerProps
                hubitat_hub_name = hub_props["hub_name"]

                hubitat_device_name = valuesDict.get("hubitatDevice", "-SELECT-")
                if hubitat_device_name != "" and hubitat_device_name in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:
                    if self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] is not None:
                        hubitat_device_properties = self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES].replace(" ", "").split(",")
                        for hubitat_device_property in hubitat_device_properties:
                            # if hubitat_device_property in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES:
                            #     if typeId in HE_PROPERTIES_SUPPORTED_BY_DEVICE_TYPES[hubitat_device_property]:
                            #         if hubitat_device_property == "dim" and (typeId == "thermostat" or typeId == "valveSecondary"):
                            #             hubitat_device_property_ui = "valve (dim)"
                            #         else:
                            #              hubitat_device_property_ui = f"{hubitat_device_property}"
                            #     else:
                            #         hubitat_device_property_ui = f"{hubitat_device_property} [n/a]"
                            #     hubitat_device_properties_list.append((hubitat_device_property, hubitat_device_property_ui))

                            hubitat_device_property_ui = f"{hubitat_device_property}"
                            if hubitat_device_property in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES[typeId]:
                                hubitat_device_property_ui = f"{hubitat_device_property} [Primary]"
                            elif hubitat_device_property == "dim" and typeId == "thermostat":
                                hubitat_device_property_ui = "valve [dim]"
                            if hubitat_device_property_ui[0:8] == "measure-":
                                hubitat_device_property_ui = hubitat_device_property[8:]
                            hubitat_device_properties_list.append((hubitat_device_property, hubitat_device_property_ui))

                # Bespoke property fix(es). TODO: Remove this code once HE MQTT has been fixed
                hubitat_device_driver = valuesDict.get("hubitatDeviceDriver", "")
                if hubitat_device_driver == "Xiaomi Aqara Mijia Sensors and Switches":
                    if "pressure" not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES]:
                        hubitat_device_properties_list.append(("pressure", "pressure"))
                        self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] = f"{self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES]},pressure"

            self.logger.debug(f"Hubitat Device Properties: {hubitat_device_properties_list}")

            return sorted(hubitat_device_properties_list, key=lambda name: name[1].lower())   # sort by hubitat device property name

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def listTasmotaDevices(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]
        try:
            tasmota_devices_list = []

            tasmota_devices_list.append(("-SELECT-", "-- Select --"))

            for tasmota_key, tasmota_device_details in self.globals[TASMOTA][TASMOTA_DEVICES].items():
                # Only list current Tasmota device and unallocated Tasmota devices
                if (tasmota_device_details[TASMOTA_INDIGO_DEVICE_ID] == 0 or
                        tasmota_device_details[TASMOTA_INDIGO_DEVICE_ID] == targetId):
                    if tasmota_device_details[TASMOTA_PAYLOAD_FRIENDLY_NAME] != "":
                        tasmota_ui_name = f"{tasmota_device_details[TASMOTA_PAYLOAD_FRIENDLY_NAME]} [{tasmota_key}]"
                    else:
                        tasmota_ui_name = f"Undiscovered? [{tasmota_key}]"
                    tasmota_devices_list.append((tasmota_key, tasmota_ui_name))

                if len(tasmota_devices_list) == 1:
                    tasmota_devices_list = [("-NONE-", "-- None --")]
                    pass
            return sorted(tasmota_devices_list, key=lambda name: name[1].lower())   # sort by Tasmota Key device name
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def mqttListHubitatDevices(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]
        try:
            hubitat_devices_list = []

            self.logger.debug("MQTT List Hubitat Devices [1]")

            hubitat_devices_list.append(("-0-|||-- Don't Log Any Devices --", "-- Don't Log Any Devices --"))
            hubitat_devices_list.append(("-1-|||-- Log All Devices --", "-- Log All Devices --"))

            # for hubitat_hub_name in iter(self.globals[HE_HUBS].keys()):  # TODO: Python 3
            for hubitat_hub_name in self.globals[HE_HUBS].keys():  # TODO: Python 2
                hubitat_hub_and_device_name_key = f"{hubitat_hub_name}|||{'hub'}"
                hubitat_hub_and_device_name_value = f"{hubitat_hub_name} | {'hub'}"
                hubitat_devices_list.append((hubitat_hub_and_device_name_key, hubitat_hub_and_device_name_value))
                for hubitat_device_name, hubitat_devices_details in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES].items():
                    hubitat_hub_and_device_name_key = f"{hubitat_hub_name}|||{hubitat_device_name}"
                    hubitat_hub_and_device_name_value = f"{hubitat_hub_name} | {hubitat_device_name}"
                    if hubitat_device_name != "hub":
                        hubitat_devices_list.append((hubitat_hub_and_device_name_key, hubitat_hub_and_device_name_value))
            return sorted(hubitat_devices_list, key=lambda name: name[1].lower())   # sort by hubitat device name
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def mqttListExportDevices(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]
        try:
            export_devices_list = list()

            export_devices_list.append((0, "-- Don't Log Any Devices --"))
            export_devices_list.append((1, "-- Log All Devices --"))

            for dev in indigo.devices:
                if dev.pluginId != "com.autologplugin.indigoplugin.hubitat":
                    if bool(dev.pluginProps.get("export_enabled", False)):
                        export_devices_list.append((dev.id, dev.name))

            return sorted(export_devices_list, key=lambda name: name[1].lower())   # sort by export device name
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def mqttListTasmotaDevices(self, filter="", valuesDict=None, typeId="", targetId=0):  # noqa [parameter value is not used]
        try:
            tasmota_devices_list = []

            self.logger.debug("MQTT List Tasmota Devices [1]")

            tasmota_devices_list.append(("-0-|||-- Don't Log Any Devices --", "-- Don't Log Any Devices --"))
            tasmota_devices_list.append(("-1-|||-- Log All Devices --", "-- Log All Devices --"))

            for tasmota_key, tasmota_device_details in self.globals[TASMOTA][TASMOTA_DEVICES].items():
                # self.logger.warning(f"TK = '{tasmota_key}', TDD:\n{tasmota_device_details}")
                tasmota_friendly_name = f"{tasmota_device_details[TASMOTA_PAYLOAD_FRIENDLY_NAME]}"
                if tasmota_friendly_name == "":
                    tasmota_friendly_name = f"Undiscovered: {tasmota_key}"
                tasmota_full_key = f"{tasmota_key}|||{tasmota_friendly_name}"
                tasmota_devices_list.append((tasmota_full_key, tasmota_friendly_name))
            return sorted(tasmota_devices_list, key=lambda name: name[1].lower())   # sort by Tasmota Key device name
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def refreshHubitatDevice(self, valuesDict=None, typeId="", targetId=0):
        try:
            values_dict_updated = self.listHubitatDeviceSelected(valuesDict, typeId, targetId)

            return values_dict_updated

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def optionally_set_indigo_2021_device_sub_type(self, dev):
        try:
            if dev.deviceTypeId == "contactSensor":
                if dev.subType != indigo.kSensorDeviceSubType.DoorWindow:
                    dev.subType = indigo.kSensorDeviceSubType.DoorWindow
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "dimmer":
                if dev.ownerProps.get("SupportsColor", False):
                    dev_subtype_to_test_against = indigo.kDimmerDeviceSubType.ColorDimmer
                else:
                    dev_subtype_to_test_against = indigo.kDimmerDeviceSubType.Dimmer
                if dev.subType != dev_subtype_to_test_against:
                    dev.subType = dev_subtype_to_test_against
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "humiditySensor" or dev.deviceTypeId == "humiditySensorSecondary":
                if dev.subType != indigo.kSensorDeviceSubType.Humidity:
                    dev.subType = indigo.kSensorDeviceSubType.Humidity
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "illuminanceSensor" or dev.deviceTypeId == "illumianceSensorSecondary":
                if dev.subType != indigo.kSensorDeviceSubType.Illuminance:
                    dev.subType = indigo.kSensorDeviceSubType.Illuminance
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "motionSensor" or dev.deviceTypeId == "multiSensor" or dev.deviceTypeId == "motionSensorSecondary":
                if dev.subType != indigo.kSensorDeviceSubType.Motion:
                    dev.subType = indigo.kSensorDeviceSubType.Motion
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "outlet":
                if dev.subType != indigo.kRelayDeviceSubType.Outlet:
                    dev.subType = indigo.kRelayDeviceSubType.Outlet
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "temperatureSensor" or dev.deviceTypeId == "temperatureSensorSecondary":
                if dev.subType != indigo.kSensorDeviceSubType.Temperature:
                    dev.subType = indigo.kSensorDeviceSubType.Temperature
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "accelerationSensorSecondary":
                if dev.subType != indigo.kDeviceSubType.Security:
                    dev.subType = indigo.kDeviceSubType.Security
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "presenceSensorSecondary":
                if dev.subType != indigo.kSensorDeviceSubType.Presence:
                    dev.subType = indigo.kSensorDeviceSubType.Presence
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "pressureSensorSecondary":
                if dev.subType != indigo.kSensorDeviceSubType.Pressure:
                    dev.subType = indigo.kSensorDeviceSubType.Pressure
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "valveSecondary":
                if dev.subType != indigo.kDimmerDeviceSubType.Valve:
                    dev.subType = indigo.kDimmerDeviceSubType.Valve
                    dev.replaceOnServer()
            elif dev.deviceTypeId == "voltageSensorSecondary":
                if dev.subType != indigo.kSensorDeviceSubType.Voltage:
                    dev.subType = indigo.kSensorDeviceSubType.Voltage
                    dev.replaceOnServer()

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def setWhiteLevelTemperature(self, action, dev):
        try:
            # dev_id = dev.id

            dev_props = dev.pluginProps

            if "hubitatDevice" in dev_props:
                hubitat_device_name = dev_props["hubitatDevice"]
                hubitat_hub_name = dev_props.get("hubitatHubName", "")
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            elif "linkedPrimaryIndigoDeviceId" in dev_props:
                hubitat_device_name = dev_props["associatedHubitatDevice"]
                linked_indigo_device_id = int(dev_props.get("linkedPrimaryIndigoDeviceId", 0))
                linked_indigo_dev = indigo.devices[linked_indigo_device_id]
                linked_dev_props = linked_indigo_dev.pluginProps
                hubitat_hub_name = linked_dev_props.get("hubitatHubName", "")
                hubitat_hub_dev_id = int(self.globals[HE_HUBS][hubitat_hub_name][HE_INDIGO_HUB_ID])
            else:
                self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as unable to resolve Hubitat Hub device.")
                return

            if hubitat_hub_dev_id > 0:
                mqtt_connected = False
                for mqtt_broker_device_id in self.globals[HE_HUBS][hubitat_hub_name][MQTT_BROKERS]:
                    if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                        mqtt_connected = True
                        break
                if not mqtt_connected:
                    self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as Hubitat Hub device '{hubitat_hub_name}' is not initialised. Is MQTT running?")
                    return
            else:
                self.logger.warning(f"Unable to perform '{action.description}' action for '{dev.name}' as unable to resolve Hubitat Hub device.")
                return

            mqtt_filter_key = f"{hubitat_hub_name.lower()}|{hubitat_device_name.lower()}"

            self.process_set_white_level_temperature(action, dev, hubitat_hub_name, mqtt_filter_key)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_set_white_level_temperature(self, action, dev, hubitat_hub_name, mqtt_filter_key):
        try:
            dev_props = dev.pluginProps
            hubitat_device_name = dev_props["hubitatDevice"]

            set_white_level = bool(action.props.get("setWhiteLevel", True))
            white_level = int(float(action.props.get("whiteLevel", 100.0)))
            set_white_temperature = bool(action.props.get("setWhiteTemperature", True))
            white_temperature = int(float(action.props.get("whiteTemperature", 3500)))

            kelvin_description = ""  # Only needed to suppress a PyCharm warning!

            if set_white_level:
                topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/dim/set"  # e.g. "homie/home-1/study-lamp_rgbw/dim/set"
                topic_payload = f"{white_level}"
                self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                if not set_white_temperature:
                    self.logger.info(f"sent \"{dev.name}\" set White Level to \"{int(white_level)}\"")

            if set_white_temperature:
                kelvin = min(ROUNDED_KELVINS, key=lambda x: abs(x - white_temperature))
                rgb, kelvin_description = ROUNDED_KELVINS[kelvin]

                topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/color-temperature/set"  # e.g. "homie/home-1/study-lamp_rgbw/color-temperature/set"
                topic_payload = f"{white_temperature}"
                self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                if not set_white_level:
                    self.logger.info(f"sent \"{dev.name}\" set White Temperature to \"{white_temperature}K [{kelvin_description}]\"")

            if set_white_level and set_white_temperature:
                self.logger.info(f"sent \"{dev.name}\" set White Level to \"{int(white_level)}\" and White Temperature to \"{white_temperature}K [{kelvin_description}]\"")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_set_color_levels(self, action, dev, hubitat_hub_name, mqtt_filter_key):
        try:
            self.logger.debug(f"processSetColorLevels ACTION:\n{action} ")

            dev_props = dev.pluginProps
            hubitat_device_name = dev_props["hubitatDevice"]

            # Determine Color / White Mode
            color_mode = False

            # First check if color is being set by the action Set RGBW levels
            if "redLevel" in action.actionValue and \
                    "greenLevel" in action.actionValue and \
                    "blueLevel" in action.actionValue:
                if float(action.actionValue["redLevel"]) > 0.0 or \
                        float(action.actionValue["greenLevel"]) > 0.0 or \
                        float(action.actionValue["blueLevel"]) > 0.0:
                    color_mode = True

            if (not color_mode) and (("whiteLevel" in action.actionValue) or ("whiteTemperature" in action.actionValue)):
                # If either of "whiteLevel" or "whiteTemperature" are altered - assume mode is White

                white_level = int(dev.states["whiteLevel"])
                white_temperature = int(dev.states["whiteTemperature"])

                if "whiteLevel" in action.actionValue:
                    white_level = int(float(action.actionValue["whiteLevel"]))

                if "whiteTemperature" in action.actionValue:
                    white_temperature = int(action.actionValue["whiteTemperature"])

                kelvin = min(ROUNDED_KELVINS, key=lambda x: abs(x - white_temperature))
                rgb, kelvin_description = ROUNDED_KELVINS[kelvin]

                topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/color-temperature/set"  # e.g. "homie/home-1/study-lamp_rgbw/color-temperature/set"
                topic_payload = f"{white_temperature}"
                self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/dim/set"  # e.g. "homie/home-1/study-lamp_rgbw/dim/set"
                topic_payload = f"{white_level}"
                self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)
                self.logger.info(f"sent \"{dev.name}\" set White Level to \"{int(white_level)}\" and White Temperature to \"{white_temperature}K [{kelvin_description}]\"")

            else:
                # As neither of "whiteTemperature" or "whiteTemperature" are set - assume mode is Colour

                props = dev.pluginProps
                if ("SupportsRGB" in props) and props["SupportsRGB"]:  # Check device supports color
                    red_level = float(dev.states["redLevel"])
                    green_level = float(dev.states["greenLevel"])
                    blue_level = float(dev.states["blueLevel"])

                    if "redLevel" in action.actionValue:
                        red_level = float(action.actionValue["redLevel"])
                    if "greenLevel" in action.actionValue:
                        green_level = float(action.actionValue["greenLevel"])
                    if "blueLevel" in action.actionValue:
                        blue_level = float(action.actionValue["blueLevel"])

                    # red = int((red_level * 256.0) / 100.0)
                    # red = 255 if red > 255 else red
                    # green = int((green_level * 256.0) / 100.0)
                    # green = 255 if green > 255 else green
                    # blue = int((blue_level * 256.0) / 100.0)
                    # blue = 255 if blue > 255 else blue
                    #
                    # he_rgb = f"#{red:02x}{green:02x}{blue:02x}".upper()
                    # he_rgb2 = f"RED:{red:02x}, GREEN:{green:02x}, BLUE:{blue:02x}".upper()

                    # Convert Indigo values for RGB (0-100) to colorSys values (0.0-1.0)
                    red = float(red_level / 100.0)  # e.g. 100.0/100.0 = 1.0
                    green = float(green_level / 100.0)  # e.g. 70.0/100.0 = 0.7
                    blue = float(blue_level / 100.0)  # e.g. 40.0/100.0 = 0.4

                    hsv_hue, hsv_saturation, hsv_value = colorsys.rgb_to_hsv(red, green, blue)

                    # Colorsys values for HSV are (0.0-1.0). Convert to to H (0-360), S (0 - 100) and V (0 - 100)
                    he_hue = int(hsv_hue * 360.0)
                    he_saturation = int(hsv_saturation * 100.0)
                    he_value = int(hsv_value * 100.0)

                    topic = f"{MQTT_ROOT_TOPIC}/{hubitat_hub_name}/{hubitat_device_name}/color/set"  # e.g. "homie/home-1/study-lamp_rgbw/color/rgb/set"

                    topic_payload = f"{he_hue},{he_saturation},{he_value}"
                    self.publish_hubitat_topic(mqtt_filter_key, hubitat_hub_name, topic, topic_payload)

                    self.logger.info(f"sent \"{dev.name}\" RGB Levels: Red {int(red_level)}%, Green {int(green_level)}%, Blue {int(blue_level)}% as HSV [{he_hue},{he_saturation},{he_value}]")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_hsm_secondary_device(self, hub_dev):
        try:
            hub_dev_id = hub_dev.id
            hub_dev_type_id = hub_dev.deviceTypeId
            hub_dev_sub_type = getattr(hub_dev, "subType", None)

            hub_props = hub_dev.ownerProps
            if "uspHsm" not in hub_props or not hub_props["uspHsm"]:
                return

            existing_secondary_dev_id_list = indigo.device.getGroupList(hub_dev_id)
            existing_secondary_dev_id_list.remove(hub_dev_id)  # Remove Hub device

            if len(existing_secondary_dev_id_list) > 0:  # Check if HSM secondary device already created
                return

            hsm_type_id = "hsmSensorSecondary"
            if hub_dev_sub_type is not None:  # If subType property supported for primary device - assume supported on Secondary
                usp_indigo = INDIGO_SUB_TYPE_INFO[hsm_type_id][1][0]
            else:
                usp_indigo = INDIGO_SUB_TYPE_INFO[hsm_type_id][1][1]

            # Create Secondary HSM Device

            secondary_name = f"{hub_dev.name} [{usp_indigo}]"  # Create default name
            # Check name is unique and if not, make it so
            if secondary_name in indigo.devices:
                name_check_count = 1
                while True:
                    check_name = f"{secondary_name}_{name_check_count}"
                    if check_name not in indigo.devices:
                        secondary_name = check_name
                        break
                    name_check_count += 1

            required_props_list = INDIGO_SUB_TYPE_INFO[hsm_type_id][2]
            props_dict = dict()
            props_dict["hubitatHubName"] = hub_dev.address
            props_dict["hubitatPropertiesInitialised"] = True
            props_dict["member_of_device_group"] = True
            props_dict["linkedPrimaryIndigoDeviceId"] = hub_dev.id
            props_dict["linkedPrimaryIndigoDevice"] = hub_dev.name
            props_dict["associatedHubitatDevice"] = "hub"

            for key, value in required_props_list:
                props_dict[key] = value

            hsm_secondary_device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                                                        address=hub_dev.address,
                                                        description="",
                                                        name=secondary_name,
                                                        folder=hub_dev.folderId,
                                                        pluginId="com.autologplugin.indigoplugin.hubitat",
                                                        deviceTypeId=hsm_type_id,
                                                        groupWithDevice=hub_dev_id,
                                                        props=props_dict)

            # Manually need to set the model and subModel names (for UI only)
            hsm_dev_id = hsm_secondary_device.id
            hsm_secondary_device = indigo.devices[hsm_dev_id]  # Refresh Indigo Device to ensure groupWithDevice isn't removed
            hsm_secondary_device.model = hub_dev.model

            if hasattr(hsm_secondary_device, "subType"):
                hsm_secondary_device.subType = ""
            else:
                hsm_secondary_device.subModel = usp_indigo

            hsm_secondary_device.configured = True
            hsm_secondary_device.enabled = True
            hsm_secondary_device.replaceOnServer()

            hub_dev = indigo.devices[hub_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed

            if hasattr(hub_dev, "subType"):
                if hub_dev.subType != INDIGO_PRIMARY_DEVICE_INFO[hub_dev_type_id][0]:
                    hub_dev.subType = INDIGO_PRIMARY_DEVICE_INFO[hub_dev_type_id][0]
                    hub_dev.replaceOnServer()
            else:
                if hub_dev.subModel != INDIGO_PRIMARY_DEVICE_INFO[hub_dev_type_id][1]:
                    hub_dev.subModel = INDIGO_PRIMARY_DEVICE_INFO[hub_dev_type_id][1]
                    hub_dev.replaceOnServer()

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def process_sub_models(self, primary_dev, hubitat_hub_name):
        try:
            primary_dev_id = primary_dev.id
            primary_dev_type_id = primary_dev.deviceTypeId
            # primary_dev_sub_type = getattr(primary_dev, "subType", None)

            if primary_dev_type_id not in INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE or len(INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE[primary_dev_type_id]) == 0:
                return

            existing_secondary_dev_id_list = indigo.device.getGroupList(primary_dev_id)
            existing_secondary_dev_id_list.remove(primary_dev_id)  # Remove Primary device

            existing_secondary_devices = dict()
            for existing_secondary_dev_id in existing_secondary_dev_id_list:
                existing_secondary_devices[indigo.devices[existing_secondary_dev_id].deviceTypeId] = existing_secondary_dev_id

            # At this point we have created a dictionary of sub-model types with their associated Indigo device Ids

            primary_dev_props = primary_dev.pluginProps
            hubitat_device_name = primary_dev_props["hubitatDevice"]

            pass

            for secondary_type_id in INDIGO_SUPPORTED_SUB_TYPES_BY_DEVICE[primary_dev_type_id]:

                # note "usp" prefix stands for "User Selectable Property" :)
                usp_indigo_name = INDIGO_SUB_TYPE_INFO[secondary_type_id][0]  # e.g. "uspIlluminanceIndigo"

                usp_native = usp_indigo_name[:-6]  # Remove 'Indigo' from usp e.g. "uspIlluminanceIndigo" . "uspIlluminance"

                # TODO: CHECK FOR USP = TRUE
                usp_required = False
                if usp_native in primary_dev_props and primary_dev_props[usp_native]:
                    usp_required = True

                if not usp_required or primary_dev_props.get(usp_indigo_name, INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) != INDIGO_SECONDARY_DEVICE:
                    # At this point the property is not required or
                    #   the state associated with the property is not required in a secondary device
                    #   therefore, if it exists, remove it.
                    if secondary_type_id in existing_secondary_devices:
                        secondary_device_id = existing_secondary_devices[secondary_type_id]
                        secondary_dev = indigo.devices[secondary_device_id]

                        indigo.device.ungroupDevice(secondary_dev)
                        secondary_dev.refreshFromServer()
                        primary_dev.refreshFromServer()

                        secondary_dev_props = secondary_dev.ownerProps
                        secondary_dev_props["member_of_device_group"] = False  # Reset to False as no longer a member of a device group
                        secondary_dev.replacePluginPropsOnServer(secondary_dev_props)

                        ungrouped_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ungrouped_name = f"{secondary_dev.name} [UNGROUPED @ {ungrouped_time}]"
                        secondary_dev.name = ungrouped_name
                        secondary_dev.replaceOnServer()

                        self.logger.warning(f"Secondary Device '{secondary_dev.name}' ungrouped from Primary Device '{primary_dev.name}' - please delete it!")

                        if hubitat_device_name in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:
                            with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                                if HE_LINKED_INDIGO_DEVICES in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                                    if secondary_device_id in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                                        del self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES][secondary_device_id]

                else:
                    # TODO: CHECK FOR USP = TRUE
                    if not usp_required:
                        continue  # As property not required, continue to check next secondary device type

                    if secondary_type_id not in existing_secondary_devices:

                        # Create Secondary Device

                        # TODO: ONLY CREATE IF IT IS REQUIRED - NEED TO CHECK USP SETTING I.E. IS PROPERTY REQUIRED OR VALID

                        if hasattr(primary_dev, "subType"):  # If subType property supported for primary device - assume supported on Secondary
                            usp_indigo_name = INDIGO_SUB_TYPE_INFO[secondary_type_id][1][0]
                        else:
                            usp_indigo_name = INDIGO_SUB_TYPE_INFO[secondary_type_id][1][1]

                        secondary_name = f"{primary_dev.name} [{usp_indigo_name}]"  # Create default name
                        # Check name is unique and if not, make it so
                        if secondary_name in indigo.devices:
                            name_check_count = 1
                            while True:
                                check_name = f"{secondary_name}_{name_check_count}"
                                if check_name not in indigo.devices:
                                    secondary_name = check_name
                                    break
                                name_check_count += 1

                        required_props_list = INDIGO_SUB_TYPE_INFO[secondary_type_id][2]
                        props_dict = dict()
                        props_dict["hubitatHubName"] = hubitat_hub_name
                        props_dict["hubitatPropertiesInitialised"] = True
                        props_dict["member_of_device_group"] = True
                        props_dict["linkedPrimaryIndigoDeviceId"] = primary_dev.id
                        props_dict["linkedPrimaryIndigoDevice"] = primary_dev.name
                        props_dict["associatedHubitatDevice"] = hubitat_device_name

                        for key, value in required_props_list:
                            props_dict[key] = value

                        primary_props = primary_dev.ownerProps
                        primary_hubitat_device = primary_props["hubitatDevice"]

                        secondary_dev = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                                                             address=primary_hubitat_device,
                                                             description="",
                                                             name=secondary_name,
                                                             folder=primary_dev.folderId,
                                                             pluginId="com.autologplugin.indigoplugin.hubitat",
                                                             deviceTypeId=secondary_type_id,
                                                             groupWithDevice=primary_dev_id,
                                                             props=props_dict)

                        # Manually need to set the model and subModel names (for UI only)
                        secondary_dev_id = secondary_dev.id
                        secondary_dev = indigo.devices[secondary_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed

                        self.optionally_set_indigo_2021_device_sub_type(secondary_dev)

                        if hubitat_device_name not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES]:
                            self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name] = dict()  # Hubitat device name
                        with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                            if HE_LINKED_INDIGO_DEVICES not in self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                                self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES] = dict()
                            self.globals[HE_HUBS][hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES][secondary_dev_id] = secondary_dev_id

                        # sub_model_device.model = primary_dev.model
                        #
                        # if hasattr(sub_model_device, "subType"):
                        #     sub_model_device.subType = ""
                        # else:
                        #     sub_model_device.subModel = usp_indigo_name
                        #
                        # sub_model_device.configured = True
                        # sub_model_device.enabled = True
                        # sub_model_device.replaceOnServer()
                        #
                        # dev = indigo.devices[primary_dev_id]  # Refresh Indigo Device to ensure groupWith Device isn't removed
                        #
                        # if hasattr(primary_dev, "subType"):
                        #     if dev.subType != INDIGO_PRIMARY_DEVICE_INFO[primary_dev_type_id][0]:
                        #         dev.subType = INDIGO_PRIMARY_DEVICE_INFO[primary_dev_type_id][0]
                        #         dev.replaceOnServer()
                        # else:
                        #     if dev.subModel != INDIGO_PRIMARY_DEVICE_INFO[primary_dev_type_id][1]:
                        #         dev.subModel = INDIGO_PRIMARY_DEVICE_INFO[primary_dev_type_id][1]
                        #         dev.replaceOnServer()

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def publish_hubitat_topic(self, hubitat_key, hubitat_hub_name, topic, payload):
        try:
            # TODO: self.globals[MQTT][MQTT_CONNECTED]
            published = False
            for mqtt_broker_device_id in self.globals[HE_HUBS][hubitat_hub_name][MQTT_BROKERS]:
                if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_broker_device_id][MQTT_PUBLISH_TO_HOMIE]:
                        self.globals[MQTT][mqtt_broker_device_id][MQTT_CLIENT].publish(topic, payload)
                        published = True

            if published:
                log_mqtt_msg = False  # Assume MQTT message should NOT be logged
                # Check if MQTT message filtering required
                if HE_MQTT_FILTERS in self.globals:
                    if len(self.globals[HE_MQTT_FILTERS]) > 0 and self.globals[HE_MQTT_FILTERS] != ["-0-"]:
                        # As entries exist in the filter list, only log MQTT message in Hubitat device in the filter list
                        if self.globals[HE_MQTT_FILTERS] == ["-1-"] or hubitat_key in self.globals[HE_MQTT_FILTERS]:
                            log_mqtt_msg = True
                if log_mqtt_msg:
                    self.logger.topic(f">>> Published to '{hubitat_hub_name}': Topic='{topic}', Payload='{payload}'")  # noqa [unresolved attribute reference]
            else:
                pass
                self.logger.error(f">>> MQTT not connected: Hubitat Topic='{topic}', Payload='{payload}' dropped")  # noqa [unresolved attribute reference]  # TODO: TESTING ONLY

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def publish_tasmota_topic(self, tasmota_key, topic, payload):
        try:
            published = False
            if tasmota_key not in self.globals[TASMOTA][MQTT_BROKERS]:
                return
            mqtt_broker_device_id = self.globals[TASMOTA][MQTT_BROKERS][tasmota_key]  # TODO: Not a list for Tasmota - just one broker
            if mqtt_broker_device_id != 0:
                if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_broker_device_id][MQTT_PUBLISH_TO_TASMOTA]:
                        self.globals[MQTT][mqtt_broker_device_id][MQTT_CLIENT].publish(topic, payload, 1, True)  # noqa [parameter value is not used] - n.b. QOS=1 Retain=True
                        published = True
            if published:
                log_mqtt_msg = False  # Assume MQTT message should NOT be logged
                # Check if MQTT message filtering required
                if TASMOTA_MQTT_FILTERS in self.globals:
                    if len(self.globals[TASMOTA_MQTT_FILTERS]) > 0 and self.globals[TASMOTA_MQTT_FILTERS] != ["-0-"]:
                        # As entries exist in the filter list, only log MQTT message in Tasmota device in the filter list
                        if self.globals[TASMOTA_MQTT_FILTERS] == ["-1-"] or tasmota_key in self.globals[TASMOTA_MQTT_FILTERS]:
                            log_mqtt_msg = True

                if log_mqtt_msg:
                    self.logger.topic(f">>> Published to Tasmota: Topic='{topic}', Payload='{payload.decode('utf-8')}'")  # noqa [unresolved attribute reference]
            else:
                pass
                self.logger.error(f">>> MQTT not connected: Tasmota Topic='{topic}', Payload='{payload}' dropped")  # noqa [unresolved attribute reference]  # TODO: TESTING ONLY

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def publish_export_topic(self, device_key, device_name, topic, payload):
        try:
            published = False
            for mqtt_broker_device_id in self.globals[EXPORT][MQTT_BROKERS]:
                if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_broker_device_id][MQTT_PUBLISH_TO_HOMIE]:
                        self.globals[MQTT][mqtt_broker_device_id][MQTT_CLIENT].publish(topic, payload, 1, True)  # noqa [parameter value is not used] - n.b. QOS=1 Retain=True
                        published = True

            published = False
            for mqtt_broker_device_id in self.globals[EXPORT][MQTT_BROKERS]:
                if self.globals[MQTT][mqtt_broker_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_broker_device_id][MQTT_PUBLISH_TO_HOMIE]:
                        self.globals[MQTT][mqtt_broker_device_id][MQTT_CLIENT].publish(topic, payload, 1, True)  # noqa [parameter value is not used] - n.b. QOS=1 Retain=True
                        published = True





            # Now check if topic should be logged
            if published:
                log_mqtt_msg = False  # Assume MQTT message should NOT be logged
                # Check if MQTT message filtering required
                if EXPORT_FILTERS in self.globals:
                    if len(self.globals[EXPORT_FILTERS]) > 0:
                        if len(self.globals[EXPORT_FILTERS]) == 1:
                            if self.globals[EXPORT_FILTERS][0] == "dev-none":
                                return
                            elif self.globals[EXPORT_FILTERS][0] == "dev-all":
                                log_mqtt_msg = True
                        else:
                            # As entries exist in the filter list, only log MQTT message in Export device in the filter list
                            if device_key in self.globals[EXPORT_FILTERS]:
                                log_mqtt_msg = True
                
                # Only log if check result is True
                if log_mqtt_msg:
                    if device_name is not None:
                        self.logger.topic(f">>> Published Indigo Exported: Topic='{topic}', Payload='{payload}' for {device_name}")
                    else:
                        self.logger.topic(f">>> Published Indigo Exported: Topic='{topic}', Payload='{payload}'")
                # self.logger.warning(f">>> Published Export [RC={rc}]: Topic='{topic}', Payload='{payload.decode('utf-8')}'")  # noqa [unresolved attribute reference]  # TODO: TESTING ONLY
            else:
                pass
                self.logger.error(f">>> MQTT not connected: Indigo Exported Topic='{topic}', Payload='{payload}' dropped")  # noqa [unresolved attribute reference]  # TODO: TESTING ONLY

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
