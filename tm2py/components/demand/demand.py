<<<<<<< HEAD
"""Demand loading from OMX (generated from demand model components) to Emme database"""

from __future__ import annotations
from abc import ABC
from typing import Dict, Union, Collection, List, TYPE_CHECKING
import numpy as np

from tm2py.components.component import Component
from tm2py.logger import LogStartEnd
from tm2py.emme.matrix import OMXManager

if TYPE_CHECKING:
    from tm2py.controller import RunController

NumpyArray = np.array


class PrepareDemand(Component, ABC):
    """Abstract base class to import and average demand."""

    def __init__(self, controller: RunController):
        super().__init__(controller)
        self._emmebank = None
<<<<<<< HEAD
        self._scenario = None
        self._source_ref_key = None

    def _read_demand(self, file_config, str_format) -> NumpyArray:
        """Load demand from cross-referenced source file,
        the named demand model component under the key self._source_ref_key
        ("highway_demand_file" or "transit_demand_file")

        Args:
            file_config (dict): the file cross-reference(s) for the demand to be loaded
                {"source": <name of demand model component in the config>,
                 "name": <OMX key name template>,
                 "factor": <factor to apply to demand in this file>}
            str_format (dict): the string formatting key: value to be used in the
                "name" (OMX key name) and file path. Usually {"period": <time_period>}
                for highway, and {"period": <time_period>, "skim_set_id": <set_key>} for transit
        """
        source = file_config["source"]
        name = file_config["name"].format(**str_format)
        factor = file_config.get("factor")
        path = self.get_abs_path(self.config[source][self._source_ref_key])
        return self._read(path.format(**str_format), name, factor)

    def _read(self, path: str, name: str, factor: float = None) -> NumpyArray:
        """Read matrix array from OMX file at path with name, and multiple by factor (if specified).

        Args:
            path: full path to OMX file
            name: name of the OMX matrix / key
            factor: optional factor to apply to matrix
        """
        with OMXManager(path, "r") as omx_file:
            demand = omx_file.read(name)
        if factor is not None:
            demand = factor * demand
        demand = self._redim_demand(demand)
        # self.logger.log(f"{name} sum: {demand.sum()}", level=3)
        return demand

    def _redim_demand(self, demand: NumpyArray) -> NumpyArray:
        """Pad numpy array with zeros to match expect number of dimensions."""
        num_zones = len(self._scenario.zone_numbers)
        _shape = demand.shape
        if _shape != (num_zones, num_zones):
            demand = np.pad(
                demand, ((0, num_zones - _shape[0]), (0, num_zones - _shape[1]))
            )
        return demand

    # Disable too many arguments recommendation
    # pylint: disable=R0913

    def _save_demand(
        self,
        name: str,
        demand: NumpyArray,
        description: str = None,
        apply_msa: bool = False,
    ):
        """Save demand array to Emme matrix with name, optional description.

        Matrix will be created if it does not exist and the model is on iteration 0.

        Args:
            name: name of the matrix in the Emmebank
            demand: NumpyArray, demand array to save
            description: str, optional description to use in the Emmebank
            apply_msa: bool, default False: use MSA on matrix with current array
                values if model is on iteration >= 1
        """
        matrix = self._emmebank.matrix(f'mf"{name}"')
        msa_iteration = self.controller.iteration
        if not apply_msa or msa_iteration <= 1:
            if not matrix:
                ident = self._emmebank.available_matrix_identifier("FULL")
                matrix = self._emmebank.create_matrix(ident)
                matrix.name = name
                if description is not None:
                    matrix.description = description
        else:
            if not matrix:
                raise Exception(f"error averaging demand: matrix {name} does not exist")
            prev_demand = matrix.get_numpy_data(self._scenario.id)
            demand = prev_demand + (1.0 / msa_iteration) * (demand - prev_demand)
        # self.logger.log(f"{name} sum: {demand.sum()}", level=3)
        matrix.set_numpy_data(demand, self._scenario.id)

    def _create_zero_matrix(self):
        zero_matrix = self._emmebank.matrix('ms"zero"')
        if zero_matrix is None:
            ident = self._emmebank.available_matrix_identifier("SCALAR")
            zero_matrix = self._emmebank.create_matrix(ident)
            zero_matrix.name = "zero"
            zero_matrix.description = "zero demand matrix"
        zero_matrix.data = 0


