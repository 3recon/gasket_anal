# Extraction schema (one CSV row = one example / comparative example in a patent or paper)

CSV, UTF-8, header row exactly as below (column order matters):

source_id,source_type,assignee,title,url,example_label,polymer_type,polymer_grade,cure_system,polymer_phr,carbon_black_phr,silica_phr,alumina_phr,barium_sulfate_phr,titanium_oxide_phr,fluororesin_phr,other_inorganic_filler_phr,organic_additive_phr,coagent_phr,peroxide_phr,nitrile_curative_phr,other_curative_phr,acid_acceptor_phr,processing_aid_phr,other_ingredients_note,hardness_shoreA,tensile_MPa,elongation_pct,m100_MPa,compression_set_pct,cs_condition,plasma_weight_loss_pct,plasma_condition,units_original,extraction_notes

## Column rules
- source_id: e.g. US7678858B2 (exact Google Patents publication number). source_type: patent | paper
- example_label: exactly as in the source, e.g. "Example 3", "Comparative Example 1"
- polymer_type: FFKM (perfluoroelastomer) | FKM (fluoroelastomer, VDF-based) | FEPM (TFE/propylene) | other
- polymer_grade: trade name / description (e.g. "DAI-EL PERFLO GA-105", "TFE/PMVE/CNVE copolymer")
- cure_system: peroxide | nitrile_triazine | nitrile_bisaminophenol | nitrile_bisamidrazone | nitrile_organotin | nitrile_other | bisphenol | polyamine | other
- All *_phr columns: parts by weight per 100 parts of total elastomer (phr). polymer_phr = 100 normally.
  Leave EMPTY (not 0) when the ingredient is not used? -> NO: write 0 when the example clearly does not contain it.
  Only leave empty if the amount is genuinely unknown.
  * carbon_black_phr: any carbon black (MT N990, Ketjen black, thermal black, etc.)
  * silica_phr: SiO2 (fumed / precipitated / fused)
  * alumina_phr: Al2O3
  * barium_sulfate_phr: BaSO4
  * titanium_oxide_phr: TiO2
  * fluororesin_phr: PTFE / PFA / FEP / ETFE micropowder or fluororesin filler
  * other_inorganic_filler_phr: everything inorganic not above (AlF3, CaF2, clay, talc, SiC, Si3N4, YF3, zeolite, ...)
  * organic_additive_phr: organic fillers / pigments / antioxidants / imide fillers / polymer particles (non-fluororesin)
  * coagent_phr: TAIC, TMAIC, bis-olefin, etc. (peroxide coagents)
  * peroxide_phr: organic peroxide (Perhexa 25B, Varox DBPH-50, etc.; record as stated, note if 50% active)
  * nitrile_curative_phr: curatives/catalysts for nitrile cure sites (bisaminophenol, BOAP, bis(aminophenyl), ammonia generators, triazine catalysts, organotin, amidine etc.)
  * other_curative_phr: bisphenol AF, polyol, polyamine, onium accelerator, etc.
  * acid_acceptor_phr: MgO, Ca(OH)2, ZnO, PbO, hydrotalcite
  * processing_aid_phr: waxes, carnauba, release aids, plasticizers
  * other_ingredients_note: short text naming what went into the "other_*" / organic columns, e.g. "AlF3 10; pigment Cromophtal Red 2020 2"
- hardness_shoreA: Shore A / Durometer type A / JIS-A (peak or instantaneous as reported). If the patent only reports IRHD or Shore D, leave empty and mention in extraction_notes.
- tensile_MPa, m100_MPa: MPa. Convert kgf/cm2 x 0.0980665 ; psi x 0.00689476. Round to 2 decimals. Record conversion in units_original.
- elongation_pct: elongation at break (%)
- compression_set_pct + cs_condition: e.g. "200C x 70h, 25% compression, P-24 O-ring". Use the main (normal) value; if several temperatures, pick the one at 200C if available, else the highest/primary one, and list others in extraction_notes.
- plasma_weight_loss_pct + plasma_condition: weight reduction (%) under a plasma; if several plasmas, pick O2 plasma and put others in extraction_notes.
- Only "normal state" (original, not heat-aged) properties go into the property columns.

## Integrity rules (very important)
- Every number must be copied from the source table/text. NEVER estimate, interpolate or invent values.
- If an amount or property is not reported, leave the cell empty.
- Include comparative examples (they are valuable data).
- Keep a row only if at least one of hardness/tensile/elongation/m100/compression_set is reported.
- Quote CSV fields containing commas.
