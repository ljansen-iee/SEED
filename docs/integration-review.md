# Steel-production integration review

**Status: draft integration; not approved for merge or final model inputs.**

## Protected baseline and scope

The integration branch starts from local `main` at
`fadd333da09272d104a38cf450fe5772cec9ef2f` and merges the **entire** feature at
`ca76f6a6bf0f090c57155988c293a5acb696f6ee`, without cherry-picking. Rechecking
and fetching found `origin/main` at `fadd333`, not the earlier recorded
`2519cd9`. The merge had no textual conflicts; coupled configuration,
calculator, preprocessing, emissions and export changes were reviewed together.

Work took place in a separate Git worktree. The original `main` worktree's
21 untracked files were backed up externally and their SHA256 values and Git
status were checked unchanged. No original untracked documentation, instruction
files, notebooks or schema examples are included in this branch. No generated
model outputs were added. The existing fork URLs, hosting and SSL hook
configuration remain unchanged.

## Migration

- The industry API is the central generator and `FinalEnergyCalculator`;
  there is no legacy wide-config compatibility shim. Both use the same
  generated long-format configuration and all 13 industry subsectors.
- Deleted shared preprocessing and additional-sector producers are restored
  from the main workflow, with explicit input/output controls.
- Residential, transport and industry validation paths can all use an external
  output tree. Importing executable modules does not run the workflows.
- Transport detailed energy is GWh; aggregate indicators are already TWh.
  LPG no longer contributes twice to road oil/gas totals.
- ISO2 `NA` is retained as Namibia, not parsed as a missing identifier.
- [The export contract](data/pypsa-output-contract.md) preserves BAU,
  Progressive and Optimistic, all five horizons, root `pypsa_input/`, the
  reference energy columns and the industry country/quantity/subsector layout.
  Unit sidecars distinguish TWh/a, MWh/a, tSteel/a and tCO2/a. The legacy
  industry index field named `carrier` includes typed non-energy quantities;
  process emissions are never added to energy sums.

## Isolated validation evidence

All artifacts and logs were written outside tracked/generated output trees.
The standard projection scope was 2030, 2035, 2040, 2045 and 2050 under all
three scenarios. Producer checks also included the residential base year.

| Check | Result |
| --- | --- |
| Focused unittest suite, including example and real-producer checks | 91 tests passed |
| Changed/new Python syntax | 62 files passed parsing |
| Industry runtime imports | All 56 inspected modules imported |
| Raw-input central industry generation | Passed for Morocco, Egypt, South Africa and Namibia; 5,153 config rows |
| Fresh industry calculation | Passed for all four countries; 488 wide rows and all 13 subsectors |
| Shared shares, CAGR and additional sectors | Passed for all four countries; 24 additional-sector country/year rows |
| Residential production | Passed for all four countries; 72 country/scenario/year summaries |
| Transport production | Passed for all four countries; 60 country/scenario/year aggregate rows |
| Producer merge-key uniqueness | No duplicates in the inspected producer tables |
| Real energy exports | Morocco and Namibia: all 15 scenario/year combinations each passed |
| Real energy exports, Egypt and South Africa | Blocked by nonzero coal measures absent from the example schema |
| Real industry exports | Blocked for all four countries; 120 of 300 sector-emissions rows have unresolved physical CO2 |
| Full exporter failure behavior | Blocked industry validation writes no partial final exports |
| Documentation site build | Passed after removing the stale Windows SSL-hook reference; generated outside the worktree |

Synthetic accepted-factor fixtures are arithmetic tests, not accepted model
inputs. Hand checks include 152,000 tCO2 for hierarchical steel routes,
756,000 tCO2 for clinker and 187,500 tCO2 for route-specific HVC. The extra
100-fold production conversion is removed; production units are read explicitly.

The schema examples used for read-only validation are local reference files,
not redistribution fixtures. Optional artifact tests take explicitly supplied
`PYPSA_*_DIR` environment variables and do not require personal filesystem paths.
The installed project environment still needs to be refreshed from the corrected
dependency declaration: `tabula-py`, rather than the unrelated `tabula` package.
PDF API validation used externally installed dependencies without altering the
project environment. VS Code diagnostics in the original, separately opened
workspace cannot resolve some new worktree-only imports; runtime imports passed.

## Blocking review decisions

### Factor provenance and accounting

The user's decisions are to **retain the defined factors**, calculate ammonia
emissions in this workflow, and export aluminium **CO2 only**. Numeric factors
have not been invented or replaced. Their stated JRC-IDEES attribution lacks
a verified release, table/row reference, gas basis and accounting boundary.
Machine-readable readiness metadata retains these as blockers.

The retained SMR ammonia factor of zero was defined on an energy-side boundary;
it is not evidence for zero process CO2 under the selected calculate-here
boundary. Primary aluminium's retained 1.5 factor has a legacy PFC annotation;
its physical CO2-only basis cannot be certified from that comment. Missing
physical values stay missing, including with review-only provisional options.
Factor/route matching and HVC mappings also need provenance review before
acceptance. Cement uses clinker, not cement mass.

Detailed source files exist for all required sectors, but file availability is
not proof of complete observations: Morocco steel numeric history/aluminium
observations are incomplete and existing documented assumptions/fallbacks need
scientific review. Existing transport international-maritime zero-share
warnings and residential pandas warnings also remain visible in the logs.

### Coal columns missing from the downstream reference

The fresh Egypt additional-sector output has nonzero `non energy coal`.
South Africa has nonzero `services coal`, `non energy coal` and `other coal`.
These fields do not exist in the supplied energy-totals schema. A reviewed
downstream schema extension or a physically justified consumer allocation is
required. No coal has been dropped, zeroed or relabeled as another fuel.
Agriculture coal is already a supported example column.

### Documentation/hosting

The stale `hooks/ssl_fix.py` reference has been removed. The deleted hook
replaced `ssl.create_default_context` with a context that disabled both
certificate verification and hostname checking. That Windows-only workaround
is unnecessary for the GitHub Pages build, which runs on GitHub Actions'
`ubuntu-latest` runner; it is also unsafe as a global TLS change. GitHub Pages'
hosting and HTTPS configuration and the existing repository/site URLs are
unchanged. Local Windows documentation builds are optional, not a CI acceptance
requirement. The full MkDocs site build passed with output directed to an
external temporary directory.

## Acceptance gate

Review the full branch diff, scientific factor sources/boundaries, coal schema,
environment and output contracts. Repeat the isolated producer/export checks
after resolving those decisions. Do not merge to `main`, mark outputs as final,
or bypass missing physical CO2 to make the workflow appear accepted.
