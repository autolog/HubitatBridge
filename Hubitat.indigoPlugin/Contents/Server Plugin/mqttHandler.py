#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Hubitat - MQTT Handler © Autolog 2022 - 2023
#

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    pass

import logging

try:
    import paho.mqtt.client as mqtt
except ImportError:
    pass

import sys
import threading
import traceback
import time

from constants import *


# https://cryptography.io/en/latest/fernet/#using-passwords-with-fernet
def decode(key, encrypted_password):
    # print(f"Python 3 Decode, Arguments: Key='{key}', Encrypted Password='{encrypted_password}'")

    f = Fernet(key)
    unencrypted_password = f.decrypt(encrypted_password)

    # print(f"Python 3 Decode: Unencrypted Password = {unencrypted_password}")

    return unencrypted_password


# noinspection PyPep8Naming
class ThreadMqttHandler(threading.Thread):

    # This class handles interactions with the MQTT Broker

    def __init__(self, pluginGlobals, event, mqtt_Broker_dev_id):
        try:

            threading.Thread.__init__(self)

            self.globals = pluginGlobals

            self.mqtt_client = None

            self.mqtt_broker_dev_id = mqtt_Broker_dev_id

            self.mqttHandlerLogger = logging.getLogger("Plugin.MQTT")
            self.mqttHandlerLogger.debug(f"Debugging '{indigo.devices[self.mqtt_broker_dev_id]}' MQTT Handler Thread")

            self.threadStop = event

            self.bad_disconnection = False

            self.publish_to_homie = None
            self.publish_to_tasmota = None
            self.subscribe_to_homie = None
            self.subscribe_to_tasmota = None

            self.mqtt_message_sequence = 0
            
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
        self.mqttHandlerLogger.error(log_message)

    def run(self):
        try:
            # Initialise routine on thread start

            mqtt_broker_dev = indigo.devices[self.mqtt_broker_dev_id]
            mqtt_broker_dev.updateStateOnServer(key="status", value="disconnected")
            mqtt_broker_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            self.mqttHandlerLogger.info(f"Client ID: {self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_CLIENT_ID]}")

            self.mqtt_client = mqtt.Client(client_id=self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_CLIENT_ID],
                                           clean_session=True,
                                           userdata=None,
                                           protocol=self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PROTOCOL])

            # self.client = mqtt.Client(client_id=f"indigo-mqtt-{device.id}", clean_session=True, userdata=None, protocol=self.protocol, transport=self.transport)  # Example from @FlyingDiver

            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_disconnect = self.on_disconnect
            self.mqtt_client.on_subscribe = self.on_subscribe

            self.publish_to_homie = bool(mqtt_broker_dev.pluginProps.get("mqtt_publish_to_homie", True))
            self.publish_to_tasmota = bool(mqtt_broker_dev.pluginProps.get("mqtt_publish_to_tasmota", True))
            self.subscribe_to_homie = bool(mqtt_broker_dev.pluginProps.get("mqtt_subscribe_to_homie", True))
            self.subscribe_to_tasmota = bool(mqtt_broker_dev.pluginProps.get("mqtt_subscribe_to_tasmota", True))

            self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBED_TOPICS] = list()
            if self.subscribe_to_homie:
                self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBED_TOPICS].append("homie/#")
            if self.subscribe_to_tasmota:
                self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBED_TOPICS].append(f"{TASMOTA_ROOT_TOPIC_TASMOTA_DISCOVERY}/#")
                self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBED_TOPICS].append(f"{TASMOTA_ROOT_TOPIC_STAT}/#")
                self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBED_TOPICS].append(f"{TASMOTA_ROOT_TOPIC_TELE}/#")
            if len(self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBED_TOPICS]) > 0:
                for mqtt_subscription in self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBED_TOPICS]:
                    self.mqtt_client.message_callback_add(mqtt_subscription, self.handle_message)
            mqtt_connected = False
            try:
                broker_name = indigo.devices[self.mqtt_broker_dev_id].name
                # self.mqttHandlerLogger.warning(f"Connect to {broker_name} [1] - User : {self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_USERNAME]}")
                decoded_password = ""
                if self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PASSWORD] != "":
                    encrypted_password = self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PASSWORD].encode()
                    # self.mqttHandlerLogger.warning(f"Connect to {broker_name} [2] - Encrypted Password [{type(encrypted_password)}]: '{encrypted_password}'")
                    decoded_password = decode(self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_ENCRYPTION_KEY], encrypted_password)
                    # self.mqttHandlerLogger.warning(f"Connect to {broker_name} [3] - Decoded Password [{type(decoded_password)}]: '{decoded_password}'")

                if decoded_password != "" or self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_USERNAME] != "":
                    self.mqtt_client.username_pw_set(username=self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_USERNAME],
                                                     password=decoded_password)

                self.mqtt_client.connect(host=self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_IP],
                                         port=self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PORT],
                                         keepalive=60,
                                         bind_address="")
                mqtt_connected = True
            except Exception as exception_error:
                # DONE: Make this more user friendly!
                error_intercepted = False
                base_error_message = (f"Plugin is unable to connect to the MQTT Broker at "
                                      f"{self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_IP]}:{self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PORT]}."
                                      f" Is it running?")
                try:
                    errno = exception_error.errno  # noqa
                    strerror = exception_error.strerror  # noqa
                    if errno == 61:
                        self.mqttHandlerLogger.error(f"{base_error_message} Error: {strerror}.")
                        error_intercepted = True
                except:
                    pass
                if not error_intercepted:
                    self.exception_handler(f"{base_error_message} Connection error reported as: {exception_error}", False)  # Log error

            if mqtt_connected:
                self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_CLIENT] = self.mqtt_client

                self.mqtt_client.loop_start()

                while not self.threadStop.is_set():
                    try:
                        time.sleep(2)
                    except self.threadStop:
                        pass  # Optionally catch the StopThread exception and do any needed cleanup.
                        self.mqtt_client.loop_stop()
                        # self.globals[HE_HUBS][self.hubitat_hub_name][HE_HUB_MQTT_INITIALISED] = False
            else:
                pass
                # TODO: At this point, queue a recovery for n seconds time
                # TODO: In the meanwhile, just disable and then enable the Indigo Hubitat Elevation Hub device

            self.mqttHandlerLogger.debug("MQTT Handler Thread close-down commencing.")

            self.handle_quit()

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def on_publish(self, client, userdata, mid):  # noqa [parameter value is not used]
        try:
            pass
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def on_connect(self, client, userdata, flags, rc):  # noqa [Unused parameter values]
        try:
            # TODO: Loop round the Hub, tasmota and Export devices and set their connected status ???

            # for dev in indigo.devices.iter("self"):
            #     if dev.deviceTypeId == "hubitatElevationHub" or dev.deviceTypeId == "indigoExport" or dev.deviceTypeId == "tasmota":
            #         if dev.enabled:
            #             dev.updateStateOnServer(key='status', value="Connected")
            #             dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            for mqtt_subscription in self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBED_TOPICS]:
                self.mqtt_client.subscribe(mqtt_subscription, qos=1)

            self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBE_TO_HOMIE] = self.subscribe_to_homie
            self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_SUBSCRIBE_TO_TASMOTA] = self.subscribe_to_tasmota
            self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PUBLISH_TO_HOMIE] = self.publish_to_homie
            self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PUBLISH_TO_TASMOTA] = self.publish_to_tasmota
            self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_CONNECTED] = True
            mqtt_broker_dev = indigo.devices[self.mqtt_broker_dev_id]
            mqtt_broker_dev.updateStateOnServer(key="status", value="connected")
            mqtt_broker_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            if self.bad_disconnection:  # Check if previous disconnection was bad to set as "reconnected" as opposed to "connected"
                self.bad_disconnection = False
                connection_ui = "Reconnected"
            else:
                connection_ui = "Connected"
            self.mqttHandlerLogger.info(f"{connection_ui} to MQTT Broker at {self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_IP]}:{self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PORT]}")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def on_disconnect(self, client, userdata, rc):  # noqa [Unused parameter values]
        try:
            self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_CONNECTED] = False
            if rc != 0:
                # TODO - Interpret RC code
                self.mqttHandlerLogger.warning(
                    f"Plugin encountered an unexpected disconnection from MQTT Broker at {self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_IP]}:{self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PORT]}. MQTT Broker [Code {rc}]. Retrying connection ...")

                self.bad_disconnection = True
            else:
                self.mqttHandlerLogger.warning(f"Disconnected from MQTT Broker at {self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_IP]}:{self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PORT]}")
                self.mqtt_client.loop_stop()
            try:
                for dev in indigo.devices.iter("self"):
                    if dev.deviceTypeId == "hubitatElevationHub" or dev.deviceTypeId == "indigoExport" or dev.deviceTypeId == "tasmota":
                        if dev.enabled:
                            dev.updateStateOnServer(key="status", value="disconnected")
                            dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            except KeyError:  # Indigo device may have been already deleted
                pass

            mqtt_broker_dev = indigo.devices[self.mqtt_broker_dev_id]
            mqtt_broker_dev.updateStateOnServer(key="status", value="disconnected")
            mqtt_broker_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handle_quit(self):
        try:
            self.mqtt_client.disconnect()
            self.mqtt_client.loop_stop()
            self.mqttHandlerLogger.warning(f"Disconnected from MQTT Broker at {self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_IP]}:{self.globals[MQTT][self.mqtt_broker_dev_id][MQTT_PORT]}")
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def on_subscribe(self, client, userdata, mid, granted_qos):  # noqa [Unused parameter values]
        try:
            pass
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def handle_message(self, client, userdata, msg):  # noqa [Unused parameter values: client, userdata]
        try:
            self.mqtt_message_sequence += 1

            topic_list = msg.topic.split("/")  # noqa [Duplicated code fragment!]
            payload = msg.payload.decode('utf-8')

            if len(topic_list) < 3:
                return

            if topic_list[0] == "homie":
                hub_name = topic_list[1]
                if hub_name in self.globals[HE_HUBS]:
                    hub_id = self.globals[HE_HUBS][hub_name][HE_INDIGO_HUB_ID]
                    if hub_id is None or hub_id == 0:
                        return
                    hub_dev = indigo.devices[hub_id]
                    if hub_dev.states["status"] == "disconnected":
                        hub_dev.updateStateOnServer(key=u'status', value="connected")
                        hub_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

                    self.globals[QUEUES][MQTT_HUB_QUEUE].put([self.mqtt_message_sequence, MQTT_PROCESS_COMMAND_HANDLE_TOPICS, hub_id, msg.topic, topic_list, payload])
                else:
                    if EXPORT_ROOT_TOPIC_ID in self.globals[EXPORT]:
                        if not self.globals[EXPORT][EXPORT_ROOT_TOPIC_ID] is None:
                            if self.globals[EXPORT][EXPORT_ROOT_TOPIC_ID] == topic_list[1]:
                                self.globals[QUEUES][MQTT_EXPORT_QUEUE].put([self.mqtt_message_sequence, MQTT_PROCESS_COMMAND_HANDLE_TOPICS, msg.topic, topic_list, payload])
                    return

            elif topic_list[0] in (TASMOTA_ROOT_TOPIC_TASMOTA, TASMOTA_ROOT_TOPIC_STAT, TASMOTA_ROOT_TOPIC_TELE):

                # TODO: Remove this - 18-March-2022. = self.mqttHandlerLogger.error(f"PAYLOAD TYPE: {type(payload)}, PAYLOAD DATA: {payload}")

                self.globals[QUEUES][MQTT_TASMOTA_QUEUE].put([self.mqtt_message_sequence, MQTT_PROCESS_COMMAND_HANDLE_TOPICS, msg.topic, topic_list, payload])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
