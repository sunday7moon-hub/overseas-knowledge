# Credit Analysis: XHS Automation Approaches

Reference data for understanding why this skill's approach minimizes Credit.

## Cost Comparison Per Note

| Approach | Research | Writing | Images | Publish | Total Rounds |
|----------|----------|---------|--------|---------|-------------|
| **Expert Agent (全AI)** | 2-3 | 3-5 | 4x multimodal | 5-10 | 15-20+ |
| **OpenClaw + MCP** | 2 (RPA) | 3-5 (LLM) | manual | 2 (MCP) | 5-7 |
| **xiaohongshu-mcp solo** | 1 | N/A | N/A | 2 | 3 |
| **This skill (recommended)** | 0-1 | 1-2 | 0 | 1 | 3-4 |

## Why Multimodal Generation is the Biggest Drain

Each AI-generated image (混元/多模态生图) costs significantly more than one conversation round.
For a typical note with 1 cover + 3-4 supporting images:
- 4 images x high cost = massive Credit consumption
- This alone often equals 10+ conversation rounds

**Alternative: HTML/CSS cover + Pillow info cards = 0 Credit**

## Why Iterative Writing Multiplies Cost

A common anti-pattern:
1. AI writes draft (1 round)
2. User: "make it shorter" (1 round)
3. AI rewrites (1 round)
4. User: "change the tone" (1 round)
5. AI rewrites again (1 round)
...result: 5-8 rounds for one note

**Fix: One-shot comprehensive prompt → ship first output**
