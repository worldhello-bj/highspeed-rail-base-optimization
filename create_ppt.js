const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "胡鹏禹";
pres.title = "高铁快运基地选址与规模多维协同优化";

// === Color Palette: 高铁蓝 ===
const C = {
  dark:   "1B3A5C",
  mid:    "2E86C1",
  light:  "D4E6F1",
  accent: "E74C3C",
  white:  "FFFFFF",
  text:   "2C3E50",
  gray:   "7F8C8D",
  green:  "27AE60",
  orange: "F39C12",
};
const FONT = "Microsoft YaHei";

// ============================================================
// Slide 1: 封面
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.dark };
  // top accent bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.mid } });
  // left accent line
  s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 1.2, w: 0.06, h: 2.8, fill: { color: C.accent } });
  // title
  s.addText("高铁快运基地选址与规模\n多维协同优化", {
    x: 1.1, y: 1.3, w: 8, h: 2.0,
    fontSize: 36, fontFace: FONT, color: C.white, bold: true, lineSpacingMultiple: 1.3,
  });
  // subtitle
  s.addText("基于混合整数规划的网络流分配与财务评估", {
    x: 1.1, y: 3.3, w: 8, h: 0.6,
    fontSize: 16, fontFace: FONT, color: C.mid,
  });
  // bottom bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.7, w: 10, h: 0.92, fill: { color: C.mid, transparency: 30 } });
  s.addText("汇报人：胡鹏禹  |  2026年6月  |  现代交通运输智能优化实训", {
    x: 0.5, y: 4.75, w: 9, h: 0.8,
    fontSize: 13, fontFace: FONT, color: C.white, align: "center", valign: "middle",
  });
}

// ============================================================
// Slide 2: 项目背景
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  // top bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.mid } });
  // section number
  s.addText("01", { x: 0.5, y: 0.25, w: 0.8, h: 0.5, fontSize: 28, fontFace: FONT, color: C.mid, bold: true });
  s.addText("项目背景与问题定义", {
    x: 1.2, y: 0.25, w: 6, h: 0.5, fontSize: 24, fontFace: FONT, color: C.dark, bold: true,
  });
  s.addShape(pres.shapes.LINE, { x: 0.5, y: 0.8, w: 9, h: 0, line: { color: C.light, width: 1.5 } });

  // Key stats - 2x2 grid
  const stats = [
    { num: "34", label: "高铁车站", sub: "44条双向区间" },
    { num: "12", label: "候选基地", sub: "4种规模层级可选" },
    { num: "190", label: "OD 需求对", sub: "1908.4 吨/日总需求" },
    { num: "3", label: "运输模式", sub: "货动/捎带/中转" },
  ];
  stats.forEach((st, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.5 + col * 4.7;
    const y = 1.1 + row * 1.6;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.3, h: 1.3,
      fill: { color: C.light, transparency: 50 },
      rectRadius: 0.05,  // using RECTANGLE here
    });
    // I'll use ROUNDED_RECTANGLE
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y, w: 4.3, h: 1.3,
      fill: { color: C.white },
      rectRadius: 0.1,
      shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.08 },
    });
    s.addText(st.num, {
      x: x + 0.3, y: y + 0.1, w: 1.2, h: 0.75,
      fontSize: 36, fontFace: FONT, color: C.mid, bold: true, valign: "middle",
    });
    s.addText(st.label, {
      x: x + 1.5, y: y + 0.15, w: 2.5, h: 0.5,
      fontSize: 16, fontFace: FONT, color: C.dark, bold: true, valign: "bottom",
    });
    s.addText(st.sub, {
      x: x + 1.5, y: y + 0.6, w: 2.5, h: 0.5,
      fontSize: 12, fontFace: FONT, color: C.gray, valign: "top",
    });
  });

  // bottom callout
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 4.5, w: 9, h: 0.75,
    fill: { color: C.accent, transparency: 10 },
  });
  s.addText("🎯 核心问题：在12个候选站点中，选择哪些建基地？选多大？如何分配货流？→ 最大化日均净利润", {
    x: 0.8, y: 4.5, w: 8.4, h: 0.75,
    fontSize: 14, fontFace: FONT, color: C.accent, bold: true, valign: "middle",
  });
}

