#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Hubitat - Tasmota Handler © Autolog 2021
#

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

import json
import logging
try:
    # Python 3
    import queue
except ImportError:
    # Python 2
    import Queue as queue

import sys
import threading
import traceback
import time

from constants import *


# noinspection PyPep8Naming
class ThreadTasmotaHandler(threading.Thread):

    # This class handles Tasmota processing

    def __init__(self, pluginGlobals, tasmota_id, event):
        try:

            threading.Thread.__init__(self)

            self.globals = pluginGlobals

            self.tasmotaHandlerLogger = logging.getLogger("Plugin.TASMOTA")

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
        self.tasmotaHandlerLogger.error(log_message)

    def run(self):
        try:
            while not self.threadStop.is_set():
                try:
                    mqtt_message_sequence, mqtt_process_command, mqtt_topics, mqtt_topics_list, mqtt_payload = self.globals[QUEUES][MQTT_TASMOTA_QUEUE].get(True, 5)

                    if mqtt_process_command == MQTT_PROCESS_COMMAND_HANDLE_TOPICS:
                        self.handle_topics(mqtt_topics, mqtt_topics_list, mqtt_payload)

                except queue.Empty:
                    pass
                except Exception as exception_error:
                    self.exception_handler(exception_error, True)  # Log error and display failing statement
            else:
                pass
                # TODO: At this point, queue a recovery for n seconds time
                # TODO: In the meanwhile, just disable and then enable the Indigo Hubitat Elevation Hub device

            self.tasmotaHandlerLogger.debug("Tasmota Handler Thread close-down commencing.")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handle_topics(self, topics, topics_list, payload):
        try:
            # Note that there are a minimum of three topic entries in the topics_list

            if topics_list[0] == TASMOTA_ROOT_TOPIC_STAT:
                self.handle_message_stat(topics, topics_list, payload)
            elif topics_list[0] == TASMOTA_ROOT_TOPIC_TELE:
                self.handle_message_tele(topics, topics_list, payload)
            elif topics_list[0] == TASMOTA_ROOT_TOPIC_TASMOTA:
                self.handle_message_discovery(topics, topics_list, payload)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handle_message_discovery(self, msg_topic, topics_list, payload):
        try:
            if len(topics_list) != 4:
                return

            if topics_list[1] != TASMOTA_ROOT_TOPIC_DISCOVERY:
                return

            # if len(topics_list[2]) != 12:
            #     return

            try:
                int(topics_list[2], 16)  # Check for hexadecimal
            except ValueError:
                return

            tasmota_key = topics_list[2][6:]

            # if tasmota_key not in self.globals[TASMOTA][MQTT_BROKERS]:
            #     return
            # subscribed = False
            # mqtt_client_device_id = self.globals[TASMOTA][MQTT_BROKERS][tasmota_key]  # TODO: Not a list for Tasmota - just one broker
            # if mqtt_client_device_id != 0:
            #     if self.globals[MQTT][mqtt_client_device_id][MQTT_CONNECTED]:
            #         if self.globals[MQTT][mqtt_client_device_id][MQTT_SUBSCRIBE_TO_TASMOTA]:
            #             subscribed = True
            # if not subscribed:
            #     return

            self.mqtt_filter_log_processing(tasmota_key, msg_topic, payload)  # noqa [Duplicated code fragment!]

            self.update_tasmota_status(tasmota_key)

            if tasmota_key not in self.globals[TASMOTA][TASMOTA_DEVICES]:
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key] = dict()
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_DISCOVERY_DETAILS] = False
            if TASMOTA_INDIGO_DEVICE_ID not in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] = 0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_POWER] = False
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE] = "n/a"
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_DEVICE_NAME] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_T] = ""

            if tasmota_key in self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS]:
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] = self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS][tasmota_key]

            if topics_list[3] == "config":
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(f'Received [Payload Data]: \'{payload_data}\'')
                except ValueError:
                    self.tasmotaHandlerLogger.warning(f'Received [JSON Payload Data] could not be decoded: \'{payload}\'')
                    return

                if "sw" in payload_data:
                    firmware = payload_data["sw"]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE] = firmware
                if "fn" in payload_data:
                    friendly_name = payload_data["fn"][0]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME] = friendly_name
                if "dn" in payload_data:
                    device_name = payload_data["dn"]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_DEVICE_NAME] = device_name
                if "mac" in payload_data:
                    mac = payload_data["mac"]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC] = mac
                if "md" in payload_data:
                    model = payload_data["md"]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL] = model
                if "t" in payload_data:
                    t_field = payload_data["t"]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_T] = t_field
                if "ip" in payload_data:
                    ip = payload_data["ip"]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_IP_ADDRESS] = ip

                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_DISCOVERY_DETAILS] = True

                if TASMOTA_INDIGO_DEVICE_ID in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                    if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] != 0:
                        if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] in indigo.devices:
                            dev = indigo.devices[self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID]]

                            if dev.deviceTypeId == "tasmotaOutlet":
                                key_value_list = list()
                                key_value_list.append({"key": "friendlyName", "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME]})
                                key_value_list.append({"key": "ipAddress", "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_IP_ADDRESS]})
                                key_value_list.append({"key": "macAddress", "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC]})
                                key_value_list.append({"key": "model", "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL]})
                                dev.updateStatesOnServer(key_value_list)

                                props = dev.ownerProps
                                firmware = props.get("version", "")
                                if firmware != self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE]:
                                    props["version"] = self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE]
                                    dev.replacePluginPropsOnServer(props)

            elif topics_list[3] == "sensors":
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(f'Received [Payload Data]: \'{payload_data}\'')
                except ValueError:
                    self.tasmotaHandlerLogger.warning(f'Received [JSON Payload Data] could not be decoded: \'{payload}\'')
                    return

                if "sn" in payload_data:
                    self.update_energy_states(tasmota_key, payload_data["sn"])

                # Refresh Power State
                topic = f"cmnd/tasmota_{tasmota_key}/Status"  # e.g. "cmnd/tasmota_6E641A/Status"
                topic_payload = "8"  # Show power usage
                self.publish_tasmota_topic(tasmota_key, topic, topic_payload)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handle_message_stat(self, msg_topic, topics_list, payload):
        try:
            if topics_list[1][0:8] != "tasmota_":  # noqa [Duplicated code fragment!]
                return
            if len(topics_list[1][8:]) != 6:
                return
            try:
                int(topics_list[1][8:], 16)  # Check for hexadecimal
            except ValueError:
                return

            tasmota_key = topics_list[1][8:]

            if tasmota_key not in self.globals[TASMOTA][MQTT_BROKERS]:
                return
            subscribed = False
            mqtt_client_device_id = self.globals[TASMOTA][MQTT_BROKERS][tasmota_key]  # TODO: Not a list for Tasmota - just one broker
            if mqtt_client_device_id != 0:
                if self.globals[MQTT][mqtt_client_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_client_device_id][MQTT_SUBSCRIBE_TO_TASMOTA]:
                        subscribed = True
            if not subscribed:
                return

            self.mqtt_filter_log_processing(tasmota_key, msg_topic, payload)

            if len(topics_list) != 3:
                return

            if topics_list[2] == "POWER":
                if payload == "OFF":
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_POWER] = False
                elif payload == "ON":
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_POWER] = True
                else:
                    return
    
                # self.tasmotaHandlerLogger.warning(f"Tasmota [STAT] Topic: {topics}, payload: {payload}")

                if TASMOTA_INDIGO_DEVICE_ID in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                    if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] != 0:
                        if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] in indigo.devices:
                            dev = indigo.devices[self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID]]

                            if dev.deviceTypeId == "tasmotaOutlet":
                                key_value_list = list()
                                if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_POWER]:
                                    payload_ui = "on"  # Force to On
                                    dev.updateStateOnServer(key="onOffState", value=True)
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                                else:
                                    payload_ui = "off"  # Force to Off
                                    dev.updateStateOnServer(key="onOffState", value=False)
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
                                key_value_list.append({"key": "lwt", "value": "Online"})
                                dev.updateStatesOnServer(key_value_list)

                                if not bool(dev.pluginProps.get("hidePowerBroadcast", False)):
                                    self.tasmotaHandlerLogger.info(
                                        f"received \"{dev.name}\" outlet state update: \"{payload_ui}\"")
            elif topics_list[2] == "STATUS8":
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(f'Received [Payload Data]: \'{payload_data}\'')
                except ValueError:
                    self.tasmotaHandlerLogger.warning(f'Received [JSON Payload Data] could not be decoded: \'{payload}\'')
                    return

                if "StatusSNS" in payload_data:
                    self.update_energy_states(tasmota_key, payload_data["StatusSNS"])

            elif topics_list[2] == "RESULT":  # Result of Resetting Total
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(f'Received [Payload Data]: \'{payload_data}\'')
                except ValueError:
                    self.tasmotaHandlerLogger.warning(f'Received [JSON Payload Data] could not be decoded: \'{payload}\'')
                    return

                if "EnergyReset" in payload_data:
                    self.reset_energy_total(tasmota_key, payload_data["EnergyReset"])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handle_message_tele(self, msg_topic, topics_list, payload):
        try:
            # self.tasmotaHandlerLogger.warning(f"TASMOTA [handle_message_tele]: Topic={msg_topic}, Payload={payload}")
            if topics_list[1][0:8] != "tasmota_":  # noqa [Duplicated code fragment!]
                return
            if len(topics_list[1][8:]) != 6:
                return
            try:
                int(topics_list[1][8:], 16)  # Check for hexadecimal
            except ValueError:
                return

            tasmota_key = topics_list[1][8:]

            subscribed = False
            if tasmota_key not in self.globals[TASMOTA][MQTT_BROKERS]:
                return
            mqtt_client_device_id = self.globals[TASMOTA][MQTT_BROKERS][tasmota_key]  # TODO: Not a list for Tasmota - just one broker
            if mqtt_client_device_id != 0:
                if self.globals[MQTT][mqtt_client_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_client_device_id][MQTT_SUBSCRIBE_TO_TASMOTA]:
                        subscribed = True
            if not subscribed:
                return

            self.mqtt_filter_log_processing(tasmota_key, msg_topic, payload)

            self.update_tasmota_status(tasmota_key)  # noqa [Duplicated code fragment!]

            if tasmota_key not in self.globals[TASMOTA][TASMOTA_DEVICES]:
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key] = dict()
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_DISCOVERY_DETAILS] = False
            if TASMOTA_INDIGO_DEVICE_ID not in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] = 0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_POWER] = False
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE] = "n/a"
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_DEVICE_NAME] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_T] = ""

            if (tasmota_key in self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS] and
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] == 0):
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] = self.globals[TASMOTA][TASMOTA_KEYS_TO_INDIGO_DEVICE_IDS][tasmota_key]

                if not self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_DISCOVERY_DETAILS]:
                    tasmota_dev = indigo.devices[self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID]]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME] = tasmota_dev.states["friendlyName"]
                    # self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_DEVICE_NAME] = tasmota_dev.states["friendlyName"]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC] = tasmota_dev.states["macAddress"]
                    self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL] = tasmota_dev.states["model"]
                    # self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_T] = tasmota_dev.states["friendlyName"]

            if topics_list[2] == "LWT":
                if TASMOTA_INDIGO_DEVICE_ID in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                    if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] != 0:
                        if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] in indigo.devices:
                            dev = indigo.devices[self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID]]

                            key_value_list = list()
                            if dev.deviceTypeId == "tasmotaOutlet":
                                if payload != "Online":
                                    key_value_list.append({"key": "onOffState", "value": False})
                                    key_value_list.append({"key": "lwt", "value": "Offline"})
                                    dev.updateStatesOnServer(key_value_list)
                                    dev.setErrorStateOnServer("offline")
                                else:
                                    key_value_list.append({"key": "lwt", "value": "Online"})
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                                    if dev.onState:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                                    else:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

                                    dev.updateStatesOnServer(key_value_list)

            elif topics_list[2] == "SENSOR":
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(f'Received [Payload Data]: \'{payload_data}\'')
                except ValueError:
                    self.tasmotaHandlerLogger.warning(f'Received [JSON Payload Data] could not be decoded: \'{payload}\'')
                    return

                self.update_energy_states(tasmota_key, payload_data)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def mqtt_filter_log_processing(self, tasmota_key, msg_topic, payload):
        log_mqtt_msg = False  # Assume MQTT message should NOT be logged
        # Check if MQTT message filtering required
        if TASMOTA_MQTT_FILTERS in self.globals:
            if len(self.globals[TASMOTA_MQTT_FILTERS]) > 0 and self.globals[TASMOTA_MQTT_FILTERS] != ["-0-"]:
                # As entries exist in the filter list, only log MQTT message in Tasmota device in the filter list
                if self.globals[TASMOTA_MQTT_FILTERS] == ["-1-"] or tasmota_key in self.globals[TASMOTA_MQTT_FILTERS]:
                    log_mqtt_msg = True

        if log_mqtt_msg:
            self.tasmotaHandlerLogger.topic(f"Received from Tasmota: Topic='{msg_topic}', Payload='{payload.decode('utf-8')}'")  # noqa [unresolved attribute reference]

    def update_tasmota_status(self, tasmota_key):
        try:
            if tasmota_key not in self.globals[TASMOTA][TASMOTA_QUEUE]:
                return
            # dev_id = self.globals[TASMOTA][TASMOTA_QUEUE][tasmota_key]
            del self.globals[TASMOTA][TASMOTA_QUEUE][tasmota_key]

            # self.tasmotaHandlerLogger.warning(f"Requesting status update for '{indigo.devices[dev_id].name}'")

            topic = f"cmnd/tasmota_{tasmota_key}/Power"  # e.g. "cmnd/tasmota_6E641A/Power"
            topic_payload = ""  # No payload returns status
            self.publish_tasmota_topic(tasmota_key, topic, topic_payload)
            topic = f"cmnd/tasmota_{tasmota_key}/Status"  # e.g. "cmnd/tasmota_6E641A/Status"
            topic_payload = "8"  # Show power usage
            self.publish_tasmota_topic(tasmota_key, topic, topic_payload)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def publish_tasmota_topic(self, tasmota_key, topic, payload):
        try:
            published = False
            if tasmota_key not in self.globals[TASMOTA][MQTT_BROKERS]:
                return
            mqtt_client_device_id = self.globals[TASMOTA][MQTT_BROKERS][tasmota_key]  # TODO: Not a list for Tasmota - just one broker
            if mqtt_client_device_id != 0:
                if self.globals[MQTT][mqtt_client_device_id][MQTT_CONNECTED]:
                    if self.globals[MQTT][mqtt_client_device_id][MQTT_PUBLISH_TO_HOMIE]:
                        self.globals[MQTT][mqtt_client_device_id][MQTT_CLIENT].publish(topic, payload, 1, True)  # noqa [parameter value is not used] - n.b. QOS=1 Retain=True
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
                    self.tasmotaHandlerLogger.topic(f">>> Published to Tasmota: Topic='{topic}', Payload='{payload.decode('utf-8')}'")  # noqa [unresolved attribute reference]

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def reset_energy_total(self, tasmota_key, payload_data):
        try:
            if "Total" in payload_data:
                if float(payload_data["Total"]) == 0.0:
                    if TASMOTA_INDIGO_DEVICE_ID in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                        if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] != 0:
                            if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] in indigo.devices:
                                dev = indigo.devices[self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID]]
                                if dev.deviceTypeId == "tasmotaOutlet":
                                    key_value_list = list()
                                    kwh = self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL]
                                    kwh_string = str("%0.3f kWh" % kwh)
                                    kwhReformatted = float(str("%0.3f" % kwh))
                                    key_value_list.append({"key": "accumEnergyTotal", "value": kwhReformatted, "uiValue": kwh_string})
                                    dev.updateStatesOnServer(key_value_list)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def update_energy_states(self, tasmota_key, payload_data):
        try:
            if "ENERGY" not in payload_data or "Time" not in payload_data:
                return

            if TASMOTA_PAYLOAD_TIME not in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_APPARENT_POWER] = 0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_CURRENT] = 0.0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_FACTOR] = 0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_PERIOD] = 0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_POWER] = 0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_REACTIVE_POWER] = 0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TODAY] = 0.0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL] = 0.0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL_START_TIME] = ""
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_VOLTAGE] = 0
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_YESTERDAY] = 0.0

            self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_TIME] = payload_data["Time"]

            payload_energy = payload_data["ENERGY"]
            if "ApparentPower" in payload_energy:
                apparent_power = int(payload_energy["ApparentPower"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                    TASMOTA_PAYLOAD_ENERGY_APPARENT_POWER] = apparent_power
            if "Current" in payload_energy:
                current = int(payload_energy["Current"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_CURRENT] = current
            if "Factor" in payload_energy:
                factor = int(payload_energy["Factor"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_FACTOR] = factor
            if "Period" in payload_energy:
                period = int(payload_energy["Period"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_PERIOD] = period
            if "Power" in payload_energy:
                power = int(payload_energy["Power"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_POWER] = power
            if "ReactivePower" in payload_energy:
                reactive_power = int(payload_energy["ReactivePower"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                    TASMOTA_PAYLOAD_ENERGY_REACTIVE_POWER] = reactive_power
            if "Today" in payload_energy:
                today = float(payload_energy["Today"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TODAY] = today
            if "Total" in payload_energy:
                total = float(payload_energy["Total"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL] = total
            if "TotalStartTime" in payload_energy:
                total_start_time = payload_energy["TotalStartTime"]
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                    TASMOTA_PAYLOAD_ENERGY_TOTAL_START_TIME] = total_start_time
            if "Voltage" in payload_energy:
                voltage = int(payload_energy["Voltage"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_VOLTAGE] = voltage
            if "Yesterday" in payload_energy:
                yesterday = float(payload_energy["Yesterday"])
                self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_YESTERDAY] = yesterday

            if TASMOTA_INDIGO_DEVICE_ID in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] != 0:
                    if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] in indigo.devices:
                        dev = indigo.devices[self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID]]

                        if dev.deviceTypeId == "tasmotaOutlet":
                            tasmota_update_time = dev.states["tasmotaUpdateTime"]
                            if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_TIME] > tasmota_update_time:
                                key_value_list = list()
                                key_value_list.append({"key": "energyApparentPower",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_APPARENT_POWER]})
                                key_value_list.append({"key": "energyCurrent",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_CURRENT]})
                                key_value_list.append({"key": "energyFactor",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_FACTOR]})
                                key_value_list.append({"key": "energyPeriod",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_PERIOD]})

                                key_value_list.append({"key": "energyPower",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_POWER]})
                                key_value_list.append({"key": "energyReactivePower",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_REACTIVE_POWER]})
                                key_value_list.append({"key": "energyToday",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_TODAY]})
                                key_value_list.append({"key": "energyTotal",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL]})
                                key_value_list.append({"key": "energyTotalStartTime",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_TOTAL_START_TIME]})
                                key_value_list.append({"key": "energyVoltage",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_VOLTAGE]})
                                key_value_list.append({"key": "energyYesterday",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_YESTERDAY]})
                                key_value_list.append({"key": "tasmotaUpdateTime",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_TIME]})

                                # Update Indigo UI states: "accumEnergyTotal" and "curEnergyLevel"

                                power_units_ui = f" {dev.pluginProps.get('tasmotaPowerUnits', 'Watts')}"
                                try:
                                    power = float(self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_POWER])
                                except ValueError:
                                    return
                                minimumPowerLevel = float(dev.pluginProps.get("tasmotaPowerMinimumReportingLevel", 0.0))
                                reportingPowerHysteresis = float(dev.pluginProps.get("tasmotaPowerReportingHysteresis", 6.0))
                                if reportingPowerHysteresis > 0.0:  # noqa [Duplicated code fragment!]
                                    reportingPowerHysteresis = reportingPowerHysteresis / 2
                                previousPowerLevel = float(dev.states["curEnergyLevel"])
                                report_power_state = False
                                power_variance_minimum = previousPowerLevel - reportingPowerHysteresis
                                power_variance_maximum = previousPowerLevel + reportingPowerHysteresis
                                if power_variance_minimum < 0.0:
                                    power_variance_minimum = 0.0
                                if power >= minimumPowerLevel:
                                    if power < power_variance_minimum or power > power_variance_maximum:
                                        report_power_state = True
                                elif previousPowerLevel >= minimumPowerLevel:
                                    if power < power_variance_minimum or power > power_variance_maximum:
                                        report_power_state = True

                                # if power != previousPowerLevel:
                                #     self.tasmotaHandlerLogger.warning(
                                #         f"Tasmota Report Power State: Power={power}, Previous={previousPowerLevel}, Level={minimumPowerLevel}, Min={power_variance_minimum}, Max={power_variance_maximum}")

                                decimal_places = int(dev.pluginProps.get("tasmotaPowerDecimalPlaces", 0))
                                value, uiValue = self.processDecimalPlaces(power, decimal_places, power_units_ui, INDIGO_NO_SPACE_BEFORE_UNITS)
                                key_value_list.append({"key": "curEnergyLevel", "value": value, "uiValue": uiValue})
                                if report_power_state:
                                    if not bool(dev.pluginProps.get("hideTasmotaPowerBroadcast", False)):
                                        self.tasmotaHandlerLogger.info(f"received \"{dev.name}\" power update to {uiValue}")

                                # Only update the Accumulated Energy Total if the new value isn't zero
                                if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL] != 0.0:
                                    total_units_ui = f" {dev.pluginProps.get('tasmotaPowerAccumulatedUnits', 'kWh')}"
                                    total = self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL]
                                    decimal_places = int(dev.pluginProps.get("tasmotaPowerAccumulatedDecimalPlaces", 3))
                                    value, uiValue = self.processDecimalPlaces(total, decimal_places, total_units_ui, INDIGO_NO_SPACE_BEFORE_UNITS)
                                    key_value_list.append({"key": "accumEnergyTotal", "value": value, "uiValue": uiValue})

                                dev.updateStatesOnServer(key_value_list)

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
