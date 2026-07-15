"""
GCS storage pricing — USD per GB-month, by location type and storage class.
=========================================================================
These are *list* at-rest storage prices (data storage only — NOT operations,
network egress, retrieval, or early-delete fees). Prices vary by region;
the values below are common US defaults. **Edit to match your region/contract.**

Source of truth: https://cloud.google.com/storage/pricing  (check periodically)
"""

# USD / GB-month (1 GB = 1e9 bytes, Google bills in binary GiB but uses GB in
# the price sheet; we use GB = 1e9 to stay consistent with the pricing page).
PRICE_PER_GB_MONTH = {
    "region": {
        "STANDARD": 0.020,
        "NEARLINE": 0.010,
        "COLDLINE": 0.004,
        "ARCHIVE":  0.0012,
    },
    "dual-region": {
        "STANDARD": 0.044,
        "NEARLINE": 0.020,
        "COLDLINE": 0.008,
        "ARCHIVE":  0.0024,
    },
    "multi-region": {
        "STANDARD": 0.026,
        "NEARLINE": 0.010,
        "COLDLINE": 0.007,
        "ARCHIVE":  0.0025,
    },
}

# Legacy / alias storage-class names map to current ones.
CLASS_ALIASES = {
    "REGIONAL": "STANDARD",
    "MULTI_REGIONAL": "STANDARD",
    "DURABLE_REDUCED_AVAILABILITY": "STANDARD",
}


def normalise_class(storage_class: str) -> str:
    sc = (storage_class or "STANDARD").upper()
    return CLASS_ALIASES.get(sc, sc)


def price_per_gb(location_type: str, storage_class: str) -> float:
    """USD/GB-month for a (location_type, storage_class). Falls back to region/STANDARD."""
    lt = (location_type or "region").lower()
    table = PRICE_PER_GB_MONTH.get(lt, PRICE_PER_GB_MONTH["region"])
    return table.get(normalise_class(storage_class), table["STANDARD"])


def monthly_cost(size_bytes: int, location_type: str, storage_class: str) -> float:
    """Estimated monthly at-rest storage cost in USD for an object/aggregate."""
    gb = size_bytes / 1e9
    return gb * price_per_gb(location_type, storage_class)
