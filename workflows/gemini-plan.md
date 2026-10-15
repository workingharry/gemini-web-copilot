# Workflow: /plan with Gemini Web Copilot

本工作流指導 Antigravity 如何透過 `gemini-web-copilot` 將高階系統架構規劃與複雜演算法設計委派給 Google Gemini 網頁版（[gemini.google.com](https://gemini.google.com)），充分調用其 Thinking / 進階長上下文模型或自訂 Gems。

---

## 觸發條件
當用戶在對話中輸入 `/plan`，或要求「調用 Gemini 規劃系統架構 / 撰寫實作計畫」時觸發。

---

## 執行步驟

### 步驟 1：整理任務上下文
1. 收集當前專案現況、核心問題與約束條件。
2. 組合出清晰的系統規劃提示詞（可參考 `examples/planning_prompt.md`）。
3. 若需參考專案現有檔案，將該檔案路徑傳入 `--context-file`。

### 步驟 2：調用 Gemini Web Copilot
執行封裝腳本將規劃任務送入 Gemini 網頁版：
```bash
bash ~/.gemini/config/skills/gemini-web-copilot/scripts/run.sh \
  --prompt "請身為資深系統架構師，針對以下專案進行詳細 Planning 與實施計畫..." \
  --output ./docs/gemini_plan.md
```

### 步驟 3：呈現規劃文檔供用戶審批
1. 檢視 `./docs/gemini_plan.md` 生成之架構圖、模組劃分與實施步驟。
2. 建立或更新 `<Artifact Directory>/plan.md`，請求用戶確認。
3. 等待用戶給予反饋或批准（例如輸入 `/go`）。