// ============================================================
// Slide 3: 技术路线
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.mid } });
  s.addText("02", { x: 0.5, y: 0.25, w: 0.8, h: 0.5, fontSize: 28, fontFace: FONT, color: C.mid, bold: true });
  s.addText("技术路线：多阶段协同递进规划", {
    x: 1.2, y: 0.25, w: 7, h: 0.5, fontSize: 24, fontFace: FONT, color: C.dark, bold: true,
  });
  s.addShape(pres.shapes.LINE, { x: 0.5, y: 0.8, w: 9, h: 0, line: { color: C.light, width: 1.5 } });

  // 6 stages as numbered cards
  const stages = [
    { no: "1", title: "最短路计算", desc: "Dijkstra 算法\n34站点190个OD", color: C.mid },
    { no: "2", title: "MCMF 分配", desc: "能力约束下\n费用最小化", color: "2980B9" },
    { no: "3", title: "MIP 选址", desc: "0-1整数规划\n48个二值变量", color: "8E44AD" },
    { no: "4", title: "路径拆解", desc: "贪心算法\n还原班列方案", color: C.orange },
    { no: "5", title: "财务评估", desc: "20年NPV/IRR\n盈亏平衡分析", color: C.green },
    { no: "6", title: "竞争分析", desc: "高铁vs航空vs公路\n成本-距离对比", color: C.accent },
  ];

  stages.forEach((st, i) => {
    const x = 0.3 + i * 1.6;
    const y = 1.2;
    // card bg
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y, w: 1.35, h: 3.5,
      fill: { color: C.white },
      rectRadius: 0.1,
      shadow: { type: "outer", color: "000000", blur: 5, offset: 2, angle: 135, opacity: 0.1 },
    });
    // top colored bar
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 1.35, h: 0.06, fill: { color: st.color } });
    // number circle
    s.addShape(pres.shapes.OVAL, {
      x: x + 0.35, y: y + 0.3, w: 0.65, h: 0.65,
      fill: { color: st.color },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 1.5, angle: 135, opacity: 0.2 },
    });
    s.addText(st.no, {
      x: x + 0.35, y: y + 0.3, w: 0.65, h: 0.65,
      fontSize: 22, fontFace: FONT, color: C.white, bold: true, align: "center", valign: "middle",
    });
    // title
    s.addText(st.title, {
      x: x + 0.05, y: y + 1.15, w: 1.25, h: 0.5,
      fontSize: 14, fontFace: FONT, color: C.dark, bold: true, align: "center",
    });
    // desc
    s.addText(st.desc, {
      x: x + 0.05, y: y + 1.65, w: 1.25, h: 1.2,
      fontSize: 10, fontFace: FONT, color: C.gray, align: "center", lineSpacingMultiple: 1.4,
    });
    // arrow between cards (except last)
    if (i < 5) {
      s.addText("▸", {
        x: x + 1.35, y: y + 1.5, w: 0.25, h: 0.4,
        fontSize: 18, fontFace: FONT, color: C.light, align: "center", valign: "middle",
      });
    }
  });

  // bottom note
  s.addText("工具链：Python 3.10 + NetworkX + Gurobi 12.0 + Matplotlib  |  求解时间：~1.58秒（至1% gap）", {
    x: 0.5, y: 5.1, w: 9, h: 0.4,
    fontSize: 10, fontFace: FONT, color: C.gray, align: "center",
  });
}

