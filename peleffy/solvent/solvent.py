"""
This module contains classes and functions involved in the manipulation of
PELE's solvent templates.
"""

from simtk import unit

from peleffy.utils import get_data_file_path
from peleffy.utils import Logger


class _SolventWrapper(object):
    """
    A wrapper for any solvent-like class.
    """
    _ff_file = None
    _name = None
    _compatibility = None

    def __init__(self, topology):
        """
        Initializes a SolventWrapper object.

        Parameters
        ----------
        topology : a Topology object
            The molecular topology representation to write as a
            Impact template
        """
        self._topology = topology
        self._radii = dict.fromkeys([tuple((idx, ))
                                     for idx in range(0, len(topology.atoms))],
                                    unit.Quantity())
        self._scales = dict.fromkeys([tuple((idx, ))
                                      for idx in range(0, len(topology.atoms))],
                                     unit.Quantity())

    @property
    def name(self):
        """
        The name of the solvent.

        Returns
        -------
        name : str
            The name of this solvent object.
        """
        return self._name

    @property
    def topology(self):
        """
        The peleffy's Topology.

        Returns
        -------
        topology : a peleffy.topology.Topology
            The molecular topology representation to write as a
            Impact template
        """
        return self._topology

    @property
    def radii(self):
        """
        The dict of radii of the parameterized molecule.

        Returns
        -------
        radii : dict[atom indexes: simtk.unit.Quantity]
            The radius assigned to each atom of the molecule
        """
        return self._radii

    @property
    def scales(self):
        """
        The dict of scales of the parameterized molecule.

        Returns
        -------
        scales : dict[atom indexes: simtk.unit.Quantity]
            The scale assigned to each atom of the molecule
        """
        return self._scales


class _OpenFFCompatibleSolvent(_SolventWrapper):
    """
    Implementation of a solvent-template generator compatible with
    PELE's OpenFF implementation.
    """

    _compatibility = 'openff'

    def __init__(self, topology):
        """
        It initializes an OpenFFCompatibleSolvent.

        Parameters
        ----------
        topology : a Topology object
            The molecular topology representation to write as a
            Impact template
        """
        super().__init__(topology)

        self._initialize_from_topology()

    def _initialize_from_topology(self):
        """
        Initializes a SolventWrapper object using a peleffy's
        molecular Topology.
        """
        logger = Logger()
        logger.info(' - Generating solvent parameters')

        from peleffy.utils.toolkits import OpenForceFieldToolkitWrapper

        off_toolkit = OpenForceFieldToolkitWrapper()
        GBSA_handler = off_toolkit.get_parameter_handler_from_forcefield(
            'GBSA', self._ff_file)

        self._solvent_dielectric = GBSA_handler.solvent_dielectric
        self._solute_dielectric = GBSA_handler.solute_dielectric
        self._surface_area_penalty = GBSA_handler.surface_area_penalty
        self._solvent_radius = GBSA_handler.solvent_radius

        from peleffy.forcefield import OpenForceField

        forcefield = OpenForceField(self._ff_file)
        parameters = forcefield.parameterize(self.topology.molecule,
                                             charge_method='dummy')

        self._radii = parameters['GBSA_radii']
        self._scales = parameters['GBSA_scales']

    def to_dict(self):
        """
        Returns this OpenFFCompatibleSolvent object as a dictionary.

        Returns
        -------
        data : dict
            A dictionary containing the data of this SolventWrapper object
        """
        data = dict()
        data['SolventParameters'] = dict()
        data['SolventParameters']['Name'] = self.name
        data['SolventParameters']['General'] = dict()
        data['SolventParameters']['General']['solvent_dielectric'] = \
            round(self.solvent_dielectric, 5)
        data['SolventParameters']['General']['solute_dielectric'] = \
            round(self.solute_dielectric, 5)
        data['SolventParameters']['General']['solvent_radius'] = \
            round(self.solvent_radius.value_in_unit(unit.angstrom), 5)
        data['SolventParameters']['General']['surface_area_penalty'] = \
            round(self.surface_area_penalty.value_in_unit(
                unit.kilocalorie / (unit.angstrom**2 * unit.mole)), 8)
        data['SolventParameters'][self.topology.molecule.tag] = dict()

        atom_names = self.topology.molecule.get_pdb_atom_names()

        for atom, name in zip(self.topology.molecule.rdkit_molecule.GetAtoms(),
                              atom_names):
            name = name.replace(' ', '_')
            index = atom.GetIdx()
            data['SolventParameters'][self.topology.molecule.tag][name] = \
                {'radius': round(self.radii[tuple((index, ))].value_in_unit(
                                 unit.angstrom), 5),
                 'scale': round(self.scales[tuple((index, ))], 5)}

        return data

    def to_file(self, path):
        """
        Writes this OpenFFCompatibleSolvent object to a file.

        Parameters
        ----------
        path : str
            Path to save the output file to
        """
        import json
        with open(path, 'w') as file:
            json.dump(self.to_dict(), file, indent=4)

    @property
    def solvent_dielectric(self):
        """
        The solvent dielectric value of this solvent object.

        Returns
        -------
        solvent_dielectric : float
            The solvent dielectric value
        """
        return self._solvent_dielectric

    @property
    def solute_dielectric(self):
        """
        The solute dielectric value of this solvent object.

        Returns
        -------
        solute_dielectric : float
            The solute dielectric value
        """
        return self._solute_dielectric

    @property
    def surface_area_penalty(self):
        """
        The surface area penalty value of this solvent object.

        Returns
        -------
        surface_area_penalty : float
            The surface area penalty value
        """
        return self._surface_area_penalty

    @property
    def solvent_radius(self):
        """
        The solvent radius value of this solvent object.

        Returns
        -------
        solvent_radius : float
            The solvent radius value
        """
        return self._solvent_radius


