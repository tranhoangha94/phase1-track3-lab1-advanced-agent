# Lab 16 — Báo cáo đánh giá Reflexion Agent

## 1. Metadata
- **Dataset:** hotpot_mini.json
- **Mode:** llm
- **Tổng records:** 40
- **Agents:** react, reflexion

## 2. So sánh ReAct vs Reflexion

| Metric | ReAct | Reflexion | Delta (Reflexion − ReAct) |
|---|---:|---:|---:|
| Exact Match (EM) | 25.0% | 35.0% | +0.1000 |
| Avg attempts | 1 | 2.35 | +1.3500 |
| Avg tokens | 1840.5 | 6849.35 | +5008.85 |
| Avg latency (ms) | 3116.35 | 32080.9 | +28964.55 |

**Đọc nhanh:** EM cao hơn = trả lời đúng nhiều hơn; attempts/tokens/latency cao hơn = tốn thêm tài nguyên cho vòng phản chiếu.

## 3. Bảng ước tính cost & running time

**Model:** `qwen2:1.5b` | **Nguồn giá:** `reference_table:qwen2` | **Input:** $0.07/1M | **Output:** $0.28/1M

Ước tính tham chiếu theo bảng giá cloud API (`qwen2`) (Ollama local — không có hóa đơn thật). Thêm `LLM_INPUT_COST_PER_1M` / `LLM_OUTPUT_COST_PER_1M` vào `.env` để dùng giá riêng.

### Chi phí thực tế của run hiện tại

| Metric | ReAct | Reflexion | Delta (Reflexion − ReAct) | Cả run (ReAct + Reflexion) |
|---|---:|---:|---:|---:|
| Số câu đã chạy | 20 | 20 | — | 40 records |
| Tổng tokens | 36,810 | 136,987 | +100,177 | 173,797 |
| TB tokens / câu | 1,840.5 | 6,849.35 | +5008.85 | — |
| Tổng running time | 1m 2s | 10m 41s | 9m 39s | 11m 43s |
| TB thời gian / câu | 3s | 32s | — | — |
| Ước tính API cost (USD) | $0.0047 | $0.0176 | $+0.0129 | $0.0224 |

### Projection cho 100 câu hỏi

| Metric | ReAct | Reflexion | Combined |
|---|---:|---:|---:|
| Ước tính running time | 5m 11s | 53m 28s | 58m 39s |
| Ước tính API cost (USD) | $0.0237 | $0.0882 | $0.1119 |

*Projection = scale tuyến tính từ run hiện tại × (100 / số câu đã đo).*

## 4. Failure modes
```json
{
  "react": {
    "wrong_final_answer": 15,
    "none": 5
  },
  "reflexion": {
    "wrong_final_answer": 13,
    "none": 7
  }
}
```

