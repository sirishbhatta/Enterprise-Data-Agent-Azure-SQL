// Multi-Agent BI Platform: 90-Day Pivot
// LinkedIn Carousel Presentation

const PptxGenJS = require('pptxgenjs');
const prs = new PptxGenJS();

prs.defineLayout({ name: 'LAYOUT1', master: 'BLANK' });
prs.defineLayout({ name: 'LAYOUT2', master: 'BLANK' });

// Color Palette
const colors = {
  navy: '0F1419',      // Deep navy
  teal: '00A896',      // Teal accent
  cream: 'F5F5F5',     // Off-white
  white: 'FFFFFF',     // Pure white
  charcoal: '2C3E50',  // Dark text
  lightGray: 'E8E8E8', // Light divider
  gold: 'F9AB00'       // Highlight
};

// Slide dimensions
const w = 10;
const h = 5.625;

// Helper function for title slides
function addTitleSlide(title, subtitle, number) {
  const slide = prs.addSlide();
  
  // Navy background
  slide.background = { color: colors.navy };
  
  // Teal accent bar (left side)
  slide.addShape(prs.ShapeType.rect, {
    x: 0, y: 0, w: 0.15, h: h,
    fill: { color: colors.teal },
    line: { type: 'none' }
  });
  
  // Slide number (top right)
  slide.addText(number, {
    x: 9.2, y: 0.3, w: 0.6, h: 0.4,
    fontSize: 14, bold: true,
    color: colors.teal, align: 'right'
  });
  
  // Title
  slide.addText(title, {
    x: 0.5, y: 1.8, w: 9, h: 1.2,
    fontSize: 44, bold: true,
    color: colors.white,
    align: 'left'
  });
  
  // Subtitle
  slide.addText(subtitle, {
    x: 0.5, y: 3.1, w: 9, h: 1.2,
    fontSize: 20,
    color: colors.cream,
    align: 'left'
  });
}

// Helper function for content slides
function addContentSlide(title, sections, number) {
  const slide = prs.addSlide();
  
  // Light background
  slide.background = { color: colors.white };
  
  // Teal accent bar (left side)
  slide.addShape(prs.ShapeType.rect, {
    x: 0, y: 0, w: 0.15, h: h,
    fill: { color: colors.teal },
    line: { type: 'none' }
  });
  
  // Navy header bar
  slide.addShape(prs.ShapeType.rect, {
    x: 0, y: 0, w: w, h: 0.7,
    fill: { color: colors.navy },
    line: { type: 'none' }
  });
  
  // Title
  slide.addText(title, {
    x: 0.5, y: 0.15, w: 8.5, h: 0.5,
    fontSize: 32, bold: true,
    color: colors.white
  });
  
  // Slide number
  slide.addText(number, {
    x: 9.2, y: 0.2, w: 0.6, h: 0.4,
    fontSize: 14, bold: true,
    color: colors.teal
  });
  
  // Content sections
  let yPos = 1.1;
  sections.forEach((section, idx) => {
    // Colored circle icon
    slide.addShape(prs.ShapeType.ellipse, {
      x: 0.5, y: yPos + 0.05, w: 0.35, h: 0.35,
      fill: { color: section.color || colors.teal },
      line: { type: 'none' }
    });
    
    // Icon number/text inside circle
    slide.addText(String(idx + 1), {
      x: 0.5, y: yPos + 0.05, w: 0.35, h: 0.35,
      fontSize: 14, bold: true,
      color: colors.white,
      align: 'center', valign: 'middle'
    });
    
    // Section title
    slide.addText(section.title, {
      x: 1.1, y: yPos, w: 8.4, h: 0.25,
      fontSize: 14, bold: true,
      color: colors.navy
    });
    
    // Section description
    slide.addText(section.desc, {
      x: 1.1, y: yPos + 0.3, w: 8.4, h: 0.6,
      fontSize: 12,
      color: colors.charcoal
    });
    
    yPos += 1.0;
  });
}

// ═══════════════════════════════════════════════════════════════════
// SLIDE 1: The 90-Day Pivot
// ═══════════════════════════════════════════════════════════════════
addTitleSlide(
  '15 Years of BI.',
  '90 Days of Python. Here is What Changed.',
  '1/5'
);

// ═══════════════════════════════════════════════════════════════════
// SLIDE 2: The Multi-Agent Blueprint
// ═══════════════════════════════════════════════════════════════════
const slide2 = prs.addSlide();
slide2.background = { color: colors.white };

// Accent bar
slide2.addShape(prs.ShapeType.rect, {
  x: 0, y: 0, w: 0.15, h: h,
  fill: { color: colors.teal },
  line: { type: 'none' }
});

// Header
slide2.addShape(prs.ShapeType.rect, {
  x: 0, y: 0, w: w, h: 0.7,
  fill: { color: colors.navy },
  line: { type: 'none' }
});

