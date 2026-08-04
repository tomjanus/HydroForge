"""Serialization and file I/O for :class:`EPANETNetworkModel`.

This module is responsible for everything that turns an in-memory
:class:`~hydroforge.epanetfile_io.model_wrapper.EPANETNetworkModel` into a
serialized representation (a plain dictionary, a JSON file, or an EPANET
``.inp`` file) and back again. It deliberately contains no data-modeling
logic of its own -- that responsibility belongs to
:mod:`hydroforge.epanetfile_io.model_wrapper`. This split keeps the model
focused on representing and manipulating network data, while this module
focuses purely on converting to/from external representations.

The overall workflow this module enables is:

1. Read an EPANET ``.inp`` file into an :class:`EPANETNetworkModel` (no
   external simulation packages such as WNTR are required).
2. Inspect and modify the model in place using the typed accessors provided
   by :class:`EPANETNetworkModel`.
3. Write the (possibly modified) model back out to an ``.inp`` file.
"""
import json
from collections import OrderedDict
from typing import Any, Dict

from hydroforge.epanetfile_io.file_io import EPANETFileIO
from hydroforge.epanetfile_io.model_wrapper import EPANETNetworkModel, NetworkCollection


class EPANETNetworkModelIO:
    """Serialization and file I/O helpers for :class:`EPANETNetworkModel`.

    All methods are static: this class exists purely as a namespace and
    holds no state of its own.
    """

    @staticmethod
    def from_dict(network_data: OrderedDict) -> EPANETNetworkModel:
        """Build an :class:`EPANETNetworkModel` from a raw section dictionary.

        Parameters
        ----------
        network_data : OrderedDict
            Dictionary keyed by EPANET section name (e.g. ``'JUNCTIONS'``),
            with each value being a list of tokenized rows, as produced by
            :meth:`hydroforge.epanetfile_io.file_io.EPANETFileIO.read_inp_file`.

        Returns
        -------
        EPANETNetworkModel
            Model populated from ``network_data``. Sections absent from
            ``network_data`` are left at their default (empty) value.
        """
        kwargs: Dict[str, Any] = {}
        for field_mapping in EPANETNetworkModel.COLLECTION_MAPPINGS:
            if field_mapping.section in network_data:
                kwargs[field_mapping.attr_name] = NetworkCollection(
                    field_mapping.item_type,
                    network_data[field_mapping.section]
                )
        for field_mapping in EPANETNetworkModel.LIST_FIELD_MAPPINGS:
            if field_mapping.section in network_data:
                kwargs[field_mapping.attr_name] = network_data[field_mapping.section]
        return EPANETNetworkModel(**kwargs)
    
    @staticmethod
    def to_dict(model: EPANETNetworkModel) -> Dict[str, Any]:
        """Convert an :class:`EPANETNetworkModel` back to a section dictionary.

        Parameters
        ----------
        model : EPANETNetworkModel
            Model to serialize.

        Returns
        -------
        dict
            Dictionary keyed by EPANET section name, with each value being
            a list of tokenized rows, suitable for
            :meth:`hydroforge.epanetfile_io.file_io.EPANETFileIO.write_inp_file`
            or JSON serialization. Empty sections are omitted.
        """
        result: Dict[str, Any] = OrderedDict()

        for field_mapping in EPANETNetworkModel.COLLECTION_MAPPINGS:
            collection: NetworkCollection = getattr(model, field_mapping.attr_name)
            result[field_mapping.section] = collection.to_list()
        for field_mapping in EPANETNetworkModel.LIST_FIELD_MAPPINGS:
            values = getattr(model, field_mapping.attr_name)
            if values:
                result[field_mapping.section] = values
        # EPANET input files must be terminated by an [END] section marker.
        # Without it, section-ending parsers (such as
        # ``EPANETFileIO.read_inp_file``) cannot reliably detect the end of
        # the final data section.
        result['END'] = []
        return result

    @staticmethod
    def from_json_file(filepath: str) -> EPANETNetworkModel:
        """Load an :class:`EPANETNetworkModel` from a JSON file.

        Parameters
        ----------
        filepath : str
            Path to a JSON file containing a serialized network dictionary.

        Returns
        -------
        EPANETNetworkModel
            Model populated from the JSON file contents.
        """
        with open(filepath, 'r', encoding='utf-8') as file_handle:
            network_data = json.load(file_handle)
        return EPANETNetworkModelIO.from_dict(network_data)

    @staticmethod
    def to_json_file(model: EPANETNetworkModel, filepath: str, indent: int = 4) -> None:
        """Save an :class:`EPANETNetworkModel` to a JSON file.

        Parameters
        ----------
        model : EPANETNetworkModel
            Model to serialize.
        filepath : str
            Destination path for the JSON file.
        indent : int, optional
            Indentation level passed to :func:`json.dump`. Default is 4.
        """
        with open(filepath, 'w', encoding='utf-8') as file_handle:
            json.dump(EPANETNetworkModelIO.to_dict(model), file_handle, indent=indent)

    @staticmethod
    def from_inp_file(filepath: str) -> EPANETNetworkModel:
        """Load an :class:`EPANETNetworkModel` from an EPANET ``.inp`` file.

        Parameters
        ----------
        filepath : str
            Path to the EPANET input file.

        Returns
        -------
        EPANETNetworkModel
            Model populated from the parsed INP file.
        """
        return EPANETNetworkModelIO.from_dict(EPANETFileIO.read_inp_file(filepath))

    @staticmethod
    def to_inp_file(model: EPANETNetworkModel, filepath: str) -> None:
        """Save an :class:`EPANETNetworkModel` to an EPANET ``.inp`` file.

        Parameters
        ----------
        model : EPANETNetworkModel
            Model to serialize.
        filepath : str
            Destination path for the ``.inp`` file.
        """
        EPANETFileIO.write_inp_file(filepath, EPANETNetworkModelIO.to_dict(model))