class _OPLS2005CompatibleSolvent(_SolventWrapper):
    """
    Implementation of a solvent-template generator compatible with
    PELE's OPLS2005 implementation.
    """

    _compatibility = 'opls2005'
    _PARAMS_PATH = get_data_file_path('parameters/solventParamsHCTOBC.txt')

    def __init__(self, topology):
        """
        It initializes an OPLS2005CompatibleSolvent.

        Parameters
        ----------
        topology : a Topology object
            The molecular topology representation to write as a
            Impact template
        """
        super().__init__(topology)

        from peleffy.forcefield import OPLS2005ForceField
        from peleffy.forcefield.parameters import OPLS2005ParameterWrapper

        # Parameterize with OPLS2005 only is the parameters in topology
        # are not obtained with OPLS2005
        if isinstance(topology.parameters, OPLS2005ParameterWrapper):
            parameters = topology.parameters
        else:
            forcefield = OPLS2005ForceField()
            parameters = forcefield.parameterize(self.molecule)

        self._radii = parameters['GBSA_radii']
        self._scales = parameters['GBSA_scales']

    def to_file(self, path):
        """
        Writes this OPLS2005CompatibleSolvent object to a file
        compatible with PELE.

        Parameters
        ----------
        path : str
            Path to save the output file to
        """

        # Load parameters for standard residues
        with open(self._PARAMS_PATH) as f:
            standard_params = f.read()

        # Add parameters for non standard residues
        atom_names = [param.replace('_', '')
                      for param in self.topology.parameters['atom_names']]

        with open(path, 'w') as f:
            f.write(standard_params)

            for atom_name, atom_type, scale, radii in zip(
                atom_names, self.topology.parameters['atom_types'],
                    self.scales, self.radii):

                f.write(self.topology.molecule.tag + 'Z'.upper() + '   '
                        + atom_name + '   '
                        + atom_type + '    '
                        + str(scale) + '   '
                        + str(radii._value) + '\n')


class OBC1(_OpenFFCompatibleSolvent):
    """
    Implementation of the OBC1 solvent.
    """

    _ff_file = get_data_file_path('forcefields/GBSA_OBC1-1.0.offxml')
    _name = 'OBC1'

    def __init__(self, topology):
        """
        Initializes an OBC1 object.

        Parameters
        ----------
        topology : a Topology object
            The molecular topology representation to write as a
            Impact template
        """
        # Not implemented in PELE
        logger = Logger()
        logger.warning('OBC1 is not implemented in PELE')

        super().__init__(topology)


class OBC2(_OpenFFCompatibleSolvent):
    """
    Implementation of the OBC2 solvent.
    """

    _ff_file = get_data_file_path('forcefields/GBSA_OBC2-1.0.offxml')
    _name = 'OBC2'

    def __init__(self, topology):
        """
        Initializes an OBC2 object.

        Parameters
        ----------
        topology : a Topology object
            The molecular topology representation to write as a
            Impact template

        Examples
        --------

        Generate the solvent parameters of a molecule

        >>> from peleffy.topology import Molecule

        >>> molecule = Molecule('molecule.pdb')

        >>> from peleffy.forcefield import OpenForceField

        >>> openff = OpenForceField('openff_unconstrained-1.2.1.offxml')
        >>> parameters = openff.parameterize(molecule)

        >>> from peleffy.topology import Topology

        >>> topology = Topology(molecule, parameters)

        >>> from peleffy.solvent import OBC2

        >>> solvent = OBC2(topology)
        >>> solvent.to_file('OBC_parameters.txt')

        """
        super().__init__(topology)


class OPLSOBC(_OPLS2005CompatibleSolvent):
    """
    It defines a template generator for OBC compatible with the OPLS2005
    force field implemented in PELE.
    """
    _name = 'OBC'

    def __init__(self, topology):
        """
        Initializes an OPLSOBC object.

        Parameters
        ----------
        topology : a Topology object
            The molecular topology representation to write as a
            Impact template

        Examples
        --------

        Generate the solvent parameters of a molecule

        >>> from peleffy.topology import Molecule

        >>> molecule = Molecule('molecule.pdb')

        >>> from peleffy.forcefield import OPLS2005ForceField

        >>> opls2005 = OPLS2005ForceField()
        >>> parameters = opls2005.parameterize(molecule)

        >>> from peleffy.topology import Topology

        >>> topology = Topology(molecule, parameters)

        >>> from peleffy.solvent import OPLSOBC

        >>> solvent = OPLSOBC(topology)
        >>> solvent.to_file('OBC_parameters.txt')

        """
        super().__init__(topology)
