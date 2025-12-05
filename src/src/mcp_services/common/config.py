"""
MCP服务配置文件
=============

配置文件说明：
- 所有配置项都支持通过环境变量覆盖
- 路径配置会自动转换为绝对路径
- 服务端口配置在 MCP_SERVICE_PORTS 中统一管理
"""
import os
from pathlib import Path

from . import PROJECT_ROOT, SRC_ROOT

# =============================================================================
# MCP协议配置
# =============================================================================

# MCP协议基础配置
MCP_CONFIG = {
    # 传输协议：streamable-http（支持实时流式响应）
    "protocol": "streamable-http",
    
    # MCP协议特性开关
    "features": {
        # tools: 工具调用功能（函数/方法调用）
        # 说明：启用后Dify Agent可以调用MCP服务暴露的工具（如classify_intent、comprehensive_search）
        "tools": True,
        
        # resources: 资源访问功能（文件、数据库等）
        # 说明：如果需要让Agent直接访问文件或数据库，可以启用此功能
        # 当前未启用：我们通过工具调用封装了所有资源访问逻辑
        "resources": False,
        
        # prompts: 预定义提示词模板功能
        # 说明：如果需要在MCP服务中提供标准化的提示词模板供Agent使用，可启用此功能
        # 当前未启用：Agent提示词在Dify中统一管理
        "prompts": False
    }
}

# =============================================================================
# 多模态AI配置（图片/视频识别）
# =============================================================================

MULTIMODAL_CONFIG = {
    # 使用千问VL多模态大模型
    "provider": "dashscope",
    "api_key": os.getenv("DASHSCOPE_API_KEY", "sk-1e36ef9b200944b4830da66c7d6f8fb6"),
    "model": os.getenv("MULTIMODAL_MODEL", "qwen-vl-max"),  # qwen-vl-max (更强大) 或 qwen-vl-plus (更快)
    "api_base": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    
    # 视频处理配置
    "video": {
        "max_frames": 10,  # 最多提取10个关键帧
        "frame_interval": 5,  # 每5秒提取一帧
        "extract_audio": True,  # 是否提取音频
        "audio_language": "zh",  # 音频语言（中文）
    },
    
    # 图片处理配置
    "image": {
        "max_size": 5 * 1024 * 1024,  # 最大5MB
        "formats": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
    }
}

# =============================================================================
# MCP服务网络配置
# =============================================================================

# MCP服务端口配置
# 说明：确保端口未被占用，可通过环境变量覆盖
MCP_SERVICE_PORTS = {
    "intent_classifier": 8001,      # 意图识别服务（问题类型判断 + 数据源预测 + 智能引导）
    "multi_source_search": 8002,    # 多源检索服务（QA/RAG/KG检索，不生成答案）
    "context_manager": 8003,        # 上下文管理服务（对话历史存储与检索）
    "generate_answer": 8004         # 生成回复服务（根据检索结果生成答案，应用回复格式约束）
}

# 服务绑定地址
# 说明：0.0.0.0 允许外部访问，127.0.0.1 仅本地访问
MCP_DEFAULT_HOST = "0.0.0.0"

# 传输协议
# 说明：streamable-http 支持实时流式响应，适合长时间检索任务
MCP_TRANSPORT_PROTOCOL = "streamable-http"

# =============================================================================
# 辅助函数
# =============================================================================

def _default_path(env_key: str, default_relative: Path) -> str:
    """
    通用路径读取函数，优先使用环境变量，否则使用默认相对路径。
    
    Args:
        env_key: 环境变量名称
        default_relative: 默认相对路径（相对于PROJECT_ROOT）
    
    Returns:
        解析后的绝对路径字符串
    """
    return str(Path(os.getenv(env_key, default_relative)).resolve())


# =============================================================================
# 业务服务配置
# =============================================================================

