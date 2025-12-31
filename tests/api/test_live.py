"""Live matches endpoint tests."""


def test_get_all_live_matches(client, sample_match):
    """Test getting all live matches."""
    response = client.get("/live")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["sofascore_id"] == 3001
    assert "status" in data[0]


def test_get_live_matches_by_sport(client, sample_match):
    """Test getting live matches filtered by sport."""
    response = client.get("/live/football")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["sport"] == "football"
