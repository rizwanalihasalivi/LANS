"""Separate bounded cooperative-sensing schema; never invent a vehicle identity."""
from dataclasses import asdict
import json
from integrations.connected_v2v.messages import vehicle_id,_unique_object,_invalid_constant
from integrations.connected_v2v.autonomy.study import decode_scan

MAX_BYTES=8192


def encode_peer_scan(observer,scan):
    vehicle_id(observer)
    raw=json.dumps(dict(version=1,kind='range_scan',observer_id=observer,scan=asdict(scan)),
                   separators=(',',':'),allow_nan=False).encode()
    if len(raw)>MAX_BYTES:raise ValueError('peer scan too large')
    return raw


def is_peer_scan(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:return False
    try:return isinstance((obj:=json.loads(raw)),dict) and obj.get('kind')=='range_scan'
    except (ValueError,UnicodeError,RecursionError):return False


def decode_peer_scan(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise ValueError('bounded peer scan required')
    try:
        obj=json.loads(raw,object_pairs_hook=_unique_object,parse_constant=_invalid_constant)
        if not isinstance(obj,dict) or set(obj)!= {'version','kind','observer_id','scan'} or type(obj['version']) is not int or obj['version']!=1 or obj['kind']!='range_scan':
            raise ValueError('unsupported peer scan schema')
        observer=vehicle_id(obj['observer_id'])
        if set(obj['scan'])!={'sequence','observed_s','ego_state','detections','complete'}:raise ValueError('unknown scan fields')
        scan=decode_scan(obj['scan'])
        return observer,scan
    except (TypeError,KeyError,UnicodeError,RecursionError) as error:
        raise ValueError('invalid peer scan') from error