## 5. Bảng so sánh từng câu
| QID | Question | ReAct | Reflexion | ReAct answer | Reflexion answer | Reflexion attempts |
|---|---|:---:|:---:|---|---|---:|
| 5a7166395542994082a3e814 | What is the name of the fight song of the university whose main campus is in Law | ✗ | ✓ | unknown | University of Kansas | 2 |
| 5a75e05c55429976ec32bc5f | Brown State Fishing Lake is in a country that has a population of how many inhab | ✗ | ✗ | unknown | unknown | 3 |
| 5a7bbb64554299042af8f7cc | Who is older, Annie Morton or Terry Richardson? | ✗ | ✗ | unknown | unknown | 3 |
| 5a8133725542995ce29dcbdb | Which writer was from England, Henry Roth or Robert Erskine Childers? | ✗ | ✓ | unknown | Robert Erskine Childers | 1 |
| 5a85b2d95542997b5ce40028 | Who was known by his stage name Aladin and helped organizations improve their pe | ✗ | ✗ | Amaruk Kayshapanta | Amaruk Kayshapanta Anchapacxi | 3 |
| 5a85ea095542994775f606a8 | What science fantasy young adult series, told in first person, has a set of comp | ✓ | ✓ | The Hork-Bajir Chronicles | The Hork-Bajir Chronicles | 1 |
| 5a877e5d5542993e715abf7d | What screenwriter with credits for "Evolution" co-wrote a film starring Nicolas  | ✓ | ✓ | David Weissman | David Weissman | 1 |
| 5a87ab905542996e4f3088c1 | The arena where the Lewiston Maineiacs played their home games can seat how many | ✗ | ✗ | unknown | unknown | 3 |
| 5a8b57f25542995d1e6f1371 | Were Scott Derrickson and Ed Wood of the same nationality? | ✗ | ✗ | unknown | unknown | 3 |
| 5a8c7595554299585d9e36b6 | What government position was held by the woman who portrayed Corliss Archer in t | ✓ | ✓ | Janet Marie Waldo | Janet Marie Waldo | 1 |
| 5a8db19d5542994ba4e3dd00 | Are Local H and For Against both from the United States? | ✗ | ✗ | unknown | unknown | 3 |
| 5a8e3ea95542995a26add48d | The director of the romantic comedy "Big Stone Gap" is based in what New York ci | ✗ | ✗ | unknown | unknown | 3 |
| 5ab29c24554299449642c932 | Are Giuseppe Verdi and Ambroise Thomas both Opera composers ? | ✗ | ✗ | unknown | unknown | 3 |
| 5ab3b0bf5542992ade7c6e39 | What year did Guns N Roses perform a promo for a movie starring Arnold Schwarzen | ✗ | ✗ | unknown | unknown | 3 |
| 5ab3e45655429976abd1bcd4 | The Vermont Catamounts men's soccer team currently competes in a conference that | ✗ | ✗ | unknown | America East Conference | 3 |
| 5ab56e32554299637185c594 | Are Random House Tower and 888 7th Avenue both used for real estate? | ✓ | ✓ | unknown | unknown | 1 |
| 5ab6d09255429954757d337d | The football manager who recruited David Beckham managed Manchester United durin | ✗ | ✗ | unknown | unknown | 3 |
| 5abd94525542992ac4f382d2 | 2014 S/S is the debut album of a South Korean boy group that was formed by who? | ✗ | ✗ | unknown | unknown | 3 |
| 5adbf0a255429947ff17385a | Are the Laleli Mosque and Esma Sultan Mansion located in the same neighborhood? | ✓ | ✓ | unknown | unknown | 1 |
| 5ae0d4c9554299603e418468 | Roger O. Egeberg was Assistant Secretary for Health and Scientific Affairs durin | ✗ | ✗ | unknown | unknown | 3 |

## 6. Ví dụ sai tiêu biểu
- **5a8b57f25542995d1e6f1371** (react): gold=`yes`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0
- **5a8e3ea95542995a26add48d** (react): gold=`Greenwich Village, New York City`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0
- **5abd94525542992ac4f382d2** (react): gold=`YG Entertainment`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0
- **5a85b2d95542997b5ce40028** (react): gold=`Eenasul Fateh`, pred=`Amaruk Kayshapanta`, mode=`wrong_final_answer`, reflections=0
- **5a87ab905542996e4f3088c1** (react): gold=`3,677 seated`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0
- **5a7bbb64554299042af8f7cc** (react): gold=`Terry Richardson`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0
- **5a8db19d5542994ba4e3dd00** (react): gold=`yes`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0
- **5a7166395542994082a3e814** (react): gold=`Kansas Song`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0
- **5ab3b0bf5542992ade7c6e39** (react): gold=`1999`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0
- **5ab6d09255429954757d337d** (react): gold=`from 1986 to 2013`, pred=`unknown`, mode=`wrong_final_answer`, reflections=0

## 7. Extensions đã triển khai
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding

## 8. Discussion
### Phân tích tổng quan

Trên 20 câu hỏi, ReAct đạt EM 25.0% với trung bình 1.00 lần thử, còn Reflexion đạt EM 35.0% với trung bình 2.35 lần thử. Reflexion cải thiện EM so với ReAct.

Reflexion tốn thêm token trung bình 5009 và latency 28965 ms mỗi câu so với ReAct. Đây là chi phí đổi lấy khả năng phản chiếu sau khi trả lời sai.

### So sánh failure modes

ReAct sai chủ yếu ở mode `wrong_final_answer`; Reflexion sai chủ yếu ở mode `wrong_final_answer`. Reflection memory hữu ích nhất khi lỗi đến từ multi-hop chưa hoàn tất hoặc chọn nhầm entity ở bước cuối — reflector gợi ý chiến thuật cụ thể để attempt tiếp theo bám context hơn.

### Câu Reflexion cứu được / làm tệ hơn

- Câu Reflexion sửa được so với ReAct: 5a7166395542994082a3e814, 5a8133725542995ce29dcbdb
- Câu ReAct đúng nhưng Reflexion sai: không có

### Kết luận

Reflexion phù hợp khi câu trả lời cần nhiều bước suy luận và attempt đầu dễ dừng sớm. ReAct vẫn hợp lý khi ưu tiên chi phí thấp và độ trễ ngắn. Chất lượng cuối cùng phụ thuộc mạnh vào evaluator (chấm 0/1 chính xác) và reflector (đưa ra strategy khả thi cho attempt kế tiếp).