// ============================================================
// Slide 4: 核心模型 MIP
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.mid } });
  s.addText("03", { x: 0.5, y: 0.25, w: 0.8, h: 0.5, fontSize: 28, fontFace: FONT, color: C.mid, bold: true });
  s.addText("核心模型：0-1混合整数规划 (MIP)", {
    x: 1.2, y: 0.25, w: 7, h: 0.5, fontSize: 24, fontFace: FONT, color: C.dark, bold: true,
  });
  s.addShape(pres.shapes.LINE, { x: 0.5, y: 0.8, w: 9, h: 0, line: { color: C.light, width: 1.5 } });

  // Left: model summary
  const modelBox = [
    { text: "决策变量", options: { bold: true, fontSize: 15, color: C.dark, breakLine: true } },
    { text: "  z_{i,s} ∈ {0,1} : 站点 i 建规模 s 基地", options: { fontSize: 11, breakLine: true, color: C.text } },
    { text: "  sat_k ≥ 0    : OD k 满足的货流量", options: { fontSize: 11, breakLine: true, color: C.text } },
    { text: "  x_{uv}^k ≥ 0  : 货运动车组弧流量", options: { fontSize: 11, breakLine: true, color: C.text } },
    { text: "  y_{ij}^k ≥ 0  : 捎带直通流量", options: { fontSize: 11, breakLine: true, color: C.text } },
    { text: "", options: { fontSize: 6, breakLine: true } },
    { text: "目标函数", options: { bold: true, fontSize: 15, color: C.dark, breakLine: true } },
    { text: "  max 运输收入 − 固定折旧 − 运营成本", options: { fontSize: 11, breakLine: true, color: C.text } },
    { text: "", options: { fontSize: 6, breakLine: true } },
    { text: "关键约束", options: { bold: true, fontSize: 15, color: C.dark, breakLine: true } },
    { text: "  • 每候选点最多选 1 种规模", options: { fontSize: 11, breakLine: true, color: C.text } },
    { text: "  • 非基地站禁止货动装卸和中转", options: { fontSize: 11, breakLine: true, color: C.text } },
    { text: "  • 基地处理能力 ≤ 规模上限", options: { fontSize: 11, breakLine: true, color: C.text } },
    { text: "  • 区间通过能力 ≤ 680 t/d", options: { fontSize: 11, breakLine: true, color: C.text } },
  ];
  s.addText(modelBox, {
    x: 0.5, y: 1.0, w: 5.5, h: 4.4,
    fontFace: FONT, valign: "top", lineSpacingMultiple: 1.5,
  });

  // Right: scale comparison
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 6.3, y: 1.0, w: 3.4, h: 4.4,
    fill: { color: C.light, transparency: 60 },
    rectRadius: 0.1,
  });
  s.addText("规模参数对比", {
    x: 6.5, y: 1.1, w: 3.0, h: 0.4,
    fontSize: 14, fontFace: FONT, color: C.dark, bold: true,
  });

  const scales = [
    { name: "改建小规模", cost: "0.77亿", cap: "1列/日", color: C.green },
    { name: "新建小规模", cost: "5.76亿", cap: "4列/日", color: C.orange },
    { name: "新建中规模", cost: "7.68亿", cap: "8列/日", color: "E67E22" },
    { name: "新建大规模", cost: "9.60亿", cap: "10列/日", color: C.accent },
  ];
  scales.forEach((sc, i) => {
    const y = 1.7 + i * 0.85;
    s.addShape(pres.shapes.RECTANGLE, { x: 6.6, y, w: 0.08, h: 0.6, fill: { color: sc.color } });
    s.addText(sc.name, { x: 6.85, y, w: 1.5, h: 0.3, fontSize: 11, fontFace: FONT, color: C.dark, bold: true, valign: "middle" });
    s.addText(`投资 ${sc.cost}  |  能力 ${sc.cap}`, {
      x: 6.85, y: y + 0.3, w: 2.7, h: 0.3, fontSize: 9, fontFace: FONT, color: C.gray, valign: "middle",
    });
  });

  // bottom callout
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 5.15, w: 9, h: 0.35, fill: { color: C.light, transparency: 40 } });
  s.addText("规模：262,390 连续变量 + 48 个 0-1 变量  |  33,262 条约束  |  Gurobi 12.0 求解 1.58 秒", {
    x: 0.5, y: 5.15, w: 9, h: 0.35,
    fontSize: 11, fontFace: FONT, color: C.mid, align: "center", valign: "middle",
  });
}

