mastermind_prompt_bank = {
    "netso_product_photography": [
        "Studio product photograph of a commercial solar rooftop installation at a Bangladesh garment factory, framed through a ground-level wide-angle view. Matte navy-blue inverter and cabling system on concrete roof surface, amber safety markings visible. Professional engineering photography, soft sunrise lighting over Chattogram industrial skyline in background, clean technical catalog style, shot from the front-left corner. 1:1 square, ultra detailed, 8k commercial asset.",
        "Professional technical product shot: 80kW commercial solar array installed on a flat industrial rooftop in Bangladesh. Rows of deep-navy framed panels on gray aluminum racking, perspective from slightly elevated ground level. Industrial concrete, soft morning light, shallow depth of field on first panel row. Executive clean energy photography style. 1:1.",
        "Close-up commercial solar product photograph: matte black inverter, combiner box, and DC cabling against polished concrete rooftop. Netso Energy branding implied through navy-amber safety label accents. Three-point synthetic light, elevated 45-degree angle, commercial EPC documentation quality, 1:1.",
    ],
    "netso_hero_banners": [
        "Wide cinematic hero banner for Netso Energy: solar rooftop installation spanning a large Bangladesh garment factory rooftop at golden hour. Chattogram skyline faint in the distance, 80kW system delivering power to the facility below. Deep navy and solar amber accent color grading, professional energy sector photography, 16:9, massive scale, copyspace upper third.",
        "Landing hero image for Netso Energy C&I solar PPA: bright morning light over an RMG factory rooftop with solar panels fully commissioned, first rays hitting glass facets. IDCOL-funded project feel, clean commercial energy aesthetic, deep navy primary, amber secondary, 16:9 banner, lots of negative space for top headline.",
        "Website hero banner: aerial perspective of a 80kW commercial solar installation on a Bangladesh factory rooftop, Chattogram environment. Soft sunrise gradient sky, vast solar array order and scale, professional energy developer photography style. Deep navy brand palette. 16:9, copyspace right side.",
    ],
    "netso_social_carousels": [
        "Instagram carousel slide frame for Netso Energy: bold left-aligned sans-serif headline reading '23% Energy Savings', right side data visualization panel. Deep navy and solar amber Swiss editorial style, huge whitespace, modern corporate design, clean icons, 4:5 portrait.",
        "Social media carousel explaining C&I solar PPA economics: minimalist infographic layout with left headline column and right metric column. Key statistic 'BDT 12.98 vs BDT 10.00 PPA rate'. Deep navy #0B1D2E and amber #F5A623 accents, professional editorial design, clean typography, lots of whitespace, 4:5 portrait.",
        "Instagram carousel slide for Netso Energy: industrial rooftop solar narrative, clean panel composition, copy space purposely left open for overlaid text. Modern Swiss editorial color system, deep navy and amber accents, professional energy company look, 4:5 portrait, high data clarity.",
    ],
    "netso_pitch_deck_slides": [
        "Investor pitch deck slide for Netso Energy: Bangladesh C&I solar market overview. Clean layout with left side large headline, right side market metrics panel showing '80kW → 10MW Year 5 target', '$500K SAFE @ $3M cap', 'DSCR 2.25x'. Deep navy and amber corporate palette, modern infographic style, 16:9 investor presentation.",
        "Pitch deck design, Netso Energy CGS reference project: left half showing Chattogram factory rooftop solar, right half showing project finance metrics table. Executive clean energy brand aesthetic, navy-amber palette, premium investor deck feel, modern corporate layout, 16:9.",
        "Investor deck slide, Netso Energy financial highlights: left text panel 'Levered Equity IRR 68.7% / Payback 4.1 years / DSCR 2.25x', right side solar PPA visual. Opulent pitch materials, navy and amber executive palette, high contrast typography, ample whitespace, 16:9.",
    ],
    "netso_marketing_assets": [
        "LinkedIn ad creative for Netso Energy: Bangladesh factory rooftop solar financing. Professional B2B energy sector tone, headline area top, clean product shot bottom. Deep navy and solar amber accents, copyspace, conversion-focused layout, 1:1 square.",
        "Meta ad creative: Netso Energy C&I solar PPA landing. Bold energy-sector headline space, brand colors dominant, high contrast, commercial solar imagery, clean business aesthetic, conversion-optimized square, 1:1.",
        "Facebook lead ad for Netso Energy: industrial solar PPA offer for Bangladesh factories. Bold headline copy area top, solar product visual bottom half, high-contrast navy and amber palette, clean corporate design, trust factors included, 1:1 square.",
    ],
    "netso_editorial_content": [
        "Editorial photograph for Netso Energy story: early morning at a Bangladesh garment factory rooftop, crew commissioning an 80kW solar system. IDCOL-financed project aesthetic, professional energy journalism tone, Chattogram industrial environment, clean magazine cover style, 16:9.",
        "News editorial image for Netso Energy: Bangladesh C&I solar finance feature. Professional workspace with financial documents, solar panel product shots staged on desk, soft natural light, executive energy developer brand feel, magazine quality, 16:9.",
    ],
    "netso_infographics": [
        "Clean infographic design: Netso Energy CGS project financials. Left: 80kW system summary with key metrics. Right: savings waterfall diagram showing BDT 12.98 → BDT 10.00 → 23% savings. Deep navy and amber accents, data viz excellence, professional energy developer brand, 1:1.",
        "Infographic: Bangladesh C&I solar PPA value chain — from IDCOL financing to factory rooftop commissioning. Clean flowchart layout with icons at each stage. Deep navy #0B1D2E and solar amber #F5A623 palette, Swiss editorial typography, lots of whitespace, 1:1.",
        "Static infographic slide: Netso Energy commercial rooftop solar economics. Three-panel layout showing 80kW reference deal, 23% customer savings, DSCR 2.25x and payback 4.1 years. Modern data viz, navy-amber branding, executive design language, 1:1.",
    ],
}

# Exact Netso Energy ground-truth facts — embed these in prompts for realism and brand accuracy.
netso_facts = {
    "capacity_kw": "80kW",
    "reference_deal": "CGS Chattogram rooftop",
    "annual_generation_kwh": "115,632 kWh/year",
    "ppa_rate_bdt": "BDT 10.00/kWh",
    "true_variable_bdt": "BDT 12.98/kWh",
    "savings_pct": "23.0%",
    "dscr": "2.25x",
    "equity_irr_20yr_pct": "68.7%",
    "project_payback_yrs": "4.1 years",
    "equity_payback_yrs": "1.47 years",
    "capex_baseline_bdt": "BDT 4,400,000",
    "capex_upside_bdt": "BDT 3,200,000",
    "idcol_debt_pct": "80%",
    "idcol_interest_pct": "6.0%",
    "idcol_term_yrs": "10 years",
    "capacity_factor_pct": "16.5%",
    "safe_ask_usd": "$500K",
    "safe_cap_usd": "$3M",
    "tariff_category": "MT-2",
    "annual_consumption_kwh": "118,000 kWh",
    "annual_bill_bdt": "BDT 1,748,056",
    "customer_savings_year1_bdt": "BDT 344,991",
    "color_primary": "deep navy #0B1D2E",
    "color_accent": "solar amber #F5A623",
    "surface": "polished concrete or soft-gray rooftop surface",
    "location": "Chattogram, Bangladesh",
    "sector": "Bangladesh RMG garment manufacturing",
    "brand": "Netso Energy",
}

# Static substitution map — templates above are already hand-built with exact Netso facts.
# Keep this minimal so it stays readable and trustworthy.
static_substitutions = {}
