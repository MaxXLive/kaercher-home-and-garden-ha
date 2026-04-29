"""Constants for Kärcher Home & Garden integration."""
from __future__ import annotations

DOMAIN = "karcher_hg"

# Auth / OAuth
AUTH_BASE = "https://auth.kaercher.com"
COGNITO_HOSTED_BASE = "https://auth-irp-prd.auth.eu-west-1.amazoncognito.com"
COGNITO_CLIENT_ID = "1eniads92koet91k3mhqcfc50f"
COGNITO_USER_POOL_ID = "eu-west-1_qGFv4JkBJ"
COGNITO_IDENTITY_POOL_ID = "eu-west-1:9338a823-bbf9-4218-be94-61caf9241999"
IDP_NAME = "ak-oidc-ruds"
AWS_REGION = "eu-west-1"
OAUTH_REDIRECT_SCHEME = "com.kaercher.consumer.devicesapp"
OAUTH_REDIRECT_URI = f"{OAUTH_REDIRECT_SCHEME}://"
COGNITO_AUTHORIZE_URL = f"{COGNITO_HOSTED_BASE}/oauth2/authorize"
COGNITO_TOKEN_URL = f"{COGNITO_HOSTED_BASE}/oauth2/token"

# Kärcher REST API
API_BASE = "https://api.iot.kaercher.com"
API_KEY = "ZFZ13TTUWS4YL06B23UY812V7CaAt0ib50Ys4vuK"  # from app, public
API_VERSION = "1"
APP_VERSION = "3.16.3"
APP_PLATFORM = "android"

# AWS IoT Data
IOT_DATA_HOST = "data-ats.iot.eu-west-1.amazonaws.com"
IOT_DATA_ENDPOINT = f"https://{IOT_DATA_HOST}"

# Named shadows (all accessible via REST get_thing_shadow)
SHADOW_AK_HG_APP = "ak-hg-app"
SHADOW_STATE = "state"
SHADOW_TELEMETRY = "telemetry"
SHADOW_MACHINE_INFO = "machineInformation"
SHADOW_MAPS = "maps"
ALL_SHADOW_NAMES = [
    SHADOW_AK_HG_APP,
    SHADOW_STATE,
    SHADOW_TELEMETRY,
    SHADOW_MACHINE_INFO,
    SHADOW_MAPS,
]

# Coordinator
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Device-type known codes
DEVICE_TYPE_LB1 = "LB1"  # robot vacuum (RCV)

# Config-entry keys
CONF_REFRESH_TOKEN = "refresh_token"
CONF_USER_ID = "user_id"

# Command endpoint: POST /dmapi/things/<dmId>/commands/<vendor>-<product>-<command>
# Vendor/product for RCV 5: ff01-3001
DEFAULT_VENDOR_PRODUCT = "ff01-3001"

# Wire command names (used in endpoint URL)
CMD_FIND_DEVICE = "findDevice"
CMD_SET_ROOM_CLEAN = "setRoomClean"
CMD_START_RECHARGE = "startRecharge"
CMD_STOP_RECHARGE = "stopRecharge"
CMD_START_EXPLORE = "startExplore"
CMD_SET_PREFERENCE = "setPreference"
CMD_SET_VIRTUAL_WALL = "setVirtualWall"
CMD_ARRANGE_ROOM = "arrangeRoom"
CMD_SPLIT_ROOM = "splitRoom"
CMD_RENAME_ROOM = "renameRoom"
CMD_RESET_FACTORY = "resetFactory"
CMD_ADD_ORDER = "addOrder"
CMD_GET_ORDER = "getOrder"
CMD_DEL_ORDER = "delOrder"
CMD_RESET_CONSUMABLE = "resetConsumable"
CMD_SET_DIRECTION = "setDirection"
CMD_SET_CALIBRATION = "setCalibration"
CMD_SET_ZONE_POINTS = "setZonePoints"
CMD_SET_ZONE_CLEAN = "setZoneClean"
CMD_UPLOAD_LOGS = "uploadRobotLogs"

# cleanType enum
CLEAN_TYPE_GLOBAL = 0
CLEAN_TYPE_BORDER = 1

# ctrValue enum (note: setRoomClean uses "ctrValue", setZoneClean uses "ctrlValue")
CTR_STOP = 0
CTR_START = 1
CTR_PAUSE = 2

# sweep_type enum (cleaning mode — set via setPreference command)
SWEEP_TYPE_VACUUM = 0       # nur saugen
SWEEP_TYPE_VACUUM_MOP = 1   # saugen + wischen
SWEEP_TYPE_MOP_ONLY = 2     # nur wischen
SWEEP_TYPE_VAC_THEN_MOP = 3 # erst saugen, dann wischen

# state.status values (from shadow)
STATUS_IDLE = 0
STATUS_CLEANING = 1
STATUS_PAUSED = 2
STATUS_CHARGING = 3  # inferred
STATUS_RETURNING = 4  # inferred
STATUS_EXPLORING = 5  # inferred

# direction values (setDirection)
DIR_FORWARD = 1
DIR_RIGHT = 2
DIR_BACKWARD = 3
DIR_LEFT = 4

