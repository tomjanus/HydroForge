# Sensors Module (deprecated compatibility shim)

.. deprecated:: 1.0.0
    ``hydroforge.sensors`` is a backwards-compatibility shim. Its contents have
    moved to their canonical locations:

    * Generic sensor / measurement imperfection models
      (``Sensor``, ``RandomNoiseSensor``, ``WindowAverager``, ...):
      :mod:`hydroforge.measurements`
    * WDN-specific sensor placement and the sensor-network graph:
      :mod:`hydroforge.wdn_modelling.measurement_placement`

    Top-level generic packages (``hydroforge.measurements``,
    ``hydroforge.auxiliary``, ``hydroforge.uncertainty``,
    ``hydroforge.sampling``) never import from :mod:`hydroforge.wdn_modelling`.

The public imports from the package root still work via this shim and emit a
:class:`DeprecationWarning`:

```python
import warnings
warnings.simplefilter("always", DeprecationWarning)

from hydroforge.sensors import RandomNoiseSensor, GreedySensorPlacement
# DeprecationWarning: hydroforge.sensors is a deprecated compatibility shim; ...
```

New code should import directly:

```python
from hydroforge.measurements import RandomNoiseSensor, WindowAverager
from hydroforge.wdn_modelling.measurement_placement import GreedySensorPlacement
from hydroforge.wdn_modelling.measurement_placement import SensorNetworkGraph
```

See :mod:`hydroforge.measurements` and
:mod:`hydroforge.wdn_modelling.measurement_placement` for the full API.