BASE_CONFIG = {
    # -------------------------------------------------------------------------
    # 多模态AI配置（图片/视频识别）
    # -------------------------------------------------------------------------
    "multimodal": MULTIMODAL_CONFIG,

    # -------------------------------------------------------------------------
    # 意图识别模型服务（通义千问API） - 多API Key负载均衡
    # -------------------------------------------------------------------------
    # 说明：用于识别用户问题类型（闲聊/敏感/专业问答）并预测数据源（QA/RAG/KG）
    # 模型：qwen2.5-7b-instruct（通义千问开源版API，低延迟低成本）
    # 服务：阿里云DashScope
    # 优化：支持多API Key轮询，突破单账号100 RPM限制
    "intent_model": {
        "api_type": "dashscope",  # API类型
        # 多API Key配置（轮询负载均衡）
        "api_keys": [
            os.getenv("DASHSCOPE_API_KEY_1", "sk-1e36ef9b200944b4830da66c7d6f8fb6"),  # 主Key: 100 RPM
            os.getenv("DASHSCOPE_API_KEY_2", ""),  # 备用Key 2: 100 RPM (留空则不启用)
            os.getenv("DASHSCOPE_API_KEY_3", ""),  # 备用Key 3: 100 RPM (留空则不启用)
        ],
        # 向后兼容：单Key模式（如果api_keys为空，使用此key）
        "api_key": os.getenv("DASHSCOPE_API_KEY", "sk-1e36ef9b200944b4830da66c7d6f8fb6"),
        "model": os.getenv("INTENT_MODEL_NAME", "qwen2.5-7b-instruct"),  # 改为qwen2.5-7b-instruct
        "timeout": int(os.getenv("INTENT_MODEL_TIMEOUT", "30")),  # 超时时间（秒）
        "enabled": os.getenv("INTENT_MODEL_ENABLED", "true").lower() == "true",  # 是否启用模型服务
        # 负载均衡策略
        "load_balance_strategy": os.getenv("LLM_LOAD_BALANCE_STRATEGY", "round_robin"),  # round_robin(轮询) / random(随机)
    },
    
    # -------------------------------------------------------------------------
    # RAG向量数据库配置（Chroma）
    # -------------------------------------------------------------------------
    # 说明：存储售后文档的向量化数据，支持语义检索
    # 数据规模：43个文档，13083个向量块
    "vector_db": {
        "type": "chroma",  # 向量库类型（固定为chroma）
        "persist_directory": _default_path(
            "VECTOR_DB_DIR",
            PROJECT_ROOT / "resource" / "chroma" / "JSchroma_db"
        ),
        "collection_name": os.getenv("VECTOR_DB_COLLECTION", "langchain")  # Collection名称
    },
    
    # -------------------------------------------------------------------------
    # 嵌入模型服务（BGE-Large-ZH-v1.5）
    # -------------------------------------------------------------------------
    # 说明：用于将文本转换为1024维向量，支持RAG和KG向量检索
    # 服务器：192.168.1.160:7000
    "embedding": {
        "url": os.getenv("EMBEDDING_SERVICE_URL", "http://192.168.1.160:7000"),
        "model": os.getenv("EMBEDDING_MODEL_NAME", "bge-large-zh-v1.5"),
        "timeout": int(os.getenv("EMBEDDING_TIMEOUT", "300"))  # 超时时间（秒）
    },
    
    # -------------------------------------------------------------------------
    # 重排序模型服务（BGE-Reranker-Large）
    # -------------------------------------------------------------------------
    # 说明：用于对检索结果进行二次排序，提高召回精度
    # 服务器：192.168.1.160:7001
    "reranker": {
        "url": os.getenv("RERANKER_SERVICE_URL", "http://192.168.1.160:7001"),
        "model": os.getenv("RERANKER_MODEL_NAME", "bge-reranker-large"),
        "top_n": int(os.getenv("RERANKER_TOP_N", "5")),  # 重排序后保留的结果数
        "enabled": os.getenv("RERANKER_ENABLED", "true").lower() == "true"  # 是否启用重排序
    },
    
    # -------------------------------------------------------------------------
    # 检索配置统一（Retrieval Configuration）
    # -------------------------------------------------------------------------
    # 说明：统一管理QA/RAG/KG三个数据源的检索参数
    # 策略：两阶段检索（初始召回 + 重排过滤）
    #   - 第一阶段：向量/语义检索，召回更多候选（initial_top_k）
    #   - 第二阶段：重排序模型精排，返回最优结果（final_top_k）
    "retrieval": {
        # QA知识库检索配置（Dify）
        "qa": {
            "initial_top_k": int(os.getenv("QA_INITIAL_TOP_K", "5")),      # Dify初始检索数量
            "final_top_k": int(os.getenv("QA_FINAL_TOP_K", "3")),          # 重排后返回数量
            "score_threshold": float(os.getenv("QA_SCORE_THRESHOLD", "0.5")),  # 相似度阈值
            "target_document_id": os.getenv("QA_TARGET_DOC_ID", "ee3a5cb0-3fa9-4cd1-9a1a-113bc43b5d5a") # 目标文档ID（用于QA召回统计）- 微信聊天.txt
        },
        # RAG文档检索配置（ChromaDB）
        "rag": {
            "initial_top_k": int(os.getenv("RAG_INITIAL_TOP_K", "5")),     # 向量初始检索数量
            "final_top_k": int(os.getenv("RAG_FINAL_TOP_K", "3")),         # 重排后返回数量
            "score_threshold": float(os.getenv("RAG_SCORE_THRESHOLD", "0.6"))  # 相似度阈值
        },
        # KG知识图谱检索配置（Neo4j + ChromaDB）
        "kg": {
            "entity_top_k": int(os.getenv("KG_ENTITY_TOP_K", "5")),        # 实体向量检索数量
            "relation_max": int(os.getenv("KG_RELATION_MAX", "10")),       # 关系查询上限
            "final_top_k": int(os.getenv("KG_FINAL_TOP_K", "3")),          # 重排后返回数量
            "score_threshold": float(os.getenv("KG_SCORE_THRESHOLD", "0.55"))  # 相似度阈值
        }
    },

    # -------------------------------------------------------------------------
    # 轻量级LLM配置（用于摘要生成、标题生成等简单任务）
    # -------------------------------------------------------------------------
    "light_llm": {
        "api_type": "dashscope",
        "api_key": os.getenv("DASHSCOPE_API_KEY", "sk-1e36ef9b200944b4830da66c7d6f8fb6"),
        "model": os.getenv("LIGHT_LLM_MODEL", "qwen2.5-7b-instruct"),
        "timeout": 30,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },

    # -------------------------------------------------------------------------
    # LLM配置（可选：Ollama本地 / DeepSeek API / 通义千问API） - 多API Key负载均衡
    # -------------------------------------------------------------------------
    # 说明：用于生成最终答案的大语言模型
    # 性能对比（售后问答场景）：
    #   - qwen3-max API（云端）: 2-5秒，效果最优，￥0.04/千tokens（输入）、￥0.12/千tokens（输出）
    #   - qwen3-plus API（云端）: 1-3秒，效果优秀，￥0.008/千tokens（输入）、￥0.024/千tokens（输出）
    #   - Ollama qwen2.5:14b（本地）: 14秒，效果好，免费
    #   - DeepSeek API（云端）: 3-8秒，效果优秀，￥1/百万tokens
    
    # 当前配置：通义千问API (qwen3-max) - 支持多Key负载均衡
    "llm": {
         "api_type": "dashscope",  # LLM类型：dashscope / ollama / openai / deepseek
         # 多API Key配置（轮询负载均衡）- 可突破单账号100 RPM限制
         "api_keys": [
             os.getenv("DASHSCOPE_API_KEY_1", "sk-1e36ef9b200944b4830da66c7d6f8fb6"),  # 主Key: 100 RPM
             os.getenv("DASHSCOPE_API_KEY_2", ""),  # 备用Key 2: 100 RPM (留空则不启用)
             os.getenv("DASHSCOPE_API_KEY_3", ""),  # 备用Key 3: 100 RPM (留空则不启用)
             os.getenv("DASHSCOPE_API_KEY_4", ""),  # 备用Key 4: 100 RPM (留空则不启用)
             os.getenv("DASHSCOPE_API_KEY_5", ""),  # 备用Key 5: 100 RPM (留空则不启用)
         ],
         # 向后兼容：单Key模式（如果api_keys为空，使用此key）
         "api_key": os.getenv("DASHSCOPE_API_KEY", "sk-1e36ef9b200944b4830da66c7d6f8fb6"),
         "model": os.getenv("LLM_MODEL", "qwen3-max"),  # qwen3-max (最强) 或 qwen3-plus (性价比高)
         "timeout": 300,  # 超时时间（秒）
         "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",  # DashScope兼容OpenAI格式
         # 负载均衡策略
         "load_balance_strategy": os.getenv("LLM_LOAD_BALANCE_STRATEGY", "round_robin"),  # round_robin(轮询) / random(随机)
         # RPM限制（单个API Key）
         "rpm_limit_per_key": int(os.getenv("LLM_RPM_LIMIT_PER_KEY", "100")),  # 每个Key的RPM限制
     },

    # # 备选配置：本地Ollama
    # "llm": {
    #     "api_type": "ollama",
    #     "base_url": "http://192.168.1.177:11434",
    #     "model": "qwen2.5:14b",
    #     "timeout": 300,
    #     "api_key": ""
    # },

    # # 备选配置：DeepSeek API
    # "llm": {
    #     "api_type": "openai",
    #     "base_url": "https://api.deepseek.com",
    #     "model": "deepseek-chat",
    #     "timeout": 300,
    #     "api_key": "sk-63956cebbf854d8aaa0ad1f24bf8483c"
    # },
    
    # -------------------------------------------------------------------------
    # Dify知识库配置
    # -------------------------------------------------------------------------
    # 说明：Dify知识库用于存储标准化的问答对，适合精确查询
    # 服务器：192.168.1.138
    "dify": {
        "api_base": os.getenv("DIFY_API_BASE", "http://192.168.1.138/v1"),  # Dify API地址
        "api_key": os.getenv("DIFY_API_KEY", "dataset-fXAE3HzlkMltZoiJmXCdgZtK"),  # API密钥
        "knowledge_base_id": os.getenv("DIFY_KB_ID", "1397b9d1-8e25-4269-ba12-046059a425b6"),  # 知识库ID
        "document_id": os.getenv("DIFY_DOC_ID", "ee3a5cb0-3fa9-4cd1-9a1a-113bc43b5d5a"),  # 文档ID(用于QA检索)
        "timeout": int(os.getenv("DIFY_TIMEOUT", "60")),  # 超时时间（秒）
        
        # 人工审核QA添加配置
        "manual_review": {
            "dataset_id": os.getenv("DIFY_MANUAL_REVIEW_DATASET_ID", "1397b9d1-8e25-4269-ba12-046059a425b6"),  # 知识库ID
            "document_id": os.getenv("DIFY_MANUAL_REVIEW_DOCUMENT_ID", "a025564c-33b4-458e-835b-324ac75c0e24"),  # 目标文档ID(用于添加QA)
        }
    },
    
    # -------------------------------------------------------------------------
    # Neo4j知识图谱配置
    # -------------------------------------------------------------------------
    # 说明：通过外部API访问知识图谱服务
    "neo4j": {
        # 知识图谱API地址
        "api_base": os.getenv("KG_API_BASE", "http://192.168.1.63:8080"),
        
        # 是否启用KG检索
        "enabled": os.getenv("NEO4J_ENABLED", "true").lower() == "true",
    },
    
    # -------------------------------------------------------------------------
    # SQLite数据库配置（统一管理所有数据库路径）
    # -------------------------------------------------------------------------
    # 说明：用于存储对话上下文、QA召回统计、用户反馈、日志等持久化数据
    "sqlite": {
        # 会话管理核心数据库（sessions, conversation_log, conversation_context）
        "session_db": _default_path(
            "SESSION_DB_PATH",
            PROJECT_ROOT / "resource" / "data" / "session_management.db"
        ),
        
        # QA召回统计数据库（qa_sources, qa_records, qa_recall_history）
        "qa_recall_db": _default_path(
            "QA_RECALL_DB_PATH",
            PROJECT_ROOT / "resource" / "data" / "QA_recall.db"
        ),
        
        # 用户反馈数据库（user_feedback, qa_supplements）
        "user_feedback_db": _default_path(
            "USER_FEEDBACK_DB_PATH",
            PROJECT_ROOT / "resource" / "data" / "user_feedback.db"
        ),
        
        # 意图识别日志数据库（intent_logs）
        "intent_log_db": _default_path(
            "INTENT_LOG_DB_PATH",
            PROJECT_ROOT / "resource" / "data" / "intent_recognition_log.db"
        ),
        
        # 操作日志数据库（operation_log）- 向量库管理使用
        "operation_log_db": _default_path(
            "OPERATION_LOG_DB_PATH",
            PROJECT_ROOT / "resource" / "data" / "operation_log.db"
        ),
        
        # QA补充数据库（user_qa_supplement）- 会话管理系统使用
        "qa_supplement_db": _default_path(
            "QA_SUPPLEMENT_DB_PATH",
            PROJECT_ROOT / "resource" / "data" / "user_qa_supplement.db"
        ),
        
        # API密钥数据库（api_keys）- 外部QA接口使用
        "api_key_db": _default_path(
            "API_KEY_DB_PATH",
            PROJECT_ROOT / "resource" / "data" / "api_keys.db"
        ),
        
        # 兼容性保留（逐步废弃）
        "db_path": _default_path(
            "SQLITE_DB_PATH",
            PROJECT_ROOT / "resource" / "data" / "session_management.db"
        )
    },
    
    # -------------------------------------------------------------------------
    # 对话上下文配置
    # -------------------------------------------------------------------------
    # 说明：管理多轮对话历史，当前暂未启用（为减少Token消耗）
    "conversation": {
        "history_max_turns": int(os.getenv("CONTEXT_MAX_TURNS", "6")),  # 最大保留对话轮数
        "history_trim_chars": int(os.getenv("CONTEXT_MAX_CHARS", "1600")),  # 历史总字符数上限
        "history_join_delimiter": os.getenv("CONTEXT_JOIN_DELIMITER", "\n"),  # 历史记录分隔符
        
        # 会话自动清理配置
        "auto_cleanup": {
            "enabled": os.getenv("CONTEXT_AUTO_CLEANUP_ENABLED", "false").lower() == "true",  # 是否启用自动清理（默认关闭）
            "interval_hours": int(os.getenv("CONTEXT_AUTO_CLEANUP_HOURS", "24")),  # 清理超过N小时未活跃的会话
            "delete_permanently": os.getenv("CONTEXT_AUTO_CLEANUP_PERMANENT", "false").lower() == "true"  # 是否物理删除（默认软删除）
        }
    },
    
    # UI显示配置
    "ui": {
        # 列表中长内容缩略字符数
        "truncate_length": int(os.getenv("UI_TRUNCATE_LENGTH", "15"))
    },
    
    # -------------------------------------------------------------------------
    # RAG检索配置（高级优化版）
    # -------------------------------------------------------------------------
    # 说明：文档分块与检索策略的核心配置
    "rag": {
        # 文档分块配置
        "chunk_size": int(os.getenv("RAG_CHUNK_SIZE", "1000")),  # 单个文档块的字符数
        "chunk_overlap": int(os.getenv("RAG_CHUNK_OVERLAP", "200")),  # 块之间的重叠字符数
        
        # 检索配置
        "top_k": int(os.getenv("RAG_TOP_K", "5")),  # 检索返回的最大结果数
        "score_threshold": float(os.getenv("RAG_SCORE_THRESHOLD", "0.7")),  # 相似度阈值
        
        # 混合检索配置（BM25关键词 + 向量语义）
        "use_hybrid": os.getenv("RAG_USE_HYBRID", "true").lower() == "true",  # 是否启用混合检索
        "bm25_weight": float(os.getenv("RAG_BM25_WEIGHT", "0.2")),  # BM25权重（关键词匹配）
        "vector_weight": float(os.getenv("RAG_VECTOR_WEIGHT", "0.8")),  # 向量检索权重（语义匹配）
        
        # 智能分块配置
        "use_semantic_chunking": os.getenv("RAG_USE_SEMANTIC", "true").lower() == "true",  # 是否使用语义分块
        "semantic_threshold": int(os.getenv("RAG_SEMANTIC_THRESHOLD", "90"))  # 语义相似度阈值（0-100）
    },

    # -------------------------------------------------------------------------
    # 文件上传配置
    # -------------------------------------------------------------------------
    "file_upload": {
        "allowed_extensions": {
            "image": {"png", "jpg", "jpeg", "gif", "webp"},
            "file": {"pdf", "doc", "docx", "txt", "xls", "xlsx"}
        },
        "max_file_size": int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024))),  # 10MB
        "upload_folder": _default_path("UPLOAD_FOLDER", PROJECT_ROOT / "src" / "web_admin" / "conversation-page" / "uploads")
    },

    # -------------------------------------------------------------------------
    # 提示词模板配置
    # -------------------------------------------------------------------------
    "prompts": {
        "title_generation": """请为以下用户问题生成一个简洁的会话标题（不超过15个字）：

用户问题：{first_message}

要求：
1. 标题要能概括问题核心内容
2. 不超过15个字
3. 不要加引号或其他符号
4. 直接输出标题文本""",
        
        "summary_generation": """请为以下对话生成一个简洁的概要（100-150字）：

{full_conversation}

要求：
1. 概括用户的主要问题或需求
2. 总结助手提供的关键解决方案
3. 突出重点信息，去除冗余
4. 语言简洁专业
5. 不超过150字""",

        "message_compression": """请将以下{role_desc}压缩为50字以内的摘要，保留核心意思：

原文：{content}

要求：
1. 只输出摘要，不要任何解释
2. 保留关键信息（产品型号、故障现象、操作步骤等）
3. 50字以内""",

        "cleanup_message": """✅ **会话已成功清理！**

对话历史已清空，系统已重置为初始状态。

---

🎯 **重新开始**

您好！👋

我是简思科技的智能售后助手"简小助"，很高兴继续为您服务！

我专注于工业自动化产品的售后技术支持，可以帮您解决：

🔧 **故障诊断**  
快速定位PLC、HMI、VFD等设备的故障原因并提供解决方案

⚙️ **操作指导**  
提供设备配置、参数设置、通信调试等详细操作步骤

📊 **参数查询**  
查询产品技术规格、通信协议、接口定义等技术资料

🔗 **兼容性咨询**  
分析不同设备间的兼容性，推荐最佳配套方案

💡 **示例提问**：
• "JS-PLC-200出现ERR报警灯亮起怎么办？"
• "如何通过Modbus连接HMI和PLC？"
• "JS-VFD-2.2K支持哪些控制模式？"
• "PLC扩展模块的最大数量是多少？"

请描述您遇到的问题，我会尽力为您解答！😊""",

        "no_data_message": """很抱歉，我在知识库中未找到与您问题相关的信息。

这可能是因为：
• 问题超出了当前知识库的范围
• 表述方式比较特殊，系统未能理解

💡 **建议**：
• 尝试换个方式描述问题
• 提供更具体的设备型号或故障现象
• 联系人工售后工程师获得专业支持

如需人工支持，请联系：
📞 **售后热线**：17363809492
📧 **技术邮箱**：205446492@qq.com
🏢 **公司地址**：湖南省娄底市娄星区经济技术开发区电机产业园3栋5楼"""
    },
}

# =============================================================================
# 配置访问函数
# =============================================================================

# 向后兼容：提供CONTEXT_MANAGER_CONFIG别名
CONTEXT_MANAGER_CONFIG = BASE_CONFIG

def get_config():
    """获取配置"""
    return BASE_CONFIG


def get_mcp_config():
    """获取MCP配置"""
    return MCP_CONFIG