# ── Fault codes extracted from app v3.16.3 (decompiled Hermes bytecode) ──
# type=banner → blocking error shown as persistent banner in app
# type=snack  → transient notification, non-blocking
FAULT_CODES: dict[int, tuple[str, str, bool]] = {
    # (code): (key, description_DE, is_blocking)
    0:    ("none", "Kein Fehler", False),
    500:  ("lidarTimeout", "LIDAR-Timeout", True),
    501:  ("robotWheelsLifted", "Roboterräder angehoben", True),
    502:  ("lowBattery", "Niedriger Batteriestand", True),
    503:  ("dustBinNotInstalled", "Mülleimer nicht installiert", True),
    508:  ("robotStartOnSlope", "Roboter startete an Hang", True),
    509:  ("cliffSensorBlocked", "Klippensensoren blockiert", True),
    510:  ("collisionSensorAbnormal", "Kollisionssensor defekt", True),
    511:  ("failedToReturnDock", "Rückkehr zum Dock fehlgeschlagen", True),
    513:  ("navigationFailed", "Navigation fehlgeschlagen", True),
    514:  ("escapeFailed", "Fluchtversuch gescheitert", True),
    516:  ("highBatteryTemperature", "Hohe Batterietemperatur", True),
    518:  ("insufficientBattery", "Akku zu schwach", True),
    521:  ("waterTankNotInstalled", "Wassertank nicht installiert", True),
    522:  ("moppingPadNotInstalled", "Wischpad nicht installiert", True),
    525:  ("waterTankEmpty", "Wassertank leer", True),
    531:  ("2in1WaterTankNotInstalled", "2-in-1-Wassertank nicht installiert", True),
    533:  ("standbyTimeTooLong", "Standby-Zeit zu lang", True),
    534:  ("deviceLowBattery", "Niedriger Akkustand, schaltet ab", True),
    550:  ("batteryTemperatureAbnormal", "Batterietemperatur abnormal", True),
    551:  ("batteryTemperatureNormal", "Batterietemperatur normal", False),
    559:  ("mappingFailed", "Kartierung fehlgeschlagen", True),
    560:  ("sideBrushAbnormal", "Seitenbürste abnormal", True),
    561:  ("visionRecognitionSensor", "Bilderkennungssensor-Fehler", True),
    562:  ("edgeInfraredSensor", "Kanten-Infrarotsensor abnormal", True),
    563:  ("dustBinDetached", "Mülleimer abmontiert", True),
    564:  ("2in1WaterTankDetached", "2-in-1-Wassertank abmontiert", True),
    565:  ("lidarObstructed", "LIDAR blockiert", True),
    566:  ("waterTankDetached", "Wassertank abmontiert", True),
    567:  ("robotInRestrictedZone", "Roboter in Sperrzone", True),
    568:  ("leftDriveWheel", "Linkes Antriebsrad abnormal", True),
    569:  ("rightDriveWheel", "Rechtes Antriebsrad abnormal", True),
    570:  ("mainBrushAbnormal", "Hauptbürste abnormal", True),
    571:  ("mainBrushCutting", "Freischneidermesser blockiert", True),
    572:  ("robotInRestrictedZone2", "Roboter in Sperrzone", True),
    573:  ("fanAbnormal", "Ventilator abnormal", True),
    574:  ("lidarTangled", "LIDAR verheddert/festgefahren", True),
    580:  ("noWater", "Keine Wasserausgabe", False),  # snack
    588:  ("robotOnCarpet", "Roboter auf Teppich", False),  # snack
    589:  ("robotLocalizationFailure", "Lokalisierungsfehler (Station)", True),
    611:  ("localizationFailure", "Lokalisierung fehlgeschlagen", True),
    612:  ("mapChanged", "Karte geändert, neu zuordnen", True),
    701:  ("surroundingObstacles", "Hindernisse in der Umgebung", True),
    711:  ("dirtyWater", "Schmutzwassertank voll/fehlt", True),
    712:  ("cleanWaterTank", "Frischwassertank niedrig/fehlt", True),
    # 2xxx = non-blocking notifications (snack in app)
    2007: ("pathPlanningFailed", "Pfadplanung fehlgeschlagen", False),
    2012: ("areaUnreachable", "Gebiet nicht erreichbar", False),
    2013: ("didNotStartFromStation", "Nicht an Station gestartet", False),
    2014: ("carpetDetectionAbnormal", "Teppicherkennungsfehler", False),
    2015: ("cleaningInProgress", "Reinigung läuft bereits", False),
    2016: ("reMap", "Neuzuordnung nötig", False),
    2114: ("cleanedFor15Hours", "15h gereinigt, Behälter leeren", False),
}


def decode_fault(code: int | None) -> tuple[str, bool]:
    """Return (description, is_blocking) for a fault code."""
    if code is None or code == 0:
        return ("Kein Fehler", False)
    entry = FAULT_CODES.get(code)
    if entry:
        return (entry[1], entry[2])
    return (f"Unbekannter Fehler ({code})", code < 2000)
