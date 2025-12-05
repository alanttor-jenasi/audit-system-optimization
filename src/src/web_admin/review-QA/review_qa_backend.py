"""
QA审核与修正系统 - 后端服务
====================================

功能：
1. 提供Dify知识库分段的增删改查接口
2. 支持未审核区域和已审核区域的数据管理
3. 处理QA的审核、编辑、分类和转移
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import sys
import re
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import logging
from duplicate_checker import DuplicateChecker

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'mcp_services'))
from common.config import BASE_CONFIG

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            template_folder='.',
            static_folder='static')
CORS(app)

# Dify配置
DIFY_CONFIG = BASE_CONFIG['dify']
DIFY_API_KEY = DIFY_CONFIG['api_key']
DIFY_BASE_URL = DIFY_CONFIG['api_base']

# 知识库配置
UNREVIEWED_DATASET_ID = "1397b9d1-8e25-4269-ba12-046059a425b6"  # 未审核知识库
REVIEWED_DATASET_ID = "2df8ca5b-ac31-4dba-8b48-fc09f678b62d"    # 已审核知识库

# 本地API配置
LOCAL_QUERY_API_BASE = "http://192.168.1.138:49154/api/local/query"

# 未审核知识库的文档配置
UNREVIEWED_DOCUMENTS = {
    "1a92b558-2051-4ebc-9441-2209dfd356b8": "旧QA",
    "ee3a5cb0-3fa9-4cd1-9a1a-113bc43b5d5a": "微信每日QA",
    "a025564c-33b4-458e-835b-324ac75c0e24": "人工/用户添加"
}

# 已审核知识库的文档配置
REVIEWED_DOCUMENTS = {
    "e4d103ba-ab38-4c0b-8c4d-5fd65da451e0": "接线类",
    "6ed1a963-f4f4-4755-8f58-65ed4ccad67e": "电机类",
    "0f615db6-35be-40b8-ad48-34db22ed2fb0": "触摸屏类",
    "b22e210a-0bc8-496a-9828-c6016389bca2": "程序类",
    "d894cff9-c9aa-4d56-a8ae-d09f979779bf": "产品型号功能类",
    "fce7c466-da39-4c37-a281-225087f29dee": "产品维修类",
    "4bc158d8-72e1-4881-a3c9-75d94f0c9e2a": "产品功能类",
    "55e92a15-cc40-49de-a69d-2ef9e863a88a": "modbus通信地址表_SEN类",
    "8f4f53d9-8a48-4a0a-aad3-b14b96a46c93": "产品知识类",
    "9ac2c969-aea2-40a5-a57d-91b98e9421a2": "通信参数类",
    "56f3277a-46d5-4dc0-9d1b-c86b92b979cd": "下载功能类",
    "dbb66ae8-4d9a-4ea9-b5de-603f8d18e1b6": "咨询类",
    "175f56a9-47ec-4c8f-b75e-cd57d8c99627": "通讯类",
    "010a4033-033e-456d-8e13-452d86cb2c16": "操作类"
}


class DifyAPIClient:
    """Dify API客户端"""
    
    def __init__(self):
        self.base_url = DIFY_BASE_URL
        self.api_key = DIFY_API_KEY
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def get_segment(self, dataset_id: str, document_id: str, segment_id: str):
        """获取单个分段（最优方案）"""
        url = f"{self.base_url}/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            return {'success': True, 'data': result.get('data')}
        except Exception as e:
            logger.error(f"获取分段失败 [segment_id={segment_id}]: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_document_segments(self, dataset_id: str, document_id: str, page: int = 1, limit: int = 100):
        """获取文档的所有分段"""
        url = f"{self.base_url}/datasets/{dataset_id}/documents/{document_id}/segments"
        params = {'page': page, 'limit': limit}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return {'success': True, 'data': response.json()}
        except Exception as e:
            logger.error(f"获取分段失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_all_segments(self, dataset_id: str, document_id: str):
        """获取文档的所有分段（处理分页）"""
        all_segments = []
        page = 1
        
        while True:
            result = self.get_document_segments(dataset_id, document_id, page=page, limit=100)
            if not result['success']:
                return result
            
            data = result['data']
            segments = data.get('data', [])
            all_segments.extend(segments)
            
            # 检查是否还有更多数据
            if not data.get('has_more', False):
                break
            
            page += 1
        
        return {'success': True, 'data': all_segments}
    
    def update_segment(self, dataset_id: str, document_id: str, segment_id: str, content: str, keywords: list = None):
        """更新分段内容"""
        url = f"{self.base_url}/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}"
        payload = {'segment': {'content': content}}
        
        if keywords:
            payload['segment']['keywords'] = keywords
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            logger.info(f"✅ 分段更新成功 [segment_id={segment_id}]")
            return {'success': True, 'data': response.json()}
        except Exception as e:
            logger.error(f"❌ 分段更新失败 [segment_id={segment_id}]: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_segment(self, dataset_id: str, document_id: str, segment_id: str):
        """删除分段"""
        url = f"{self.base_url}/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}"
        
        try:
            response = requests.delete(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            logger.info(f"✅ 分段删除成功 [segment_id={segment_id}]")
            return {'success': True}
        except Exception as e:
            logger.error(f"❌ 分段删除失败 [segment_id={segment_id}]: {e}")
            return {'success': False, 'error': str(e)}
    
    def add_segment(self, dataset_id: str, document_id: str, content: str, keywords: list = None):
        """添加分段"""
        url = f"{self.base_url}/datasets/{dataset_id}/documents/{document_id}/segments"
        payload = {
            'segments': [{
                'content': content,
                'keywords': keywords or []
            }]
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            logger.info(f"✅ 分段添加成功 [document_id={document_id}]")
            return {'success': True, 'data': response.json()}
        except Exception as e:
            logger.error(f"❌ 分段添加失败 [document_id={document_id}]: {e}")
            return {'success': False, 'error': str(e)}


def parse_qa_content(content: str):
    """从分段内容中解析问答对和元数据"""
    lines = content.split('\n')
    question = ""
    answer = ""
    source = ""
    add_type = ""
    classification = ""  # 新增分类字段
    
    # 状态标记：当前正在收集哪个字段
    collecting = None
    
    for line in lines:
        line_stripped = line.strip()
        
        # 检查是否是新的字段开始
        if line_stripped.startswith('问:') or line_stripped.startswith('问：'):
            question = line_stripped[2:].strip()
            collecting = 'question' if not question else None
        elif line_stripped.startswith('答:') or line_stripped.startswith('答：'):
            answer = line_stripped[2:].strip()
            collecting = 'answer'  # 开始收集答案（即使当前行为空）
        elif line_stripped.startswith('#source#:') or line_stripped.startswith('#source#：'):
            # 支持中文冒号和英文冒号
            if ':' in line_stripped:
                source = line_stripped.split(':', 1)[1].strip()
            elif '：' in line_stripped:
                source = line_stripped.split('：', 1)[1].strip()
            collecting = 'source' if not source else None
        elif line_stripped.startswith('classification:') or line_stripped.startswith('classification：'):
            # 解析分类字段
            if ':' in line_stripped:
                classification = line_stripped.split(':', 1)[1].strip()
            elif '：' in line_stripped:
                classification = line_stripped.split('：', 1)[1].strip()
            collecting = None
        elif line_stripped.startswith('添加人员:') or line_stripped.startswith('添加人员：'):
            # 支持中文冒号和英文冒号
            if ':' in line_stripped:
                add_type = line_stripped.split(':', 1)[1].strip()
            elif '：' in line_stripped:
                add_type = line_stripped.split('：', 1)[1].strip()
            collecting = None
        elif line_stripped and collecting:
            # 继续收集当前字段的内容
            if collecting == 'question':
                question += ('\n' if question else '') + line_stripped
            elif collecting == 'answer':
                answer += ('\n' if answer else '') + line_stripped
            elif collecting == 'source':
                source += ('\n' if source else '') + line_stripped
    
    return {
        'question': question.strip(),
        'answer': answer.strip(),
        'source': source.strip(),
        'add_type': add_type.strip(),
        'classification': classification.strip()  # 返回分类字段
    }


def clean_qa_content(content: str) -> str:
    """
    清理和规范化QA内容
    
    清理规则（参考parse_qa_content的逻辑，但不调用它）：
    1. 解析content提取各个字段（问、答、source、添加人员、分类）
    2. 清理各个字段：去除多余空格、空行
    3. 统一格式：统一使用中文冒号（问：、答：）
    4. 重新格式化为标准格式
    
    Args:
        content: 原始content字符串
        
    Returns:
        清理后的content字符串
    """
    if not content:
        return content
    
    lines = content.split('\n')
    question = ""
    answer = ""
    source = ""
    add_type = ""
    classification = ""
    
    # 状态标记：当前正在收集哪个字段
    collecting = None
    
    # 使用正则表达式查找"答:"或"答："来分割问题和答案（处理问和答在同一行的情况）
    answer_match = re.search(r'答[：:]', content)
    
    if answer_match:
        # 找到"答:"或"答："，分割问题和答案
        question_part = content[:answer_match.start()].strip()
        answer_part = content[answer_match.end():].strip()
        
        # 去除问题部分开头的"问:"或"问："
        question_part = re.sub(r'^问[：:]\s*', '', question_part)
        question = question_part.strip()
        
        # 处理答案部分，需要提取source、classification、add_type
        answer_lines = answer_part.split('\n')
        answer_content = []
        
        for line in answer_lines:
            line_stripped = line.strip()
            
            # 检查是否包含元数据标签（可能在行内）
            if '#source#' in line_stripped or 'source#' in line_stripped:
                # 提取source
                source_match = re.search(r'#?source#?[：:]\s*(.+)', line_stripped)
                if source_match:
                    source = source_match.group(1).strip()
                # 如果source在行内，只取前面的部分作为答案
                if '#source#' in line_stripped or 'source#' in line_stripped:
                    before_source = re.split(r'#?source#?[：:]', line_stripped)[0].strip()
                    if before_source:
                        answer_content.append(before_source)
                break
            elif 'classification' in line_stripped.lower():
                # 提取classification
                class_match = re.search(r'classification[：:]\s*(.+)', line_stripped, re.IGNORECASE)
                if class_match:
                    classification = class_match.group(1).strip()
                # 如果classification在行内，只取前面的部分
                if 'classification' in line_stripped.lower():
                    before_class = re.split(r'classification[：:]', line_stripped, flags=re.IGNORECASE)[0].strip()
                    if before_class:
                        answer_content.append(before_class)
                break
            elif '添加人员' in line_stripped:
                # 提取add_type
                add_match = re.search(r'添加人员[：:]\s*(.+)', line_stripped)
                if add_match:
                    add_type = add_match.group(1).strip()
                # 如果add_type在行内，只取前面的部分
                if '添加人员' in line_stripped:
                    before_add = line_stripped.split('添加人员')[0].strip()
                    if before_add:
                        answer_content.append(before_add)
                break
            else:
                answer_content.append(line_stripped)
        
        answer = '\n'.join(answer_content).strip()
        
        # 如果还没有提取到source、classification、add_type，继续从剩余内容中提取
        remaining_content = '\n'.join(answer_lines[len(answer_content):])
        for line in remaining_content.split('\n'):
            line_stripped = line.strip()
            if line_stripped.startswith('#source#:') or line_stripped.startswith('#source#：'):
                if ':' in line_stripped:
                    source = line_stripped.split(':', 1)[1].strip()
                elif '：' in line_stripped:
                    source = line_stripped.split('：', 1)[1].strip()
            elif line_stripped.startswith('classification:') or line_stripped.startswith('classification：'):
                if ':' in line_stripped:
                    classification = line_stripped.split(':', 1)[1].strip()
                elif '：' in line_stripped:
                    classification = line_stripped.split('：', 1)[1].strip()
            elif line_stripped.startswith('添加人员:') or line_stripped.startswith('添加人员：'):
                if ':' in line_stripped:
                    add_type = line_stripped.split(':', 1)[1].strip()
                elif '：' in line_stripped:
                    add_type = line_stripped.split('：', 1)[1].strip()
    else:
        # 回退到原始的行-by-line解析逻辑
        for line in lines:
            line_stripped = line.strip()
            
            # 检查是否是新的字段开始
            if line_stripped.startswith('问:') or line_stripped.startswith('问：'):
                question = line_stripped[2:].strip()
                collecting = 'question' if not question else None
            elif line_stripped.startswith('答:') or line_stripped.startswith('答：'):
                answer = line_stripped[2:].strip()
                collecting = 'answer'
            elif line_stripped.startswith('#source#:') or line_stripped.startswith('#source#：'):
                if ':' in line_stripped:
                    source = line_stripped.split(':', 1)[1].strip()
                elif '：' in line_stripped:
                    source = line_stripped.split('：', 1)[1].strip()
                collecting = None
            elif line_stripped.startswith('classification:') or line_stripped.startswith('classification：'):
                if ':' in line_stripped:
                    classification = line_stripped.split(':', 1)[1].strip()
                elif '：' in line_stripped:
                    classification = line_stripped.split('：', 1)[1].strip()
                collecting = None
            elif line_stripped.startswith('添加人员:') or line_stripped.startswith('添加人员：'):
                if ':' in line_stripped:
                    add_type = line_stripped.split(':', 1)[1].strip()
                elif '：' in line_stripped:
                    add_type = line_stripped.split('：', 1)[1].strip()
                collecting = None
            elif line_stripped and collecting:
                # 继续收集当前字段的内容
                if collecting == 'question':
                    question += ('\n' if question else '') + line_stripped
                elif collecting == 'answer':
                    answer += ('\n' if answer else '') + line_stripped
    
    # 清理各个字段
    question = question.strip()
    answer = answer.strip()
    source = source.strip()
    add_type = add_type.strip()
    classification = classification.strip()
    
    # 清理问题：去除多余空格，但保留换行（如果有）
    if question:
        # 去除每行首尾空格，去除空行
        question_lines = question.split('\n')
        question = '\n'.join(line.strip() for line in question_lines if line.strip())
        # 将多个连续空格替换为单个空格（但保留换行）
        question = re.sub(r' +', ' ', question)
    
    # 清理答案：去除多余空行，但保留必要的换行
    if answer:
        # 去除连续的空行（超过2个换行符的替换为2个）
        answer = re.sub(r'\n{3,}', '\n\n', answer)
        # 去除每行首尾空格
        answer_lines = answer.split('\n')
        answer = '\n'.join(line.strip() for line in answer_lines if line.strip())
    
    # 清理source、add_type、classification：去除多余空格
    source = ' '.join(source.split()) if source else ''
    add_type = ' '.join(add_type.split()) if add_type else ''
    classification = ' '.join(classification.split()) if classification else ''
    
    # 重新格式化为标准格式（统一使用中文冒号）
    cleaned_parts = []
    
    if question:
        cleaned_parts.append(f"问：{question}")
    
    if answer:
        cleaned_parts.append(f"答：{answer}")
    
    if source:
        cleaned_parts.append(f"#source#:{source}")
    
    if add_type:
        cleaned_parts.append(f"添加人员:{add_type}")
    
    if classification:
        cleaned_parts.append(f"分类:{classification}")
    
    cleaned_content = '\n'.join(cleaned_parts)
    
    return cleaned_content


def format_qa_content(question: str, answer: str, source: str = "", add_type: str = "", classification: str = ""):
    """格式化问答对内容"""
    content = f"问:{question}\n答:{answer}"
    
    if source:
        content += f"\n#source#:{source}"
    
    if add_type:
        content += f"\n添加人员:{add_type}"
    
    if classification:
        content += f"\n分类:{classification}"
    
    return content


def determine_add_method(document_id: str, add_type: str):
    """确定添加方式"""
    if document_id == "1a92b558-2051-4ebc-9441-2209dfd356b8":
        return "旧QA"
    elif document_id == "ee3a5cb0-3fa9-4cd1-9a1a-113bc43b5d5a":
        return "微信每日QA"
    elif document_id == "a025564c-33b4-458e-835b-324ac75c0e24":
        # 从 add_type 判断
        if add_type == "人工添加":
            return "人工添加"
        elif add_type == "用户添加":
            return "用户添加"
        else:
            return "未知"
    else:
        return "未知"


def determine_add_source(source: str):
    """确定添加来源"""
    return source if source else '-'


# ==================== 路由接口 ====================

@app.route('/')
def index():
    """主页面"""
    return render_template('review_qa.html')


@app.route('/api/unreviewed/segments', methods=['GET'])
def get_unreviewed_segments():
    """获取未审核区域的所有分段"""
    try:
        # 调用本地API获取数据
        dataset_id = UNREVIEWED_DATASET_ID
        api_url = f"{LOCAL_QUERY_API_BASE}?dataset_id={dataset_id}"
        
        logger.info(f"请求本地API: {api_url}")
        response = requests.get(api_url, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"本地API请求失败: status_code={response.status_code}")
            return jsonify({'success': False, 'error': f'本地API请求失败: {response.status_code}'}), 500
        
        api_data = response.json()
        segments = api_data.get('data', [])
        
        if not segments:
            logger.warning("本地API返回数据为空")
            return jsonify({
                'success': True,
                'data': [],
                'total': 0
            })
        
        all_segments = []
        
        # 遍历所有分段，进行数据转换和处理
        for seg in segments:
            # 1. 字段名转换：segment_id → id
            if 'segment_id' in seg:
                seg['id'] = seg.pop('segment_id')
            elif 'id' not in seg:
                logger.warning(f"分段缺少id字段: {seg}")
                continue
            
            # 2. 时间格式转换：字符串(UTC) → 时间戳(东八区)
            created_at_str = seg.get('created_at', '')
            if isinstance(created_at_str, str):
                try:
                    # 解析为UTC时间
                    dt_utc = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                    # 转换为东八区时间（UTC+8）
                    dt_cst = dt_utc.astimezone(timezone(timedelta(hours=8)))
                    seg['created_at'] = int(dt_cst.timestamp())
                except ValueError as e:
                    logger.warning(f"时间格式解析失败: {created_at_str}, 错误: {e}")
                    seg['created_at'] = 0
            elif not isinstance(created_at_str, (int, float)):
                seg['created_at'] = 0
            
            # 3. 处理 updated_at：如果没有则使用 created_at
            updated_at = seg.get('updated_at')
            if updated_at:
                if isinstance(updated_at, str):
                    try:
                        # 解析为UTC时间
                        dt_utc = datetime.strptime(updated_at, '%Y-%m-%d %H:%M:%S')
                        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                        # 转换为东八区时间（UTC+8）
                        dt_cst = dt_utc.astimezone(timezone(timedelta(hours=8)))
                        seg['updated_at'] = int(dt_cst.timestamp())
                    except ValueError:
                        seg['updated_at'] = seg.get('created_at', 0)
                elif not isinstance(updated_at, (int, float)):
                    seg['updated_at'] = seg.get('created_at', 0)
            else:
                seg['updated_at'] = seg.get('created_at', 0)
            
            # 4. 获取 document_name（根据 document_id 查找）
            doc_id = seg.get('document_id', '')
            doc_name = UNREVIEWED_DOCUMENTS.get(doc_id, '未知文档')
            seg['document_name'] = doc_name
            
            # 5. 保留原始 content 字段（用于后续解析）
            content = seg.get('content', '')
            
            # 5.5. 清理content（规范化格式）
            cleaned_content = clean_qa_content(content)
            
            # 6. 解析QA内容
            parsed = parse_qa_content(cleaned_content)
            
            seg['question'] = parsed.get('question', '')
            seg['answer'] = parsed.get('answer', '')
            seg['add_method'] = determine_add_method(doc_id, parsed.get('add_type', ''))
            seg['add_source'] = determine_add_source(parsed.get('source', ''))
            seg['classification'] = parsed.get('classification', '')
            
            all_segments.append(seg)
        
        # 按 updated_at 降序排列（优先使用 updated_at，如果没有则使用 created_at）
        all_segments.sort(key=lambda x: x.get('updated_at', x.get('created_at', 0)), reverse=True)
        
        logger.info(f"成功获取 {len(all_segments)} 个未审核分段")
        
        return jsonify({
            'success': True,
            'data': all_segments,
            'total': len(all_segments)
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"本地API请求异常: {e}")
        return jsonify({'success': False, 'error': f'本地API请求异常: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"获取未审核分段失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reviewed/documents', methods=['GET'])
def get_reviewed_documents():
    """获取已审核文档列表"""
    try:
        documents = [
            {'id': doc_id, 'name': doc_name}
            for doc_id, doc_name in REVIEWED_DOCUMENTS.items()
        ]
        
        return jsonify({
            'success': True,
            'data': documents
        })
        
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/document-categories', methods=['GET'])
def get_document_categories():
    """获取所有文档分类列表(用于下拉选择)"""
    try:
        categories = [
            {'id': doc_id, 'name': doc_name}
            for doc_id, doc_name in REVIEWED_DOCUMENTS.items()
        ]
        
        return jsonify({
            'success': True,
            'categories': categories,
            'total': len(categories)
        })
        
    except Exception as e:
        logger.error(f"获取文档分类列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reviewed/segments/<document_id>', methods=['GET'])
def get_reviewed_segments(document_id):
    """获取已审核区域指定文档的所有分段"""
    try:
        if document_id not in REVIEWED_DOCUMENTS:
            return jsonify({'success': False, 'error': '无效的文档ID'}), 400
        
        client = DifyAPIClient()
        result = client.get_all_segments(REVIEWED_DATASET_ID, document_id)
        
        if not result['success']:
            return jsonify(result), 500
        
        segments = result['data']
        
        # 为每个分段添加元数据
        for segment in segments:
            content = segment.get('content', '')
            parsed = parse_qa_content(content)
            
            segment['document_id'] = document_id
            segment['document_name'] = REVIEWED_DOCUMENTS[document_id]
            segment['question'] = parsed['question']
            segment['answer'] = parsed['answer']
        
        # 按updated_at降序排序
        segments.sort(key=lambda x: x.get('updated_at', 0), reverse=True)
        
        return jsonify({
            'success': True,
            'data': segments,
            'total': len(segments)
        })
        
    except Exception as e:
        logger.error(f"获取已审核分段失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/segment/update', methods=['POST'])
def update_segment():
    """更新分段内容"""
    try:
        data = request.json
        dataset_id = data.get('dataset_id')
        document_id = data.get('document_id')
        segment_id = data.get('segment_id')
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        
        if not all([dataset_id, document_id, segment_id, question, answer]):
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        # 获取原分段以保留元数据
        client = DifyAPIClient()
        result = client.get_document_segments(dataset_id, document_id)
        
        if not result['success']:
            return jsonify(result), 500
        
        # 查找原分段
        original_segment = None
        for seg in result['data'].get('data', []):
            if seg['id'] == segment_id:
                original_segment = seg
                break
        
        if not original_segment:
            return jsonify({'success': False, 'error': '分段不存在'}), 404
        
        # 解析原内容以保留元数据
        original_content = original_segment.get('content', '')
        parsed = parse_qa_content(original_content)
        
        # 构造新内容
        new_content = format_qa_content(
            question, 
            answer,
            parsed.get('source', ''),
            parsed.get('add_type', '')
        )
        
        # 更新分段
        keywords = [question[:50]] if len(question) > 0 else []
        result = client.update_segment(dataset_id, document_id, segment_id, new_content, keywords)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"更新分段失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/segment/delete', methods=['POST'])
def delete_segment():
    """删除分段"""
    try:
        data = request.json
        dataset_id = data.get('dataset_id')
        document_id = data.get('document_id')
        segment_id = data.get('segment_id')
        
        if not all([dataset_id, document_id, segment_id]):
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        client = DifyAPIClient()
        result = client.delete_segment(dataset_id, document_id, segment_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"删除分段失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reviewed/segment/<segment_id>', methods=['GET'])
def get_reviewed_segment_by_id(segment_id):
    """获取单个已审核分段(RESTful风格)"""
    try:
        # 需要遍历所有文档查找该分段
        client = DifyAPIClient()
        
        for doc_id, doc_name in REVIEWED_DOCUMENTS.items():
            result = client.get_segment(REVIEWED_DATASET_ID, doc_id, segment_id)
            if result['success']:
                return jsonify(result)
        
        return jsonify({'success': False, 'error': '分段不存在'}), 404
        
    except Exception as e:
        logger.error(f"获取分段失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reviewed/segments/<segment_id>', methods=['PUT'])
def update_reviewed_segment(segment_id):
    """更新已审核分段内容(RESTful风格)"""
    try:
        data = request.json
        document_id = data.get('document_id')
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        
        if not all([document_id, question, answer]):
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        # 获取原分段以保留元数据
        client = DifyAPIClient()
        result = client.get_segment(REVIEWED_DATASET_ID, document_id, segment_id)
        
        if not result['success']:
            return jsonify(result), 500
        
        original_segment = result['data']
        
        # 解析原内容以保留元数据
        original_content = original_segment.get('content', '')
        parsed = parse_qa_content(original_content)
        
        # 构造新内容
        new_content = format_qa_content(
            question, 
            answer,
            parsed.get('source', ''),
            parsed.get('add_type', ''),
            parsed.get('classification', '')
        )
        
        # 更新分段
        keywords = [question[:50]] if len(question) > 0 else []
        result = client.update_segment(REVIEWED_DATASET_ID, document_id, segment_id, new_content, keywords)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"更新分段失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reviewed/segments/<segment_id>', methods=['DELETE'])
def delete_reviewed_segment(segment_id):
    """删除已审核分段(RESTful风格)"""
    try:
        data = request.json
        document_id = data.get('document_id')
        
        if not document_id:
            return jsonify({'success': False, 'error': '缺少document_id参数'}), 400
        
        client = DifyAPIClient()
        result = client.delete_segment(REVIEWED_DATASET_ID, document_id, segment_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"删除分段失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/segment/approve', methods=['POST'])
def approve_segment():
    """通过审核（转移到已审核知识库）"""
    try:
        data = request.json
        source_document_id = data.get('source_document_id')
        segment_id = data.get('segment_id')
        target_document_id = data.get('target_document_id')
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        
        if not all([source_document_id, segment_id, target_document_id, question, answer]):
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        if target_document_id not in REVIEWED_DOCUMENTS:
            return jsonify({'success': False, 'error': '无效的目标文档ID'}), 400
        
        client = DifyAPIClient()
        
        # 1. 使用单个分段查询API（最优方案）
        result = client.get_segment(UNREVIEWED_DATASET_ID, source_document_id, segment_id)
        
        if not result['success']:
            logger.error(f"❌ 获取分段失败: {segment_id}")
            return jsonify({'success': False, 'error': f"获取原分段失败: {result.get('error')}"}), 500
        
        original_segment = result['data']
        
        if not original_segment:
            logger.error(f"❌ 分段不存在: {segment_id}")
            return jsonify({'success': False, 'error': '原分段不存在'}), 404
        
        # 2. 解析原内容
        original_content = original_segment.get('content', '')
        parsed = parse_qa_content(original_content)
        
        # 3. 构造新内容（保留元数据）
        new_content = format_qa_content(
            question,
            answer,
            parsed.get('source', ''),
            parsed.get('add_type', '')
        )
        
        # 4. 在目标文档中添加分段
        keywords = [question[:50]] if len(question) > 0 else []
        add_result = client.add_segment(REVIEWED_DATASET_ID, target_document_id, new_content, keywords)
        
        if not add_result['success']:
            return jsonify({'success': False, 'error': f'添加到目标文档失败: {add_result.get("error")}'}), 500
        
        # 5. 删除原分段
        delete_result = client.delete_segment(UNREVIEWED_DATASET_ID, source_document_id, segment_id)
        
        if not delete_result['success']:
            logger.warning(f"⚠️ 删除原分段失败，但已添加到目标文档: {delete_result.get('error')}")
        
        target_doc_name = REVIEWED_DOCUMENTS.get(target_document_id, '未知文档')
        logger.info(f"✅ 审核通过 [segment_id={segment_id}] -> [目标文档={target_doc_name}]")
        
        # 记录审核统计
        record_approval()
        
        return jsonify({
            'success': True,
            'message': f'已转移到 {REVIEWED_DOCUMENTS[target_document_id]}'
        })
        
    except Exception as e:
        logger.error(f"审核通过失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# 审核统计数据库 - 统一存放在resource/data文件夹
# __file__: src/web_admin/review-QA/review_qa_backend.py
# parent: src/web_admin/review-QA/
# parent.parent: src/web_admin/
# parent.parent.parent: src/
# parent.parent.parent.parent: 项目根目录
STATS_DB = Path(__file__).parent.parent.parent.parent / 'resource' / 'data' / 'approval_stats.db'

def init_stats_db():
    """初始化统计数据库"""
    import sqlite3
    
    # 确保目录存在
    STATS_DB.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(STATS_DB))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS approval_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_date DATE NOT NULL,
            count INTEGER DEFAULT 0,
            UNIQUE(approval_date)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ 审核统计数据库初始化完成 [db_path=%s]", STATS_DB)

def record_approval():
    """记录一次审核"""
    import sqlite3
    from datetime import date
    
    today = date.today().isoformat()
    
    conn = sqlite3.connect(str(STATS_DB))
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO approval_stats (approval_date, count)
        VALUES (?, 1)
        ON CONFLICT(approval_date) 
        DO UPDATE SET count = count + 1
    ''', (today,))
    
    conn.commit()
    conn.close()

@app.route('/api/stats/today', methods=['GET'])
def get_today_stats():
    """获取今日审核统计"""
    try:
        import sqlite3
        from datetime import date
        
        today = date.today().isoformat()
        
        conn = sqlite3.connect(str(STATS_DB))
        cursor = conn.cursor()
        
        cursor.execute('SELECT count FROM approval_stats WHERE approval_date = ?', (today,))
        result = cursor.fetchone()
        
        conn.close()
        
        count = result[0] if result else 0
        
        return jsonify({
            'success': True,
            'count': count,
            'date': today
        })
        
    except Exception as e:
        logger.error(f"获取今日统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats/monthly', methods=['GET'])
def get_monthly_stats():
    """获取月度审核统计"""
    try:
        import sqlite3
        from datetime import date
        
        year = request.args.get('year', date.today().year, type=int)
        month = request.args.get('month', date.today().month, type=int)
        
        # 构造月份范围
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        conn = sqlite3.connect(str(STATS_DB))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT approval_date, count 
            FROM approval_stats 
            WHERE approval_date >= ? AND approval_date < ?
            ORDER BY approval_date
        ''', (start_date, end_date))
        
        results = cursor.fetchall()
        conn.close()
        
        # 转换为字典
        stats = {row[0]: row[1] for row in results}
        
        return jsonify({
            'success': True,
            'stats': stats,
            'year': year,
            'month': month
        })
        
    except Exception as e:
        logger.error(f"获取月度统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 缓存已审核总数
reviewed_total_cache = {'total': 0, 'timestamp': 0}
CACHE_DURATION = 300  # 5分钟缓存

@app.route('/api/stats/total-reviewed', methods=['GET'])
def get_total_reviewed():
    """获取已审核区域总条数（带缓存）"""
    try:
        import time
        current_time = time.time()
        
        # 检查缓存是否有效
        if current_time - reviewed_total_cache['timestamp'] < CACHE_DURATION:
            logger.info(f"✅ 使用缓存的已审核总数: {reviewed_total_cache['total']}")
            return jsonify({
                'success': True,
                'total': reviewed_total_cache['total'],
                'cached': True
            })
        
        # 缓存过期，重新计算
        client = DifyAPIClient()
        total = 0
        
        logger.info("🔄 重新计算已审核总数...")
        # 遍历所有已审核文档
        for doc_id in REVIEWED_DOCUMENTS.keys():
            result = client.get_all_segments(REVIEWED_DATASET_ID, doc_id)
            if result['success']:
                total += len(result['data'])
        
        # 更新缓存
        reviewed_total_cache['total'] = total
        reviewed_total_cache['timestamp'] = current_time
        
        logger.info(f"✅ 已审核总数: {total}")
        
        return jsonify({
            'success': True,
            'total': total,
            'cached': False
        })
        
    except Exception as e:
        logger.error(f"获取已审核总数失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reviewed/check-duplicates', methods=['POST'])
def check_duplicates():
    """查重功能 - 使用BGE模型 + 余弦相似度"""
    try:
        data = request.json
        similarity_threshold = data.get('similarity_threshold', 0.8)  # 默认0.8 (80%)
        
        logger.info(f"🔍 开始查重 [阈值={similarity_threshold}]")
        
        # 1. 加载所有已审核文档的分段
        client = DifyAPIClient()
        all_segments = []
        
        for doc_id, doc_name in REVIEWED_DOCUMENTS.items():
            result = client.get_all_segments(REVIEWED_DATASET_ID, doc_id)
            
            if result['success']:
                segments = result['data']
                
                # 为每个分段添加元数据
                for seg in segments:
                    content = seg.get('content', '')
                    parsed = parse_qa_content(content)
                    
                    seg['document_id'] = doc_id
                    seg['document_name'] = doc_name
                    seg['question'] = parsed['question']
                    seg['answer'] = parsed['answer']
                    seg['classification'] = parsed.get('classification', '-')
                    
                    all_segments.append(seg)
        
        logger.info(f"✅ 加载完成 [总数={len(all_segments)}]")
        
        # 2. 调用查重器
        checker = DuplicateChecker()
        duplicate_groups = checker.find_duplicates(
            all_segments, 
            similarity_threshold=similarity_threshold
        )
        
        # 3. 格式化结果
        result = checker.format_duplicate_groups(duplicate_groups)
        
        logger.info(f"✅ 查重完成 [重复组={result['total_groups']}, 重复条目={result['total_duplicates']}]")
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"❌ 查重失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("🚀 QA审核与修正系统启动")
    logger.info("="*60)
    logger.info(f"📊 未审核知识库ID: {UNREVIEWED_DATASET_ID}")
    logger.info(f"📊 已审核知识库ID: {REVIEWED_DATASET_ID}")
    logger.info(f"📄 未审核文档数: {len(UNREVIEWED_DOCUMENTS)}")
    logger.info(f"📄 已审核文档数: {len(REVIEWED_DOCUMENTS)}")
    logger.info("✨ 使用单个分段查询API，数据实时同步")
    logger.info("="*60)
    
    # 初始化统计数据库
    init_stats_db()
    
    logger.info("🌐 服务器启动中... [http://0.0.0.0:5002]")
    app.run(host='0.0.0.0', port=5002, debug=True)
