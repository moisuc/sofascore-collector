"""Match endpoints tests."""


def test_get_matches(client, sample_match):
    """Test getting matches with default filters."""
    response = client.get("/matches")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_match_details(client, sample_match):
    """Test getting match details by SofaScore ID."""
    response = client.get(f"/matches/{sample_match.sofascore_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["sofascore_id"] == sample_match.sofascore_id
    assert data["home_team"]["name"] == "Real Madrid"
    assert data["away_team"]["name"] == "Barcelona"
