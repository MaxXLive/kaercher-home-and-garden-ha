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
