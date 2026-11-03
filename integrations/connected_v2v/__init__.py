"""Multi-vehicle cooperative awareness adapter for the unified LANS pipeline."""

from .messages import Beacon, decode_beacon, encode_beacon
from .node import V2VEndpoint
from .network import Link, SimulatedChannel

__all__ = ['Beacon', 'decode_beacon', 'encode_beacon', 'V2VEndpoint', 'Link', 'SimulatedChannel']
