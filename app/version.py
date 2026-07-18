from __future__ import annotations

APP_NAME = "AITS"
SEMANTIC_VERSION = "1.0.0-rc.6"
RELEASE_CHANNEL = "release_candidate"
BUILD_NUMBER = 5
MIN_DATA_SCHEMA_VERSION = 1
MAX_DATA_SCHEMA_VERSION = 1


def version_info() -> dict[str, object]:
    return {
        "app_name": APP_NAME,
        "semantic_version": SEMANTIC_VERSION,
        "release_channel": RELEASE_CHANNEL,
        "build_number": BUILD_NUMBER,
        "minimum_data_schema_version": MIN_DATA_SCHEMA_VERSION,
        "maximum_supported_data_schema_version": MAX_DATA_SCHEMA_VERSION,
    }
