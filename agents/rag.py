"""
RAG (Retrieval-Augmented Generation) 知识库检索模块
使用 ChromaDB 向量存储 + DashScope Embedding 实现语义搜索
索引 knowledge.md 和 memory.md，提供 search_knowledge 工具
"""
import os
import re
import chromadb
from chromadb.utils import embedding_functions
from config import load_api_config

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_PERSIST_DIR = os.path.join(_PROJECT_ROOT, "storage", "chromadb")

# 全局 RAG 实例
_rag_instance = None


class KnowledgeRAG:
    """知识库 RAG 检索器"""

    def __init__(self):
        api_config = load_api_config(model_type='openai')
        self.api_key = api_config['api_key']
        self.api_base = api_config['base_url']

        # 使用 DashScope 兼容的 Embedding
        self.ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=self.api_key,
            api_base=self.api_base,
            model_name="text-embedding-v2"
        )

        os.makedirs(_PERSIST_DIR, exist_ok=True)
        self.client = chromadb.PersistentClient(path=_PERSIST_DIR)
        self.collection = self.client.get_or_create_collection(
            name="field_audit_knowledge",
            embedding_function=self.ef,
            metadata={"description": "企业外勤核验 knowledge base + memory"}
        )

    # ---- 索引构建 ----

    def index_all(self, force: bool = False) -> dict:
        """索引 knowledge.md 和 memory.md，返回索引统计"""
        if force:
            # 清空重建
            try:
                self.client.delete_collection("field_audit_knowledge")
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                name="field_audit_knowledge",
                embedding_function=self.ef,
            )

        stats = {}
        stats['knowledge'] = self._index_file(os.path.join("data", "knowledge.md"), "knowledge")
        stats['memory'] = self._index_file(os.path.join("data", "memory.md"), "memory")
        return stats

    def _index_file(self, filename: str, source_type: str) -> int:
        """解析并索引单个 Markdown 文件，返回新增条目数"""
        filepath = os.path.join(_PROJECT_ROOT, filename)
        if not os.path.exists(filepath):
            return 0

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 按 ### 标题拆分为知识条目
        entries = self._parse_entries(content)
        if not entries:
            return 0

        # 获取已索引的 ID 集合（基于文件名前缀）
        existing_ids = set()
        try:
            all_items = self.collection.get()
            if all_items and all_items['ids']:
                prefix = f"{source_type}_"
                existing_ids = {id for id in all_items['ids'] if id.startswith(prefix)}
        except Exception:
            pass

        documents, ids, metadatas = [], [], []
        new_count = 0

        for entry in entries:
            title = entry.get('title', 'Untitled')
            text = entry.get('full_text', '')
            if not text.strip():
                continue

            doc_id = f"{source_type}_{self._slug(title)}"

            if doc_id in existing_ids:
                continue  # 已索引，跳过

            documents.append(text)
            ids.append(doc_id)
            metadatas.append({
                "title": title,
                "source": filename,
                "type": source_type,
                "date": entry.get('date', ''),
                "category": entry.get('category', ''),
            })
            new_count += 1

        if documents:
            try:
                self.collection.add(documents=documents, ids=ids, metadatas=metadatas)
            except Exception as e:
                print(f"[RAG] 索引 {filename} 失败: {e}")
                return 0

        return new_count

    def _parse_entries(self, content: str) -> list:
        """解析 Markdown 中的 ### 标题条目"""
        entries = []
        # 按 ### 分割，保留分隔符
        parts = re.split(r'\n(?=### )', content)
        for part in parts:
            part = part.strip()
            if not part or not part.startswith('### '):
                continue

            header_line = part.split('\n')[0]
            header = header_line.replace('### ', '').strip()

            # 尝试提取分类 [category] 和日期 [YYYY-MM-DD]
            category_match = re.match(r'\[([^\]]+)\]', header)
            category = category_match.group(1) if category_match else ''
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', header)
            date = date_match.group(1) if date_match else ''

            entries.append({
                'title': header,
                'category': category,
                'date': date,
                'full_text': part,
            })
        return entries

    # ---- 检索 ----

    def search(self, query: str, top_k: int = 5) -> dict:
        """语义搜索知识库，返回格式化结果"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
        except Exception as e:
            return {
                'found': False,
                'formatted': f"RAG 检索失败: {str(e)}",
                'raw': []
            }

        if not results or not results['documents'] or not results['documents'][0]:
            return {
                'found': False,
                'formatted': "知识库和记忆中未找到相关内容。",
                'raw': []
            }

        documents = results['documents'][0]
        metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(documents)
        distances = results['distances'][0] if results['distances'] else [0] * len(documents)

        # 过滤低相关度结果（余弦距离 0=相同 1=正交 2=相反）
        filtered = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            relevance = max(0, 1 - dist)  # 余弦距离 → 相似度
            if dist < 1.3:  # 余弦距离 < 1.3 认为有一定相关性
                filtered.append((doc, meta, relevance))

        if not filtered:
            return {
                'found': False,
                'formatted': "知识库中未找到足够相关的内容。",
                'raw': []
            }

        # 构建格式化输出
        formatted = "## 🔍 知识库检索结果\n\n"
        for i, (doc, meta, rel) in enumerate(filtered):
            source_label = "📚 知识库" if meta.get('type') == 'knowledge' else "🧠 对话记忆"
            formatted += (
                f"**结果 {i+1}** | {source_label} | "
                f"相关度: {rel:.0%} | {meta.get('title', '')}\n"
                f"---\n"
                f"{doc[:600]}\n\n"
            )

        return {
            'found': True,
            'formatted': formatted.strip(),
            'raw': [{'title': m.get('title', ''), 'source': m.get('source', ''), 'relevance': r}
                    for _, m, r in filtered]
        }

    # ---- 添加单条 ----

    def add_entry(self, text: str, title: str, source_type: str, metadata: dict = None) -> bool:
        """动态添加一条新知识/记忆到向量库"""
        doc_id = f"{source_type}_{self._slug(title)}"
        try:
            self.collection.add(
                documents=[text],
                ids=[doc_id],
                metadatas=[{
                    "title": title,
                    "source": f"{source_type}.md",
                    "type": source_type,
                    **(metadata or {})
                }]
            )
            return True
        except Exception as e:
            print(f"[RAG] 添加条目失败: {e}")
            return False

    def get_stats(self) -> dict:
        """获取索引统计信息"""
        try:
            count = self.collection.count()
            return {'total_indexed': count, 'status': 'ready'}
        except Exception as e:
            return {'total_indexed': 0, 'status': f'error: {e}'}

    @staticmethod
    def _slug(text: str) -> str:
        """生成安全的 ID slug"""
        return re.sub(r'[^a-zA-Z0-9一-鿿_-]', '_', text)[:64]


# ---- 全局单例 ----

def get_rag() -> KnowledgeRAG:
    """获取全局 RAG 实例（懒加载）"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = KnowledgeRAG()
    return _rag_instance


def init_rag(force: bool = False) -> dict:
    """初始化 RAG 索引（应用启动时调用）"""
    rag = get_rag()
    return rag.index_all(force=force)