slide2.addText('The Multi-Agent Blueprint', {
  x: 0.5, y: 0.15, w: 8.5, h: 0.5,
  fontSize: 32, bold: true,
  color: colors.white
});

slide2.addText('2/5', {
  x: 9.2, y: 0.2, w: 0.6, h: 0.4,
  fontSize: 14, bold: true,
  color: colors.teal
});

// Architecture flow (simplified)
// User box
slide2.addShape(prs.ShapeType.roundRect, {
  x: 0.5, y: 1.1, w: 2, h: 0.6,
  fill: { color: colors.teal },
  line: { type: 'none' }
});

slide2.addText('User Question', {
  x: 0.5, y: 1.1, w: 2, h: 0.6,
  fontSize: 12, bold: true,
  color: colors.white,
  align: 'center', valign: 'middle'
});

// Arrow
slide2.addText('→', {
  x: 2.7, y: 1.2, w: 0.3, h: 0.4,
  fontSize: 20, color: colors.navy, align: 'center'
});

// Memory box
slide2.addShape(prs.ShapeType.roundRect, {
  x: 3.1, y: 1.1, w: 2, h: 0.6,
  fill: { color: colors.gold },
  line: { type: 'none' }
});

slide2.addText('Vector Memory', {
  x: 3.1, y: 1.1, w: 2, h: 0.6,
  fontSize: 12, bold: true,
  color: colors.white,
  align: 'center', valign: 'middle'
});

// Arrow
slide2.addText('→', {
  x: 5.3, y: 1.2, w: 0.3, h: 0.4,
  fontSize: 20, color: colors.navy, align: 'center'
});

// Supervisor box
slide2.addShape(prs.ShapeType.roundRect, {
  x: 5.7, y: 1.1, w: 2, h: 0.6,
  fill: { color: colors.charcoal },
  line: { type: 'none' }
});

slide2.addText('Supervisor AI', {
  x: 5.7, y: 1.1, w: 2, h: 0.6,
  fontSize: 12, bold: true,
  color: colors.white,
  align: 'center', valign: 'middle'
});

// Arrow
slide2.addText('→', {
  x: 7.9, y: 1.2, w: 0.3, h: 0.4,
  fontSize: 20, color: colors.navy, align: 'center'
});

// Results box
slide2.addShape(prs.ShapeType.roundRect, {
  x: 8.3, y: 1.1, w: 1.2, h: 0.6,
  fill: { color: colors.teal },
  line: { type: 'none' }
});

slide2.addText('Results', {
  x: 8.3, y: 1.1, w: 1.2, h: 0.6,
  fontSize: 12, bold: true,
  color: colors.white,
  align: 'center', valign: 'middle'
});

// Descriptions below
slide2.addText('What happens', {
  x: 0.5, y: 1.85, w: 9, h: 0.4,
  fontSize: 11, color: colors.charcoal, italic: true
});

slide2.addText('1. Question embedded (768 numbers)\n2. Search past successes (similarity)\n3. Route to correct database\n4. Execute query with memory hints\n5. Return results + AI summary', {
  x: 0.5, y: 2.3, w: 9, h: 2.2,
  fontSize: 11, color: colors.charcoal,
  valign: 'top'
});

// ═══════════════════════════════════════════════════════════════════
// SLIDE 3: The Learning Brain (Vector Memory)
// ═══════════════════════════════════════════════════════════════════
addContentSlide(
  'The Learning Brain: Vector Memory',
  [
    {
      title: 'Week 1: Naive Question',
      desc: 'Can AI generate SQL? Answer: Sometimes, but not reliably.',
      color: '#FF6B6B'
    },
    {
      title: 'Week 4: Memory Added',
      desc: 'Questions embedded (768 numbers). Similar past questions automatically found and reused.',
      color: '#FFA500'
    },
    {
      title: 'Week 12: Self-Improving',
      desc: 'Each thumbs-up strengthens memory. System reuses proven patterns. Never regenerates from scratch.',
      color: colors.teal
    }
  ],
  '3/5'
);

// ═══════════════════════════════════════════════════════════════════
// SLIDE 4: Real-World Value (Federated Queries)
// ═══════════════════════════════════════════════════════════════════
const slide4 = prs.addSlide();
slide4.background = { color: colors.white };

// Accent bar
slide4.addShape(prs.ShapeType.rect, {
  x: 0, y: 0, w: 0.15, h: h,
  fill: { color: colors.teal },
  line: { type: 'none' }
});

// Header
slide4.addShape(prs.ShapeType.rect, {
  x: 0, y: 0, w: w, h: 0.7,
  fill: { color: colors.navy },
  line: { type: 'none' }
});

