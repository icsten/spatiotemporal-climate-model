from thermal_comfort import ThermalComfort
from typing import Union, Optional

import numpy as np

def get_thermal_comfort(
        ta: Union[float, np.ndarray],
        rh: Union[float, np.ndarray],
        ws: Union[float, np.ndarray],
        wbgt: Optional[Union[float, np.ndarray]] = None,
        is_tg: bool = False,
        height: float = 3.5,
    ) -> dict:
    '''
    GET UTCI and stress category results for given metereological inputs.

    Parameters:
        ta: Air temperature [°C]
        rh: Relative humidity [%]
        ws: Wind speed [m/s]
        wbgt: Wet Bulb Globe Temperature or Globe Temperature [°C]. None value returns empty results.
        is_tg: If True, wbgt is the Globe Temperature. Else, calculate Globe Temperature. Default: False
        height: Measurement height of variables [m]. Default: 3.5.

    Returns:
        dict with keys "utci" (float, ndarray) and "stress_category" (str, ndarray),
        or keys with None values if wbgt is None.
    '''

    tc = ThermalComfort(ta, rh, ws, wbgt, is_tg, height)
    return {
        "utci": float(tc.utci) if np.isscalar(tc.utci) else tc.utci.tolist(),
        "stress_category": tc.category if np.isscalar(tc.category) else tc.category.tolist(),
    }
