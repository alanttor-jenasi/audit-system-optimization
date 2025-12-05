"""
QA查重模块 - 使用BGE嵌入模型 + 余弦相似度
====================================

功能:
1. 加载已审核知识库的所有QA
2. 使用BGE模型生成向量
3. 计算余弦相似度
4. 返回重复组
"""

import requests
import numpy as np
from typing import List, Dict, Tuple
import logging
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'mcp_services'))
from common.config import BASE_CONFIG

logger = logging.getLogger(__name__)


class DuplicateChecker:
    """QA查重器"""
    
    def __init__(self):
        """初始化查重器"""
        # BGE嵌入模型配置
        self.embedding_url = BASE_CONFIG['embedding']['url']
        self.embedding_model = BASE_CONFIG['embedding']['model']
        self.embedding_timeout = BASE_CONFIG['embedding']['timeout']
        
        logger.info(f"✅ 查重器初始化完成 [模型={self.embedding_model}, 服务={self.embedding_url}]")
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        调用BGE模型生成文本向量 (OpenAI兼容接口)
        
        Args:
            texts: 文本列表
            
        Returns:
            向量矩阵 (n, 1024)
        """
        try:
            # 使用OpenAI兼容的API接口
            response = requests.post(
                f"{self.embedding_url}/v1/embeddings",
                json={
                    "input": texts,
                    "model": self.embedding_model
                },
                timeout=self.embedding_timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # 解析OpenAI格式的响应
            embeddings = [item['embedding'] for item in result['data']]
            embeddings = np.array(embeddings)
            logger.info(f"✅ 向量生成成功 [数量={len(texts)}, 维度={embeddings.shape}]")
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ 向量生成失败: {e}")
            raise
    
    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度 (0-1)
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def find_duplicates(
        self, 
        segments: List[Dict], 
        similarity_threshold: float = 0.85,
        batch_size: int = 100
    ) -> List[List[Dict]]:
        """
        查找重复的QA分段
        
        Args:
            segments: 分段列表,每个包含 {id, question, answer, document_id, document_name}
            similarity_threshold: 相似度阈值 (0-1)
            batch_size: 批处理大小
            
        Returns:
            重复组列表,每组包含相似的分段
        """
        if not segments:
            return []
        
        logger.info(f"🔍 开始查重 [总数={len(segments)}, 阈值={similarity_threshold}]")
        
        # 1. 准备文本数据(问题+答案)
        texts = []
        for seg in segments:
            # 组合问题和答案作为完整文本
            combined_text = f"问:{seg['question']}\n答:{seg['answer']}"
            texts.append(combined_text)
        
        # 2. 分批生成向量(避免内存溢出)
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_embeddings = self.get_embeddings(batch_texts)
            all_embeddings.append(batch_embeddings)
            logger.info(f"📊 进度: {min(i+batch_size, len(texts))}/{len(texts)}")
        
        # 合并所有向量
        embeddings = np.vstack(all_embeddings)
        
        # 3. 计算相似度矩阵
        logger.info("🧮 计算相似度矩阵...")
        n = len(segments)
        visited = set()
        duplicate_groups = []
        
        for i in range(n):
            if i in visited:
                continue
            
            # 当前分段的重复组
            current_group = [(segments[i], 1.0)]  # (segment, similarity_to_first)
            visited.add(i)
            
            # 与后续分段比较
            for j in range(i+1, n):
                if j in visited:
                    continue
                
                # 计算余弦相似度
                similarity = self.cosine_similarity(embeddings[i], embeddings[j])
                
                if similarity >= similarity_threshold:
                    current_group.append((segments[j], float(similarity)))
                    visited.add(j)
            
            # 只保留有重复的组(至少2个)
            if len(current_group) >= 2:
                # 添加相似度信息到每个分段
                for seg, sim in current_group:
                    seg['similarity_score'] = sim
                # 只保存segment对象
                duplicate_groups.append([seg for seg, _ in current_group])
        
        logger.info(f"✅ 查重完成 [发现{len(duplicate_groups)}个重复组]")
        return duplicate_groups
    
    def format_duplicate_groups(self, duplicate_groups: List[List[Dict]]) -> Dict:
        """
        格式化重复组为前端需要的格式
        
        Args:
            duplicate_groups: 重复组列表
            
        Returns:
            格式化后的数据
        """
        formatted_groups = []
        
        for idx, group in enumerate(duplicate_groups, 1):
            # 计算组内平均相似度(除了第一个100%)
            similarities = [seg.get('similarity_score', 0.0) for seg in group]
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
            
            # 组内分段按相似度降序排序
            sorted_group = sorted(group, key=lambda x: x.get('similarity_score', 0.0), reverse=True)
            
            formatted_group = {
                'group_id': idx,
                'similarity': round(avg_similarity * 100, 1),  # 转换为百分比
                'count': len(group),
                'items': [
                    {
                        'segment_id': seg['id'],
                        'document_id': seg['document_id'],
                        'document_name': seg['document_name'],
                        'classification': seg.get('classification', '-'),
                        'question': seg['question'],
                        'answer': seg['answer'],
                        'similarity': round(seg.get('similarity_score', 0.0) * 100, 1),
                        'created_at': seg.get('created_at', 0),
                        'updated_at': seg.get('updated_at', 0)
                    }
                    for seg in sorted_group
                ]
            }
            formatted_groups.append(formatted_group)
        
        # 按相似度降序排序
        formatted_groups.sort(key=lambda x: x['similarity'], reverse=True)
        
        return {
            'total_groups': len(formatted_groups),
            'total_duplicates': sum(g['count'] for g in formatted_groups),
            'groups': formatted_groups
        }
