import pytest
from integrations.connected_v2v import Beacon, V2VEndpoint, Link, SimulatedChannel, encode_beacon

STATE = (30., 0., 0., 8., 0., 0.)


def payload(sequence=0, observed=0., name='car-a'):
    return encode_beacon(Beacon(name, sequence, observed, STATE))


def test_receipt_poll_never_replaces_the_original_measurement_time():
    channel = SimulatedChannel(default=Link(delay_s=.1))
    receiver = V2VEndpoint('car-b')
    channel.transmit('car-a', 'car-b', payload(observed=.4), .4)
    assert not channel.deliver(.45, {'car-b': receiver})
    events = channel.deliver(.65, {'car-b': receiver})
    assert events[0]['scheduled_s'] == .5 and events[0]['received_s'] == .65
    assert events[0]['age_s'] == pytest.approx(.25)
    assert receiver.peers(.65)['car-a']['observed_s'] == .4


def test_reordered_and_duplicate_packets_do_not_roll_back_new_state():
    key = ('car-a', 'car-b')
    channel = SimulatedChannel(links={key: Link(delay_s=.2)})
    receiver = V2VEndpoint('car-b')
    channel.transmit(*key, payload(sequence=1), 0.)
    channel.links[key] = Link(duplicate=1.)
    channel.transmit(*key, payload(sequence=2, observed=.1), .1)
    assert [e['accepted'] for e in channel.deliver(.1, {'car-b': receiver})] == [True, False]
    assert [e['accepted'] for e in channel.deliver(.2, {'car-b': receiver})] == [False]
    assert receiver.inbox.latest['car-a'].sequence == 2
    assert receiver.rejections == {'replay_or_regression': 2}


def test_blackout_applies_to_transmission_and_queued_reception():
    channel = SimulatedChannel(default=Link(delay_s=.2, blackout=((.1, .4),)))
    receiver = V2VEndpoint('car-b')
    channel.transmit('car-a', 'car-b', payload(), 0.)
    channel.transmit('car-a', 'car-b', payload(1, .1), .1)
    assert channel.deliver(.2, {'car-b': receiver}) == []
    assert channel.dropped == {'blackout': 1, 'blackout_at_delivery': 1}
    channel.transmit('car-a', 'car-b', payload(2, .4), .4)
    assert channel.deliver(.6, {'car-b': receiver})[0]['accepted']


def test_link_fault_is_specific_to_the_receiver_and_range_is_enforced():
    channel = SimulatedChannel(links={('car-a', 'car-b'): Link(loss=1.)})
    receivers = {name: V2VEndpoint(name) for name in ['car-b', 'car-c']}
    for name in receivers:
        channel.transmit('car-a', name, payload(), 0., distance_m=20.)
    assert [e['receiver'] for e in channel.deliver(0., receivers)] == ['car-c']
    assert receivers['car-b'].expected == frozenset()
    channel.transmit('car-a', 'car-c', payload(1, .1), .1, distance_m=151.)
    assert channel.dropped == {'loss': 1, 'out_of_range': 1}


def test_bounded_queue_counts_overflow_instead_of_silently_evicting_packets():
    channel = SimulatedChannel(default=Link(delay_s=.3), max_pending=1)
    channel.transmit('car-a', 'car-b', payload(), 0.)
    channel.transmit('car-a', 'car-b', payload(1, .1), .1)
    assert channel.pending == 1 and channel.dropped == {'queue_full': 1}


def test_seeded_channel_repeats_all_delivery_and_loss_outcomes():
    def run():
        channel = SimulatedChannel(seed=42, default=Link(delay_s=.08, jitter_s=.1, loss=.3, duplicate=.4))
        receiver = V2VEndpoint('car-b'); events = []
        for i in range(30):
            now = i*.1
            channel.transmit('car-a', 'car-b', payload(i, now), now)
            events += channel.deliver(now, {'car-b': receiver})
        events += channel.deliver(3.2, {'car-b': receiver})
        return events, dict(channel.dropped), dict(receiver.rejections)
    assert run() == run()


@pytest.mark.parametrize('settings', [{'loss': 1.1}, {'duplicate': -1}, {'range_m': 0},
                                      {'delay_s': -.1}, {'jitter_s': float('nan')},
                                      {'blackout': ((1., .5),)}])
def test_invalid_channel_parameters_are_refused(settings):
    with pytest.raises(ValueError):
        Link(**settings)


def test_channel_refuses_sender_impersonation_and_backwards_time():
    channel = SimulatedChannel()
    with pytest.raises(ValueError):
        channel.transmit('car-c', 'car-b', payload(), .1)
    with pytest.raises(ValueError, match='backwards'):
        channel.deliver(0., {})
