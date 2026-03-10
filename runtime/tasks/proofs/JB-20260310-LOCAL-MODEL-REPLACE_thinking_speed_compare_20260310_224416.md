# JB-20260310-LOCAL-MODEL-REPLACE thinking speed compare (20260310_224416)

## Test conditions
- Prompt: `Analyze the company snapshot. First write exactly 12 numbered findings, each between 18 and 24 English words. Then output one final compact JSON object with keys thesis, positives, risks, action. positives and risks must each contain exactly 3 short strings. Do not use markdown fences. Data: revenue +20%, operating profit -5%, free cash flow -12%, debt ratio +10pp, two new contracts, worse inventory days, capex +8%, mild FX tailwind, flat demand guidance, small insider selling.`
- Server args: `llama-server -m <MODEL> --host 127.0.0.1 --port 8090 -c 12288 -ngl 99 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.5 --top-p 0.9 --top-k 20 --min-p 0.02 --repeat-penalty 1.05 --repeat-last-n 128 --chat-template-kwargs <thinking_json>`
- Each condition run 3 times, temperature=0.0, max_tokens=900
- Approx token speed = completion_tokens / total_latency_sec

## Qwen3.5-35B-A3B-Q4_K_M::current_off
- ready_sec: 4.644
- avg_latency_sec: 13.843
- avg_completion_tokens: 280
- avg_completion_tok_per_sec: 20.227
- min/max_completion_tok_per_sec: 20.073 / 20.383
- avg_text_len: 1583
- stderr_log: `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/JB-20260310-LOCAL-MODEL-REPLACE_Qwen3.5-35B-A3B-Q4_K_M_current_off_20260310_224416.stderr.log`

### run 1
- ok: True
- latency_sec: 13.844
- usage: {"prompt_tokens": 126, "completion_tokens": 280, "total_tokens": 406}
- completion_tok_per_sec: 20.225
- text_preview:
```
1. Revenue growth of twenty percent shows strong top line expansion despite other financial pressures.
2. Operating profit decline of five percent indicates rising costs are eroding core operational margins significantly.
3. Free cash flow dropped twelve percent suggesting tighter liquidity constraints for future strategic investments.
4. Debt ratio increased by ten percentage points reflecting higher leverage and potential solvency concerns.
5. Securing two new contracts provides a positive foundation for future revenue streams and stability.
6. Inventory days worsening signals potential inefficiencies in supply chain management or demand forecasting issues.
7. Capital expenditure rose eight percent showing management commitment to long term asset development plans.
8. Mild foreign exchange tailwind offered some temporary relief against broader currency headwinds this period.
9. Flat demand guidance suggests management expects stable but not accelerating market conditions ahead.
10. Small insider selling activity might signal caution among executives regarding near term stock performance.
11. The combination of rising debt and falling cash flow creates notable financial risk expos
```

### run 2
- ok: True
- latency_sec: 13.737
- usage: {"prompt_tokens": 126, "completion_tokens": 280, "total_tokens": 406}
- completion_tok_per_sec: 20.383
- text_preview:
```
1. Revenue growth of twenty percent shows strong top line expansion despite other financial pressures.
2. Operating profit decline of five percent indicates rising costs are eroding core operational margins significantly.
3. Free cash flow dropped twelve percent suggesting tighter liquidity constraints for future strategic investments.
4. Debt ratio increased by ten percentage points reflecting higher leverage and potential solvency concerns.
5. Securing two new contracts provides a positive foundation for future revenue streams and stability.
6. Inventory days worsening signals potential inefficiencies in supply chain management or demand forecasting issues.
7. Capital expenditure rose eight percent showing management commitment to long term asset development plans.
8. Mild foreign exchange tailwind offered some temporary relief against broader currency headwinds this period.
9. Flat demand guidance suggests management expects stable but not accelerating market conditions ahead.
10. Small insider selling activity might signal caution among executives regarding near term stock performance.
11. The combination of rising debt and falling cash flow creates notable financial risk expos
```

