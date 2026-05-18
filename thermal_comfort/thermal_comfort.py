from pythermalcomfort.models import utci
from pythermalcomfort.utilities import mean_radiant_tmp, wet_bulb_tmp
from thermofeel import calculate_wbgt_simple, celsius_to_kelvin, kelvin_to_celsius
from typing import Union

import numpy as np

import math

class ThermalComfort():
    def __init__(
            self, 
            ta: Union[float, np.ndarray],               # Air Temperature            [°C]
            rh: Union[float, np.ndarray],               # Relative Humidity          [%]
            ws: Union[float, np.ndarray],               # Wind Speed                 [m/s]
            wbgt: Union[float, np.ndarray],             # Wet Bulb Globe Temperature [°C]
            is_tg: bool,                                # False: calculate Tg, True: value is already Tg
            height: float                               # Height of the station      [m]
        ):
        self.ta = ta
        self.rh = rh
        self.ws = ws
        self.wbgt = wbgt

        self.height = height
        self.ws_10m = self.convert_wind_speed_to_10m()
        self.is_tg = is_tg

        self.tg = None
        self.mrt = None
        self.utci = None
        self.category = None

        # When self.wbgt is the Globe Temperature (Tg)
        if is_tg:
            self.tg = self.wbgt

        # Estimate the WBGT with Temperature and Humidity for when WBGT is not provided
        elif wbgt is None:
            self.wbgt = self.calculate_wbgt_simple_thermofeel()
            self.tg = self.wbgt     # Experimental
 
        else:
            # Check if wbgt contains nan values
            nan_mask = np.isnan(self.wbgt)
            
            # Estimate WBGT for nan values and include them in self.wbgt
            if nan_mask.any():
                estimated_wbgt = self.calculate_wbgt_simple_thermofeel()
                self.wbgt = np.where(nan_mask, estimated_wbgt, self.wbgt)
                self.tg = self.wbgt
            
            # Calculate Tg from WBGT
            else:
                self.calculate_tg_from_wbgt()

        self.calculate_mrt_from_globe_temperature()
        self.calculate_utci_pythermalcomfort()


# -------------------- MRT Calculation --------------------
    def calculate_wbgt_simple_thermofeel(self):
        '''
        Calculate simple Wet Bulb Globe Temperature (WBGT) with thermofeel library.
        
        Parameters:
            ta: Air temperature [K]
            rh: Relative humidity [%]

        Returns:
            float: Wet Bulb Globe Temperature [°C]
        '''
        ta_K = celsius_to_kelvin(self.ta)
        wbgt_K = calculate_wbgt_simple(ta_K, self.rh)
        wbgt = kelvin_to_celsius(wbgt_K)
        wbgt = np.maximum(wbgt, self.ta)     # Tg can not be less than Ta
        return wbgt


    def calculate_tg_from_wbgt(self):
        '''
        Calculate Globe Temperature from Wet Bulb Globe Temperature (WBT).
            Reference:  Stull (2011): Wet Bulb Temperature (tw)
                            5 < rh < 99 | -20 < ta < 50

                        Minard (1961): Tg = (WBGT - 0.7Tw - 0.1Ta) / 0.2
            
        Parameters:
            ta: Air temperature [°C]
            wbgt: Wet Bulb Globe Temperature [°C]
            
        Returns:
            Globe Temperature (tg) [°C]
        '''
        tw = wet_bulb_tmp(self.ta, self.rh)
        tg = (self.wbgt - (0.7*tw) - (0.1*self.ta))/0.2

        # physical conditions: (self.ta < 20) & (tg > self.ta)
        self.tg = np.where((self.ta < 20) & (tg > self.ta), self.wbgt, tg)
        return self.tg
    

    def calculate_mrt_from_globe_temperature(self, d=0.15, emissivity=0.95, standard='Mixed Convection'):
        '''
        Calculate Mean Radiant Temperature from Globe Temperature (Tg) using pythermalcomfort library. 
            Reference:  ISO 7726 MRT 
                        Thorsson et al. (2007) Different methods for estimating the mean radiant temperature in an outdoor urban setting.
                            . Variables at the height Tg was measured 

        Parameters:
            ta: Air temperature [°C]
            tg: Globe temperature [°C]
            ws: Wind Speed [m/s]

        Returns:
            Mean Radiant Temperature (mrt) [°C]
        '''
        self.mrt = mean_radiant_tmp(self.tg, self.ta, self.ws, d, emissivity, standard)
        return self.mrt
    

# -------------------- UTCI Calculation --------------------
    def calculate_utci_pythermalcomfort(self):
        '''
        Calculate UTCI with pythermalcomfort.
            Reference:  Bröde, Peter, et al. "Deriving the operational procedure for the Universal Thermal Climate Index (UTCI)."
                        International journal of biometeorology 56.3 (2012): 481-494.
        
        Parameters:
            ta: Air temperature [°C]
            wbgt: Wet Bulb Globe Temperature [°C]
            ws: Wind Speed [m/s]
            rh: Relative Humidity [%]

        Returns:
            UTCI [°C] and Stress Category
        '''

        utci_index = utci(
            tdb = self.ta,                       # Dry bulb air temperature: Celsius
            tr = self.mrt,                       # Mean radiant temperature: Celsius
            v = np.maximum(self.ws_10m, 0.5),        # Wind speed 10m:           m/s
            rh = self.rh,                        # Relative humidity:        %
            round_output = False
        )
        self.utci = np.round((utci_index.utci), 2)
        self.category = utci_index.stress_category
        return self.utci, self.category


# -------------------- Utility Functions --------------------
    def convert_wind_speed_to_10m(self, z_0=0.1):
        '''
        Convert Wind Speed measured at a certain height to 10m (required for the calculation of UTCI) using the logarithmic wind profile.
            Reference:  Stull, R.B. (1988) An Introduction to Boundary Layer Meteorology. Springer.
                        Davenport, Alan G., et al. "Estimating the roughness of cities and sheltered country." Preprints, 12th Conf. on Applied Climatology, Asheville, NC, Amer. Meteor. Soc. Vol. 96. 2000.
                        Stewart, Ian D., and Tim R. Oke. "Local climate zones for urban temperature studies." Bulletin of the American Meteorological Society 93.12 (2012): 1879-1900.
        Parameters:
            ws: Wind Speed [m/s]
            height: Height of measured wind speed [m]. Default: 3.5 for Walter
            z_0: surface roughness length (m). Default 0.1 (roughly open)

        Returns:
            Wind Speed at height 10m [m/s]
        '''
        if self.height != 10:
            ws_10m = self.ws * (math.log(10/z_0)/math.log(self.height/z_0))
            return ws_10m
        else:
            return self.ws
    