// ============================================================
// Slide 5: 关键结果
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.mid } });
  s.addText("04", { x: 0.5, y: 0.25, w: 0.8, h: 0.5, fontSize: 28, fontFace: FONT, color: C.mid, bold: true });
  s.addText("关键发现：反直觉的最优解", {
    x: 1.2, y: 0.25, w: 7, h: 0.5, fontSize: 24, fontFace: FONT, color: C.dark, bold: true,
  });
  s.addShape(pres.shapes.LINE, { x: 0.5, y: 0.8, w: 9, h: 0, line: { color: C.light, width: 1.5 } });

  // big stat callout
  s.addText("39.7%", {
    x: 0.5, y: 1.1, w: 3.5, h: 1.2,
    fontSize: 60, fontFace: FONT, color: C.accent, bold: true, align: "center", valign: "middle",
  });
  s.addText("只满足 39.7% 的需求\n反而利润最大！", {
    x: 0.5, y: 2.3, w: 3.5, h: 0.8,
    fontSize: 14, fontFace: FONT, color: C.dark, align: "center", lineSpacingMultiple: 1.4,
  });

  // right side: key numbers
  const nums = [
    { val: "9/12", label: "建设基地", sub: "沪杭宁汉长南渝贵成" },
    { val: "257万", label: "日均净利润 (元)", sub: "年化约 9.39 亿元" },
    { val: "0.768", label: "单基地投资 (亿元)", sub: "全部选择改建小规模" },
  ];
  nums.forEach((n, i) => {
    const y = 1.1 + i * 1.35;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 4.3, y, w: 5.4, h: 1.1,
      fill: { color: C.white },
      rectRadius: 0.08,
      shadow: { type: "outer", color: "000000", blur: 4, offset: 1.5, angle: 135, opacity: 0.06 },
    });
    s.addText(n.val, {
      x: 4.5, y, w: 1.8, h: 1.1,
      fontSize: 28, fontFace: FONT, color: C.mid, bold: true, align: "center", valign: "middle",
    });
    s.addText(n.label, {
      x: 6.3, y: y + 0.05, w: 3.2, h: 0.5,
      fontSize: 14, fontFace: FONT, color: C.dark, bold: true, valign: "bottom",
    });
    s.addText(n.sub, {
      x: 6.3, y: y + 0.55, w: 3.2, h: 0.45,
      fontSize: 10, fontFace: FONT, color: C.gray, valign: "top",
    });
  });

  // bottom insight box
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.5, y: 4.55, w: 9, h: 0.9,
    fill: { color: C.light, transparency: 50 },
    rectRadius: 0.08,
  });
  s.addText([
    { text: "💡 核心洞察：", options: { bold: true, fontSize: 13, color: C.dark } },
    { text: "改建小规模→新建小规模，投资飙升7.5倍（0.77→5.76亿），日均固定成本增100倍（0.1→11万），但吞吐能力仅增4倍。Gurobi 做出理性决策：放弃微利长尾订单，以最小轻资产揽收黄金干线货流。", options: { fontSize: 11, color: C.text } },
  ], {
    x: 0.8, y: 4.55, w: 8.4, h: 0.9,
    fontFace: FONT, valign: "middle", lineSpacingMultiple: 1.3,
  });
}

// ============================================================
// Slide 6: 财务+竞争
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.mid } });
  s.addText("05", { x: 0.5, y: 0.25, w: 0.8, h: 0.5, fontSize: 28, fontFace: FONT, color: C.mid, bold: true });
  s.addText("财务评估 & 市场竞争分析", {
    x: 1.2, y: 0.25, w: 7, h: 0.5, fontSize: 24, fontFace: FONT, color: C.dark, bold: true,
  });
  s.addShape(pres.shapes.LINE, { x: 0.5, y: 0.8, w: 9, h: 0, line: { color: C.light, width: 1.5 } });

  // Left: financial metrics
  s.addText("💰 20年财务评估", {
    x: 0.5, y: 1.0, w: 4.5, h: 0.4,
    fontSize: 15, fontFace: FONT, color: C.dark, bold: true,
  });
  const finMetrics = [
    { label: "总投资", val: "6.91 亿元" },
    { label: "NPV (5%)", val: "110.0 亿元" },
    { label: "IRR", val: "135.8%" },
    { label: "回收期", val: "8.8 个月" },
    { label: "盈亏平衡货量", val: "28 吨/日 (1.5%)" },
  ];
  finMetrics.forEach((m, i) => {
    const y = 1.5 + i * 0.65;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 4.5, h: 0.5, fill: { color: i % 2 === 0 ? C.light : C.white, transparency: i % 2 === 0 ? 60 : 0 } });
    s.addText(m.label, { x: 0.7, y, w: 2.0, h: 0.5, fontSize: 12, fontFace: FONT, color: C.text, valign: "middle" });
    s.addText(m.val, { x: 2.7, y, w: 2.1, h: 0.5, fontSize: 12, fontFace: FONT, color: C.dark, bold: true, valign: "middle", align: "right" });
  });

  // Right: competition
  s.addText("🌐 多式联运竞争分析", {
    x: 5.3, y: 1.0, w: 4.5, h: 0.4,
    fontSize: 15, fontFace: FONT, color: C.dark, bold: true,
  });

  // mini competition table
  const compHeader = [
    { text: "模式", options: { bold: true, color: C.dark, fontSize: 10 } },
    { text: "    速度", options: { bold: true, color: C.dark, fontSize: 10 } },
    { text: "    成本", options: { bold: true, color: C.dark, fontSize: 10 } },
    { text: "    准点", options: { bold: true, color: C.dark, fontSize: 10 } },
  ];
  s.addText(compHeader, { x: 5.4, y: 1.5, w: 4.2, h: 0.35, fontFace: FONT, align: "center" });

  const compData = [
    { mode: "🚄 高铁快运", speed: "250km/h", cost: "中", punct: "99%", color: C.accent },
    { mode: "✈️ 航空货运", speed: "800km/h", cost: "高", punct: "75%", color: C.mid },
    { mode: "🚛 公路卡车", speed: "80km/h",  cost: "低", punct: "85%", color: C.green },
  ];
  compData.forEach((cd, i) => {
    const y = 1.9 + i * 0.55;
    s.addText([
      { text: cd.mode + "  ", options: { fontSize: 11, bold: true, color: cd.color } },
      { text: cd.speed + "  ", options: { fontSize: 10, color: C.text } },
      { text: cd.cost + "  ", options: { fontSize: 10, color: C.text } },
      { text: cd.punct, options: { fontSize: 10, color: C.text } },
    ], { x: 5.4, y, w: 4.2, h: 0.45, fontFace: FONT, valign: "middle", align: "center" });
  });

  // competitive insight
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.3, y: 3.7, w: 4.4, h: 1.0,
    fill: { color: C.light, transparency: 50 },
    rectRadius: 0.08,
  });
  s.addText("🏆 高铁快运在 500-1500km 拥有\n\"速度+成本+准点\"综合最优", {
    x: 5.5, y: 3.8, w: 4.0, h: 0.8,
    fontSize: 11, fontFace: FONT, color: C.dark, align: "center", valign: "middle", lineSpacingMultiple: 1.4,
  });

  // Bottom: sensitivity
  s.addText("🛡️ 敏感性：即使需求下降40%，年利润仍达5.49亿元；运价下调20%，年利润6.79亿元仍盈利。项目抗风险能力极强。", {
    x: 0.5, y: 5.0, w: 9, h: 0.45,
    fontSize: 11, fontFace: FONT, color: C.green, align: "center", valign: "middle",
    bold: true,
  });
}

