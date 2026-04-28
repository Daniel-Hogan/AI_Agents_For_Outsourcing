DEFAULT_AVATAR_COLOR_ID = "blue"

AVATAR_COLOR_HEX_BY_ID = {
    "blue": "#3b82f6",
    "purple": "#8b5cf6",
    "green": "#22c55e",
    "orange": "#f97316",
    "pink": "#ec4899",
    "teal": "#14b8a6",
    "red": "#ef4444",
    "yellow": "#ca8a04",
}

AVATAR_COLOR_LABEL_BY_ID = {
    "blue": "Ocean",
    "purple": "Iris",
    "green": "Mint",
    "orange": "Sunset",
    "pink": "Rose",
    "teal": "Teal",
    "red": "Cherry",
    "yellow": "Gold",
}

AVATAR_COLOR_OPTIONS = tuple(
    {
        "id": color_id,
        "label": AVATAR_COLOR_LABEL_BY_ID[color_id],
        "hex": color_hex,
    }
    for color_id, color_hex in AVATAR_COLOR_HEX_BY_ID.items()
)


def normalize_avatar_color_id(value: str | None) -> str:
    if not value:
        return DEFAULT_AVATAR_COLOR_ID
    normalized = value.strip().lower()
    if normalized in AVATAR_COLOR_HEX_BY_ID:
        return normalized
    return DEFAULT_AVATAR_COLOR_ID


def avatar_color_hex(value: str | None) -> str:
    return AVATAR_COLOR_HEX_BY_ID[normalize_avatar_color_id(value)]
