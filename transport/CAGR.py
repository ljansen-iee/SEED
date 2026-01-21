import pandas as pd
import numpy as np

def as_fraction(val):
    """
    Converts percentage to fraction if absolute value > 1.5.
    Example: 2.5 -> 0.025, 0.05 -> 0.05
    """
    if pd.isnull(val):
        return 0.0
    try:
        val = float(val)
        if abs(val) > 1.5:  
            return val / 100.0
        return val
    except Exception:
        return 0.0

def get_cagr(CAGR_VALUES, metric):
    """
    Retrieves the CAGR value dictionary for a specific metric.
    Expects CAGR_VALUES to be a dictionary where keys are metric names.
    """
    if not isinstance(CAGR_VALUES, dict):
        raise ValueError("CAGR_VALUES must be a dictionary.")
        
    entry = CAGR_VALUES.get(metric)
    
    if entry is None:
        # It's better to return an empty dict than crash, 
        # allowing the calling function to handle the default fallback.
        return {}
    
    # Handle structure: {'assumption_type': 'CAGR', 'values': {2030: ...}}
    if isinstance(entry, dict) and "values" in entry:
        return entry["values"]
    
    # Handle flat structure: {2030: ...}
    return entry

def expand_with_cagr(base_value, cagr_table, base_year, target_years, scenarios):
    """
    Expands a base value into future years using piecewise CAGRs.
    
    CRITICAL LOGIC:
    1. If the config has a rate for Year X, that rate applies to the period 
       ending at Year X (from the previous milestone).
    2. If a target year (e.g. 2035) exists in the config, we use that specific rate.
    3. If a target year is MISSING from config, we find the NEXT available milestone 
       and use its rate (effectively interpolating the growth trend).
    """
    if base_value is None:
        base_value = 0.0
        
    out = {str(base_year): float(base_value)}
    
    # 1. Gather all milestones defined in the Excel config (e.g. 2030, 2035, 2040, 2050)
    config_milestones = sorted([int(k) for k in cagr_table.keys() if str(k).isdigit()])
    
    if not config_milestones:
        # No CAGR data? Return constant base value for all years
        for y in target_years:
            for s in scenarios:
                out[f"{y}_{s}"] = float(base_value)
        return out

    def get_rate(year, scenario):
        """Helper to get rate for a specific milestone year and scenario."""
        if year not in cagr_table:
            return 0.0
        yr_data = cagr_table[year]
        
        # Priority: Specific Scenario -> Default/Baseline -> First Available
        if scenario in yr_data: return as_fraction(yr_data[scenario])
        if "default" in yr_data: return as_fraction(yr_data["default"])
        if "Baseline" in yr_data: return as_fraction(yr_data["Baseline"])
        if len(yr_data) > 0: return as_fraction(list(yr_data.values())[0])
        return 0.0

    # Calculate for each scenario independently
    for scenario in scenarios:
        current_value = float(base_value)
        current_year = int(base_year)
        
        # 2. Build the full timeline of years we need to hit
        # We merge the config milestones with the requested target years
        # Example: Config has [2030, 2050]. Target is [2030, 2035, 2040, 2050].
        # Timeline becomes: 2020 -> 2030 -> 2035 -> 2040 -> 2050
        timeline = sorted(list(set(target_years) | set(config_milestones)))
        
        # Filter out years before base year
        timeline = [t for t in timeline if t > current_year]

        # Iterate through time
        for t_year in timeline:
            # 3. Determine which rate applies to this segment (current_year -> t_year)
            
            # CASE A: If t_year is explicitly in the config, use its rate.
            # (e.g. If calculating 2035 and 2035 is in config, use 2035 rate)
            if t_year in config_milestones:
                applicable_milestone = t_year
            
            # CASE B: If t_year is NOT in config (e.g. 2035 is missing, next is 2050),
            # use the rate of the NEXT milestone.
            else:
                applicable_milestone = next((m for m in config_milestones if m >= t_year), None)
                
                # If beyond the last config milestone (e.g. 2060), extrapolate with the last known rate
                if applicable_milestone is None:
                    applicable_milestone = config_milestones[-1]
            
            rate = get_rate(applicable_milestone, scenario)
            
            # Apply CAGR formula
            years_diff = t_year - current_year
            next_value = current_value * ((1 + rate) ** years_diff)
            
            # Store if this is a requested target year
            if t_year in target_years:
                out[f"{t_year}_{scenario}"] = next_value
            
            # Update state for next segment
            current_value = next_value
            current_year = t_year

    return out

def expand_constant(value, base_year, target_years, scenarios):
    """Expands a single value constant across all years/scenarios."""
    if value is None: value = 0.0
    res = {str(base_year): value}
    for y in target_years:
        for s in scenarios:
            res[f"{y}_{s}"] = value
    return res

def poly_project(years, values, target_years, degree=2):
    """
    Project/Interpolate missing values using a polynomial fit (numpy).
    Useful for filling gaps in historical data (e.g. population).
    """
    try:
        # Filter clean data
        clean_points = [(float(y), float(v)) for y, v in zip(years, values) 
                        if str(y).replace('.','').isdigit() and pd.notnull(v)]
        
        if not clean_points:
            return {int(t): np.nan for t in target_years}
            
        x_train, y_train = zip(*clean_points)
        
        # Determine degree (cannot be > number of points - 1)
        deg = min(int(degree), len(x_train) - 1)
        
        if deg < 1:
            # Constant projection if only 1 point
            mean_val = np.mean(y_train)
            return {int(t): mean_val for t in target_years}
            
        # Fit polynomial
        coeffs = np.polyfit(x_train, y_train, deg)
        model = np.poly1d(coeffs)
        
        results = {}
        for t in target_years:
            val = model(t)
            # Prevent negative values for physical quantities
            results[int(t)] = max(0.0, float(val))
            
        # If the input BASE_YEAR was in target_years, ensure it matches input exactly if possible
        # (This block is optional but good for consistency)
        for y, v in clean_points:
            if int(y) in results:
                results[int(y)] = v

        return results
        
    except Exception as e:
        print(f"poly_project error: {e}")
        return {int(t): np.nan for t in target_years}
    