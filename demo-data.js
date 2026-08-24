/**
 * METROLOGIC - Demo Data & Offline Fixture Generator
 * Standalone demo mode support with generated SVG package images & 3 inspection scenarios
 */

// Helper to generate SVG package panel data URLs
function createPackageSvg(title, panelType, declarations, noisy = false, doubleMrp = false) {
  const width = 800;
  const height = 1000;
  
  let content = '';

  if (panelType === 'front') {
    content = `
      <rect x="50" y="50" width="700" height="900" rx="30" fill="#2563eb" stroke="#1d4ed8" stroke-width="8"/>
      <circle cx="400" cy="350" r="160" fill="#ffffff" opacity="0.95"/>
      <text x="400" y="340" font-family="sans-serif" font-size="42" font-weight="bold" fill="#1e3a8a" text-anchor="middle">BrightWash</text>
      <text x="400" y="390" font-family="sans-serif" font-size="28" font-weight="600" fill="#2563eb" text-anchor="middle">ULTRA CLEAN</text>
      
      <rect x="250" y="650" width="300" height="70" rx="10" fill="#fbbf24"/>
      <text x="400" y="695" font-family="sans-serif" font-size="32" font-weight="bold" fill="#78350f" text-anchor="middle">LAUNDRY DETERGENT</text>

      <rect x="280" y="780" width="240" height="50" rx="8" fill="#ffffff"/>
      <text x="400" y="813" font-family="sans-serif" font-size="24" font-weight="bold" fill="#0f172a" text-anchor="middle">NET QTY: 1 kg</text>
    `;
  } else if (panelType === 'back') {
    let mrpText = 'M.R.P ₹249.00 (Incl. of all taxes)';
    let mrpFill = '#0f172a';
    if (noisy) {
      mrpText = 'M.R.P R$120'; // noisy / uncertain
      mrpFill = '#475569';
    }

    content = `
      <rect x="50" y="50" width="700" height="900" rx="16" fill="#f8fafc" stroke="#94a3b8" stroke-width="6"/>
      <rect x="90" y="80" width="620" height="60" rx="6" fill="#0f172a"/>
      <text x="400" y="120" font-family="sans-serif" font-size="24" font-weight="bold" fill="#ffffff" text-anchor="middle">PRODUCT STATUTORY DECLARATIONS</text>

      <!-- Declaration Block 1: Commodity -->
      <rect x="100" y="180" width="600" height="70" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>
      <text x="120" y="222" font-family="sans-serif" font-size="20" font-weight="bold" fill="#0f172a">Commodity: Laundry Detergent Powder</text>

      <!-- Declaration Block 2: Net Quantity -->
      <rect x="100" y="270" width="600" height="70" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>
      <text x="120" y="312" font-family="sans-serif" font-size="20" font-weight="bold" fill="#0f172a">Net Quantity: 1 kg (1000 g)</text>

      <!-- Declaration Block 3: MRP -->
      <rect x="100" y="360" width="600" height="80" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>
      <text x="120" y="408" font-family="sans-serif" font-size="22" font-weight="bold" fill="${mrpFill}">${mrpText}</text>

      ${doubleMrp ? `
        <!-- Conflicting MRP Overlay Sticker -->
        <rect x="420" y="380" width="260" height="50" rx="4" fill="#fef08a" stroke="#ca8a04" stroke-width="2"/>
        <text x="550" y="413" font-family="sans-serif" font-size="20" font-weight="bold" fill="#854d0e" text-anchor="middle">MRP ₹150.00</text>
      ` : ''}

      <!-- Declaration Block 4: Manufacturing Date -->
      <rect x="100" y="460" width="600" height="70" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>
      <text x="120" y="502" font-family="sans-serif" font-size="20" font-weight="bold" fill="#0f172a">Mfg Date: 01/2026</text>

      <!-- Declaration Block 5: Manufacturer Details -->
      <rect x="100" y="550" width="600" height="110" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>
      <text x="120" y="590" font-family="sans-serif" font-size="18" font-weight="bold" fill="#0f172a">Mfd & Pkd by: Apex Consumer Goods Pvt Ltd</text>
      <text x="120" y="620" font-family="sans-serif" font-size="16" fill="#475569">Plot 42, Industrial Area, Phase II, Mumbai - 400001</text>
      
      <!-- Consumer Care -->
      <rect x="100" y="680" width="600" height="80" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>
      <text x="120" y="715" font-family="sans-serif" font-size="16" font-weight="bold" fill="#0f172a">Consumer Care Cell: 1800-111-2222</text>
      <text x="120" y="740" font-family="sans-serif" font-size="14" fill="#475569">Email: customercare@apexconsumer.com</text>
    `;
  } else {
    // Side Panel
    content = `
      <rect x="50" y="50" width="700" height="900" rx="16" fill="#f1f5f9" stroke="#94a3b8" stroke-width="6"/>
      <text x="400" y="150" font-family="sans-serif" font-size="28" font-weight="bold" fill="#1e293b" text-anchor="middle">USAGE INSTRUCTIONS</text>
      <line x1="100" y1="180" x2="700" y2="180" stroke="#cbd5e1" stroke-width="3"/>
      
      <text x="120" y="240" font-family="sans-serif" font-size="20" fill="#334155">1. Add 1 scoop (60g) to 10L water.</text>
      <text x="120" y="300" font-family="sans-serif" font-size="20" fill="#334155">2. Soak clothes for 30 minutes.</text>
      <text x="120" y="360" font-family="sans-serif" font-size="20" fill="#334155">3. Wash & rinse thoroughly.</text>

      <rect x="200" y="600" width="400" height="180" fill="#ffffff" stroke="#0f172a" stroke-width="3"/>
      <text x="400" y="700" font-family="sans-serif" font-size="32" font-weight="bold" fill="#0f172a" text-anchor="middle">BARCODE 8901234567890</text>
    `;
  }

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">
    ${content}
  </svg>`;

  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}

// Pre-built Demo Data Scenarios
export const DEMO_SCENARIOS = {
  scenario1: {
    sessionId: "ML-2026-00124",
    product: "Laundry Detergent (BrightWash 1kg)",
    status: "PASS",
    processingTime: "1.6s",
    images: {
      front: {
        url: createPackageSvg("Laundry Detergent", "front", []),
        name: "front_panel.jpg",
        size: "1.2 MB",
        dimensions: "800 x 1000"
      },
      back: {
        url: createPackageSvg("Laundry Detergent", "back", []),
        name: "back_panel.jpg",
        size: "1.4 MB",
        dimensions: "800 x 1000"
      },
      side: {
        url: createPackageSvg("Laundry Detergent", "side", []),
        name: "side_panel.jpg",
        size: "0.9 MB",
        dimensions: "800 x 1000"
      }
    },
    rules: [
      {
        id: "mrp_declaration",
        name: "MRP Declaration",
        status: "PASS",
        requirement: "Maximum Retail Price (MRP) must be clearly printed inclusive of all taxes.",
        reason: "Evidence verified on Back Panel. Legible MRP declaration detected.",
        confidence: 0.96,
        panel: "back",
        box: [100, 360, 600, 80], // [x, y, w, h] in SVG coordinates
        evidenceId: "img_back:block_mrp",
        extractedValue: "₹249.00 (Incl. of all taxes)",
        rawOcr: "M.R.P ₹249.00 (Incl. of all taxes)"
      },
      {
        id: "net_quantity",
        name: "Net Quantity",
        status: "PASS",
        requirement: "Net quantity declaration in standard SI metric units (g, kg, ml, l).",
        reason: "Evidence verified on Front and Back panels.",
        confidence: 0.98,
        panel: "back",
        box: [100, 270, 600, 70],
        evidenceId: "img_back:block_net_qty",
        extractedValue: "1 kg (1000 g)",
        rawOcr: "Net Quantity: 1 kg (1000 g)"
      },
      {
        id: "commodity_name",
        name: "Commodity Name",
        status: "PASS",
        requirement: "Generic or common name of the commodity must be prominently declared.",
        reason: "Evidence verified on Front and Back panels.",
        confidence: 0.95,
        panel: "back",
        box: [100, 180, 600, 70],
        evidenceId: "img_back:block_commodity",
        extractedValue: "Laundry Detergent Powder",
        rawOcr: "Commodity: Laundry Detergent Powder"
      },
      {
        id: "mfg_date",
        name: "Manufacturing Date",
        status: "PASS",
        requirement: "Month and Year of manufacture or packing must be declared.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.94,
        panel: "back",
        box: [100, 460, 600, 70],
        evidenceId: "img_back:block_mfg_date",
        extractedValue: "01/2026",
        rawOcr: "Mfg Date: 01/2026"
      },
      {
        id: "manufacturer_details",
        name: "Manufacturer Details",
        status: "PASS",
        requirement: "Name and complete address of the manufacturer or packer.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.97,
        panel: "back",
        box: [100, 550, 600, 110],
        evidenceId: "img_back:block_mfd",
        extractedValue: "Apex Consumer Goods Pvt Ltd, Mumbai - 400001",
        rawOcr: "Mfd & Pkd by: Apex Consumer Goods Pvt Ltd, Mumbai - 400001"
      }
    ]
  },

  scenario2: {
    sessionId: "ML-2026-00123",
    product: "Household Cleaner (CleanCare)",
    status: "REVIEW_REQUIRED",
    processingTime: "1.8s",
    images: {
      front: {
        url: createPackageSvg("Household Cleaner", "front", []),
        name: "front_panel.jpg",
        size: "1.1 MB",
        dimensions: "800 x 1000"
      },
      back: {
        url: createPackageSvg("Household Cleaner", "back", [], true), // noisy MRP
        name: "back_panel.jpg",
        size: "1.3 MB",
        dimensions: "800 x 1000"
      },
      side: {
        url: createPackageSvg("Household Cleaner", "side", []),
        name: "side_panel.jpg",
        size: "0.8 MB",
        dimensions: "800 x 1000"
      }
    },
    rules: [
      {
        id: "mrp_declaration",
        name: "MRP Declaration",
        status: "REVIEW_REQUIRED",
        requirement: "Maximum Retail Price (MRP) must be clearly printed inclusive of all taxes.",
        reason: "Low-confidence MRP extraction (63%). Symbol smudged or non-standard prefix ('R$120'). Officer verification required.",
        confidence: 0.63,
        panel: "back",
        box: [100, 360, 600, 80],
        evidenceId: "img_back:block_mrp_uncertain",
        extractedValue: "₹120 (Uncertain)",
        rawOcr: "M.R.P R$120"
      },
      {
        id: "net_quantity",
        name: "Net Quantity",
        status: "PASS",
        requirement: "Net quantity declaration in standard SI metric units (g, kg, ml, l).",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.97,
        panel: "back",
        box: [100, 270, 600, 70],
        evidenceId: "img_back:block_net_qty",
        extractedValue: "1 kg",
        rawOcr: "Net Quantity: 1 kg (1000 g)"
      },
      {
        id: "commodity_name",
        name: "Commodity Name",
        status: "PASS",
        requirement: "Generic or common name of the commodity must be declared.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.96,
        panel: "back",
        box: [100, 180, 600, 70],
        evidenceId: "img_back:block_commodity",
        extractedValue: "Laundry Detergent Powder",
        rawOcr: "Commodity: Laundry Detergent Powder"
      },
      {
        id: "mfg_date",
        name: "Manufacturing Date",
        status: "PASS",
        requirement: "Month and Year of manufacture or packing.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.95,
        panel: "back",
        box: [100, 460, 600, 70],
        evidenceId: "img_back:block_mfg_date",
        extractedValue: "01/2026",
        rawOcr: "Mfg Date: 01/2026"
      },
      {
        id: "manufacturer_details",
        name: "Manufacturer Details",
        status: "PASS",
        requirement: "Name and address of manufacturer.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.98,
        panel: "back",
        box: [100, 550, 600, 110],
        evidenceId: "img_back:block_mfd",
        extractedValue: "Apex Consumer Goods Pvt Ltd",
        rawOcr: "Mfd & Pkd by: Apex Consumer Goods Pvt Ltd, Mumbai - 400001"
      }
    ]
  },

  scenario3: {
    sessionId: "ML-2026-00125",
    product: "Shampoo (SilkShine 500ml)",
    status: "REVIEW_REQUIRED",
    processingTime: "1.9s",
    images: {
      front: {
        url: createPackageSvg("Shampoo", "front", []),
        name: "front_panel.jpg",
        size: "1.0 MB",
        dimensions: "800 x 1000"
      },
      back: {
        url: createPackageSvg("Shampoo", "back", [], false, true), // double MRP
        name: "back_panel.jpg",
        size: "1.5 MB",
        dimensions: "800 x 1000"
      },
      side: {
        url: createPackageSvg("Shampoo", "side", []),
        name: "side_panel.jpg",
        size: "0.8 MB",
        dimensions: "800 x 1000"
      }
    },
    rules: [
      {
        id: "mrp_declaration",
        name: "MRP Declaration",
        status: "REVIEW_REQUIRED",
        requirement: "Maximum Retail Price (MRP) must be single and un-altered.",
        reason: "Conflicting MRP candidates detected on Back Panel ('₹249.00' vs sticker '₹150.00'). Intra-image conflict resolution required.",
        confidence: 0.58,
        panel: "back",
        box: [100, 360, 600, 80],
        evidenceId: "img_back:block_mrp_conflict",
        extractedValue: "₹249.00 vs ₹150.00",
        rawOcr: "M.R.P ₹249.00 [Sticker: MRP ₹150.00]"
      },
      {
        id: "net_quantity",
        name: "Net Quantity",
        status: "PASS",
        requirement: "Net quantity declaration in standard SI metric units.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.98,
        panel: "back",
        box: [100, 270, 600, 70],
        evidenceId: "img_back:block_net_qty",
        extractedValue: "1 kg",
        rawOcr: "Net Quantity: 1 kg (1000 g)"
      },
      {
        id: "commodity_name",
        name: "Commodity Name",
        status: "PASS",
        requirement: "Generic or common name of commodity.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.96,
        panel: "back",
        box: [100, 180, 600, 70],
        evidenceId: "img_back:block_commodity",
        extractedValue: "Laundry Detergent Powder",
        rawOcr: "Commodity: Laundry Detergent Powder"
      },
      {
        id: "mfg_date",
        name: "Manufacturing Date",
        status: "PASS",
        requirement: "Month and Year of manufacture.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.97,
        panel: "back",
        box: [100, 460, 600, 70],
        evidenceId: "img_back:block_mfg_date",
        extractedValue: "01/2026",
        rawOcr: "Mfg Date: 01/2026"
      },
      {
        id: "manufacturer_details",
        name: "Manufacturer Details",
        status: "PASS",
        requirement: "Name and address of manufacturer.",
        reason: "Evidence verified on Back Panel.",
        confidence: 0.97,
        panel: "back",
        box: [100, 550, 600, 110],
        evidenceId: "img_back:block_mfd",
        extractedValue: "Apex Consumer Goods Pvt Ltd",
        rawOcr: "Mfd & Pkd by: Apex Consumer Goods Pvt Ltd, Mumbai - 400001"
      }
    ]
  }
};

export const DEMO_HISTORY = [
  {
    sessionId: "ML-2026-00124",
    dateTime: "2026-08-23 18:42",
    product: "Laundry Detergent (BrightWash 1kg)",
    status: "PASS",
    processingTime: "1.6s",
    scenarioKey: "scenario1"
  },
  {
    sessionId: "ML-2026-00123",
    dateTime: "2026-08-23 17:15",
    product: "Household Cleaner (CleanCare)",
    status: "REVIEW_REQUIRED",
    processingTime: "1.8s",
    scenarioKey: "scenario2"
  },
  {
    sessionId: "ML-2026-00122",
    dateTime: "2026-08-23 15:30",
    product: "Shampoo (SilkShine 500ml)",
    status: "PASS",
    processingTime: "1.5s",
    scenarioKey: "scenario1"
  }
];