slide4.addText('Real-World Value: Federated Queries', {
  x: 0.5, y: 0.15, w: 8.5, h: 0.5,
  fontSize: 32, bold: true,
  color: colors.white
});

slide4.addText('4/5', {
  x: 9.2, y: 0.2, w: 0.6, h: 0.4,
  fontSize: 14, bold: true,
  color: colors.teal
});

// Business Question
slide4.addText('The Question:', {
  x: 0.5, y: 0.95, w: 9, h: 0.25,
  fontSize: 13, bold: true,
  color: colors.navy
});

slide4.addText('Which high-earning employees have high insurance claims?', {
  x: 0.5, y: 1.2, w: 9, h: 0.4,
  fontSize: 12, italic: true,
  color: colors.gold
});

// Three databases
const dbY = 1.8;
const dbH = 0.5;

// DB 1: Payroll (PostgreSQL)
slide4.addShape(prs.ShapeType.roundRect, {
  x: 0.5, y: dbY, w: 2.8, h: dbH,
  fill: { color: '#E3F2FD' },
  line: { color: colors.teal, width: 2 }
});

slide4.addText('Payroll\nPostgreSQL', {
  x: 0.5, y: dbY, w: 2.8, h: dbH,
  fontSize: 11, bold: true,
  color: colors.navy,
  align: 'center', valign: 'middle'
});

// DB 2: Claims (SQL Server)
slide4.addShape(prs.ShapeType.roundRect, {
  x: 3.6, y: dbY, w: 2.8, h: dbH,
  fill: { color: '#FCE4EC' },
  line: { color: colors.teal, width: 2 }
});

slide4.addText('Claims\nSQL Server', {
  x: 3.6, y: dbY, w: 2.8, h: dbH,
  fontSize: 11, bold: true,
  color: colors.navy,
  align: 'center', valign: 'middle'
});

// DB 3: Azure Claims
slide4.addShape(prs.ShapeType.roundRect, {
  x: 6.7, y: dbY, w: 2.8, h: dbH,
  fill: { color: '#E0F2F1' },
  line: { color: colors.teal, width: 2 }
});

slide4.addText('Azure Claims\nSQL Server Cloud', {
  x: 6.7, y: dbY, w: 2.8, h: dbH,
  fontSize: 11, bold: true,
  color: colors.navy,
  align: 'center', valign: 'middle'
});

// Merge icon
slide4.addText('↓ ↓ ↓', {
  x: 4, y: 2.5, w: 2, h: 0.3,
  fontSize: 16, color: colors.teal, align: 'center'
});

slide4.addText('Merged Result (Python pandas)', {
  x: 0.5, y: 2.9, w: 9, h: 0.25,
  fontSize: 12, bold: true, italic: true,
  color: colors.navy
});

// Result table
const tableY = 3.3;
slide4.addShape(prs.ShapeType.rect, {
  x: 0.5, y: tableY, w: 9, h: 1.8,
  fill: { color: colors.lightGray },
  line: { color: colors.teal, width: 1 }
});

slide4.addText('Employee | Salary | Total Claims | Risk', {
  x: 0.6, y: tableY + 0.1, w: 8.8, h: 0.25,
  fontSize: 11, bold: true,
  color: colors.navy
});

slide4.addText('Sarah Chen | 180k | 24.5k | Low\nMarcus Johnson | 165k | 98.3k | High\nEmily Zhang | 195k | 12.2k | Low', {
  x: 0.6, y: tableY + 0.4, w: 8.8, h: 1.2,
  fontSize: 10, color: colors.charcoal,
  valign: 'top'
});

// ═══════════════════════════════════════════════════════════════════
// SLIDE 5: Built for Production
// ═══════════════════════════════════════════════════════════════════
addContentSlide(
  'Built for Production',
  [
    {
      title: 'Authentication (OAuth)',
      desc: 'Secure multi-user access via Google. No hardcoded passwords.',
      color: '#FF6B6B'
    },
    {
      title: 'Scheduled Reports',
      desc: 'Save queries. Run daily/weekly/monthly. Export to Excel. Zero manual effort.',
      color: '#4ECDC4'
    },
    {
      title: 'Resilience & Failover',
      desc: '7-tier model cascade: Primary AI fails? Auto-escalate. System never crashes.',
      color: colors.gold
    },
    {
      title: 'Safety Guardrails',
      desc: 'Row limits, audit logs, cost tracking, graceful error handling. Production-ready.',
      color: '#95E1D3'
    }
  ],
  '5/5'
);

// ═══════════════════════════════════════════════════════════════════
// Save presentation
// ═══════════════════════════════════════════════════════════════════
prs.save({ path: '/sessions/zealous-festive-planck/mnt/sirish_ai/LinkedIn_Carousel_RAG.pptx' });

console.log('✅ Presentation created: LinkedIn_Carousel_RAG.pptx');
