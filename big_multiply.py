import time
import random

def karatsuba(x, y):
    if x < 10 or y < 10:
        return x * y
    n = max(len(str(x)), len(str(y)))
    m = n // 2
    high1, low1 = divmod(x, 10**m)
    high2, low2 = divmod(y, 10**m)
    z0 = karatsuba(low1, low2)
    z1 = karatsuba(low1 + high1, low2 + high2)
    z2 = karatsuba(high1, high2)
    return z2 * 10**(2*m) + (z1 - z2 - z0) * 10**m + z0

test_cases = [
    ("小數", 123456789, 987654321),
    ("中數", 12345678901234567890, 98765432109876543210),
    ("大數", int("9" * 50), int("8" * 50)),
    ("超大數", int("7" * 100), int("6" * 100)),
]

results = []

for label, a, b in test_cases:
    t0 = time.perf_counter()
    result_karatsuba = karatsuba(a, b)
    t1 = time.perf_counter()
    karatsuba_time = (t1 - t0) * 1000

    t0 = time.perf_counter()
    result_builtin = a * b
    t1 = time.perf_counter()
    builtin_time = (t1 - t0) * 1000

    match = result_karatsuba == result_builtin
    results.append({
        "label": label,
        "a": str(a),
        "b": str(b),
        "result": str(result_builtin),
        "digits_a": len(str(a)),
        "digits_b": len(str(b)),
        "digits_result": len(str(result_builtin)),
        "karatsuba_ms": f"{karatsuba_time:.4f}",
        "builtin_ms": f"{builtin_time:.4f}",
        "match": match,
    })

html = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>大數乘法計算器</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }
  h1 { text-align: center; font-size: 2rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .subtitle { text-align: center; color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #334155; }
  .card-header { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem; }
  .badge { background: linear-gradient(135deg, #3b82f6, #6366f1); border-radius: 6px; padding: 0.25rem 0.75rem; font-size: 0.85rem; font-weight: 600; }
  .digits-info { color: #94a3b8; font-size: 0.85rem; margin-left: auto; }
  .operand-row { display: grid; grid-template-columns: 1fr auto 1fr; gap: 1rem; align-items: center; margin-bottom: 1rem; }
  .num-box { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 0.75rem 1rem; font-family: monospace; font-size: 0.8rem; overflow-wrap: break-word; word-break: break-all; max-height: 80px; overflow-y: auto; color: #7dd3fc; }
  .op-sym { font-size: 1.5rem; color: #f472b6; font-weight: bold; text-align: center; }
  .result-box { background: #0f172a; border: 2px solid #6366f1; border-radius: 8px; padding: 0.75rem 1rem; font-family: monospace; font-size: 0.8rem; overflow-wrap: break-word; word-break: break-all; max-height: 100px; overflow-y: auto; color: #a5f3fc; }
  .result-label { font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.4rem; }
  .perf { display: flex; gap: 1rem; margin-top: 1rem; flex-wrap: wrap; }
  .perf-item { flex: 1; background: #0f172a; border-radius: 8px; padding: 0.6rem 1rem; border: 1px solid #334155; min-width: 140px; }
  .perf-label { font-size: 0.75rem; color: #64748b; }
  .perf-val { font-size: 1rem; font-weight: 600; color: #34d399; }
  .check { color: #4ade80; font-weight: bold; }
  .summary { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 1.5rem; }
  .summary h2 { font-size: 1.1rem; color: #94a3b8; margin-bottom: 1rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { background: #0f172a; color: #94a3b8; padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #334155; }
  td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b; }
  tr:hover td { background: #0f172a33; }
  .algo-note { margin-top: 1.5rem; background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
  .algo-note h2 { color: #818cf8; margin-bottom: 0.75rem; }
  .algo-note p { color: #94a3b8; line-height: 1.6; font-size: 0.9rem; }
  code { background: #0f172a; padding: 0.1rem 0.4rem; border-radius: 4px; color: #f472b6; font-family: monospace; }
</style>
</head>
<body>
<h1>大數乘法計算器</h1>
<p class="subtitle">Karatsuba 演算法 vs Python 內建乘法</p>

<div class="summary">
  <h2>結果摘要</h2>
  <table>
    <thead>
      <tr><th>類型</th><th>A 位數</th><th>B 位數</th><th>結果位數</th><th>Karatsuba (ms)</th><th>內建 (ms)</th><th>驗證</th></tr>
    </thead>
    <tbody>
"""

for r in results:
    html += f"""      <tr>
        <td>{r['label']}</td>
        <td>{r['digits_a']}</td>
        <td>{r['digits_b']}</td>
        <td>{r['digits_result']}</td>
        <td>{r['karatsuba_ms']}</td>
        <td>{r['builtin_ms']}</td>
        <td class="check">{'✓ 一致' if r['match'] else '✗ 不符'}</td>
      </tr>
"""

html += """    </tbody>
  </table>
</div>

"""

for r in results:
    a_display = r['a'] if len(r['a']) <= 60 else r['a'][:30] + "..." + r['a'][-10:]
    b_display = r['b'] if len(r['b']) <= 60 else r['b'][:30] + "..." + r['b'][-10:]
    html += f"""<div class="card">
  <div class="card-header">
    <span class="badge">{r['label']}</span>
    <span class="digits-info">結果 {r['digits_result']} 位數</span>
  </div>
  <div class="operand-row">
    <div>
      <div class="result-label">A ({r['digits_a']} 位)</div>
      <div class="num-box">{r['a']}</div>
    </div>
    <div class="op-sym">×</div>
    <div>
      <div class="result-label">B ({r['digits_b']} 位)</div>
      <div class="num-box">{r['b']}</div>
    </div>
  </div>
  <div class="result-label">= 結果 ({r['digits_result']} 位)</div>
  <div class="result-box">{r['result']}</div>
  <div class="perf">
    <div class="perf-item"><div class="perf-label">Karatsuba 演算法</div><div class="perf-val">{r['karatsuba_ms']} ms</div></div>
    <div class="perf-item"><div class="perf-label">Python 內建</div><div class="perf-val">{r['builtin_ms']} ms</div></div>
    <div class="perf-item"><div class="perf-label">結果驗證</div><div class="perf-val check">{'✓ 完全一致' if r['match'] else '✗ 不符'}</div></div>
  </div>
</div>
"""

html += """<div class="algo-note">
  <h2>演算法說明</h2>
  <p>
    <strong>Karatsuba 演算法</strong>（1960年，Anatoly Karatsuba 發明）將大數乘法從傳統的 <code>O(n²)</code> 降至 <code>O(n^1.585)</code>。<br><br>
    核心思想：將兩個 n 位數各拆成高低兩半，只需 <strong>3次遞迴乘法</strong>（而非 4 次），再組合結果：<br><br>
    設 <code>x = x₁·B^m + x₀</code>，<code>y = y₁·B^m + y₀</code>，則：<br>
    <code>x·y = z₂·B^2m + (z₁−z₂−z₀)·B^m + z₀</code><br>
    其中 <code>z₀=x₀y₀</code>，<code>z₂=x₁y₁</code>，<code>z₁=(x₀+x₁)(y₀+y₁)</code>
  </p>
</div>
</body>
</html>"""

with open("big_multiply.html", "w", encoding="utf-8") as f:
    f.write(html)

print("HTML 已輸出至 big_multiply.html")
for r in results:
    print(f"[{r['label']}] {r['digits_a']}×{r['digits_b']} 位 => 結果 {r['digits_result']} 位 | Karatsuba: {r['karatsuba_ms']}ms | 內建: {r['builtin_ms']}ms | {'OK' if r['match'] else 'FAIL'}")
