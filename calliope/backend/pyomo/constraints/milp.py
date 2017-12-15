"""
Copyright (C) 2013-2017 Calliope contributors listed in AUTHORS.
Licensed under the Apache 2.0 License (see LICENSE file).

milp.py
~~~~~~~~~~~~~~~~~

Constraints for binary and integer decision variables

"""

import pyomo.core as po  # pylint: disable=import-error

from calliope.backend.pyomo.util import \
    get_param, \
    get_timestep_weight, \
    get_loc_tech


def load_milp_constraints(backend_model):
    sets = backend_model.__calliope_model_data__['sets']

    if 'loc_techs_milp' in sets:
        backend_model.unit_commitment_constraint = po.Constraint(
            backend_model.loc_techs_unit_commitment_constraint, backend_model.timesteps,
            rule=unit_commitment_constraint_rule
        )

        backend_model.carrier_production_max_milp_constraint = po.Constraint(
            backend_model.loc_tech_carriers_carrier_production_max_conversion_plus_milp_constraint_rule,
            backend_model.timesteps,
            rule=carrier_production_max_milp_constraint_rule
        )

        backend_model.carrier_consumption_max_milp_constraint = po.Constraint(
            backend_model.loc_tech_carriers_carrier_consumption_max_milp_constraint,
            backend_model.timesteps,
            rule=carrier_consumption_max_milp_constraint_rule
        )

    if 'loc_tech_carriers_carrier_production_min_milp_constraint' in sets:
        backend_model.carrier_production_min_milp_constraint = po.Constraint(
            backend_model.loc_tech_carriers_carrier_production_min_milp_constraint,
            backend_model.timesteps,
            rule=carrier_production_min_milp_constraint_rule
        )

    if 'loc_techs_storage_capacity_milp_constraint' in sets:
        backend_model.storage_capacity_milp_constraint = po.Constraint(
            backend_model.loc_techs_storage_capacity_milp_constraint,
            rule=storage_capacity_milp_constraint_rule
        )

    if 'loc_techs_energy_capacity_units_constraint' in sets:
        backend_model.energy_capacity_units_constraint = po.Constraint(
            backend_model.loc_techs_energy_capacity_units_constraint,
            rule=energy_capacity_units_constraint_rule
        )

    if 'loc_techs_update_costs_investment_units_constraint' in sets:
        for loc_tech, timestep in (
            backend_model.loc_techs_update_costs_investment_units_constraint):

            update_costs_investment_units_constraint(backend_model, loc_tech, timestep)

    if 'loc_techs_update_costs_investment_purchase_constraint' in sets:
        for loc_tech, timestep in (
            backend_model.loc_techs_update_costs_investment_purchase_constraint):

            update_costs_investment_purchase_constraint(backend_model, loc_tech, timestep)

    if 'loc_techs_energy_capacity_max_purchase_constraint' in sets:
        backend_model.energy_capacity_max_purchase_constraint = po.Constraint(
            backend_model.loc_techs_energy_capacity_max_purchase_constraint,
            rule=energy_capacity_max_purchase_constraint_rule
        )
    if 'loc_techs_energy_capacity_min_purchase_constraint' in sets:
        backend_model.energy_capacity_min_purchase_constraint = po.Constraint(
            backend_model.loc_techs_energy_capacity_min_purchase_constraint,
            rule=energy_capacity_min_purchase_constraint_rule
        )


def unit_commitment_constraint_rule(backend_model, loc_tech, timestep):
    """
    operating_units
    ^^^^^^^^^^^^^^^
    Constraining the number of integer units
    :math:`operating_units(loc_tech, timestep)` of a technology which
    can operate in a given timestep, based on maximum purchased units
    :math:`units(loc_tech)`

    .. math::
    $operating\_units(y, x, t) \leq units(y, x)

    """

    return (backend_model.operating_units[loc_tech, timestep]
            <= backend_model.units[loc_tech])


def carrier_production_max_milp_constraint_rule(backend_model, loc_tech_carrier, timestep):
    loc_tech = get_loc_tech(loc_tech_carrier)
    carrier_prod = backend_model.carrier_prod[loc_tech_carrier, timestep]
    timestep_resolution = get_param(backend_model, 'timestep_resolution', timestep)
    parasitic_eff = get_param(backend_model, 'parasitic_eff', (loc_tech, timestep))
    energy_cap = get_param(backend_model, 'energy_cap_per_unit', loc_tech)

    return carrier_prod <= (
        backend_model.operating_units[loc_tech, timestep] *
        timestep_resolution * energy_cap * parasitic_eff
    )

def carrier_production_max_conversion_plus_milp_constraint_rule(backend_model, loc_tech, timestep):
    """
    Set maximum carrier production. All technologies.
    """
    timestep_resolution = get_param(backend_model, 'timestep_resolution', timestep)
    energy_cap = get_param(backend_model, 'energy_cap_per_unit', loc_tech)
    loc_tech_carriers_out = split_comma_list(get_param(
        backend_model, 'lookup_loc_techs_conversion_plus', ('out', loc_tech)
    ))

    carrier_prod = sum(backend_model.carrier_prod[loc_tech_carrier, timestep]
                 for loc_tech_carrier in loc_tech_carriers_out)

    return carrier_prod <= (
        backend_model.operating_units[loc_tech, timestep] *
        timestep_resolution * energy_cap
    )