### run 3
- ok: True
- latency_sec: 13.949
- usage: {"prompt_tokens": 126, "completion_tokens": 280, "total_tokens": 406}
- completion_tok_per_sec: 20.073
- text_preview:
```
1. Revenue growth of twenty percent shows strong top line expansion despite other financial pressures.
2. Operating profit decline of five percent indicates rising costs are eroding core operational margins significantly.
3. Free cash flow dropped twelve percent suggesting tighter liquidity constraints for future strategic investments.
4. Debt ratio increased by ten percentage points reflecting higher leverage and potential solvency concerns.
5. Securing two new contracts provides a positive foundation for future revenue streams and stability.
6. Inventory days worsening signals potential inefficiencies in supply chain management or demand forecasting issues.
7. Capital expenditure rose eight percent showing management commitment to long term asset development plans.
8. Mild foreign exchange tailwind offered some temporary relief against broader currency headwinds this period.
9. Flat demand guidance suggests management expects stable but not accelerating market conditions ahead.
10. Small insider selling activity might signal caution among executives regarding near term stock performance.
11. The combination of rising debt and falling cash flow creates notable financial risk expos
```

## Qwen3.5-35B-A3B-Q4_K_M::thinking_high
- ready_sec: 4.694
- avg_latency_sec: 44.234
- avg_completion_tokens: 900
- avg_completion_tok_per_sec: 20.347
- min/max_completion_tok_per_sec: 20.24 / 20.405
- avg_text_len: 0
- stderr_log: `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/JB-20260310-LOCAL-MODEL-REPLACE_Qwen3.5-35B-A3B-Q4_K_M_thinking_high_20260310_224416.stderr.log`

### run 1
- ok: False
- latency_sec: 44.129
- usage: {"prompt_tokens": 124, "completion_tokens": 900, "total_tokens": 1024}
- completion_tok_per_sec: 20.395
- text_preview:
```

```

### run 2
- ok: False
- latency_sec: 44.467
- usage: {"prompt_tokens": 124, "completion_tokens": 900, "total_tokens": 1024}
- completion_tok_per_sec: 20.24
- text_preview:
```

```

### run 3
- ok: False
- latency_sec: 44.106
- usage: {"prompt_tokens": 124, "completion_tokens": 900, "total_tokens": 1024}
- completion_tok_per_sec: 20.405
- text_preview:
```

```

## Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M::current_off
- ready_sec: 21.387
- avg_latency_sec: 14.955
- avg_completion_tokens: 300
- avg_completion_tok_per_sec: 20.06
- min/max_completion_tok_per_sec: 19.91 / 20.187
- avg_text_len: 1668
- stderr_log: `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/JB-20260310-LOCAL-MODEL-REPLACE_Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M_current_off_20260310_224416.stderr.log`

### run 1
- ok: True
- latency_sec: 14.861
- usage: {"prompt_tokens": 125, "completion_tokens": 300, "total_tokens": 425}
- completion_tok_per_sec: 20.187
- text_preview:
```


1. Revenue growth of twenty percent indicates strong top line momentum despite other operational headwinds.
2. Operating profit decline of five percent suggests rising costs are eroding margins significantly this period.
3. Free cash flow dropped twelve percent showing reduced liquidity available for reinvestment or shareholder returns.
4. Debt ratio increased ten percentage points reflecting higher leverage and potentially elevated financial risk exposure.
5. Securing two new contracts demonstrates successful sales efforts and potential future revenue stream expansion.
6. Inventory days worsening implies slower turnover rates which may tie up working capital unnecessarily.
7. Capital expenditure rose eight percent indicating management is investing heavily in long term capacity growth.
8. Mild foreign exchange tailwind provided some benefit but was insufficient to offset broader negative trends.
9. Flat demand guidance signals management expects stable market conditions without significant near term acceleration.
10. Small insider selling activity might suggest limited confidence among executives regarding immediate stock performance.
11. The combination of lower profits and hig
```

