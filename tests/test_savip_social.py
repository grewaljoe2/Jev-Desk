from app.providers.savip_social import exact_x_observation

def test_exact_x_accepts_only_same_handle():
    o=exact_x_observation("@Project_X",{"x_handle":"Project_X","followers":12})
    assert o and o["exact_handle_verified"] is True and o["x_handle"]=="Project_X"

def test_exact_x_rejects_substitute_handle():
    assert exact_x_observation("Project_X",{"x_handle":"ProjectXFan","followers":999}) is None

def test_exact_x_missing_stays_missing():
    assert exact_x_observation("Project_X",None) is None