def carrier_production_min_milp_constraint_rule(backend_model, loc_tech_carrier, timestep):
    loc_tech = get_loc_tech(loc_tech_carrier)
    carrier_prod = backend_model.carrier_prod[loc_tech_carrier, timestep]
    timestep_resolution = get_param(backend_model, 'timestep_resolution', timestep)
    min_use = get_param(backend_model, 'energy_cap_min_use', (loc_tech, timestep))
    energy_cap = get_param(backend_model, 'energy_cap_per_unit', loc_tech)

    return carrier_prod >= (
        backend_model.operating_units[loc_tech, timestep] *
        timestep_resolution * energy_cap * min_use
    )


def carrier_consumption_max_milp_constraint_rule(backend_model, loc_tech_carrier, timestep):
    loc_tech = get_loc_tech(loc_tech_carrier)
    carrier_con = backend_model.carrier_con[loc_tech_carrier, timestep]
    timestep_resolution = get_param(backend_model, 'timestep_resolution', timestep)
    energy_cap = get_param(backend_model, 'energy_cap_per_unit', loc_tech)

    return carrier_con >= (-1 *
        backend_model.operating_units[loc_tech, timestep] *
        timestep_resolution * energy_cap
    )


def energy_capacity_units_constraint_rule(backend_model, loc_tech):

    return backend_model.energy_cap[loc_tech] == (
        backend_model.units[loc_tech] *
        get_param(backend_model, 'energy_cap_per_unit', loc_tech)
    )


def energy_capacity_max_purchase_constraint_rule(backend_model, loc_tech):
    energy_cap_max = get_param(backend_model, 'energy_cap_max', loc_tech)
    energy_cap_equals = get_param(backend_model, 'energy_cap_equals', loc_tech)
    energy_cap_scale = get_param(backend_model, 'energy_cap_scale', loc_tech)

    if energy_cap_equals:
        return backend_model.energy_cap[loc_tech] == (
            energy_cap_equals * energy_cap_scale * backend_model.purchased[loc_tech]
        )

    elif np.isinf(energy_cap_max):
        return po.Constraint.Skip

    else:
        return backend_model.energy_cap[loc_tech] <= (
            energy_cap_max * energy_cap_scale * backend_model.purchased[loc_tech]
        )


def energy_capacity_min_purchase_constraint_rule(backend_model, loc_tech):
    energy_cap_min = get_param(backend_model, 'energy_cap_min', loc_tech)
    energy_cap_equals = get_param(backend_model, 'energy_cap_equals', loc_tech)

    else:
        energy_cap_scale = get_param(backend_model, 'energy_cap_scale', loc_tech)
        return backend_model.energy_cap[loc_tech] >= (
            energy_cap_min * energy_cap_scale * backend_model.purchased[loc_tech]
        )


def storage_capacity_milp_constraint_rule(backend_model, loc_tech):
    """
    Set maximum storage capacity. Supply_plus & storage techs only
    This can be set by either storage_cap (kWh) or by
    energy_cap (charge/discharge capacity) * charge rate.
    If storage_cap.equals and energy_cap.equals are set for the technology, then
    storage_cap * charge rate = energy_cap must hold. Otherwise, take the lowest capacity
    capacity defined by storage_cap.max or energy_cap.max / charge rate.
    """

    # FIXME?: energy_cap_equals could be already dealt with in preprocessing, to
    # either be energy_cap_equals or units_equals * energy_cap_per_unit. Similarly for
    # storage_cap_equals
    units_equals = get_param(backend_model, 'units_equals', loc_tech)
    storage_cap_per_unit = get_param(backend_model, 'storage_cap_per_unit', loc_tech))
    energy_cap_per_unit = get_param(backend_model, 'energy_cap_per_unit', loc_tech))

    scale = get_param(backend_model, 'energy_cap_scale', loc_tech)
    charge_rate = get_param(backend_model, 'charge_rate', loc_tech)

    # First, set the variable with '==' is unit numbers are set in stone
    if units_equals and storage_cap_per_unit:
        return backend_model.storage_cap[loc_tech] == storage_cap
    elif units_equals and energy_cap_per_unit and charge_rate:
        return backend_model.storage_cap[loc_tech] == energy_cap * scale / charge_rate

    # If not set in stone, use the variable 'units' to set maximum
    elif storage_cap_per_unit:
        storage_cap = backend_model.units[loc_tech] * storage_cap_per_unit
        return backend_model.storage_cap[loc_tech] <= storage_cap

    elif energy_cap_per_unit and charge_rate:
        energy_cap = backend_model.units[loc_tech] * energy_cap_per_unit * scale / charge_rate
        return backend_model.storage_cap[loc_tech] <= energy_cap

    # if insufficient 'per_unit' information is given, assume there is no capacity
    else:
        return po.Constraint.NoConstraint


def update_costs_investment_units_constraint(backend_model, cost, loc_tech):
    model_data_dict = backend_model.__calliope_model_data__
    ts_weight = get_timestep_weight(backend_model)
    depreciation_rate = model_data_dict['data']['cost_depreciation_rate'][(cost, loc_tech)]

    cost_purchase = get_param(backend_model, 'cost_purchase', (cost, loc_tech))
    cost_of_purchase = backend_model.units[loc_tech] * cost_purchase

    backend_model.investment_rhs[cost, loc_tech].expr += cost_of_purchase

    return None


def update_costs_investment_purchase_constraint(backend_model, cost, loc_tech):
    model_data_dict = backend_model.__calliope_model_data__
    ts_weight = get_timestep_weight(backend_model)
    depreciation_rate = model_data_dict['data']['cost_depreciation_rate'][(cost, loc_tech)]

    cost_purchase = get_param(backend_model, 'cost_purchase', (cost, loc_tech))
    cost_of_purchase = backend_model.purchased[loc_tech] * cost_purchase

    backend_model.investment_rhs[cost, loc_tech].expr += cost_of_purchase

    return None