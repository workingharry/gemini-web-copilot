# Gemini Web UI 節點選擇器與交互規範 (Selectors Reference)

本文檔記錄 Google Gemini 網頁版（[gemini.google.com](https://gemini.google.com)）當前所採用的前端節點結構、選擇器清單與例外回退（Fallback）機制。

---

## 1. 輸入框（Prompt Input Area）

Gemini 網頁版採用 Quill / Angular 富文本組件，常見標籤如下：

| 選擇器 | 優先級 | 說明 |
| :--- | :--- | :--- |
| `rich-textarea div[contenteditable='true']` | P0 (主要) | 最新版常規提示詞編輯區域 |
| `div.ql-editor[contenteditable='true']` | P1 (備用) | Quill 編輯器核心節點 |
| `div[role='textbox']` | P2 (通用) | 具備無障礙屬性的文字輸入框 |
| `textarea[placeholder*='Prompt']` | P3 (行動版/簡化版) | 傳統原生文字輸入框 |

> **長文字優化技巧**：
> 當文字量大於 500 字元時，切勿使用 `keyboard.type()` 一個字一個字敲擊（極易觸發超時與瀏覽器卡頓）。腳本採用「寫入系統剪貼簿 + 模擬 `Cmd+V` 貼上」或「寫入檔案後透過附加元件上傳」策略。

---

## 2. 檔案上傳（File Attachment）

當 Prompt 包含大型程式碼檔案或規格文件時：

| 選擇器 | 說明 |
| :--- | :--- |
| `input[type='file']` | 隱藏的原生檔案上傳器，可用於直接調用 `set_input_files()` |
| `button[aria-label*='Upload']` / `button[aria-label*='上傳']` | 前端顯示的「+ / 上傳檔案」按鈕 |

---

## 3. 生成狀態監控（Generation State Detection）

> [!WARNING]
> **嚴禁以 Send 按鈕的可用狀態作為生成結束的依據**。
> 當輸入框為空時，Gemini 前端會禁用或隱藏 Send 按鈕，若等待 Send 按鈕啟用將導致無限等待。

正確判斷流程：
1. **生成開始**：監聽 `Stop` 按鈕出現。
   - 選擇器：`button[aria-label*='Stop']`、`button[aria-label*='停止']`、`button[data-test-id='stop-button']`
2. **生成進行中**：等待 `Stop` 按鈕消失（detached 或 hidden）。
3. **生成完全穩定**：等待該回合回覆下方的動作工具列（Action bar）中的 `Copy` 按鈕出現並保持穩定 1 秒。

---

## 4. 內容擷取（Response Extraction）

> [!IMPORTANT]
> **切勿直接爬取 DOM 文本（`.innerText` / `innerHTML`）**。
> 直接讀取 DOM 會破壞縮排、遺失代碼高亮 Markdown 標記，並夾帶 UI 雜訊（如「複製程式碼」、「python」標籤）。

正確提取流程：
1. 定位最新一則回覆下的原生複製按鈕：
   - 選擇器：`button[aria-label*='Copy']`、`button[aria-label*='複製']`、`button[data-test-id='copy-button']`
2. 腳本透過 Playwright 觸發原生點擊。
3. 直接從系統剪貼簿（Clipboard）讀取純淨的原生 Markdown。
4. **Fallback 機制**：僅在剪貼簿權限遭系統拒絕時，才退回到 `message-content` 或 `model-response` 抓取 innerText。
