# transport_demand_calc.py
import pandas as pd

def get_metric(metrics_raw, key: str, scenario: str, default=0.0) -> float:
    if key not in metrics_raw:
        return float(default)
    val = metrics_raw[key].get(scenario, default)
    try:
        return float(val)
    except Exception:
        return float(default)

def pct(metrics_raw, key: str, scenario: str, default=0.0) -> float:
    return get_metric(metrics_raw, key, scenario, default) / 100.0

def safe_div(n, d):
    if d in (None, 0): return 0.0
    if d == 99999999: return 0.0
    return n / d

def add_row(rows, sector, subsector, mode, enduse, tech, fuel, scn, vkm, share, inten):
    fed_kwh = vkm * share * inten
    fed_gwh = fed_kwh / 1e6
    rows.append([sector, subsector, mode, enduse, tech, fuel, scn, fed_gwh])

def calc_for_scenario(metrics_raw: dict, scenario: str) -> pd.DataFrame:
    rows = []

    # === Population and totals ===
    pop = get_metric(metrics_raw, "Population", scenario, 0.0) * 1e6
    pkm_pc = get_metric(metrics_raw, "Mobility per capita - Passenger", scenario, 0.0)
    tkm_pc = get_metric(metrics_raw, "Mobility per capita - Freight", scenario, 0.0)
    total_pkm = pop * pkm_pc
    total_tkm = pop * tkm_pc

    # === Passenger subsector split ===
    road_pass = total_pkm * pct(metrics_raw, "Share per Subsector - Road Passenger", scenario)
    rail_pass = total_pkm * pct(metrics_raw, "Share per Subsector - Rail Passenger = Train", scenario)
    air_pass  = total_pkm * pct(metrics_raw, "Share per Subsector - Aviation Passenger = Plane", scenario)
    ship_pass = total_pkm * pct(metrics_raw, "Share per Subsector - Navigation Passenger = Ship", scenario)

    # === Passenger road mode split ===
    sh_ldv = pct(metrics_raw, "Share per Mode - LDV", scenario)
    sh_bus = pct(metrics_raw, "Share per Mode - Bus", scenario)
    sh_23w = pct(metrics_raw, "Share per Mode - 2&3W", scenario)

    ldv_pkm = road_pass * sh_ldv
    bus_pkm = road_pass * sh_bus
    w23_pkm = road_pass * sh_23w

    # === Passenger vkm conversion ===
    vkm_ldv = safe_div(ldv_pkm, get_metric(metrics_raw, "Load Factor - LDV", scenario, 1.0))
    vkm_bus = safe_div(bus_pkm, get_metric(metrics_raw, "Load Factor - Bus", scenario, 1.0))
    vkm_23w = safe_div(w23_pkm, get_metric(metrics_raw, "Load Factor - 2&3W", scenario, 1.0))
    vkm_ptr = safe_div(rail_pass, get_metric(metrics_raw, "Load Factor - Passenger Train", scenario, 1.0))
    vkm_ppl = safe_div(air_pass,  get_metric(metrics_raw, "Load Factor - Passenger Plane", scenario, 1.0))
    vkm_psh = safe_div(ship_pass, get_metric(metrics_raw, "Load Factor - Passenger Ship", scenario, 99999999))

    # === PASSENGER: LDV ===
    for tech, fuel in [
        ("Gasoline ICE", "Gasoline"),
        ("Diesel ICE", "Diesel"),
        ("BEV", "Electricity"),
        ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Passenger","Road","LDV", tech, fuel, scenario,
                vkm_ldv,
                pct(metrics_raw, f"Share of Technology - {tech} LDV", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} LDV", scenario))

    # === PASSENGER: Bus ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"),
        ("BEV", "Electricity"),
        ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Passenger","Road","Bus", tech, fuel, scenario,
                vkm_bus,
                pct(metrics_raw, f"Share of Technology - {tech} Bus", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Bus", scenario))

    # === PASSENGER: 2&3 Wheelers ===
    for tech, fuel in [
        ("Gasoline ICE", "Gasoline"),
        ("BEV", "Electricity"),
    ]:
        add_row(rows, "Transport","Passenger","Road","2&3 Wheelers", tech, fuel, scenario,
                vkm_23w,
                pct(metrics_raw, f"Share of Technology - {tech} 2&3W", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} 2&3W", scenario))

    # === PASSENGER: Rail ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"),
        ("Direct Electric", "Electricity"),
        ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Passenger","Rail","Passenger Train", tech, fuel, scenario,
                vkm_ptr,
                pct(metrics_raw, f"Share of Technology - {tech} Passenger Train", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Passenger Train", scenario))

    # === PASSENGER: Aviation ===
    for tech, fuel in [
        ("Kerosene", "Kerosene"),
        ("BEV", "Electricity"),
        ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Passenger","Aviation","Passenger Planes", tech, fuel, scenario,
                vkm_ppl,
                pct(metrics_raw, f"Share of Technology - {tech} Passenger Plane", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Passenger Plane", scenario))

    # === PASSENGER: Ships ===
    add_row(rows, "Transport","Passenger","Navigation","Passenger Ships",
            "Diesel", "Diesel", scenario,
            vkm_psh,
            pct(metrics_raw, "Share of Technology - Diesel Passenger Ship", scenario),
            get_metric(metrics_raw, "Final Energy Intensity - Diesel Passenger Ship", scenario))

    # === FREIGHT subsectors ===
    road_frt = total_tkm * pct(metrics_raw, "Share per Subsector - Road Freight", scenario)
    rail_frt = total_tkm * pct(metrics_raw, "Share per Subsector - Rail Freight = Train", scenario)
    ship_frt = total_tkm * pct(metrics_raw, "Share per Subsector - Navigation Freight = Ship", scenario)

    sh_ldt = pct(metrics_raw, "Share per Mode - Light-Duty Trucks", scenario)
    sh_hdt = pct(metrics_raw, "Share per Mode - Heavy-Duty Trucks", scenario)

    ldt_tkm = road_frt * sh_ldt
    hdt_tkm = road_frt * sh_hdt

    vkm_ldt = safe_div(ldt_tkm, get_metric(metrics_raw, "Load Factor - LDT", scenario, 1.0))
    vkm_hdt = safe_div(hdt_tkm, get_metric(metrics_raw, "Load Factor - HDT", scenario, 1.0))
    vkm_ftr = safe_div(rail_frt, get_metric(metrics_raw, "Load Factor - Freight Train", scenario, 1.0))
    vkm_fsh = safe_div(ship_frt, get_metric(metrics_raw, "Load Factor - Freight Ship", scenario, 1.0))

    # === FREIGHT: Light-Duty Trucks ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"),
        ("BEV", "Electricity"),
        ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Freight","Road","Light-Duty Trucks", tech, fuel, scenario,
                vkm_ldt,
                pct(metrics_raw, f"Share of Technology - {tech} LDT", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} LDT", scenario))

    # === FREIGHT: Heavy-Duty Trucks ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"),
        ("BEV", "Electricity"),
        ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Freight","Road","Heavy-Duty Trucks", tech, fuel, scenario,
                vkm_hdt,
                pct(metrics_raw, f"Share of Technology - {tech} HDT", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} HDT", scenario))

    # === FREIGHT: Rail ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"),
        ("Direct Electric", "Electricity"),
        ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Freight","Rail","Freight Train", tech, fuel, scenario,
                vkm_ftr,
                pct(metrics_raw, f"Share of Technology - {tech} Freight Train", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Freight Train", scenario))

    # === FREIGHT: Navigation Ships ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"),
        ("Methanol", "Methanol"),
        ("Ammonia", "Ammonia"),
        ("BEV", "Electricity"),
        ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Freight","Navigation","Freight Ships",
                tech, fuel, scenario,
                vkm_fsh,
                pct(metrics_raw, f"Share of Technology - {tech} Freight Ship", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Freight Ship", scenario))

    # === FREIGHT: Aviation ===
    add_row(rows, "Transport","Freight","Aviation","Freight Planes","Kerosene","Kerosene", scenario,
            safe_div(total_tkm * pct(metrics_raw, "Share per Subsector - Aviation Freight = Plane", scenario),
                     get_metric(metrics_raw, "Load Factor - Freight Plane", scenario, 99999999)),
            pct(metrics_raw, "Share of Technology - Kerosene Freight Plane", scenario),
            get_metric(metrics_raw, "Final Energy Intensity - Kerosene Freight Plane", scenario))

    # === TOTAL ===
    total_gwh = sum(r[-1] for r in rows)
    rows.append(["Transport", "TOTAL", "", "", "", "TOTAL", scenario, total_gwh])

    return pd.DataFrame(rows, columns=[
        "Sector","Subsector","Mode","End-Use","Technology","Fuel","Scenario","Final Energy Demand (GWh)"])
