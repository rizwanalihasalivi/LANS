"""Versioned SI-state messages; this is not a standardized or authenticated CAM."""
from dataclasses import dataclass
import json
import math
from numbers import Real
import re

MAX_MESSAGE_BYTES = 1024
MAX_SEQUENCE = 2**63 - 1
FIELDS = {'version', 'vehicle_id', 'sequence', 'observed_s', 'state'}


def vehicle_id(value):
    if (not isinstance(value, str) or value == 'ego'
            or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}', value) is None):
        raise ValueError('vehicle_id must be 1-64 ASCII identifier characters; ego is reserved')
    return value


def timestamp(value):
    try:
        valid = not isinstance(value, bool) and isinstance(value, Real) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('nonnegative finite timestamp required')
    return float(value)


@dataclass(frozen=True)
class Beacon:
    vehicle_id: str
    sequence: int
    observed_s: float
    state: tuple

    def __post_init__(self):
        vehicle_id(self.vehicle_id)
        if type(self.sequence) is not int or not 0 <= self.sequence <= MAX_SEQUENCE:
            raise ValueError('sequence must be a nonnegative 63-bit integer')
        object.__setattr__(self, 'observed_s', timestamp(self.observed_s))
        if not isinstance(self.state, (tuple, list)) or len(self.state) != 6:
            raise ValueError('state must contain x, y, heading, speed, lateral speed and yaw rate')
        try:
            valid = all(not isinstance(v, bool) and isinstance(v, Real) and math.isfinite(v) for v in self.state)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError('six finite numeric SI states required')
        if self.state[3] < 0:
            raise ValueError('speed must be nonnegative')
        object.__setattr__(self, 'state', tuple(float(v) for v in self.state))


def encode_beacon(beacon):
    if not isinstance(beacon, Beacon):
        raise ValueError('Beacon required')
    payload = json.dumps(dict(version=1, vehicle_id=beacon.vehicle_id, sequence=beacon.sequence,
                              observed_s=beacon.observed_s, state=beacon.state),
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError('message too large')
    return payload


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('nonfinite JSON constant: ' + value)


def decode_beacon(payload):
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_MESSAGE_BYTES:
        raise ValueError('bounded byte message required')
    try:
        obj = json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_object,
                         parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('invalid JSON message') from error
    if not isinstance(obj, dict) or set(obj) != FIELDS or type(obj['version']) is not int or obj['version'] != 1:
        raise ValueError('unsupported message schema/version')
    return Beacon(obj['vehicle_id'], obj['sequence'], obj['observed_s'], obj['state'])
