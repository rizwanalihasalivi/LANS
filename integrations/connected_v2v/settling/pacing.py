"""Leader's bounded recovery pace uses its own state and RECEIVED member beacons."""
from integrations.unified_lans.traffic import extrapolate


def pace_goal(node,own,now,road,cruise,member='follower'):
    packet=node.inbox.latest.get(member)
    floor=max(0.,cruise-4.)
    if packet is None or not 0<=now-packet.observed_s<=.4+1e-9:
        return floor,dict(pacing='member_unavailable',member_age_s=None,member_gap_m=None)
    state=extrapolate(packet.state,now-packet.observed_s)
    s=road.canonical(own)[0];other=road.canonical(state)
    gap=s-other[0]
    goal=cruise if gap<=60. else max(floor,min(cruise,other[2]+.3*(60.-gap)))
    return goal,dict(pacing='range_reserve' if goal<cruise else 'cruise',
        member_age_s=now-packet.observed_s,member_gap_m=gap)