class PrepareHighwayDemand(PrepareDemand):
    """Import and average highway demand.

    Demand is imported from OMX files based on reference file paths and OMX
    matrix names in highway assignment config (highway.classes).
    The demand is average using MSA with the current demand matrices
    (in the Emmebank) if the controller.iteration > 1.

    Args:
        controller: parent RunController object
    """

    def __init__(self, controller: RunController):
        super().__init__(controller)
        self._emmebank = None

    @LogStartEnd("Prepare highway demand")
    def run(self, time_period: Union[Collection[str], str] = None):
        """Open combined demand OMX files from demand models and prepare for assignment.

        Args:
            time_period: list of str names of time_periods, or name of a single _time_period
        """
        self._source_ref_key = "highway_demand_file"
        emmebank_path = self.get_abs_path(self.config.emme.highway_database_path)
        self._emmebank = self.controller.emme_manager.emmebank(emmebank_path)
        self._create_zero_matrix()
        for time in self.time_period_names():
            for klass in self.config.highway.classes:
                self._prepare_demand(klass.name, klass.description, klass.demand, time)

    def _prepare_demand(
        self,
        name: str,
        description: str,
        demand_config: List[Dict[str, Union[str, float]]],
        time_period: str,
    ):
        """Load demand from OMX files and save to Emme matrix for highway assignment.

        Average with previous demand (MSA) if the current iteration > 1

        Args:
            name (str): the name of the highway assignment class
            description (str): the description for the highway assignment class
            demand_config (dict): the list of file cross-reference(s) for the demand to be loaded
                {"source": <name of demand model component>,
                 "name": <OMX key name>,
                 "factor": <factor to apply to demand in this file>}
            time_period (str): the time _time_period ID (name)
        """
        self._scenario = self.get_emme_scenario(self._emmebank.path, time_period)
        demand = self._read_demand(demand_config[0], {"period": time_period.upper()})
        for file_config in demand_config[1:]:
            demand = demand + self._read_demand(
                file_config, {"period": time_period.upper()}
            )
        demand_name = f"{time_period}_{name}"
        description = f"{time_period} {description} demand"
        self._save_demand(demand_name, demand, description, apply_msa=True)


class PrepareTransitDemand(PrepareDemand):
    """Import transit demand."""

    @LogStartEnd("Prepare transit demand")
    def run(self, time_period: Union[Collection[str], str] = None):
        """Open combined demand OMX files from demand models and prepare for assignment.

        Args:
            time_period: list of str names of time_periods, or name of a single _time_period
        """
        self._source_ref_key = "transit_demand_file"
        emmebank_path = self.get_abs_path(self.config.emme.transit_database_path)
        self._emmebank = self.controller.emme_manager.emmebank(emmebank_path)
        self._create_zero_matrix()
        for time in self._process_time_period(time_period):
            for klass in self.config.transit.classes:
                self._prepare_demand(
                    klass.skim_set_id, klass.description, klass.demand, time
                )

    def _prepare_demand(
        self,
        name: str,
        description: str,
        demand_config: List[Dict[str, Union[str, float]]],
        time_period: str,
    ):
        """Load demand from OMX files and save to Emme matrix for transit assignment.

        Average with previous demand (MSA) if the current iteration > 1 and
        config.transit.apply_msa_demand is True

        Args:
            name (str): the name of the transit assignment class in the OMX files, usually a number
            description (str): the description for the transit assignment class
            demand_config (dict): the list of file cross-reference(s) for the demand to be loaded
                {"source": <name of demand model component>,
                 "name": <OMX key name>,
                 "factor": <factor to apply to demand in this file>}
            time_period (str): the time _time_period ID (name)
        """
        self._scenario = self.get_emme_scenario(self._emmebank.path, time_period)
        str_format = {"period": time_period.upper(), "skim_set_id": name}
        demand = self._read_demand(demand_config[0], str_format)
        for file_config in demand_config[1:]:
            demand = demand + self._read_demand(file_config, str_format)
        demand_name = f"TRN_{name}_{time_period}"
        description = f"{time_period} {description} demand"
        apply_msa = self.config.transit.apply_msa_demand
        self._save_demand(demand_name, demand, description, apply_msa=apply_msa)