// ============================================================
// Slide 7: 总结与展望
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.dark };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 1.0, w: 0.06, h: 2.0, fill: { color: C.accent } });

  s.addText("总结与展望", {
    x: 1.1, y: 1.0, w: 8, h: 0.7,
    fontSize: 30, fontFace: FONT, color: C.white, bold: true,
  });

  // key takeaways
  const takeaways = [
    "✅ 路网能力充足（最大负荷78.7%），瓶颈在基地而非线路",
    "✅ 最优方案：9 个改建小规模基地，日均净利润 257 万元",
    "✅ 选址选择 = 轻资产博弈：放弃微利长尾，聚焦黄金干线",
    "✅ 财务指标优秀：IRR 135.8%，8.8 个月回本，抗风险能力强",
    "✅ 高铁快运在 500-1500km 时效带具备综合竞争优势",
  ];
  takeaways.forEach((t, i) => {
    s.addText(t, {
      x: 1.1, y: 2.0 + i * 0.48, w: 8, h: 0.4,
      fontSize: 13, fontFace: FONT, color: C.light, valign: "middle",
    });
  });

  // future work
  s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 4.4, w: 8.6, h: 0.04, fill: { color: C.mid, transparency: 50 } });
  s.addText("下一步方向", {
    x: 1.1, y: 4.55, w: 8, h: 0.4,
    fontSize: 14, fontFace: FONT, color: C.mid, bold: true,
  });
  s.addText("门到门物流同盟构建  |  标准化集装单元研发  |  冷链等高附加值市场拓展  |  动态需求下的鲁棒优化", {
    x: 1.1, y: 4.9, w: 8, h: 0.4,
    fontSize: 11, fontFace: FONT, color: C.gray,
  });

  // thank you
  s.addText("谢谢！欢迎提问", {
    x: 0.5, y: 5.3, w: 9, h: 0.35,
    fontSize: 14, fontFace: FONT, color: C.white, align: "center", valign: "middle",
  });
}

// ============================================================
// Save
// ============================================================
pres.writeFile({ fileName: "d:/高铁快运/进度汇报_高铁快运基地优化.pptx" })
  .then(() => console.log("✅ PPT 生成成功！"))
  .catch(err => console.error("❌ 生成失败:", err));
