# Telegram Bot 与 Channel 配置（套利机会推送）

套利机会出现时，程序会向 Telegram 发送一条消息。需要配置 **Bot** 和 **接收位置**（私聊或 Channel），并把 token 与 chat_id 写入环境变量。

**推送到 Channel @polysportarb**：将 Bot 加为 @polysportarb 管理员后，设置 `TELEGRAM_CHAT_ID=@polysportarb` 即可。

---

## 1. 创建 Bot 并获取 Token

1. 在 Telegram 里搜索 **@BotFather**，打开对话。
2. 发送 `/newbot`，按提示起名（例如 `Polysportarb Alert`）、起 username（必须以 `bot` 结尾，例如 `polysportarb_alert_bot`）。
3. BotFather 会返回一串 **Token**，形如：`123456789:ABCdefGHIjkL-MNOpqrsTUVwxyz`
4. 复制该 Token，保存为环境变量 **`TELEGRAM_BOT_TOKEN`**（本地 `.env` 或 Railway Variables）。

---

## 2. 选择接收位置：私聊 或 Channel

### 方式 A：推送到「私聊」（自己收）

1. 在 Telegram 里搜索你刚创建的 Bot（用 username），点 **Start** 或发一条任意消息。
2. 获取你的 **chat_id**（私聊的 chat_id 就是你的用户 id）：
   - 浏览器打开（把 `<你的 Bot Token>` 换成真实 token）：
     ```
     https://api.telegram.org/bot<你的 Bot Token>/getUpdates
     ```
   - 发一条消息给 Bot 后刷新上述链接，在返回的 JSON 里找到 `"chat":{"id": 123456789}`，**123456789** 就是你的 **chat_id**。
3. 把该数字保存为环境变量 **`TELEGRAM_CHAT_ID`**（例如 `123456789`）。

### 方式 B：推送到「Channel」（群组/频道收）

1. 创建一个 **Channel**（或使用已有 Channel）：Telegram → 菜单 → New Channel → 起名、设为**公开**并设置 username（例如 `polysportarb`），或使用已有公开 Channel。
2. 把 Bot **加为管理员**：Channel 设置 → Administrators → Add Administrator → 搜索你的 Bot → 至少勾选 **Post messages**（或允许发消息的权限）。
3. 设置 **TELEGRAM_CHAT_ID**（二选一）：
   - **推荐：公开 Channel 用 @username**  
     若 Channel 为公开且 username 为 `@polysportarb`，直接设置 **`TELEGRAM_CHAT_ID=@polysportarb`** 即可，套利机会会推送到该 Channel。
   - 或使用数字 **chat_id**（适用于私有 Channel 或不想暴露 username 时）：  
     把 Bot 加为管理员后，在 Channel 里发一条消息，访问 `https://api.telegram.org/bot<你的 Bot Token>/getUpdates`，在 JSON 里找到 `"chat":{"id": -1001234567890, ...}`，将 **-1001234567890** 设为 **`TELEGRAM_CHAT_ID`**。
4. 将上述值保存为环境变量 **`TELEGRAM_CHAT_ID`**（例如 `@polysportarb` 或 `-1001234567890`）。

---

## 3. 在项目里配置环境变量

- **本地**：在项目根目录的 `.env` 中增加：
  ```
  TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjkL-MNOpqrsTUVwxyz
  TELEGRAM_CHAT_ID=123456789
  ```
  私聊填正数 id，Channel 填负数 id（如 `-1001234567890`）。

- **Railway**：在对应 Service 的 **Variables** 里添加：
  - `TELEGRAM_BOT_TOKEN` = 你的 Bot Token
  - `TELEGRAM_CHAT_ID` = 私聊填数字 id；**推送到 Channel @polysportarb 时填 `@polysportarb`**

保存后重启/重新部署，有套利机会时就会推送到该 Bot 的私聊或 Channel（如 @polysportarb）。

---

## 4. 校验是否生效

- 不配置 `TELEGRAM_BOT_TOKEN` 或 `TELEGRAM_CHAT_ID` 时，程序照常运行，只是不发送 Telegram 消息。
- 配置后，出现套利机会时会在对应私聊或 Channel（如 @polysportarb）收到一条「🔔 套利机会」消息；若收不到，请检查：
  - Token 是否完整、无多余空格；
  - TELEGRAM_CHAT_ID 是否正确（私聊为数字；Channel 为 @polysportarb 或 -100 开头的数字）；
  - Bot 是否已加入 Channel 且具备发消息权限（若用 Channel）。
