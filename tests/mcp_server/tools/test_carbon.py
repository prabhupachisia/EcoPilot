from pathlib import Path

import pytest

from mcp_server.tools.carbon import CarbonIntensityProfile


@pytest.fixture
def profile() -> CarbonIntensityProfile:
    return CarbonIntensityProfile(
        profile={0: 0.3, 6: 0.5, 12: 0.2, 18: 0.6},
    )


def test_intensity_at_known_hour(profile: CarbonIntensityProfile) -> None:
    assert profile.intensity_at(12) == 0.2


def test_intensity_at_wraps_past_24_hours(profile: CarbonIntensityProfile) -> None:
    assert profile.intensity_at(24) == profile.intensity_at(0)
    assert profile.intensity_at(30) == profile.intensity_at(6)


def test_as_dict_returns_a_copy(profile: CarbonIntensityProfile) -> None:
    snapshot = profile.as_dict()
    snapshot[12] = 999.0

    assert profile.intensity_at(12) == 0.2


def test_lowest_intensity_hours(profile: CarbonIntensityProfile) -> None:
    assert profile.lowest_intensity_hours(2) == [12, 0]


def test_highest_intensity_hours(profile: CarbonIntensityProfile) -> None:
    assert profile.highest_intensity_hours(2) == [18, 6]


def test_average_intensity(profile: CarbonIntensityProfile) -> None:
    assert profile.average_intensity() == pytest.approx((0.3 + 0.5 + 0.2 + 0.6) / 4)


def test_compute_emissions_kg_sums_hourly_contributions(profile: CarbonIntensityProfile) -> None:
    emissions = profile.compute_emissions_kg({0: 10.0, 12: 5.0})

    assert emissions == pytest.approx(10.0 * 0.3 + 5.0 * 0.2)


def test_estimate_emissions_kg_uses_average_intensity(profile: CarbonIntensityProfile) -> None:
    estimate = profile.estimate_emissions_kg(100.0)

    assert estimate == pytest.approx(100.0 * profile.average_intensity())


def test_estimate_emissions_kg_returns_none_for_none_input(profile: CarbonIntensityProfile) -> None:
    assert profile.estimate_emissions_kg(None) is None


def test_loads_from_the_real_config_file() -> None:
    from config.settings import CARBON_INTENSITY_PROFILE_PATH

    profile = CarbonIntensityProfile(path=CARBON_INTENSITY_PROFILE_PATH)

    assert len(profile.as_dict()) == 24
    for hour in range(24):
        assert profile.intensity_at(hour) > 0
