from .run import controller_source, prepare_native


def test_native_adapter_uses_native_radar_and_same_frozen_controller(tmp_path):
    source=controller_source()
    assert "radar = driver.getDevice('local_radar')" in source
    assert 'target = min(visible' in source and 'FusionFollower(endpoint' in source
    assert 'getFromDef' not in source and 'getSelf' not in source
    world=prepare_native(tmp_path/'native')
    text=world.read_text()
    assert text.count('name "local_radar"')==3
    assert text.count('controller "connected_vehicle"')==3
    assert 'rangeNoise 0.05 speedNoise 0.02' in text
