#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket通知服务器
用于简小助和会话管理系统之间的实时通信
"""

import sys
import io

# 设置输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
import json
import logging
from datetime import datetime
from typing import Set, Dict
import websockets
# 使用新版websockets API

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 连接池
clients: Dict[str, set] = {
    'conversation': set(),      # 简小助系统客户端
    'session_manager': set()    # 会话管理系统客户端
}

async def register_client(websocket, client_type: str):
    """注册客户端"""
    if client_type not in clients:
        clients[client_type] = set()
    
    clients[client_type].add(websocket)
    logger.info(f"✅ {client_type}客户端已连接, 当前连接数: {len(clients[client_type])}")
    
    # 发送连接统计
    stats = {client_type: len(client_set) for client_type, client_set in clients.items()}
    logger.info(f"📊 当前连接统计: {stats}")

async def unregister_client(websocket):
    """注销客户端"""
    for client_type, client_set in clients.items():
        if websocket in client_set:
            client_set.remove(websocket)
            logger.info(f"❌ {client_type}客户端已断开, 当前连接数: {len(client_set)}")
            break

async def broadcast_to_type(client_type: str, message: dict):
    """广播消息到指定类型的所有客户端"""
    if client_type not in clients:
        logger.warning(f"⚠️ 未知的客户端类型: {client_type}")
        return
    
    if not clients[client_type]:
        logger.warning(f"⚠️ 没有{client_type}类型的客户端连接")
        return
    
    disconnected = set()
    success_count = 0
    
    for client in clients[client_type]:
        try:
            await client.send(json.dumps(message, ensure_ascii=False))
            success_count += 1
        except websockets.exceptions.ConnectionClosed:
            disconnected.add(client)
            logger.warning(f"⚠️ 客户端连接已关闭,将从池中移除")
        except Exception as e:
            logger.error(f"❌ 发送消息失败: {e}")
            disconnected.add(client)
    
    # 清理断开的连接
    clients[client_type] -= disconnected
    
    logger.info(f"📤 消息已发送到{success_count}个{client_type}客户端")

async def handle_message(websocket, message: dict):
    """处理收到的消息"""
    msg_type = message.get('type')
    msg_from = message.get('from')
    msg_to = message.get('to')
    data = message.get('data', {})
    
    logger.info(f"📨 收到消息: type={msg_type}, from={msg_from}, to={msg_to}")
    
    # 消息类型处理
    if msg_type == 'ping':
        # 心跳响应
        await websocket.send(json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        }))
        return
    
    # 路由消息
    if msg_to == 'broadcast':
        # 广播给所有客户端
        logger.info("📢 广播消息到所有客户端")
        for client_type in clients:
            await broadcast_to_type(client_type, message)
    elif msg_to in clients:
        # 发送给指定类型的客户端
        logger.info(f"📬 发送消息到{msg_to}客户端")
        await broadcast_to_type(msg_to, message)
    else:
        logger.warning(f"⚠️ 未知的目标: {msg_to}")

async def handler(websocket):
    """
WebSocket连接处理器"""
    client_type = None
    try:
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    except:
        client_id = "unknown"
    
    logger.info(f"🔗 新连接: {client_id}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # 注册客户端
                if data.get('type') == 'register':
                    client_type = data.get('client')
                    await register_client(websocket, client_type)
                    await websocket.send(json.dumps({
                        'type': 'registered',
                        'client_type': client_type,
                        'client_id': client_id,
                        'timestamp': datetime.now().isoformat(),
                        'message': f'{client_type}客户端注册成功'
                    }, ensure_ascii=False))
                else:
                    # 处理其他消息
                    await handle_message(websocket, data)
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON解析失败: {e}")
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                logger.error(f"❌ 处理消息失败: {e}")
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': str(e)
                }))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"🔌 连接关闭: {client_id}")
    except Exception as e:
        logger.error(f"❌ 连接异常: {e}")
    finally:
        if client_type:
            await unregister_client(websocket)

async def heartbeat():
    """心跳检测任务"""
    while True:
        await asyncio.sleep(30)  # 每30秒检测一次
        
        for client_type, client_set in clients.items():
            disconnected = set()
            
            for client in client_set:
                try:
                    # 发送ping
                    await client.send(json.dumps({'type': 'ping'}))
                except:
                    disconnected.add(client)
            
            # 清理断开的连接
            client_set -= disconnected
            
            if disconnected:
                logger.info(f"💔 清理{len(disconnected)}个{client_type}断开连接")

async def main():
    """启动WebSocket服务器"""
    print("=" * 60)
    print("🚀 WebSocket通知服务器")
    print("=" * 60)
    print("📡 监听地址: ws://localhost:8006")
    print("🔗 支持客户端:")
    print("   - conversation: 简小助系统")
    print("   - session_manager: 会话管理系统")
    print("=" * 60)
    print()
    
    logger.info("WebSocket服务器启动中...")
    
    # 启动心跳检测任务
    asyncio.create_task(heartbeat())
    
    async with websockets.serve(handler, "0.0.0.0", 8006):
        logger.info("✅ WebSocket服务器已启动")
        await asyncio.Future()  # 永久运行

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 服务器已停止")
