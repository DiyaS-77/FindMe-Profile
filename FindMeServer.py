from gi.repository import GLib
import dbus
import dbus.mainloop.glib
import dbus.service

BLUEZ_SERVICE_NAME = 'org.bluez'
ADAPTER_IFACE = 'org.bluez.Adapter1'
GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
GATT_SERVICE_IFACE = 'org.bluez.GattService1'
GATT_CHARACTERISTIC_IFACE = 'org.bluez.GattCharacteristic1'
LE_ADVERTISEMENT_IFACE = 'org.bluez.LEAdvertisement1'

IAS_UUID = '1802'
ALERT_LEVEL_UUID = '2A06'


class Application(dbus.service.Object):
    PATH = '/org/bluez/example/app'

    def __init__(self, bus):
        self.path = self.PATH
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method('org.freedesktop.DBus.ObjectManager',
                         out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for char in service.get_characteristics():
                response[char.get_path()] = char.get_properties()
        return response


class IASService(dbus.service.Object):
    def __init__(self, bus, index):
        self.path = f'/org/bluez/example/service{index}'
        self.bus = bus
        self.uuid = IAS_UUID
        self.primary = True
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

        self.alert_level_char = AlertLevelCharacteristic(bus, 0, self)
        self.add_characteristic(self.alert_level_char)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': self.uuid,
                'Primary': self.primary,
                'Characteristics': dbus.Array(
                    [char.get_path() for char in self.characteristics],
                    signature='o')
            }
        }

    def add_characteristic(self, char):
        self.characteristics.append(char)

    def get_characteristics(self):
        return self.characteristics


class AlertLevelCharacteristic(dbus.service.Object):
    def __init__(self, bus, index, service):
        self.path = f'{service.get_path()}/char{index}'
        self.bus = bus
        self.service = service
        self.uuid = ALERT_LEVEL_UUID
        self.flags = ['write-without-response', 'notify']
        self.notifying = False
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            GATT_CHARACTERISTIC_IFACE: {
                'UUID': self.uuid,
                'Service': self.service.get_path(),
                'Flags': dbus.Array(self.flags, signature='s'),
                'Notifying': dbus.Boolean(self.notifying)
            }
        }

    @dbus.service.method(GATT_CHARACTERISTIC_IFACE,
                         in_signature='aya{sv}', out_signature='')
    def WriteValue(self, value, options):
        if not value:
            print("[AlertLevelCharacteristic] Received empty value")
            return

        level = int(value[0])
        msg = "Unknown Alert"
        if level == 0:
            msg = "No Alert"
        elif level == 1:
            msg = "Mild Alert"
        elif level == 2:
            msg = "High Alert"

        print(f"[AlertLevelCharacteristic] Received alert level: {msg}")

        # Send notification if enabled
        self.send_notification(msg)

    @dbus.service.method(GATT_CHARACTERISTIC_IFACE,
                         in_signature='', out_signature='')
    def StartNotify(self):
        self.notifying = True
        print("[AlertLevelCharacteristic] Notifications enabled")

    @dbus.service.method(GATT_CHARACTERISTIC_IFACE,
                         in_signature='', out_signature='')
    def StopNotify(self):
        self.notifying = False
        print("[AlertLevelCharacteristic] Notifications disabled")

    def send_notification(self, message):
        if not self.notifying:
            print("[AlertLevelCharacteristic] Notification skipped (not notifying)")
            return
        value = [dbus.Byte(ord(c)) for c in message]
        self.PropertiesChanged(GATT_CHARACTERISTIC_IFACE,
                               {'Value': dbus.Array(value, signature='y')}, [])

    @dbus.service.signal('org.freedesktop.DBus.Properties',
                         signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class Advertisement(dbus.service.Object):
    PATH = '/org/bluez/example/advertisement0'

    def __init__(self, bus):
        self.bus = bus
        dbus.service.Object.__init__(self, bus, self.PATH)

    @dbus.service.method('org.freedesktop.DBus.Properties',
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        return {
            'Type': 'peripheral',
            'ServiceUUIDs': dbus.Array([IAS_UUID], signature='s'),
            'LocalName': 'FindMeServer',
            'IncludeTxPower': dbus.Boolean(True)
        }

    @dbus.service.method(LE_ADVERTISEMENT_IFACE,
                         in_signature='', out_signature='')
    def Release(self):
        print("Advertisement released")


def find_adapter(bus):
    manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'),
                             'org.freedesktop.DBus.ObjectManager')
    objects = manager.GetManagedObjects()
    for path, interfaces in objects.items():
        if ADAPTER_IFACE in interfaces:
            return path
    return None



