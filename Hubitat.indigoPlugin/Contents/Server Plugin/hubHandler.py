#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Hubitat - Hub Handler © Autolog 2021
#

import colorsys
try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

import logging
import queue
import sys
import threading
import traceback

from constants import *


def _no_image():
    try:
        return getattr(indigo.kStateImageSel, "NoImage")  # Python 3
    except AttributeError:
        return getattr(indigo.kStateImageSel, "None")  # Python 2


# noinspection PyPep8Naming
class ThreadHubHandler(threading.Thread):

    # This class handles Hubitat Hub processing

    def __init__(self, pluginGlobals, hubitat_hub_id, event):
        try:

            threading.Thread.__init__(self)

            self.globals = pluginGlobals

            self.hubHandlerLogger = logging.getLogger("Plugin.HE_HUB")

            self.threadStop = event

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]  # noqa [Ignore duplicate code warning]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method}'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.hubHandlerLogger.error(log_message)

    def run(self):
        try:
            while not self.threadStop.is_set():
                try:
                    mqtt_message_sequence, mqtt_process_command, mqtt_hub_id, mqtt_topics, mqtt_topics_list, mqtt_payload = self.globals[QUEUES][MQTT_HUB_QUEUE].get(True, 5)

                    if mqtt_process_command == MQTT_PROCESS_COMMAND_HANDLE_TOPICS:
                        self.handle_topics(mqtt_hub_id, mqtt_topics, mqtt_topics_list, mqtt_payload)

                except queue.Empty:
                    pass
                except Exception as exception_error:
                    self.exception_handler(exception_error, True)  # Log error and display failing statement
            else:
                pass
                # TODO: At this point, queue a recovery for n seconds time
                # TODO: In the meanwhile, just disable and then enable the Indigo Hubitat Elevation Hub device

            self.hubHandlerLogger.debug("Hub Handler Thread close-down commencing.")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handle_topics(self, hub_id, topics, topics_list, payload):
        # print(f"Payload Type: {type(payload)}")
        try:
            # Note that there are a minimum of three topic entries in the topiocs_list
            hub_name = topics_list[1]
            mclass_test = False  # TODO: MCLASS TEST DEBUG
            if hub_name == "qualia":  # TODO: MCLASS TEST DEBUG
                mclass_test = True  # TODO: MCLASS TEST DEBUG

            if hub_name in self.globals[HE_HUBS]:
                # TODO - Use passed hub_id
                # hub_id = self.globals[HE_HUBS][hub_name][HE_INDIGO_HUB_ID]
                hub_dev = indigo.devices[hub_id]
                if hub_id is None or hub_id == 0:
                    return
            else:
                return

            subscribed = False
            for mqtt_client_device_id in self.globals[HE_HUBS][hub_name][MQTT_BROKERS]:
                if self.globals[MQTT][mqtt_client_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_client_device_id][MQTT_SUBSCRIBE_TO_HOMIE]:
                        subscribed = True
                        break
            if not subscribed:
                return

            if hub_dev.states["status"] == "disconnected":
                hub_dev.updateStateOnServer(key=u'status', value="connected")
                hub_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            if len(topics_list) == 3 and topics_list[2] == "$heartbeat":
                heartbeat = int(payload.split(",")[0])
                hub_dev.updateStateOnServer(key='heartbeat', value=heartbeat)
                return
            elif topics_list[2] == "$fw":
                return
            elif topics_list[2] == "$state":
                return
            elif topics_list[2] == "$name":
                return
            elif topics_list[2] == "$nodes":
                return

            # At this point it should be a Hubitat device (including 'hub')

            keyValueList = [
                {'key': 'lastTopic', 'value': topics},
                {'key': 'lastPayload', 'value': payload}
            ]
            indigo.devices[hub_id].updateStatesOnServer(keyValueList)

            hubitat_device_name = topics_list[2]

            log_mqtt_msg = True  # Assume MQTT message should be logged
            # Check if MQTT message filtering required
            if HE_MQTT_FILTERS in self.globals:
                if len(self.globals[HE_MQTT_FILTERS]) > 0:
                    mqtt_filter_key = f"{hub_name.lower()}|||{hubitat_device_name.lower()}"
                    # As entries exist in the filter list, only log MQTT message in Hubitat device in the filter list
                    if mqtt_filter_key not in self.globals[HE_MQTT_FILTERS]:
                        log_mqtt_msg = False  # As Hubitat device not in the filter list (and filter entries present) - don't log MQTT message

            if log_mqtt_msg:
                self.hubHandlerLogger.topic(f"Received from '{hub_name}': Topic='{topics_list}', Payload='{payload}'")

            mqtt_filter_key = f"{hub_name.lower()}|{hubitat_device_name.lower()}"
            self.mqtt_filter_log_processing(mqtt_filter_key, hub_name, topics, payload)

            if len(topics_list) == 3:
                return

            if topics_list[2] == "hub":
                if topics_list[3][0:3] == "hsm":  # Check if topic starts with "hsm"
                    hub_props = hub_dev.ownerProps
                    if "hubitatPropertyHsm" in hub_props:
                        if hub_props["hubitatPropertyHsm"] is not True:
                            hub_props["hubitatPropertyHsm"] = True
                            hub_dev.replacePluginPropsOnServer(hub_props)
                        # Check for HSM secondary device
                        linked_dev_id = self.determine_secondary_device_id(hub_id, "hsmSensorSecondary")
                        if bool(linked_dev_id):
                            hsm_dev = indigo.devices[linked_dev_id]

                            if topics_list[3] == "hsmStatus" and len(topics_list) == 4:
                                hsm_dev.updateStateOnServer(key='hsmStatus', value=payload)
                                if payload == "disarmed":
                                    hsm_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                                elif payload[0:5] == "armed":
                                    hsm_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                    # hsm_dev.updateStateOnServer(key='alarmStatus', value=payload)
                                if hsm_dev.states["hsmAlert"] == "cancel" or hsm_dev.states["hsmAlert"] == "none" or payload == "disarmed":
                                    hsm_dev.updateStateOnServer(key='alarmStatus', value=payload)
                                if not bool(hub_dev.pluginProps.get("hideHsmBroadcast", False)):
                                    self.hubHandlerLogger.info(f"received \"{hsm_dev.name}\" Hubitat Safety Monitor Status \"{payload}\" event")

                            elif topics_list[3] == "hsmAlert" and len(topics_list) == 4:
                                hsm_dev.updateStateOnServer(key='hsmAlert', value=payload)
                                if payload == "cancel" or payload == "none":
                                    hsm_status = hsm_dev.states["hsmStatus"]
                                    hsm_dev.updateStateOnServer(key='alarmStatus', value=hsm_status)
                                else:
                                    hsm_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
                                    hsm_dev.updateStateOnServer(key='alarmStatus', value=payload)
                                if not bool(hub_dev.pluginProps.get("hideHsmBroadcast", False)):
                                    self.hubHandlerLogger.info(f"received \"{hsm_dev.name}\" Hubitat Safety Monitor Alert \"{payload}\" event")

                            elif topics_list[3] == "hsmArm" and len(topics_list) == 4:
                                hsm_dev.updateStateOnServer(key='hsmArm', value=payload)
                                if not bool(hub_dev.pluginProps.get("hideHsmBroadcast", False)):
                                    self.hubHandlerLogger.info(f"received \"{hsm_dev.name}\" Hubitat Safety Monitor Arm \"{payload}\" event")
                return

            if hubitat_device_name not in self.globals[HE_HUBS][hub_name][HE_DEVICES]:
                self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name] = dict()  # Hubitat device name
            with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                if HE_LINKED_INDIGO_DEVICES not in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name]:
                    self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES] = dict()
            if HE_PROPERTIES not in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] = None
            if HE_DEVICE_DRIVER not in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] = None
            if HE_STATES not in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES] = dict()

            if topics_list[3] == "$properties":
                self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] = payload
                return

            if topics_list[3] == "-device-driver":
                self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] = payload
                return

            # Check for Acceleration
            if topics_list[3] == "acceleration":
                if len(topics_list) == 5 and topics_list[4] == "status":
                    with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                        for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                            dev = indigo.devices[dev_id]
                            if dev.pluginProps.get("uspAcceleration", False):
                                uiValue = payload
                                if uiValue == "active":
                                    value = True
                                elif uiValue == "inactive":
                                    value = False
                                else:
                                    return

                                uspAccelerationIndigo = dev.pluginProps.get("uspAccelerationIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE)

                                broadcast_device_name = dev.name
                                if uspAccelerationIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
                                    dev.updateStateOnServer(key='acceleration', value=value, uiValue=uiValue)
                                elif uspAccelerationIndigo == INDIGO_SECONDARY_DEVICE:
                                    # Find linked device in device group
                                    linked_dev_id = self.determine_secondary_device_id(dev_id, "accelerationSensorSecondary")
                                    if bool(linked_dev_id):
                                        linked_dev = indigo.devices[linked_dev_id]
                                        linked_dev.updateStateOnServer(key='onOffState', value=value, uiValue=uiValue)
                                        if value:
                                            linked_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                        else:
                                            linked_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                                        broadcast_device_name = linked_dev.name
                                else:
                                    self.hubHandlerLogger.error(f"received \"{broadcast_device_name}\" acceleration update but unable to determine how to store update?")
                                    return

                                if not bool(dev.pluginProps.get("hideAccelerationBroadcast", False)):
                                    self.hubHandlerLogger.info(f"received \"{broadcast_device_name}\" acceleration sensor \"{uiValue}\" event")

            # Check for Battery
            elif (topics_list[3] == "measure-battery" or topics_list[3] == "battery") and len(topics_list) == 4:
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("SupportsBatteryLevel", False):
                            try:
                                battery_level = int(payload)
                            except ValueError:
                                try:
                                    battery_level = int(float(payload))
                                except ValueError:
                                    self.hubHandlerLogger.warning(f"received battery level event with an invalid payload of \"{payload}\" for device \"{dev.name}\". Event discarded and ignored.")
                                    return

                            dev.updateStateOnServer(key='batteryLevel', value=battery_level)
                            self.hubHandlerLogger.info(f"received \"{dev.name}\" status update battery level {battery_level}")

            # Check for Button
            elif topics_list[3] == "button":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if bool(dev.pluginProps.get("uspButton", False)):
                            if len(topics_list) == 5 and topics_list[4][0:7] == "button-":
                                button_number = topics_list[4].split("-")[1]
                                button_state_id = f"button_{button_number}"
                                if int(button_number) <= int(dev.pluginProps.get("uspNumberOfButtons", 1)):
                                    dev.updateStateOnServer(key=button_state_id, value=payload)
                                    if payload == "idle":
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                                    else:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                    button_ui = f"Button {button_number}"
                                    dev.updateStateOnServer(key="lastButtonPressed", value=button_number, uiValue=button_ui)
                                    if not bool(dev.pluginProps.get("hideButtonBroadcast", False)):
                                        self.hubHandlerLogger.info(f"received \"{dev.name}\" button {button_number} {payload} event")
                                else:
                                    self.hubHandlerLogger.warning(f"received \"{dev.name}\" unsupported button {button_number} {payload} event")

            # Check for Color Mode
            elif topics_list[3] == "color-mode":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if bool(dev.pluginProps.get("uspColorRGB", False)) or bool(dev.pluginProps.get("uspWhiteTemperature", False)):
                            color_mode_ui = f"{payload} Unknown"
                            if payload == "CT":
                                color_mode_ui = "Color Temperature"
                            elif payload == "RGB":
                                color_mode_ui = "Red/Green/Blue"
                            dev.updateStateOnServer(key="colorMode", value=payload, uiValue=color_mode_ui)

            # Check for Color Name
            elif topics_list[3] == "color-name":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if bool(dev.pluginProps.get("uspColorRGB", False)) or bool(dev.pluginProps.get("uspWhiteTemperature", False)):
                            color_name = f"{payload}"
                            dev.updateStateOnServer(key="colorName", value=color_name)

            # Check for Color
            elif topics_list[3] == "color":
                # if len(topics_list) == 5 and topics_list[4] == "rgb":
                #     with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                #         for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                #             dev = indigo.devices[dev_id]
                #             if bool(dev.pluginProps.get("uspColorRGB", False)):
                #                 try:
                #                     if len(payload) != 7 or payload[0] != "#":
                #                         return
                #                     hex_string = payload[1:]
                #                     rgb = bytearray.fromhex(hex_string)
                #                     red, green, blue = list(rgb)
                #                     red = int((float(red) / 256.0) * 100.0)
                #                     green = int((float(green) / 256.0) * 100.0)
                #                     blue = int((float(blue) / 256.0) * 100.0)
                #                 except ValueError:
                #                     return
                #                 key_value_list = list()
                #                 key_value_list.append({"key": "redLevel", "value": red})
                #                 key_value_list.append({"key": "greenLevel", "value": green})
                #                 key_value_list.append({"key": "blueLevel", "value": blue})
                #                 dev.updateStatesOnServer(key_value_list)
                if len(topics_list) == 4:
                    # Assume HSV format published from HE for the moment!

                    with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                        for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                            dev = indigo.devices[dev_id]
                            if bool(dev.pluginProps.get("uspColorRGB", False)):

                                hue, saturation, value = payload.split(",")

                                # def hsv2rgb(h, s, v):  # https://stackoverflow.com/questions/24852345/hsv-to-rgb-color-conversion
                                #     return tuple(round(i * 100) for i in colorsys.hsv_to_rgb(h, s, v))

                                try:
                                    hue = int(hue) / 360.0  # TODO: SHOULD THIS BE FLOAT ???
                                    saturation = int(saturation) / 100.0
                                    value = int(value) / 100.0
                                    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
                                    red = int(red * 100.0)
                                    green = int(green * 100.0)
                                    blue = int(blue * 100.0)
                                except Exception:
                                    return

                                # red, green, blue = hsv2rgb(int(hue), int(saturation), int(value))
                                key_value_list = list()
                                key_value_list.append({"key": "redLevel", "value": red})
                                key_value_list.append({"key": "greenLevel", "value": green})
                                key_value_list.append({"key": "blueLevel", "value": blue})
                                dev.updateStatesOnServer(key_value_list)

            # Check for Color Temperature
            elif topics_list[3] == "color-temperature" and len(topics_list) == 4:
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if bool(dev.pluginProps.get("uspWhiteTemperature", False)):
                            try:
                                white_temperature = int(payload)
                                white_temperature_ui = f"{payload}°K"
                            except ValueError:
                                return
                            dev.updateStateOnServer(key="whiteTemperature", value=white_temperature, uiValue=white_temperature_ui)

            # Check for Contact
            elif topics_list[3] == "contact":
                if len(topics_list) == 5 and topics_list[4] == "status":
                    with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                        for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                            dev = indigo.devices[dev_id]
                            if dev.pluginProps.get("uspContact", False):
                                if payload == "open":
                                    dev.updateStateOnServer(key="onOffState", value=True)
                                    if topics_list[3] in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES[dev.deviceTypeId]:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                else:
                                    dev.updateStateOnServer(key="onOffState", value=False)
                                    if topics_list[3] in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES[dev.deviceTypeId]:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                                if not bool(dev.pluginProps.get("hideContactBroadcast", False)):
                                    self.hubHandlerLogger.info(f"received \"{dev.name}\" contact sensor \"{payload}\" event")

            # Check for POSITION
            elif topics_list[3] == "position" and len(topics_list) == 4:  # Checking that this isn't a message from the plugin to set the value; topic would be '.../position/set'
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.subType != indigo.kDimmerDeviceSubType.Blind:
                            continue

                        if bool(dev.pluginProps.get("uspPosition", False)):
                            try:
                                brightness_level = int(payload)
                                brightness_level_ui = f"{brightness_level}%"
                            except ValueError:
                                return

                            self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_DIM] = brightness_level

                            brighten_dim_ui = "set"
                            if brightness_level > 0:
                                if brightness_level > dev.brightness:
                                    brighten_dim_ui = "opened"
                                else:
                                    brighten_dim_ui = "closed"

                            if brightness_level > 0:
                                dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOn)
                            else:
                                dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOff)

                            dev.updateStateOnServer(key='brightnessLevel', value=brightness_level, uiValue=brightness_level_ui)
                            if not bool(dev.pluginProps.get("hidePositionBroadcast", False)):
                                self.hubHandlerLogger.info(f"received {brighten_dim_ui} \"{dev.name}\" to {brightness_level_ui}")

            # Check for DIM
            elif topics_list[3] == "dim" and len(topics_list) == 4:  # Checking that this isn't a message from the plugin to set the value; topic would be '.../dim/set'
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.subType == indigo.kDimmerDeviceSubType.Blind:
                            continue
                        if bool(dev.pluginProps.get("uspDimmer", False)):
                            try:
                                brightness_level = int(payload)
                                brightness_level_ui = f"{brightness_level}"
                            except ValueError:
                                return

                            self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_DIM] = brightness_level

                            brighten_dim_ui = "set"
                            if brightness_level > 0:
                                if brightness_level > dev.brightness:
                                    brighten_dim_ui = "brighten"
                                else:
                                    brighten_dim_ui = "dim"

                            if brightness_level > 0:
                                dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOn)
                            else:
                                dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOff)

                            dev.updateStateOnServer(key='brightnessLevel', value=brightness_level, uiValue=brightness_level_ui)
                            if bool(dev.pluginProps.get("SupportsWhite", False)):
                                dev.updateStateOnServer(key='whiteLevel', value=brightness_level)
                            if not bool(dev.pluginProps.get("hideDimmerBroadcast", False)):
                                self.hubHandlerLogger.info(f"received {brighten_dim_ui} \"{dev.name}\" to {brightness_level_ui}")

                        elif bool(dev.pluginProps.get("uspValve", False)):
                            def _evaluate_valve(_payload, _previous_valve_level):
                                try:
                                    _valve_level = int(_payload)
                                    _valve_level_ui = f"{_valve_level}%"
                                except ValueError:
                                    return False

                                _valve_action_ui = "set"
                                if _valve_level > 0:
                                    try:
                                        _current_valve_level = int(_previous_valve_level)
                                    except ValueError:
                                        _current_valve_level = 0
                                    if _valve_level > _current_valve_level:
                                        _valve_action_ui = "open"
                                    else:
                                        _valve_action_ui = "close"

                                return True, _valve_level, _valve_level_ui, _valve_action_ui

                            if dev.pluginProps.get("uspValveIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:

                                evaluated_valve = _evaluate_valve(payload, dev.states["valve"])
                                if evaluated_valve[0]:
                                    valve_level = evaluated_valve[1]
                                    valve_level_ui = evaluated_valve[2]
                                    valve_action_ui = evaluated_valve[3]
                                    dev.updateStateOnServer(key='valve', value=valve_level, uiValue=valve_level_ui)
                                    if not bool(dev.pluginProps.get("hideValveBroadcast", False)):
                                        self.hubHandlerLogger.info(f"received {valve_action_ui} \"{dev.name}\" valve to {valve_level_ui}")

                            elif dev.pluginProps.get("uspValveIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_SECONDARY_DEVICE:
                                dev_id_list = indigo.device.getGroupList(dev_id)
                                if len(dev_id_list) > 1:
                                    valve_dev_id = 0
                                    for linked_dev_id in dev_id_list:
                                        if linked_dev_id != dev_id and indigo.devices[linked_dev_id].deviceTypeId == "valveSecondary":
                                            valve_dev_id = linked_dev_id
                                    if valve_dev_id == 0:
                                        return
                                    valve_dev = indigo.devices[valve_dev_id]

                                    evaluated_valve = _evaluate_valve(payload, valve_dev.brightness)
                                    if evaluated_valve[0]:
                                        valve_level = evaluated_valve[1]
                                        valve_level_ui = evaluated_valve[2]
                                        valve_action_ui = evaluated_valve[3]

                                        self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_VALVE_LEVEL] = valve_dev.brightness

                                        if valve_level > 0:
                                            valve_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                        else:
                                            valve_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

                                        valve_dev.updateStateOnServer(key='brightnessLevel', value=valve_level, uiValue=valve_level_ui)
                                        if not bool(dev.pluginProps.get("hideValveBroadcast", False)):
                                            self.hubHandlerLogger.info(f"received {valve_action_ui} \"{valve_dev.name}\" to {valve_level_ui}")

            # Check for Energy
            elif topics_list[3] == "measure-energy" or topics_list[3] == "energy":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if bool(dev.pluginProps.get("uspEnergy", False)):
                            energy_units_ui = f" {dev.pluginProps.get('uspEnergyUnits', '')}"
                            try:
                                energy = float(payload)
                            except ValueError:
                                return
                            decimal_places = int(dev.pluginProps.get("uspEnergyDecimalPlaces", 0))
                            value, uiValue = self.processDecimalPlaces(energy, decimal_places, energy_units_ui, INDIGO_NO_SPACE_BEFORE_UNITS)
                            dev.updateStateOnServer(key='accumEnergyTotal', value=value, uiValue=uiValue)
                            if not bool(dev.pluginProps.get("hideEnergyBroadcast", False)):
                                self.hubHandlerLogger.info(f"received \"{dev.name}\" accumulated energy total update to {uiValue}")

            # Check for Humidity
            elif topics_list[3] == "measure-humidity" or topics_list[3] == "humidity":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("uspHumidity", False):
                            try:
                                humidity = float(payload)
                            except ValueError:
                                return

                            decimal_places = int(dev.pluginProps.get("uspHumidityDecimalPlaces", 0))
                            value, uiValue = self.processDecimalPlaces(humidity, decimal_places, "%", INDIGO_NO_SPACE_BEFORE_UNITS)

                            uspHumidityIndigo = dev.pluginProps.get("uspHumidityIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE)

                            broadcast_device_name = dev.name
                            if uspHumidityIndigo == INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE:
                                dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)

                            elif uspHumidityIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
                                dev.updateStateOnServer(key='humidity', value=value, uiValue=uiValue)
                            # elif uspHumidityIndigo in (INDIGO_SECONDARY_DEVICE_ADDITIONAL_STATE, INDIGO_SECONDARY_DEVICE):
                            elif uspHumidityIndigo in INDIGO_SECONDARY_DEVICE:
                                # Find linked device in device group
                                linked_dev_id = self.determine_secondary_device_id(dev_id, "humiditySensorSecondary")
                                if bool(linked_dev_id):
                                    linked_dev = indigo.devices[linked_dev_id]
                                    # if uspHumidityIndigo == INDIGO_SECONDARY_DEVICE_ADDITIONAL_STATE:
                                    #     linked_dev.updateStateOnServer(key='humidityInput1', value=value, uiValue=uiValue)
                                    #     linked_dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
                                    # else:
                                    #     linked_dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                    if "sensorValue" in linked_dev.states:
                                        linked_dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                    else:
                                        linked_dev.updateStateOnServer(key='humidityInput1', value=value, uiValue=uiValue)

                                    linked_dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                    linked_dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)

                                    broadcast_device_name = linked_dev.name
                            else:
                                self.hubHandlerLogger.error(f"received \"{broadcast_device_name}\" humidity update but unable to determine how to store update?")
                                return

                            if not bool(dev.pluginProps.get("hideHumidityBroadcast", False)):
                                self.hubHandlerLogger.info(f"received \"{broadcast_device_name}\" humidity update to {uiValue}")

            # Check for Illuminance
            elif topics_list[3] == "measure-illuminance" or topics_list[3] == "illuminance":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("uspIlluminance", False):
                            illuminance_units_ui = dev.pluginProps.get("uspIlluminanceUnits", "")
                            try:
                                illuminance = float(payload)
                            except ValueError:
                                return
                            decimal_places = int(dev.pluginProps.get("uspIlluminanceDecimalPlaces", 0))
                            value, uiValue = self.processDecimalPlaces(illuminance, decimal_places, illuminance_units_ui, INDIGO_ONE_SPACE_BEFORE_UNITS)

                            uspIlluminanceIndigo = dev.pluginProps.get("uspIlluminanceIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE)

                            broadcast_device_name = dev.name
                            if uspIlluminanceIndigo == INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE:
                                dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                if value:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.LightSensorOn)
                                else:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.LightSensor)
                            elif uspIlluminanceIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
                                dev.updateStateOnServer(key='illuminance', value=value, uiValue=uiValue)
                            elif uspIlluminanceIndigo == INDIGO_SECONDARY_DEVICE:
                                # Find linked device in device group
                                linked_dev_id = self.determine_secondary_device_id(dev_id, "illuminanceSensorSecondary")
                                if bool(linked_dev_id):
                                    linked_dev = indigo.devices[linked_dev_id]
                                    linked_dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                    if value:
                                        linked_dev.updateStateImageOnServer(indigo.kStateImageSel.LightSensorOn)
                                    else:
                                        linked_dev.updateStateImageOnServer(indigo.kStateImageSel.LightSensor)
                                    broadcast_device_name = linked_dev.name
                            else:
                                self.hubHandlerLogger.error(f"received \"{broadcast_device_name}\" illuminance update but unable to determine how to store update?")
                                return

                            if not bool(dev.pluginProps.get("hideIlluminanceBroadcast", False)):
                                self.hubHandlerLogger.info(f"received \"{broadcast_device_name}\" illuminance sensor \"{uiValue}\" event")

            # Check for Motion
            elif topics_list[3] == "motion":
                if len(topics_list) == 5 and topics_list[4] == "status":
                    with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                        for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                            dev = indigo.devices[dev_id]
                            if dev.pluginProps.get("uspMotion", False):
                                uiValue = payload
                                if uiValue == "active":
                                    value = True
                                elif uiValue == "inactive":
                                    value = False
                                else:
                                    return

                                uspMotionIndigo = dev.pluginProps.get("uspMotionIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE)

                                broadcast_device_name = dev.name
                                if uspMotionIndigo == INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE:
                                    dev.updateStateOnServer(key='onOffState', value=value, uiValue=uiValue)
                                    if value:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensorTripped)
                                    else:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor)
                                elif uspMotionIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
                                    dev.updateStateOnServer(key='motion', value=value, uiValue=uiValue)
                                elif uspMotionIndigo == INDIGO_SECONDARY_DEVICE:
                                    # Find linked device in device group
                                    linked_dev_id = self.determine_secondary_device_id(dev_id, "motionSensorSecondary")
                                    if bool(linked_dev_id):
                                        linked_dev = indigo.devices[linked_dev_id]
                                        linked_dev.updateStateOnServer(key='onOffState', value=value, uiValue=uiValue)
                                        if value:
                                            linked_dev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensorTripped)
                                        else:
                                            linked_dev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor)
                                        broadcast_device_name = linked_dev.name
                                else:
                                    self.hubHandlerLogger.error(f"received \"{broadcast_device_name}\" motion sensor update but unable to determine how to store update?")
                                    return

                                if not bool(dev.pluginProps.get("hideMotionBroadcast", False)):
                                    self.hubHandlerLogger.info(f"received \"{broadcast_device_name}\" motion sensor \"{uiValue}\" event")

            # Check for On / Off
            elif topics_list[3] == "onoff":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("uspOnOff", False):
                            if len(topics_list) != 4:
                                return
                            if payload not in ["on", "off", "true", "false"]:
                                return
                            if payload == "on" or payload == "true":
                                payload_ui = "on"  # Force to On
                                if dev.deviceTypeId != "thermostat":
                                    dev.updateStateOnServer(key="onOffState", value=True)
                                    if dev.deviceTypeId == "dimmer":
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOn)
                                    elif dev.deviceTypeId == "valveSecondary":
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                    else:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                                else:
                                    # deviceTypeId is a Thermostat - Indigo On/off state isn't updated
                                    pass
                                # Next bit of logic, restores previous dim level when a dimmer is switched on
                                if HE_STATES in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name]:
                                    if HE_STATE_DIM in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES]:
                                        if dev.deviceTypeId == "dimmer":
                                            brightness_level = int(self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_DIM])
                                            brightness_level_ui = f"{brightness_level}"
                                            dev.updateStateOnServer(key='brightnessLevel', value=brightness_level, uiValue=brightness_level_ui)
                                            dev.updateStateOnServer(key='whiteLevel', value=brightness_level)
                                    elif HE_STATE_VALVE_LEVEL in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES]:
                                        if dev.deviceTypeId == "valveSecondary":
                                            valve_level = int(self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_VALVE_LEVEL])
                                            valve_level_ui = f"{valve_level}%"
                                            dev.updateStateOnServer(key='brightnessLevel', value=valve_level, uiValue=valve_level_ui)
                            else:
                                # payload == "off" or payload == "false"
                                payload_ui = "off"  # Force to Off
                                if dev.deviceTypeId != "thermostat":
                                    if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "valveSecondary":
                                        # Save current Valve Level before switching off
                                        if dev.brightness != 0:
                                            if HE_STATE_VALVE_LEVEL in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES]:
                                                self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_VALVE_LEVEL] = dev.brightness
                                        brightness_level_ui = "0"
                                        dev.updateStateOnServer(key='brightnessLevel', value=0, uiValue=brightness_level_ui)

                                        if dev.deviceTypeId == "valveSecondary":
                                            dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                                        elif dev.deviceTypeId == "dimmer":
                                            if bool(dev.pluginProps.get("SupportsWhite", False)):
                                                dev.updateStateOnServer(key='whiteLevel', value=0)

                                            dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOff)
                                    else:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
                                    dev.updateStateOnServer(key="onOffState", value=False)
                                elif dev.deviceTypeId == "thermostat":
                                    # deviceTypeId is a Thermostat - Indigo On/off state isn't updated
                                    pass

                            if not bool(dev.pluginProps.get("hidePowerBroadcast", False)):
                                device_type_ui = ""
                                if dev.deviceTypeId == "dimmer":
                                    device_type_ui = "dimmer"
                                elif dev.deviceTypeId == "outlet (socket)":
                                    device_type_ui = "dimmer"
                                elif dev.deviceTypeId == "valveSecondary":
                                    device_type_ui = "valve"
                                self.hubHandlerLogger.info(f"received \"{dev.name}\" {device_type_ui} \"{payload_ui}\" event")

            # Check for Power
            elif topics_list[3] == "measure-power" or topics_list[3] == "power":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if bool(dev.pluginProps.get("uspPower", False)):
                            power_units_ui = f" {dev.pluginProps.get('uspPowerUnits', '')}"
                            try:
                                power = float(payload)
                            except ValueError:
                                return
                            minimumPowerLevel = float(dev.pluginProps.get("uspPowerMinimumReportingLevel", 0.0))
                            reportingPowerHysteresis = float(dev.pluginProps.get("uspPowerReportingHysteresis", 6.0))
                            if reportingPowerHysteresis > 0.0:  # noqa [Duplicated code fragment!]
                                reportingPowerHysteresis = reportingPowerHysteresis / 2
                            previousPowerLevel = float(dev.states["curEnergyLevel"])
                            report_power_state = False
                            power_variance_minimum = previousPowerLevel - reportingPowerHysteresis
                            power_variance_maximum = previousPowerLevel + reportingPowerHysteresis
                            if power_variance_minimum < 0.0:
                                power_variance_minimum = 0.0
                            if power >= minimumPowerLevel:
                                # power_variance_minimum = previousPowerLevel - powerReportingVariance
                                # power_variance_maximum = previousPowerLevel + powerReportingVariance
                                if power < power_variance_minimum or power > power_variance_maximum:
                                    report_power_state = True
                            elif previousPowerLevel >= minimumPowerLevel:
                                if power < power_variance_minimum or power > power_variance_maximum:
                                    report_power_state = True

                            # if power != previousPowerLevel:
                            #     self.hubHandlerLogger.warning(
                            #         f"HE Report Power State: Power={power}, Previous={previousPowerLevel}, Level={minimumPowerLevel}, Min={power_variance_minimum}, Max={power_variance_maximum}")

                            decimal_places = int(dev.pluginProps.get("uspPowerDecimalPlaces", 0))
                            value, uiValue = self.processDecimalPlaces(power, decimal_places, power_units_ui, INDIGO_NO_SPACE_BEFORE_UNITS)
                            dev.updateStateOnServer(key='curEnergyLevel', value=value, uiValue=uiValue)
                            if report_power_state:
                                if not bool(dev.pluginProps.get("hidePowerBroadcast", False)):
                                    self.hubHandlerLogger.info(f"received \"{dev.name}\" power update to {uiValue}")

            # Check for Presence
            if topics_list[3] == "presence-sensor" or topics_list[3] == "presence":
                if len(topics_list) == 5 and topics_list[4] == "status":
                    with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                        for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                            dev = indigo.devices[dev_id]
                            if dev.pluginProps.get("uspPresence", False):
                                uiValue = payload
                                if uiValue == "present":
                                    value = True
                                else:
                                    value = False

                                uspPresenceIndigo = dev.pluginProps.get("uspPresenceIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE)

                                broadcast_device_name = dev.name
                                if uspPresenceIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
                                    dev.updateStateOnServer(key='presence', value=value, uiValue=uiValue)
                                elif uspPresenceIndigo == INDIGO_SECONDARY_DEVICE:
                                    # Find linked device in device group
                                    linked_dev_id = self.determine_secondary_device_id(dev_id, "presenceSensorSecondary")
                                    if bool(linked_dev_id):
                                        linked_dev = indigo.devices[linked_dev_id]
                                        linked_dev.updateStateOnServer(key='onOffState', value=value, uiValue=uiValue)
                                        if value:
                                            linked_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                        else:
                                            linked_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                                        broadcast_device_name = linked_dev.name
                                else:
                                    self.hubHandlerLogger.error(f"received \"{broadcast_device_name}\" presence sensor update but unable to determine how to store update?")
                                    return

                                if not bool(dev.pluginProps.get("hidePresenceBroadcast", False)):
                                    self.hubHandlerLogger.info(f"received \"{broadcast_device_name}\" presence sensor \"{uiValue}\" event")

            # Check for Pressure
            elif topics_list[3] == "measure-pressure" or topics_list[3] == "pressure":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("uspPressure", False):
                            pressure_units_ui = dev.pluginProps.get("uspPressureUnits", "")
                            try:
                                pressure = float(payload)
                            except ValueError:
                                return
                            decimal_places = int(dev.pluginProps.get("uspPressureDecimalPlaces", 0))
                            value, uiValue = self.processDecimalPlaces(pressure, decimal_places, pressure_units_ui, INDIGO_ONE_SPACE_BEFORE_UNITS)

                            uspPressureIndigo = dev.pluginProps.get("uspPressureIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE)

                            broadcast_device_name = dev.name
                            if uspPressureIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
                                dev.updateStateOnServer(key='pressure', value=value, uiValue=uiValue)
                            elif uspPressureIndigo == INDIGO_SECONDARY_DEVICE:
                                # Find linked device in device group
                                linked_dev_id = self.determine_secondary_device_id(dev_id, "pressureSensorSecondary")
                                if bool(linked_dev_id):
                                    linked_dev = indigo.devices[linked_dev_id]
                                    linked_dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                    if value:
                                        linked_dev.updateStateImageOnServer(_no_image())  # TODO: Decide best icon
                                    else:
                                        linked_dev.updateStateImageOnServer(_no_image())  # TODO: Decide best icon
                                    broadcast_device_name = linked_dev.name
                            else:
                                self.hubHandlerLogger.error(f"received \"{broadcast_device_name}\" pressure update but unable to determine how to store update?")
                                return

                            if not bool(dev.pluginProps.get("hidePressureBroadcast", False)):
                                self.hubHandlerLogger.info(f"received \"{broadcast_device_name}\" pressure sensor update to \"{uiValue}\" event")

            # Check for HVAC Mode
            elif topics_list[3] == "mode":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.deviceTypeId == "thermostat" and dev.pluginProps.get("uspHvacMode", False):
                            if payload == "off" or payload == "switched off":
                                indigo_state_value = indigo.kHvacMode.Off
                            elif payload == "heat":
                                indigo_state_value = indigo.kHvacMode.Heat
                            elif payload == "eco":
                                indigo_state_value = indigo.kHvacMode.Cool
                            elif payload == "auto":
                                indigo_state_value = indigo.kHvacMode.HeatCool
                            else:
                                self.hubHandlerLogger.warning(f"received \"{dev.name}\" hvac unknown mode update: payload = '{payload}'")
                                return

                            dev.updateStateOnServer(key='hvacMode', value=payload)
                            if not bool(dev.pluginProps.get("hideHvacModeBroadcast", False)):
                                dev.updateStateOnServer(key='hvacOperationMode', value=indigo_state_value)
                                self.hubHandlerLogger.info(f"received \"{dev.name}\" hvac mode update to {payload}")

            # Check for HVAC State
            elif topics_list[3] == "state":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.subType == indigo.kDimmerDeviceSubType.Blind and dev.pluginProps.get("uspState", False):
                            dev.updateStateOnServer(key='state', value=payload)
                            if not bool(dev.pluginProps.get("hideStateBroadcast", False)):
                                self.hubHandlerLogger.info(f"received \"{dev.name}\" state update to {payload}")

            # Check for Setpoint
            elif topics_list[3] == "thermostat-setpoint":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("uspSetpoint", False):
                            try:
                                setpointUnitsConversion = dev.pluginProps.get("uspSetpointUnitsConversion", "C")
                                if setpointUnitsConversion in ["C", "F>C"]:  # noqa [Duplicated code fragment!]
                                    setpoint_unit_ui = "°C"
                                else:
                                    setpoint_unit_ui = "°F"
                                if setpointUnitsConversion == "C>F":
                                    setpoint = float(((float(payload) * 9) / 5) + 32.0)
                                elif setpointUnitsConversion == "F>C":
                                    setpoint = float(((float(payload) - 32.0) * 5) / 9)
                                else:
                                    setpoint = float(payload)
                            except ValueError:
                                return

                            decimal_places = int(dev.pluginProps.get("uspSetpointDecimalPlaces", 0))
                            value, uiValue = self.processDecimalPlaces(setpoint, decimal_places, setpoint_unit_ui, INDIGO_NO_SPACE_BEFORE_UNITS)
                            dev.updateStateOnServer(key='setpointHeat', value=value, uiValue=uiValue)
                            # if topics_list[3] in HE_DEVICE_TYPES_MAIN_HABITAT_PROPERTIES[dev.deviceTypeId]:
                            #     dev.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
                            if not bool(dev.pluginProps.get("hideSetpointBroadcast", False)):
                                self.hubHandlerLogger.info(f"received \"{dev.name}\" setpoint update to {uiValue}")

            # Check for Temperature
            elif topics_list[3] == "measure-temperature" or topics_list[3] == "temperature":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("uspTemperature", False):
                            try:
                                temperatureUnitsConversion = dev.pluginProps.get("uspTemperatureUnitsConversion", "C")
                                if temperatureUnitsConversion in ["C", "F>C"]:  # noqa [Duplicated code fragment!]
                                    temperature_unit_ui = "°C"
                                else:
                                    temperature_unit_ui = "°F"
                                if temperatureUnitsConversion == "C>F":
                                    temperature = float(((float(payload) * 9) / 5) + 32.0)
                                elif temperatureUnitsConversion == "F>C":
                                    temperature = float(((float(payload) - 32.0) * 5) / 9)
                                else:
                                    temperature = float(payload)
                            except ValueError:
                                return

                            decimal_places = int(dev.pluginProps.get("uspTemperatureDecimalPlaces", 0))
                            value, uiValue = self.processDecimalPlaces(temperature, decimal_places, temperature_unit_ui, INDIGO_NO_SPACE_BEFORE_UNITS)

                            uspTemperatureIndigo = dev.pluginProps.get("uspTemperatureIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE)

                            broadcast_device_name = dev.name
                            if uspTemperatureIndigo == INDIGO_PRIMARY_DEVICE_MAIN_UI_STATE:
                                if dev.deviceTypeId == "thermostat":
                                    dev.updateStateOnServer(key='temperatureInput1', value=value, uiValue=uiValue)
                                else:
                                    # Temperature Sensor
                                    if "sensorValue" in dev.states:
                                        dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                    else:
                                        dev.updateStateOnServer(key='temperatureInput1', value=value, uiValue=uiValue)
                                dev.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
                            elif uspTemperatureIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
                                dev.updateStateOnServer(key='temperature', value=value, uiValue=uiValue)
                            elif uspTemperatureIndigo == INDIGO_SECONDARY_DEVICE:
                                # Find linked device in device group
                                linked_dev_id = self.determine_secondary_device_id(dev_id, "temperatureSensorSecondary")
                                if bool(linked_dev_id):
                                    linked_dev = indigo.devices[linked_dev_id]
                                    if "sensorValue" in linked_dev.states:
                                        linked_dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                    else:
                                        linked_dev.updateStateOnServer(key='temperatureInput1', value=value, uiValue=uiValue)
                                    linked_dev.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
                                    broadcast_device_name = linked_dev.name
                            else:
                                self.hubHandlerLogger.error(f"received \"{broadcast_device_name}\" temperature update but unable to determine how to store update?")
                                return

                            if not bool(dev.pluginProps.get("hideTemperatureBroadcast", False)):
                                # self.hubHandlerLogger.error(f"TYPE UIVALUE: \"{type(uiValue)}\", TYPE BROADCAST_DEVICE_NAME: \"{type(broadcast_device_name)}\"")
                                self.hubHandlerLogger.info(f"received \"{broadcast_device_name}\" temperature update to {uiValue}")

            # Check for Voltage
            elif topics_list[3] == "measure-voltage" or topics_list[3] == "voltage":
                with self.globals[LOCK_HE_LINKED_INDIGO_DEVICES]:
                    for dev_id in self.globals[HE_HUBS][hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("uspVoltage", False):
                            try:
                                voltage = float(payload)
                            except ValueError:
                                return
                            decimal_places = int(dev.pluginProps.get("uspVoltageDecimalPlaces", 0))
                            value, uiValue = self.processDecimalPlaces(voltage, decimal_places, "Volts", INDIGO_ONE_SPACE_BEFORE_UNITS)

                            uspVoltageIndigo = dev.pluginProps.get("uspVoltageIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE)

                            broadcast_device_name = dev.name
                            if uspVoltageIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
                                dev.updateStateOnServer(key='voltage', value=value, uiValue=uiValue)
                            elif uspVoltageIndigo == INDIGO_SECONDARY_DEVICE:
                                # Find linked device in device group
                                linked_dev_id = self.determine_secondary_device_id(dev_id, "voltageSensorSecondary")
                                if bool(linked_dev_id):
                                    linked_dev = indigo.devices[linked_dev_id]
                                    linked_dev.updateStateOnServer(key='sensorValue', value=value, uiValue=uiValue)
                                    if value:
                                        linked_dev.updateStateImageOnServer(indigo.kStateImageSel.LightSensorOn)
                                    else:
                                        linked_dev.updateStateImageOnServer(indigo.kStateImageSel.LightSensorOff)
                                    broadcast_device_name = linked_dev.name
                            else:
                                self.hubHandlerLogger.error(f"received \"{broadcast_device_name}\" voltage update but unable to determine how to store update?")
                                return

                            if not bool(dev.pluginProps.get("hideVoltageBroadcast", False)):
                                self.hubHandlerLogger.info(f"received \"{broadcast_device_name}\" voltage \"{uiValue}\" event")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def determine_secondary_device_id(self, dev_id, secondary_dev_type_id):
        try:
            dev_id_list = indigo.device.getGroupList(dev_id)
            secondary_dev_id = 0
            if len(dev_id_list) > 1:
                for grouped_dev_id in dev_id_list:
                    if grouped_dev_id != dev_id and indigo.devices[grouped_dev_id].deviceTypeId == secondary_dev_type_id:
                        secondary_dev_id = grouped_dev_id
                        break
            return secondary_dev_id

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processDecimalPlaces(self, field, decimal_places, units, space_before_units):
        try:
            units_plus_optional_space = f" {units}" if space_before_units else f"{units}"  # noqa [Duplicated code fragment!]
            if decimal_places == 0:
                return int(field), f"{int(field)}{units_plus_optional_space}"
            else:
                value = round(field, decimal_places)

                uiValue = "{{0:.{0}f}}{1}".format(decimal_places, units_plus_optional_space).format(field)

                return value, uiValue

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def mqtt_filter_log_processing(self, hubitat_key, hub_name, topics, payload):
        try:
            log_mqtt_msg = False  # Assume MQTT message should NOT be logged
            # Check if MQTT message filtering required
            if HE_MQTT_FILTERS in self.globals:
                if len(self.globals[HE_MQTT_FILTERS]) > 0 and self.globals[HE_MQTT_FILTERS] != ["-0-"]:
                    # As entries exist in the filter list, only log MQTT message in Hubitat device in the filter list
                    if self.globals[HE_MQTT_FILTERS] == ["-1-"] or hubitat_key in self.globals[HE_MQTT_FILTERS]:
                        log_mqtt_msg = True

            if log_mqtt_msg:
                self.hubHandlerLogger.topic(f"Received from '{hub_name}': Topic='{topics}', Payload='{payload}'")  # noqa [Unresolved attribute reference]

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
