# 系統規劃提示詞範本 (Planning Prompt Example)

適用情境：當需要請 Gemini Web（特別是其長上下文模型、Thinking 模式或自訂 Gems）為整個專案進行架構評估與階段性實施規劃。

```markdown
請身為系統架構師，針對以下專案進行深度 Planning 與技術評估：

### 目標任務
[簡述欲規劃的系統或新功能模組]

### 現狀與約束條件
[附上相關的現有架構、資料結構或配置]

### 規劃輸出要求
1. **架構圖與模組劃分** (請使用 Mermaid 語法繪製流程圖或架構圖)
2. **關鍵技術選型與權衡分析 (Trade-offs)**
3. **分階段實施計劃 (Milestones & Steps)**
4. **潛在風險與預防措施 (Risks & Mitigations)**
```
