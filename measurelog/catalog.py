"""Ready-made test definitions taken from the laboratory SOPs.

Everything here is a starting point, not a constraint: tests added from this
catalogue are ordinary editable entries, and anything not listed can still be
added by hand on the Setup tab.

Each entry carries what the SOP's summary matrix specifies - the target units,
the replicate count, and the method - plus the sensible display precision for
that measurement and, where the SOP states one, the %RSD its QC section
requires.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Location, Test


@dataclass(frozen=True)
class CatalogTest:
    """One test as written up in the SOPs."""

    name: str
    code: str
    unit: str
    decimals: int
    replicates: int
    method: str
    notes: str = ""
    rsd_limit: float | None = None
    group: str = ""

    def to_test(self) -> Test:
        """A fresh, fully editable Test for the database."""
        return Test(
            name=self.name,
            code=self.code,
            unit=self.unit,
            decimals=self.decimals,
            replicates=self.replicates,
            rsd_limit=self.rsd_limit,
            notes=self.notes_for_test(),
        )

    def notes_for_test(self) -> str:
        parts = [f"Method: {self.method}"]
        if self.notes:
            parts.append(self.notes)
        return "\n".join(parts)

    @property
    def summary(self) -> str:
        bits = [self.unit or "no unit", f"{self.replicates} replicates"]
        if self.rsd_limit is not None:
            bits.append(f"RSD < {self.rsd_limit:g}%")
        return "  |  ".join(bits)


SOLIDS = "Solids and moisture"
CHEMISTRY = "Organic load and carbon"
NUTRIENTS = "Nutrients and stability"
PHYSICAL = "Physical and electrochemical"

TESTS: tuple[CatalogTest, ...] = (
    CatalogTest(
        name="pH",
        code="PH",
        unit="",            # pH is dimensionless; "pH (pH units)" reads badly
        decimals=2,
        replicates=3,
        rsd_limit=2.0,
        group=PHYSICAL,
        method="Potentiometric - pH meter and probe (Hach QC30d with IntelliCal)",
        notes=(
            "Calibrate with pH 4.01 / 7.00 / 10.01 buffers before testing.\n"
            "Rinse the electrode with DI water between samples and let the reading settle.\n"
            "Record to 0.01 units; repeat replicates until %RSD is below 2%."
        ),
    ),
    CatalogTest(
        name="Total Solids (TS)",
        code="TS",
        unit="%",
        decimals=2,
        replicates=3,
        group=SOLIDS,
        method="Gravimetric - drying oven at 103-105 C",
        notes=(
            "Pre-bake the dish, cool in a desiccator and record the tare weight.\n"
            "% TS = ((W_dry - W_dish) / W_sample) x 100"
        ),
    ),
    CatalogTest(
        name="Total Volatile Solids (TVS)",
        code="TVS",
        unit="% of TS",
        decimals=2,
        replicates=3,
        group=SOLIDS,
        method="Gravimetric - muffle furnace at 550 C",
        notes=(
            "Uses the dried dish from the Total Solids test.\n"
            "% TVS (of TS) = ((W_dry - W_ash) / (W_dry - W_dish)) x 100\n"
            "% TVS (of total sample) = ((W_dry - W_ash) / W_sample) x 100"
        ),
    ),
    CatalogTest(
        name="Moisture Content",
        code="MOIST",
        unit="%",
        decimals=2,
        replicates=3,
        group=SOLIDS,
        method="Gravimetric loss on drying, or calculated from Total Solids",
        notes="% Moisture = 100 - % TS",
    ),
    CatalogTest(
        name="Chemical Oxygen Demand (COD)",
        code="COD",
        unit="mg/L",
        decimals=0,
        replicates=3,
        group=CHEMISTRY,
        method="Dichromate digestion at 150 C, read on spectrophotometer at 600/620 nm",
        notes=(
            "Digest 2.0 mL of homogenised sample for 2 hours with a DI water blank.\n"
            "Record the dilution factor used - it is easy to lose track of later."
        ),
    ),
    CatalogTest(
        name="Density",
        code="DENS",
        unit="g/mL",
        decimals=3,
        replicates=3,
        group=PHYSICAL,
        method="Volumetric flask or pycnometer with analytical balance at 20 C",
        notes="Density = (M_filled - M_empty) / V_vessel",
    ),
    CatalogTest(
        name="Total Organic Carbon (TOC)",
        code="TOC",
        unit="mg/L",
        decimals=0,
        replicates=3,
        group=CHEMISTRY,
        method="Carbon analyser, or derived from COD",
        notes="Derived: TOC = COD x 0.375, or the lab's own empirical factor.",
    ),
    CatalogTest(
        name="Total Inorganic Carbon (TIC)",
        code="TIC",
        unit="mg/L",
        decimals=0,
        replicates=3,
        group=CHEMISTRY,
        method="Carbon analyser, or derived from alkalinity",
        notes="Derived: TIC = Alkalinity (mg CaCO3/L) x 0.24",
    ),
    CatalogTest(
        name="Total Carbon (TC)",
        code="TC",
        unit="mg/L",
        decimals=0,
        replicates=3,
        group=CHEMISTRY,
        method="Carbon analyser, or TOC + TIC",
        notes="TC = TOC + TIC",
    ),
    CatalogTest(
        name="Total Nitrogen (TN)",
        code="TN",
        unit="mg N/L",
        decimals=1,
        replicates=3,
        group=NUTRIENTS,
        method="Persulfate digestion with colorimetric finish on spectrophotometer",
        notes="Digest at 105-120 C for 30 minutes, then develop colour per the kit.",
    ),
    CatalogTest(
        name="Alkalinity",
        code="ALK",
        unit="mg CaCO3/L",
        decimals=0,
        replicates=3,
        group=NUTRIENTS,
        method="Titration with standard acid to pH 4.5 and pH 3.7",
        notes=(
            "Titrate 50 mL of sample with stirring; record the acid volume at each endpoint.\n"
            "Alkalinity (mg CaCO3/L) = (V_acid x N_acid x 50,000) / V_sample"
        ),
    ),
    CatalogTest(
        name="Volatile Fatty Acids (VFAs)",
        code="VFA",
        unit="mg/L",
        decimals=0,
        replicates=3,
        group=NUTRIENTS,
        method="FOS/TAC titration, GC-FID or HPLC",
        notes=(
            "Centrifuge at 4000 rpm for 15 minutes and filter through 0.45 um.\n"
            "Reported as acetic acid equivalent."
        ),
    ),
    CatalogTest(
        name="Ammonia (NH3-N / TAN)",
        code="NH3N",
        unit="mg NH3-N/L",
        decimals=1,
        replicates=3,
        group=NUTRIENTS,
        method="Ammonia ISE probe, or salicylate / Nessler colorimetric method",
        notes="Allow 15 minutes for colour development. Note dilution ratios used.",
    ),
    CatalogTest(
        name="Conductivity (EC)",
        code="EC",
        unit="mS/cm",
        decimals=2,
        replicates=3,
        group=PHYSICAL,
        method="Conductivity cell, temperature compensated",
        notes=(
            "Calibrate daily against a standard (1413 uS/cm or 12.88 mS/cm).\n"
            "Report values standardised to 25 C."
        ),
    ),
)

# The SOP's worked example of sampling points along the process.
LOCATIONS: tuple[str, ...] = ("Influent", "Digester 1", "Digester 2", "Effluent")

GROUP_ORDER: tuple[str, ...] = (PHYSICAL, SOLIDS, CHEMISTRY, NUTRIENTS)


def grouped() -> list[tuple[str, list[CatalogTest]]]:
    """Catalogue tests arranged under their headings, in display order."""
    groups = []
    for name in GROUP_ORDER:
        members = [test for test in TESTS if test.group == name]
        if members:
            groups.append((name, members))
    ungrouped = [test for test in TESTS if test.group not in GROUP_ORDER]
    if ungrouped:
        groups.append(("Other", ungrouped))
    return groups


def by_name(name: str) -> CatalogTest | None:
    lowered = name.strip().lower()
    return next((test for test in TESTS if test.name.lower() == lowered), None)


def default_locations() -> list[Location]:
    return [
        Location(name=name, sort_order=index) for index, name in enumerate(LOCATIONS)
    ]