### run 2
- ok: True
- latency_sec: 15.068
- usage: {"prompt_tokens": 125, "completion_tokens": 300, "total_tokens": 425}
- completion_tok_per_sec: 19.91
- text_preview:
```


1. Revenue growth of twenty percent indicates strong top line momentum despite other operational headwinds.
2. Operating profit decline of five percent suggests rising costs are eroding margins significantly this period.
3. Free cash flow dropped twelve percent showing reduced liquidity available for reinvestment or shareholder returns.
4. Debt ratio increased ten percentage points reflecting higher leverage and potentially elevated financial risk exposure.
5. Securing two new contracts demonstrates successful sales efforts and potential future revenue stream expansion.
6. Inventory days worsening implies slower turnover rates which may tie up working capital unnecessarily.
7. Capital expenditure rose eight percent indicating management is investing heavily in long term capacity growth.
8. Mild foreign exchange tailwind provided some benefit but was insufficient to offset broader negative trends.
9. Flat demand guidance signals management expects stable market conditions without significant near term acceleration.
10. Small insider selling activity might suggest limited confidence among executives regarding immediate stock performance.
11. The combination of lower profits and hig
```

### run 3
- ok: True
- latency_sec: 14.937
- usage: {"prompt_tokens": 125, "completion_tokens": 300, "total_tokens": 425}
- completion_tok_per_sec: 20.084
- text_preview:
```


1. Revenue growth of twenty percent indicates strong top line momentum despite other operational headwinds.
2. Operating profit decline of five percent suggests rising costs are eroding margins significantly this period.
3. Free cash flow dropped twelve percent showing reduced liquidity available for reinvestment or shareholder returns.
4. Debt ratio increased ten percentage points reflecting higher leverage and potentially elevated financial risk exposure.
5. Securing two new contracts demonstrates successful sales efforts and potential future revenue stream expansion.
6. Inventory days worsening implies slower turnover rates which may tie up working capital unnecessarily.
7. Capital expenditure rose eight percent indicating management is investing heavily in long term capacity growth.
8. Mild foreign exchange tailwind provided some benefit but was insufficient to offset broader negative trends.
9. Flat demand guidance signals management expects stable market conditions without significant near term acceleration.
10. Small insider selling activity might suggest limited confidence among executives regarding immediate stock performance.
11. The combination of lower profits and hig
```

## Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M::thinking_high
- ready_sec: 4.695
- avg_latency_sec: 43.932
- avg_completion_tokens: 900
- avg_completion_tok_per_sec: 20.488
- min/max_completion_tok_per_sec: 20.235 / 20.635
- avg_text_len: 0
- stderr_log: `/Users/jobiseu/.openclaw/workspace/runtime/tasks/proofs/JB-20260310-LOCAL-MODEL-REPLACE_Qwen3.5-35B-A3B-Claude-4.6-Opus-Reasoning-Distilled.i1-Q4_K_M_thinking_high_20260310_224416.stderr.log`

### run 1
- ok: False
- latency_sec: 44.478
- usage: {"prompt_tokens": 124, "completion_tokens": 900, "total_tokens": 1024}
- completion_tok_per_sec: 20.235
- text_preview:
```

```

### run 2
- ok: False
- latency_sec: 43.703
- usage: {"prompt_tokens": 124, "completion_tokens": 900, "total_tokens": 1024}
- completion_tok_per_sec: 20.594
- text_preview:
```

```

### run 3
- ok: False
- latency_sec: 43.615
- usage: {"prompt_tokens": 124, "completion_tokens": 900, "total_tokens": 1024}
- completion_tok_per_sec: 20.635
- text_preview:
```

```

## Restore
{
  "ok": true,
  "ready_sec": 4.571,
  "error": null
}