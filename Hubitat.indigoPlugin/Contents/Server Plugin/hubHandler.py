#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Hubitat - Hub Handler © Autolog 2021
#

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError, e:
    pass

import logging
import paho.mqtt.client as mqtt
import sys
import threading
import time

from constants import *


# noinspection PyPep8Naming
class ThreadHubHandler(threading.Thread):

    # This class handles Hub processing

    def __init__(self, pluginGlobals, hubitat_hub_id, event):
        try:

            threading.Thread.__init__(self)

            self.globals = pluginGlobals

            self.hubitat_hub_id = hubitat_hub_id

            hub_props = indigo.devices[self.hubitat_hub_id].ownerProps
            self.hubitat_hub_name = hub_props["hub_name"]

            self.hubHandlerLogger = logging.getLogger("Plugin.HE_HUB")
            self.hubHandlerLogger.debug(u"Debugging Hub Handler Thread")

            self.threadStop = event

            self.bad_disconnection = False

            self.mqtt_client = self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_CLIENT]
            self.mqtt_message_sequence = 0
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method '__init__'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def run(self):
        try:
            time.sleep(2.0)  # Allow time for Indigo devices to start
            # Initialise routine on thread start
            self.hubHandlerLogger.debug(u"Hub Handler Thread initialised for '{0}'".format(self.hubitat_hub_name))
            self.hubHandlerLogger.debug(u"HE-HUB Details:/n{0}".format(self.globals[HE_HUBS][self.hubitat_hub_name]))

            self.mqtt_client = mqtt.Client(client_id=self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_CLIENT_ID],
                                           clean_session=True,
                                           userdata=None,
                                           protocol=mqtt.MQTTv31)
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_disconnect = self.on_disconnect
            self.mqtt_client.on_subscribe = self.on_subscribe
            self.mqtt_client.message_callback_add(self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_TOPIC], self.handle_message)
            mqtt_connected = False
            try:
                self.mqtt_client.connect(host=self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_BROKER_IP],
                                         port=self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_BROKER_PORT],
                                         keepalive=60,
                                         bind_address="")
                mqtt_connected = True
            except Exception as err:
                self.hubHandlerLogger.error(u"Hub Handler for '{0}' is unable to connect to MQTT. Is it running? Connection error reported as '{1}'".format(self.hubitat_hub_name, err))

            if mqtt_connected:
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_CLIENT] = self.mqtt_client
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_INITIALISED] = True

                self.hubHandlerLogger.debug(u"Autolog Hubitat Hub {0} now started".format(self.hubitat_hub_name))
                self.mqtt_client.loop_start()

                while not self.threadStop.is_set():
                    try:
                        time.sleep(2)
                    except self.threadStop:
                        pass  # Optionally catch the StopThread exception and do any needed cleanup.
                        self.mqtt_client.loop_stop()
                        self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_INITIALISED] = False
            else:
                pass
                # TODO: At this point, queue a recovery for n seconds time
                # TODO: In the meanwhile, just disable and then enable the Indigo Hubitat Elevation Hub device

            self.hubHandlerLogger.debug(u"Hub Handler Thread for '{0}' close-down commencing.".format(self.hubitat_hub_name))

            self.handle_quit()
            
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method 'run'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def on_connect(self, client, userdata, flags, rc):  # noqa [Unused parameter values]
        try:
            indigo.devices[self.hubitat_hub_id].updateStateOnServer(key='status', value="Connected")
            indigo.devices[self.hubitat_hub_id].updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            self.mqtt_client.subscribe(self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_TOPIC], qos=1)
            # self.hubHandlerLogger.info(u"MQTT subscription to Hubitat Hub '{0}' initialized".format(self.hubitat_hub_name))

            self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_INITIALISED] = True

            if self.bad_disconnection:
                self.bad_disconnection = False
                self.hubHandlerLogger.info(u"'{0}' reconnected to MQTT Broker.".format(indigo.devices[self.hubitat_hub_id].name))

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method 'on_connect'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def on_disconnect(self, client, userdata, rc):  # noqa [Unused parameter values]
        try:
            if rc != 0:
                self.hubHandlerLogger.warning(
                    u"'{0}' encountered an unexpected disconnection from MQTT Broker [Code {1}]. Retrying connection ...".format(indigo.devices[self.hubitat_hub_id].name, rc))
                self.bad_disconnection = True
            else:
                self.hubHandlerLogger.info(u"MQTT subscription to Hubitat Hub '{0}' ended".format(self.hubitat_hub_name))
                self.mqtt_client.loop_stop()
            try:
                indigo.devices[self.hubitat_hub_id].updateStateOnServer(key='status', value="Disconnected")
                indigo.devices[self.hubitat_hub_id].updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
            except KeyError:  # Indigo device may have been already deleted
                pass
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method 'on_disconnect'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def handle_quit(self):
        try:
            self.mqtt_client.disconnect()
            self.mqtt_client.loop_stop()
            self.hubHandlerLogger.info(u"Autolog Hubitat hub '{0}' disconnected from MQTT".format(self.hubitat_hub_name))
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method 'handle_quit'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def on_subscribe(self, client, userdata, mid, granted_qos):  # noqa [Unused parameter values]
        try:
            pass
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method 'on_subscribe'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def handle_message(self, client, userdata, msg):  # noqa [Unused parameter values]
        try:
            # self.mqtt_message_sequence += 1
            # mqtt_message_sequence = '{0}'.format(self.mqtt_message_sequence)

            topics = msg.topic.split("/")  # noqa [Duplicated code fragment!]
            payload = str(msg.payload)
            # qos = msg.qos

            indigo.devices[self.hubitat_hub_id].updateStateOnServer(key='lastTopic', value=msg.topic)
            indigo.devices[self.hubitat_hub_id].updateStateOnServer(key='lastPayload', value=msg.payload)

            # self.hubHandlerLogger.debug(u"MSG [{2}] - Processing Topic = '{0}', QOS = '{1}', Payload  = '{3}'".format(msg.topic, qos, mqtt_message_sequence, payload))

            if len(topics) == 0:
                return
            if topics[0] != "homie":
                return

            if len(topics) == 1:
                return
            if topics[1] != self.hubitat_hub_name:
                return
            elif self.hubitat_hub_name not in self.globals[HE_HUBS]:
                self.hubHandlerLogger.error(u"Plugin Logic Error - '{0}' missing from internal store".format(self.hubitat_hub_name))
                return

            if len(topics) == 2:
                return
            if topics[2] == "$implementation":
                if len(topics) == 4 and topics[3] == "heartbeat":
                    hub_id = self.globals[HE_HUBS][self.hubitat_hub_name][HE_INDIGO_HUB_ID]
                    if hub_id is None or hub_id == 0:
                        return
                    heartbeat = int(payload.split(",")[0])
                    hub = indigo.devices[hub_id]
                    hub.updateStateOnServer(key='heartbeat', value=heartbeat)
                return
            elif topics[2] == "$fw":
                return
            elif topics[2] == "$state":
                return
            elif topics[2] == "$name":
                return
            elif topics[2] == "$nodes":
                return

            # At this point it should be a Hubitat device (including 'hub')

            hubitat_device_name = topics[2]

            # log_mqtt_msg = True  # Assume MQTT message should be logged
            # # Check if MQTT message filtering required
            # if HE_MQTT_FILTERS in self.globals:
            #     if len(self.globals[HE_MQTT_FILTERS]) > 0:
            #         mqtt_filter_key = u"{0}|||{1}".format(self.hubitat_hub_name.lower(), hubitat_device_name.lower())
            #         # As entries exist in the filter list, only log MQTT message in Hubitat device in the filter list
            #         if mqtt_filter_key not in self.globals[HE_MQTT_FILTERS]:
            #             log_mqtt_msg = False  # As Hubitat device not in the filter list (and filter entries present) - don't log MQTT message

            # if log_mqtt_msg:
            #     self.hubHandlerLogger.topic(u"Received from '{0}': Topic='{1}', Payload='{2}'".format(self.hubitat_hub_name, msg.topic, payload))

            mqtt_filter_key = u"{0}|{1}".format(self.hubitat_hub_name.lower(), hubitat_device_name.lower())
            self.mqtt_filter_log_processing(mqtt_filter_key, self.hubitat_hub_name, topics, payload)

            if len(topics) == 3:
                return

            if topics[2] == "hub":
                if topics[3][0:3] == "hsm":  # Check if topic starts with "hsm"
                    hub_dev = indigo.devices[self.hubitat_hub_id]
                    hub_props = hub_dev.ownerProps
                    if "hubitatPropertyHsm" in hub_props:
                        if hub_props["hubitatPropertyHsm"] is not True:
                            hub_props["hubitatPropertyHsm"] = True
                            hub_dev.replacePluginPropsOnServer(hub_props)
                        # Check for HSM secondary device
                        linked_dev_id = self.determine_secondary_device_id(self.hubitat_hub_id, "hsmSensorSecondary")
                        if bool(linked_dev_id):
                            hsm_dev = indigo.devices[linked_dev_id]

                            if topics[3] == "hsmStatus":
                                hsm_dev.updateStateOnServer(key='hsmStatus', value=payload)
                                if payload == "disarmed":
                                    hsm_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                                elif payload[0:5] == "armed":
                                    hsm_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                    # hsm_dev.updateStateOnServer(key='alarmStatus', value=payload)
                                if hsm_dev.states["hsmAlert"] == "cancel" or hsm_dev.states["hsmAlert"] == "none" or payload == "disarmed":
                                    hsm_dev.updateStateOnServer(key='alarmStatus', value=payload)
                                if not bool(hub_dev.pluginProps.get("hideHsmBroadcast", False)):
                                    self.hubHandlerLogger.info(u"received \"{0}\" Hubitat Safety Monitor Status \"{1}\" event".format(hsm_dev.name, payload))

                            elif topics[3] == "hsmAlert":
                                hsm_dev.updateStateOnServer(key='hsmAlert', value=payload)
                                if payload == "cancel" or payload == "none":
                                    hsm_status = hsm_dev.states["hsmStatus"]
                                    hsm_dev.updateStateOnServer(key='alarmStatus', value=hsm_status)
                                else:
                                    hsm_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
                                    hsm_dev.updateStateOnServer(key='alarmStatus', value=payload)
                                if not bool(hub_dev.pluginProps.get("hideHsmBroadcast", False)):
                                    self.hubHandlerLogger.info(u"received \"{0}\" Hubitat Safety Monitor Alert \"{1}\" event".format(hsm_dev.name, payload))

                            elif topics[3] == "hsmArm":
                                hsm_dev.updateStateOnServer(key='hsmArm', value=payload)
                                if not bool(hub_dev.pluginProps.get("hideHsmBroadcast", False)):
                                    self.hubHandlerLogger.info(u"received \"{0}\" Hubitat Safety Monitor Arm \"{1}\" event".format(hsm_dev.name, payload))
                return

            if hubitat_device_name not in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES]:
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name] = dict()  # Hubitat device name
            if HE_LINKED_INDIGO_DEVICES not in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES] = dict()
            if HE_PROPERTIES not in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] = None
            if HE_DEVICE_DRIVER not in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] = None
            if HE_STATES not in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES] = dict()

            if topics[3] == "$properties":
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_PROPERTIES] = payload
                return

            if topics[3] == "-device-driver":
                self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_DEVICE_DRIVER] = payload
                return

            # Check for Acceleration
            if topics[3] == "acceleration":
                if len(topics) == 5 and topics[4] == "status":
                    for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
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
                                self.hubHandlerLogger.error(u"received \"{0}\" acceleration update but unable to determine how to store update?".format(broadcast_device_name))
                                return

                            if not bool(dev.pluginProps.get("hideAccelerationBroadcast", False)):
                                self.hubHandlerLogger.info(u"received \"{0}\" acceleration sensor \"{1}\" event".format(broadcast_device_name, uiValue))

            # Check for Battery
            elif topics[3] == "measure-battery" or topics[3] == "battery":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if dev.pluginProps.get("SupportsBatteryLevel", False):
                        battery_level = int(float(payload))
                        dev.updateStateOnServer(key='batteryLevel', value=battery_level)
                        self.hubHandlerLogger.info(u"received \"{0}\" status update battery level {1}".format(dev.name, battery_level))

            # Check for Button
            elif topics[3] == "button":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if bool(dev.pluginProps.get("uspButton", False)):
                        if len(topics) == 5 and topics[4][0:7] == "button-":
                            button_number = topics[4].split("-")[1]
                            button_state_id = u"button_{0}".format(button_number)
                            if int(button_number) <= int(dev.pluginProps.get("uspNumberOfButtons", 1)):
                                dev.updateStateOnServer(key=button_state_id, value=payload)
                                if payload == u"idle":
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                                else:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                button_ui = u"Button {0}".format(button_number)
                                dev.updateStateOnServer(key="lastButtonPressed", value=button_number, uiValue=button_ui)
                                if not bool(dev.pluginProps.get("hideButtonBroadcast", False)):
                                    self.hubHandlerLogger.info(u"received \"{0}\" button {1} {2} event".format(dev.name, button_number, payload))
                            else:
                                self.hubHandlerLogger.warning(u"received \"{0}\" unsupported button {1} {2} event".format(dev.name, button_number, payload))

            # Check for Color Mode
            elif topics[3] == "color-mode":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if bool(dev.pluginProps.get("uspColorRGB", False)) or bool(dev.pluginProps.get("uspWhiteTemperature", False)):
                        color_mode_ui = u"{0} Unknown".format(payload)
                        if payload == "CT":
                            color_mode_ui = "Color Temperature"
                        elif payload == "RGB":
                            color_mode_ui = "Red/Green/Blue"
                        dev.updateStateOnServer(key="colorMode", value=payload, uiValue=color_mode_ui)

            # Check for Color Name
            elif topics[3] == "color-name":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if bool(dev.pluginProps.get("uspColorRGB", False)) or bool(dev.pluginProps.get("uspWhiteTemperature", False)):
                        color_name = u"{0}".format(payload)
                        dev.updateStateOnServer(key="colorName", value=color_name)

            # Check for Color
            elif topics[3] == "color":
                if len(topics) == 5 and topics[4] == "rgb":
                    for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if bool(dev.pluginProps.get("uspColorRGB", False)):
                            try:
                                if len(payload) != 7 or payload[0] != "#":
                                    return
                                hex_string = payload[1:]
                                rgb = bytearray.fromhex(hex_string)
                                red, green, blue = list(rgb)
                                red = int((float(red) / 256.0) * 100.0)
                                green = int((float(green) / 256.0) * 100.0)
                                blue = int((float(blue) / 256.0) * 100.0)
                            except ValueError:
                                return
                            key_value_list = list()
                            key_value_list.append({"key": "redLevel", "value": red})
                            key_value_list.append({"key": "greenLevel", "value": green})
                            key_value_list.append({"key": "blueLevel", "value": blue})
                            dev.updateStatesOnServer(key_value_list)

            # Check for Color Temperature
            elif topics[3] == "color-temperature" and len(topics) == 4:
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if bool(dev.pluginProps.get("uspWhiteTemperature", False)):
                        try:
                            white_temperature = int(payload)
                            white_temperature_ui = u"{0}ºK".format(payload)
                        except ValueError:
                            return
                        dev.updateStateOnServer(key="whiteTemperature", value=white_temperature, uiValue=white_temperature_ui)

            # Check for Contact
            elif topics[3] == "contact":
                if len(topics) == 5 and topics[4] == "status":
                    for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                        dev = indigo.devices[dev_id]
                        if dev.pluginProps.get("uspContact", False):
                            if payload == "open":
                                dev.updateStateOnServer(key="onOffState", value=True)
                                if topics[3] in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES[dev.deviceTypeId]:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                            else:
                                dev.updateStateOnServer(key="onOffState", value=False)
                                if topics[3] in HE_PRIMARY_INDIGO_DEVICE_TYPES_AND_HABITAT_PROPERTIES[dev.deviceTypeId]:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                            if not bool(dev.pluginProps.get("hideContactBroadcast", False)):
                                self.hubHandlerLogger.info(u"received \"{0}\" contact sensor \"{1}\" event".format(dev.name, payload))

            # Check for DIM
            elif topics[3] == "dim" and len(topics) == 4:  # Checking that this isn't a message from the plugin to set the value; topic would be '.../dim/set'
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if bool(dev.pluginProps.get("uspDimmer", False)):
                        try:
                            brightness_level = int(payload)
                            brightness_level_ui = u"{0}".format(brightness_level)
                        except ValueError:
                            return

                        self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_DIM] = brightness_level

                        brighten_dim_ui = u"set"
                        if brightness_level > 0:
                            if brightness_level > dev.brightness:
                                brighten_dim_ui = u"brighten"
                            else:
                                brighten_dim_ui = u"dim"

                        if brightness_level > 0:
                            dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOn)
                        else:
                            dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOff)

                        dev.updateStateOnServer(key='brightnessLevel', value=brightness_level, uiValue=brightness_level_ui)
                        if bool(dev.pluginProps.get("SupportsWhite", False)):
                            dev.updateStateOnServer(key='whiteLevel', value=brightness_level)
                        if not bool(dev.pluginProps.get("hideDimmerBroadcast", False)):
                            self.hubHandlerLogger.info(u"received {0} \"{1}\" to {2}".format(brighten_dim_ui, dev.name, brightness_level_ui))

                    elif bool(dev.pluginProps.get("uspValve", False)):
                        def _evaluate_valve(_payload, _previous_valve_level):
                            try:
                                _valve_level = int(_payload)
                                _valve_level_ui = u"{0}%".format(_valve_level)
                            except ValueError:
                                return False

                            _valve_action_ui = u"set"
                            if _valve_level > 0:
                                try:
                                    _current_valve_level = int(_previous_valve_level)
                                except ValueError:
                                    _current_valve_level = 0
                                if _valve_level > _current_valve_level:
                                    _valve_action_ui = u"open"
                                else:
                                    _valve_action_ui = u"close"

                            return True, _valve_level, _valve_level_ui, _valve_action_ui

                        if dev.pluginProps.get("uspValveIndigo", INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE) == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:

                            evaluated_valve = _evaluate_valve(payload, dev.states["valve"])
                            if evaluated_valve[0]:
                                valve_level = evaluated_valve[1]
                                valve_level_ui = evaluated_valve[2]
                                valve_action_ui = evaluated_valve[3]
                                dev.updateStateOnServer(key='valve', value=valve_level, uiValue=valve_level_ui)
                                if not bool(dev.pluginProps.get("hideValveBroadcast", False)):
                                    self.hubHandlerLogger.info(u"received {0} \"{1}\" valve to {2}".format(valve_action_ui, dev.name, valve_level_ui))

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

                                    self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_VALVE_LEVEL] = valve_dev.brightness

                                    if valve_level > 0:
                                        valve_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
                                    else:
                                        valve_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

                                    valve_dev.updateStateOnServer(key='brightnessLevel', value=valve_level, uiValue=valve_level_ui)
                                    if not bool(dev.pluginProps.get("hideValveBroadcast", False)):
                                        self.hubHandlerLogger.info(u"received {0} \"{1}\" to {2}".format(valve_action_ui, valve_dev.name, valve_level_ui))

            # Check for Energy
            elif topics[3] == "measure-energy" or topics[3] == "energy":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if bool(dev.pluginProps.get("uspEnergy", False)):
                        energy_units_ui = u" {0}".format(dev.pluginProps.get("uspEnergyUnits", ""))
                        try:
                            energy = float(payload)
                        except ValueError:
                            return
                        decimal_places = int(dev.pluginProps.get("uspEnergyDecimalPlaces", 0))
                        value, uiValue = self.processDecimalPlaces(energy, decimal_places, energy_units_ui, INDIGO_NO_SPACE_BEFORE_UNITS)
                        dev.updateStateOnServer(key='accumEnergyTotal', value=value, uiValue=uiValue)
                        if not bool(dev.pluginProps.get("hideEnergyBroadcast", False)):
                            self.hubHandlerLogger.info(u"received \"{1}\" accumulated energy total update to {0}".format(uiValue, dev.name))

            # Check for Humidity
            elif topics[3] == "measure-humidity" or topics[3] == "humidity":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
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
                        if uspHumidityIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
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
                            self.hubHandlerLogger.error(u"received \"{0}\" humidity update but unable to determine how to store update?".format(broadcast_device_name))
                            return

                        if not bool(dev.pluginProps.get("hideHumidityBroadcast", False)):
                            self.hubHandlerLogger.info(u"received \"{1}\" humidity update to {0}".format(uiValue, broadcast_device_name))

            # Check for Illuminance
            elif topics[3] == "measure-illuminance" or topics[3] == "illuminance":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
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
                        if uspIlluminanceIndigo == INDIGO_PRIMARY_DEVICE_ADDITIONAL_STATE:
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
                            self.hubHandlerLogger.error(u"received \"{0}\" illuminance update but unable to determine how to store update?".format(broadcast_device_name))
                            return

                        if not bool(dev.pluginProps.get("hideIlluminanceBroadcast", False)):
                            self.hubHandlerLogger.info(u"received \"{0}\" illuminance sensor \"{1}\" event".format(broadcast_device_name, uiValue))

            # Check for Motion
            elif topics[3] == "motion":
                if len(topics) == 5 and topics[4] == "status":
                    for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
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
                                self.hubHandlerLogger.error(u"received \"{0}\" motion sensor update but unable to determine how to store update?".format(broadcast_device_name))
                                return

                            if not bool(dev.pluginProps.get("hideMotionBroadcast", False)):
                                self.hubHandlerLogger.info(u"received \"{0}\" motion sensor \"{1}\" event".format(broadcast_device_name, uiValue))

            # Check for On / Off
            elif topics[3] == "onoff":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if dev.pluginProps.get("uspOnOff", False):
                        if payload not in ["on", "off", "true", "false"]:
                            return
                        if payload == "on" or payload == "true":
                            payload_ui = u"on"  # Force to On
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
                            if HE_STATES in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name]:
                                if HE_STATE_DIM in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES]:
                                    if dev.deviceTypeId == "dimmer":
                                        brightness_level = int(self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_DIM])
                                        brightness_level_ui = u"{0}".format(brightness_level)
                                        dev.updateStateOnServer(key='brightnessLevel', value=brightness_level, uiValue=brightness_level_ui)
                                        dev.updateStateOnServer(key='whiteLevel', value=brightness_level)
                                elif HE_STATE_VALVE_LEVEL in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES]:
                                    if dev.deviceTypeId == "valveSecondary":
                                        valve_level = int(self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_VALVE_LEVEL])
                                        valve_level_ui = u"{0}%".format(valve_level)
                                        dev.updateStateOnServer(key='brightnessLevel', value=valve_level, uiValue=valve_level_ui)
                        else:
                            # payload == "off" or payload == "false"
                            payload_ui = u"off"  # Force to Off
                            if dev.deviceTypeId != "thermostat":
                                if dev.deviceTypeId == "dimmer" or dev.deviceTypeId == "valveSecondary":
                                    # Save current Valve Level before switching off
                                    if dev.brightness != 0:
                                        if HE_STATE_VALVE_LEVEL in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES]:
                                            self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_STATES][HE_STATE_VALVE_LEVEL] = dev.brightness
                                    brightness_level_ui = u"0"
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
                            device_tye_ui = ""
                            if dev.deviceTypeId == "dimmer":
                                device_tye_ui = "dimmer"
                            elif dev.deviceTypeId == "outlet (socket)":
                                device_tye_ui = "dimmer"
                            elif dev.deviceTypeId == "valveSecondary":
                                device_tye_ui = "valve"
                            self.hubHandlerLogger.info(u"received \"{0}\" {1} \"{2}\" event".format(dev.name, device_tye_ui, payload_ui))

            # Check for Power
            elif topics[3] == "measure-power" or topics[3] == "power":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if bool(dev.pluginProps.get("uspPower", False)):
                        power_units_ui = u" {0}".format(dev.pluginProps.get("uspPowerUnits", ""))
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
                        #     self.hubHandlerLogger.warning(u"HE Report Power State: Power={0}, Previous={1}, Level={2}, Min={3}, Max={4}"
                        #                                   .format(power, previousPowerLevel, minimumPowerLevel, power_variance_minimum, power_variance_maximum))

                        decimal_places = int(dev.pluginProps.get("uspPowerDecimalPlaces", 0))
                        value, uiValue = self.processDecimalPlaces(power, decimal_places, power_units_ui, INDIGO_NO_SPACE_BEFORE_UNITS)
                        dev.updateStateOnServer(key='curEnergyLevel', value=value, uiValue=uiValue)
                        if report_power_state:
                            if not bool(dev.pluginProps.get("hidePowerBroadcast", False)):
                                self.hubHandlerLogger.info(u"received \"{1}\" power update to {0}".format(uiValue, dev.name))

            # Check for Presence
            if topics[3] == "presence-sensor" or topics[3] == "presence":
                if len(topics) == 5 and topics[4] == "status":
                    for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
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
                                self.hubHandlerLogger.error(u"received \"{0}\" presence sensor update but unable to determine how to store update?".format(broadcast_device_name))
                                return

                            if not bool(dev.pluginProps.get("hidePresenceBroadcast", False)):
                                self.hubHandlerLogger.info(u"received \"{0}\" presence sensor \"{1}\" event".format(broadcast_device_name, uiValue))

            # Check for Pressure
            elif topics[3] == "measure-pressure" or topics[3] == "pressure":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
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
                                    linked_dev.updateStateImageOnServer(indigo.kStateImageSel.None)  # TODO: Decide best icon
                                else:
                                    linked_dev.updateStateImageOnServer(indigo.kStateImageSel.None)  # TODO: Decide best icon
                                broadcast_device_name = linked_dev.name
                        else:
                            self.hubHandlerLogger.error(u"received \"{0}\" pressure update but unable to determine how to store update?".format(broadcast_device_name))
                            return

                        if not bool(dev.pluginProps.get("hidePressureBroadcast", False)):
                            self.hubHandlerLogger.info(u"received \"{0}\" pressure sensor update to \"{1}\" event".format(broadcast_device_name, uiValue))

            # Check for HVAC Mode
            elif topics[3] == "mode":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
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
                            self.hubHandlerLogger.warning(u"received \"{1}\" hvac unknown mode update: payload = '{0}'".format(payload, dev.name))
                            return

                        dev.updateStateOnServer(key='hvacMode', value=payload)
                        if not bool(dev.pluginProps.get("hideHvacModeBroadcast", False)):
                            dev.updateStateOnServer(key='hvacOperationMode', value=indigo_state_value)
                            self.hubHandlerLogger.info(u"received \"{1}\" hvac mode update to {0}".format(payload, dev.name))

            # Check for HVAC State
            elif topics[3] == "state":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if dev.deviceTypeId == "thermostat" and dev.pluginProps.get("uspHvacState", False):
                        dev.updateStateOnServer(key='hvacState', value=payload)
                        if not bool(dev.pluginProps.get("hideHvacStateBroadcast", False)):
                            self.hubHandlerLogger.info(u"received \"{1}\" hvac state update to {0}".format(payload, dev.name))

            # Check for Setpoint
            elif topics[3] == "thermostat-setpoint":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if dev.pluginProps.get("uspSetpoint", False):
                        try:
                            setpointUnitsConversion = dev.pluginProps.get("uspSetpointUnitsConversion", "C")
                            if setpointUnitsConversion in ["C", "F>C"]:  # noqa [Duplicated code fragment!]
                                setpoint_unit_ui = u"ºC"
                            else:
                                setpoint_unit_ui = u"ºF"
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
                        # if topics[3] in HE_DEVICE_TYPES_MAIN_HABITAT_PROPERTIES[dev.deviceTypeId]:
                        #     dev.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
                        if not bool(dev.pluginProps.get("hideSetpointBroadcast", False)):
                            self.hubHandlerLogger.info(u"received \"{1}\" setpoint update to {0}".format(uiValue, dev.name))

            # Check for Temperature
            elif topics[3] == "measure-temperature" or topics[3] == "temperature":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
                    dev = indigo.devices[dev_id]
                    if dev.pluginProps.get("uspTemperature", False):
                        try:
                            temperatureUnitsConversion = dev.pluginProps.get("uspTemperatureUnitsConversion", "C")
                            if temperatureUnitsConversion in ["C", "F>C"]:  # noqa [Duplicated code fragment!]
                                temperature_unit_ui = u"ºC"
                            else:
                                temperature_unit_ui = u"ºF"
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
                            self.hubHandlerLogger.error(u"received \"{0}\" temperature update but unable to determine how to store update?".format(broadcast_device_name))
                            return

                        if not bool(dev.pluginProps.get("hideTemperatureBroadcast", False)):
                            self.hubHandlerLogger.info(u"received \"{1}\" temperature update to {0}".format(uiValue, broadcast_device_name))

            # Check for Voltage
            elif topics[3] == "measure-voltage" or topics[3] == "voltage":
                for dev_id in self.globals[HE_HUBS][self.hubitat_hub_name][HE_DEVICES][hubitat_device_name][HE_LINKED_INDIGO_DEVICES]:
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
                            self.hubHandlerLogger.error(u"received \"{0}\" voltage update but unable to determine how to store update?".format(broadcast_device_name))
                            return

                        if not bool(dev.pluginProps.get("hideVoltageBroadcast", False)):
                            self.hubHandlerLogger.info(u"received \"{0}\" voltage \"{1}\" event".format(broadcast_device_name, uiValue))

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method 'handle_message'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

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

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method 'determine_secondary_device_id'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def processDecimalPlaces(self, field, decimal_places, units, space_before_units):
        try:
            units_plus_optional_space = u" {0}".format(units) if space_before_units else u"{0}".format(units)  # noqa [Duplicated code fragment!]
            if decimal_places == 0:
                return int(field), u"{0}{1}".format(int(field), units_plus_optional_space)
            else:
                value = round(field, decimal_places)

                uiValue = u"{{0:.{0}f}}{1}".format(decimal_places, units_plus_optional_space).format(field)

                return value, uiValue

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.hubHandlerLogger.error(u"Error detected in 'hubHandler' method 'processDecimalPlaces'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def mqtt_filter_log_processing(self, hubitat_key, hub_name, topics, payload):
        log_mqtt_msg = False  # Assume MQTT message should NOT be logged
        # Check if MQTT message filtering required
        if HE_MQTT_FILTERS in self.globals:
            if len(self.globals[HE_MQTT_FILTERS]) > 0 and self.globals[HE_MQTT_FILTERS] != [u"-0-"]:
                # As entries exist in the filter list, only log MQTT message in Hubitat device in the filter list
                if self.globals[HE_MQTT_FILTERS] == [u"-1-"] or hubitat_key in self.globals[HE_MQTT_FILTERS]:
                    log_mqtt_msg = True

        if log_mqtt_msg:
            self.hubHandlerLogger.topic(u"Received from '{0}': Topic='{1}', Payload='{2}'".format(hub_name, topics, payload))  # noqa [Unresolved attribute reference]
