# WebSocket通信服务

## 目录结构

```
websocket/
├── websocket_server.py    # WebSocket服务器主程序
└── README.md             # 本文档
```

## 功能说明

WebSocket服务器用于简小助系统和会话管理系统之间的实时双向通信,主要用于:
- 简小助通知会话管理系统有新的待审核QA
- 会话管理系统通知简小助审核结果(通过/打回)

## 启动方式

```bash
# 进入websocket目录
cd src/web_admin/websocket

# 启动服务器
python websocket_server.py
```

**监听地址**: `ws://localhost:8006`

## 消息格式

### 1. 注册消息
```json
{
  "type": "register",
  "client": "conversation|session_manager"
}
```

### 2. 待审核QA通知
```json
{
  "type": "qa_pending",
  "data": {
    "qa_id": 123,
    "question": "问题内容",
    "answer": "答案内容",
    "user_id": "用户ID",
    "timestamp": "2025-11-29T10:00:00"
  },
  "from": "conversation",
  "to": "session_manager"
}
```

### 3. 审核通过通知
```json
{
  "type": "qa_approved",
  "data": {
    "qa_id": 123,
    "status": "approved",
    "timestamp": "2025-11-29T10:05:00"
  },
  "from": "session_manager",
  "to": "conversation"
}
```

### 4. 审核打回通知
```json
{
  "type": "qa_rejected",
  "data": {
    "qa_id": 123,
    "status": "rejected",
    "reason": "打回原因",
    "timestamp": "2025-11-29T10:05:00"
  },
  "from": "session_manager",
  "to": "conversation"
}
```

## 测试

```bash
# 测试脚本位于 src/scripts/
cd src/scripts

# 简单测试
python test_ws_simple.py

# 完整测试
python test_websocket.py
```

## 注意事项

1. **端口占用**: 确保8006端口未被占用
2. **编码问题**: 已处理UTF-8编码,支持中文和emoji
3. **心跳机制**: 每30秒自动发送心跳检测
4. **断线重连**: 客户端需要实现自动重连逻辑

## 故障排查

### 问题1: 端口被占用
```
OSError: [Errno 10048] 通常每个套接字地址只允许使用一次
```

**解决方法**:
```bash
# Windows
netstat -ano | findstr :8006
taskkill /PID <进程ID> /F

# 或重启服务器
```

### 问题2: 连接失败
```
ConnectionRefusedError: [WinError 10061] 由于目标计算机积极拒绝,无法连接
```

**解决方法**:
- 确认WebSocket服务器已启动
- 检查防火墙设置
- 确认端口号正确(8006)

### 问题3: 内部错误
```
received 1011 (internal error)
```

**解决方法**:
- 查看服务器日志
- 检查消息格式是否正确
- 确认handler函数签名正确

## 版本信息

- Python: 3.13+
- websockets: 最新版本
- 编码: UTF-8
