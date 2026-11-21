"""Tests for runtime CDF exception boundaries."""

import pytest

from hydroforge.uncertainty import (
    AdditiveUncertainty,
    DiracDeltaDistribution,
    Parameter,
    ParameterType,
    UncertaintySpecification,
)
from hydroforge.uncertainty.common import CDFNotAvailable, TheoreticalCDFAbsent
from hydroforge.uncertainty.specification import SpecificationError


def test_distribution_without_theoretical_cdf_raises_theoretical_cdf_absent():
    distribution = DiracDeltaDistribution(value="opaque")

    with pytest.raises(TheoreticalCDFAbsent):
        distribution.cdf("opaque")


def test_parameter_unavailable_cdf_raises_cdf_not_available():
    parameter = Parameter(
        name="offset",
        nominal_value=1.0,
        uncertainty=AdditiveUncertainty(distribution=DiracDeltaDistribution(value=0.0)),
        type=ParameterType.NUMERICAL,
    )

    with pytest.raises(CDFNotAvailable):
        parameter.cdf(1.0)


def test_spec_created_parameter_keeps_runtime_cdf_exception_family():
    specification = UncertaintySpecification.from_dict(
        {
            "schema_version": "1.0",
            "parameters": {"material": {"nominal_value": "PVC"}},
        }
    )
    parameter = specification.create_parameter("material")

    with pytest.raises(CDFNotAvailable) as error:
        parameter.cdf("PVC")

    assert not isinstance(error.value, SpecificationError)
