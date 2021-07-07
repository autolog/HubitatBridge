#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Hubitat - Tasmota Handler © Autolog 2021
#

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError, e:
    pass

import json
import logging
import paho.mqtt.client as mqtt
import sys
import threading
import time

from constants import *


# noinspection PyPep8Naming
class ThreadTasmotaHandler(threading.Thread):

    # This class handles Tasmota processing

    def __init__(self, pluginGlobals, tasmota_id, event):
        try:

            threading.Thread.__init__(self)

            self.globals = pluginGlobals

            self.tasmota_id = tasmota_id

            self.tasmotaHandlerLogger = logging.getLogger("Plugin.TASMOTA")
            self.tasmotaHandlerLogger.debug(u"Debugging Tasmota Handler Thread")

            self.threadStop = event

            self.bad_disconnection = False

            self.mqtt_client = self.globals[TASMOTA][TASMOTA_MQTT_CLIENT]
            self.mqtt_message_sequence = 0
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method '__init__'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def run(self):
        try:
            # time.sleep(2.0)  # Allow time for Indigo devices to start
            # Initialise routine on thread start
            self.tasmotaHandlerLogger.debug(u"Tasmota Handler Thread initialised")

            self.mqtt_client = mqtt.Client(client_id=self.globals[TASMOTA][TASMOTA_MQTT_CLIENT_ID],
                                           clean_session=True,
                                           userdata=None,
                                           protocol=mqtt.MQTTv31)
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_disconnect = self.on_disconnect
            self.mqtt_client.on_subscribe = self.on_subscribe
            self.mqtt_client.on_publish = self.on_publish
            for tasmota_subscription in self.globals[TASMOTA][TASMOTA_MQTT_TOPICS]:
                self.mqtt_client.message_callback_add(tasmota_subscription, self.handle_message)
            try:
                self.mqtt_client.connect(host=self.globals[TASMOTA][TASMOTA_MQTT_BROKER_IP],
                                         port=self.globals[TASMOTA][TASMOTA_MQTT_BROKER_PORT],
                                         keepalive=60,
                                         bind_address="")
            except:
                self.tasmotaHandlerLogger.warning(u"Unable to connect to MQTT for Tasmota Tasmota devices")

                # At this point, queue a recovery for n seconds time
                return

            # for tasmota_subscription in self.globals[TASMOTA][TASMOTA_MQTT_TOPICS]:
            #     self.mqtt_client.subscribe(tasmota_subscription, qos=1)
            # self.tasmotaHandlerLogger.info(u"MQTT subscription(s) to Tasmota devices is initialized")

            self.globals[TASMOTA][TASMOTA_MQTT_CLIENT] = self.mqtt_client

            self.tasmotaHandlerLogger.debug(u"Autolog Tasmota now started")
            self.mqtt_client.loop_start()

            while not self.threadStop.is_set():
                try:
                    time.sleep(2)
                except self.threadStop:
                    pass  # Optionally catch the StopThread exception and do any needed cleanup.
                    self.mqtt_client.loop_stop()
                    self.globals[TASMOTA][TASMOTA_MQTT_INITIALISED] = False

            self.tasmotaHandlerLogger.debug(u"Tasmota Handler Thread close-down commencing.")

            self.handle_quit()
            
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'run'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def on_publish(self, client, userdata, mid):
        try:
            pass
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'on_publish'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def on_connect(self, client, userdata, flags, rc):
        try:
            indigo.devices[self.tasmota_id].updateStateOnServer(key='status', value="Connected")
            indigo.devices[self.tasmota_id].updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            for tasmota_subscription in self.globals[TASMOTA][TASMOTA_MQTT_TOPICS]:
                self.mqtt_client.subscribe(tasmota_subscription, qos=1)
            # self.tasmotaHandlerLogger.info(u"MQTT subscription(s) to Tasmota devices is initialized")

            self.globals[TASMOTA][TASMOTA_MQTT_INITIALISED] = True

            if self.bad_disconnection:
                self.bad_disconnection = False
                self.tasmotaHandlerLogger.info(u"'{0}' reconnected to MQTT Broker.".format(indigo.devices[self.tasmota_id].name))

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'on_connect'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def on_disconnect(self, client, userdata, rc):
        try:
            if rc != 0:
                self.tasmotaHandlerLogger.warning(u"'{0}' encountered an unexpected disconnection from MQTT Broker [Code {1}]. Retrying connection ...".format(indigo.devices[self.tasmota_id].name, rc))
                self.bad_disconnection = True
            else:
                self.tasmotaHandlerLogger.info(u"MQTT subscription to Tasmota ended")
                self.mqtt_client.loop_stop()
            try:
                indigo.devices[self.tasmota_id].updateStateOnServer(key='status', value="Disconnected")
                indigo.devices[self.tasmota_id].updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
            except KeyError:  # Indigo device may have been already deleted
                pass
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'on_disconnect'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def handle_quit(self):
        try:
            self.mqtt_client.disconnect()
            self.mqtt_client.loop_stop()
            self.tasmotaHandlerLogger.info(u"Autolog Tasmota disconnected from MQTT")
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'handle_quit'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def on_subscribe(self, client, userdata, mid, granted_qos):
        try:
            pass
        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'on_subscribe'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def handle_message(self, client, userdata, msg):
        try:
            # self.mqtt_message_sequence += 1
            # mqtt_message_sequence = '{0}'.format(self.mqtt_message_sequence)

            topics_list = msg.topic.split("/")
            payload = str(msg.payload)
            # qos = msg.qos

            indigo.devices[self.tasmota_id].updateStateOnServer(key='lastTopic', value=msg.topic)
            indigo.devices[self.tasmota_id].updateStateOnServer(key='lastPayload', value=msg.payload)

            # self.tasmotaHandlerLogger.warning(u"Tasmota Processing Topic = '{0}', Payload  = '{1}'".format(msg.topic, payload))

            if len(topics_list) == 0:
                return

            if len(topics_list) == 1:
                return

            if topics_list[0] == TASMOTA_ROOT_TOPIC_STAT:
                self.handle_message_stat(msg.topic, topics_list, payload)
            elif topics_list[0] == TASMOTA_ROOT_TOPIC_TELE:
                self.handle_message_tele(msg.topic, topics_list, payload)
            elif topics_list[0] == TASMOTA_ROOT_TOPIC_TASMOTA:
                self.handle_message_discovery(msg.topic, topics_list, payload)

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'handle_message'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def handle_message_discovery(self, msg_topic, topics_list, payload):
        try:
            if len(topics_list) != 4:
                return

            if topics_list[1] != TASMOTA_ROOT_TOPIC_DISCOVERY:
                return

            if len(topics_list[2]) != 12:
                return

            try:
                int(topics_list[2], 16)  # Check for hexadecimal
            except ValueError:
                return

            tasmota_key = topics_list[2][6:]

            self.mqtt_filter_log_processing(tasmota_key, msg_topic, payload)

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
                    self.tasmotaHandlerLogger.debug(u'Received [Payload Data]: \'{0}\''.format(payload_data))
                except ValueError:
                    self.tasmotaHandlerLogger.warning(u'Received [JSON Payload Data] could not be decoded: \'{0}\''.format(payload))
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
                                key_value_list.append({u"key": u"friendlyName", u"value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FRIENDLY_NAME]})
                                key_value_list.append({u"key": u"ipAddress", u"value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_IP_ADDRESS]})
                                key_value_list.append({u"key": u"macAddress", u"value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MAC]})
                                key_value_list.append({u"key": u"model", u"value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_MODEL]})
                                dev.updateStatesOnServer(key_value_list)

                                props = dev.ownerProps
                                firmware = props.get(u"version", "")
                                if firmware != self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE]:
                                    props[u"version"] = self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_FIRMWARE]
                                    dev.replacePluginPropsOnServer(props)



            elif topics_list[3] == "sensors":
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(u'Received [Payload Data]: \'{0}\''.format(payload_data))
                except ValueError:
                    self.tasmotaHandlerLogger.warning(u'Received [JSON Payload Data] could not be decoded: \'{0}\''.format(payload))
                    return

                if "sn" in payload_data:
                    self.update_energy_states(tasmota_key, payload_data["sn"])

                # Refresh Power State
                topic = u"cmnd/tasmota_{0}/Status".format(tasmota_key)  # e.g. "cmnd/tasmota_6E641A/Status"
                topic_payload = "8"  # Show power usage
                self.publish_tasmota_topic(tasmota_key, topic, topic_payload)

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'handle_message_discovery'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def handle_message_stat(self, msg_topic, topics_list, payload):
        try:
            if topics_list[1][0:8] != "tasmota_":
                return
            if len(topics_list[1][8:]) != 6:
                return
            try:
                int(topics_list[1][8:], 16)  # Check for hexadecimal
            except ValueError:
                return

            tasmota_key = topics_list[1][8:]

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
    
                # self.tasmotaHandlerLogger.warning(u"Tasmota [STAT] Topic: {0}, payload: {1}".format(topics, payload))

                if TASMOTA_INDIGO_DEVICE_ID in self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key]:
                    if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] != 0:
                        if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID] in indigo.devices:
                            dev = indigo.devices[self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_INDIGO_DEVICE_ID]]

                            if dev.deviceTypeId == "tasmotaOutlet":
                                key_value_list = list()
                                if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_POWER]:
                                    payload_ui = u"on"  # Force to On
                                    dev.updateStateOnServer(key="onOffState", value=True)
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                                else:
                                    payload_ui = u"off"  # Force to Off
                                    dev.updateStateOnServer(key="onOffState", value=False)
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
                                key_value_list.append({u"key": u"lwt", u"value": u"Online"})
                                dev.updateStatesOnServer(key_value_list)

                                if not bool(dev.pluginProps.get("hidePowerBroadcast", False)):
                                    self.tasmotaHandlerLogger.info(
                                        u"received \"{0}\" outlet state update: \"{1}\"".format(dev.name, payload_ui))
            elif topics_list[2] == "STATUS8":
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(u'Received [Payload Data]: \'{0}\''.format(payload_data))
                except ValueError:
                    self.tasmotaHandlerLogger.warning(u'Received [JSON Payload Data] could not be decoded: \'{0}\''.format(payload))
                    return

                if "StatusSNS" in payload_data:
                    self.update_energy_states(tasmota_key, payload_data["StatusSNS"])

            elif topics_list[2] == "RESULT":  # Result of Resetting Total
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(u'Received [Payload Data]: \'{0}\''.format(payload_data))
                except ValueError:
                    self.tasmotaHandlerLogger.warning(u'Received [JSON Payload Data] could not be decoded: \'{0}\''.format(payload))
                    return

                if "EnergyReset" in payload_data:
                    self.reset_energy_total(tasmota_key, payload_data["EnergyReset"])

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'handle_message_stat'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

    def handle_message_tele(self, msg_topic, topics_list, payload):
        try:
            if topics_list[1][0:8] != "tasmota_":
                return
            if len(topics_list[1][8:]) != 6:
                return
            try:
                int(topics_list[1][8:], 16)  # Check for hexadecimal
            except ValueError:
                return

            tasmota_key = topics_list[1][8:]
            self.mqtt_filter_log_processing(tasmota_key, msg_topic, payload)

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
                                    key_value_list.append({u"key": u"onOffState", u"value": False})
                                    key_value_list.append({u"key": u"lwt", u"value": u"Offline"})
                                    dev.updateStatesOnServer(key_value_list)
                                    dev.setErrorStateOnServer(u"offline")
                                else:
                                    key_value_list.append({u"key": u"lwt", u"value": u"Online"})
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                                    if dev.onState:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                                    else:
                                        dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

                                    dev.updateStatesOnServer(key_value_list)

            elif topics_list[2] == "SENSOR":
                try:
                    payload_data = json.loads(payload)
                    self.tasmotaHandlerLogger.debug(u'Received [Payload Data]: \'{0}\''.format(payload_data))
                except ValueError:
                    self.tasmotaHandlerLogger.warning(u'Received [JSON Payload Data] could not be decoded: \'{0}\''.format(payload))
                    return

                self.update_energy_states(tasmota_key, payload_data)

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'handle_message_tele'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))


    def mqtt_filter_log_processing(self, tasmota_key, msg_topic, payload):
        log_mqtt_msg = False  # Assume MQTT message should NOT be logged
        # Check if MQTT message filtering required
        if TASMOTA_MQTT_FILTERS in self.globals:
            if len(self.globals[TASMOTA_MQTT_FILTERS]) > 0 and self.globals[TASMOTA_MQTT_FILTERS] != [u"-0-"]:
                # As entries exist in the filter list, only log MQTT message in Tasmota device in the filter list
                if self.globals[TASMOTA_MQTT_FILTERS] == [u"-1-"] or tasmota_key in self.globals[TASMOTA_MQTT_FILTERS]:
                    log_mqtt_msg = True

        if log_mqtt_msg:
            self.tasmotaHandlerLogger.topic(u"Received from Tasmota: Topic='{0}', Payload='{1}'".format(msg_topic, payload))

    def update_tasmota_status(self, tasmota_key):
        try:
            if tasmota_key not in self.globals[TASMOTA][TASMOTA_QUEUE]:
                return
            dev_id = self.globals[TASMOTA][TASMOTA_QUEUE][tasmota_key]
            del self.globals[TASMOTA][TASMOTA_QUEUE][tasmota_key]

            # self.tasmotaHandlerLogger.warning(u"Requesting status update for '{0}'".format(indigo.devices[dev_id].name))

            topic = u"cmnd/tasmota_{0}/Power".format(tasmota_key)  # e.g. "cmnd/tasmota_6E641A/Power"
            topic_payload = u""  # No payload returns status
            self.publish_tasmota_topic(tasmota_key, topic, topic_payload)
            topic = u"cmnd/tasmota_{0}/Status".format(tasmota_key)  # e.g. "cmnd/tasmota_6E641A/Status"
            topic_payload = "8"  # Show power usage
            self.publish_tasmota_topic(tasmota_key, topic, topic_payload)

        except StandardError, err:
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'update_tasmota_status'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, err))

    def publish_tasmota_topic(self, tasmota_key, topic, payload):
        try:
            self.globals[TASMOTA][TASMOTA_MQTT_CLIENT].publish(topic, payload)

            log_mqtt_msg = False  # Assume MQTT message should NOT be logged
            # Check if MQTT message filtering required
            if TASMOTA_MQTT_FILTERS in self.globals:
                if len(self.globals[TASMOTA_MQTT_FILTERS]) > 0 and self.globals[TASMOTA_MQTT_FILTERS] != [u"-0-"]:
                    # As entries exist in the filter list, only log MQTT message in Tasmota device in the filter list
                    if self.globals[TASMOTA_MQTT_FILTERS] == [u"-1-"] or tasmota_key in self.globals[TASMOTA_MQTT_FILTERS]:
                        log_mqtt_msg = True

            if log_mqtt_msg:
                self.tasmotaHandlerLogger.topic(u">>> Published to Tasmota: Topic='{0}', Payload='{1}'".format(topic, payload))

        except StandardError, err:
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'publish_tasmota_topic'. Line '{0}' has error='{1}'"
                              .format(sys.exc_traceback.tb_lineno, err))

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

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'reset_energy_states'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))

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

                                # Only update the Acuumulated Energy Total if the new value isn't zero
                                if self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL] != 0.0:
                                    kwh = self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][TASMOTA_PAYLOAD_ENERGY_TOTAL]
                                    kwh_string = str("%0.3f kWh" % kwh)
                                    kwhReformatted = float(str("%0.3f" % kwh))
                                    key_value_list.append({"key": "accumEnergyTotal", "value": kwhReformatted, "uiValue": kwh_string})

                                wattStr = "%3.0f Watts" % (self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_POWER])
                                key_value_list.append({"key": "curEnergyLevel",
                                                       "value": self.globals[TASMOTA][TASMOTA_DEVICES][tasmota_key][
                                                           TASMOTA_PAYLOAD_ENERGY_POWER],
                                                       "uiValue": wattStr})
                                key_value_list.append({u"key": u"lwt", u"value": u"Online"})
                                dev.updateStatesOnServer(key_value_list)

        except Exception as err:
            trace_back = sys.exc_info()[2]
            self.tasmotaHandlerLogger.error(u"Error detected in 'tasmotaHandler' method 'update_energy_states'. Line '{0}' has error='{1}'".format(trace_back.tb_lineno, err))
